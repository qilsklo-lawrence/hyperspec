import os
import h5py
import numpy as np
import time
import json
import threading
import uuid
import hashlib
from werkzeug.utils import secure_filename
from flask import Flask, jsonify, send_from_directory, request, Response
from precompute import process_h5
from fit import perform_fits

app = Flask(__name__, static_folder='frontend/dist', static_url_path='')

datasets = {}
file_hashes = {}
dataset_names = {}
processing_status = {}  # Store background task status

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
default_data_path = os.path.join(BASE_DIR, 'precomputed_data.json')
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

NAMES_DB = os.path.join(UPLOAD_FOLDER, 'dataset_names.json')

def save_names_db():
    with open(NAMES_DB, 'w') as f:
        json.dump(dataset_names, f)

def load_names_db():
    global dataset_names
    if os.path.exists(NAMES_DB):
        with open(NAMES_DB, 'r') as f:
            dataset_names = json.load(f)

load_names_db()

if os.path.exists(default_data_path):
    try:
        with open(default_data_path, 'r') as f:
            datasets['default'] = json.load(f)
            if 'default' not in dataset_names:
                dataset_names['default'] = 'default (MAPPING.h5)'
    except json.JSONDecodeError:
        print("Warning: precomputed_data.json is corrupted or is a Git LFS pointer file. Default dataset will not be loaded.")

def get_file_hash(filepath):
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def load_single_dataset_from_file(filepath, filename):
    file_hash = get_file_hash(filepath)
    dataset_id = file_hash[:8]
    
    file_hashes[file_hash] = dataset_id
    if dataset_id not in dataset_names:
        dataset_names[dataset_id] = filename
        save_names_db()
    
    json_filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"{dataset_id}.json")
    if os.path.exists(json_filepath):
        print(f"Loading cached fits for {dataset_id} in background...")
        processing_status[dataset_id] = {'status': 'processing', 'current': 0, 'total': 1, 'message': 'Loading from disk...'}
        try:
            with open(json_filepath, 'r') as f:
                datasets[dataset_id] = json.load(f)
            processing_status[dataset_id] = {'status': 'done', 'dataset_id': dataset_id}
        except Exception as e:
            print(f"Failed to load cached {dataset_id}: {e}")
            processing_status[dataset_id] = {'status': 'error', 'error': str(e)}
    else:
        print(f"Precomputing fits for new file {filename} in background...")
        process_file_background(filepath, dataset_id, filename)

def load_persisted_datasets_bg():
    print("Scanning uploads directory for datasets in background...")
    for filename in os.listdir(UPLOAD_FOLDER):
        if filename.endswith('.h5') or filename.endswith('.mat'):
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            threading.Thread(target=load_single_dataset_from_file, args=(filepath, filename), daemon=True).start()

# Launch in background so server startup is extremely fast
threading.Thread(target=load_persisted_datasets_bg, daemon=True).start()
save_names_db()

def process_file_background(filepath, dataset_id, filename):
    processing_status[dataset_id] = {'status': 'processing', 'current': 0, 'total': 1, 'message': 'Initializing...'}
    def update_progress(current, total, message):
        processing_status[dataset_id] = {'status': 'processing', 'current': current, 'total': total, 'message': message}
    
    try:
        data = process_h5(filepath, progress_callback=update_progress)
        datasets[dataset_id] = data
        dataset_names[dataset_id] = filename
        save_names_db()
        
        json_filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"{dataset_id}.json")
        with open(json_filepath, 'w') as f:
            json.dump(data, f, separators=(',', ':'))
            
        processing_status[dataset_id] = {'status': 'done', 'dataset_id': dataset_id}
    except Exception as e:
        if os.path.exists(filepath):
            os.remove(filepath)
        processing_status[dataset_id] = {'status': 'error', 'error': str(e)}


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if file and (file.filename.endswith('.h5') or file.filename.endswith('.mat')):
        filename = secure_filename(file.filename)
        temp_id = str(uuid.uuid4())
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"{temp_id}_{filename}")
        file.save(filepath)
        
        file_hash = get_file_hash(filepath)
        dataset_id = file_hash[:8]
        
        if dataset_id in datasets:
            os.remove(filepath)
            original_name = dataset_names.get(dataset_id, dataset_id)
            return jsonify({
                "message": f"Dataset already exists as '{original_name}'.",
                "dataset_id": dataset_id,
                "filename": filename,
                "duplicate": True
            })
            
        new_filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"{dataset_id}_{filename}")
        os.rename(filepath, new_filepath)
        file_hashes[file_hash] = dataset_id
        
        thread = threading.Thread(target=process_file_background, args=(new_filepath, dataset_id, filename))
        thread.start()
        
        return jsonify({
            "message": "File upload started",
            "dataset_id": dataset_id,
            "filename": filename,
            "duplicate": False
        })
    return jsonify({"error": "Invalid file type. Only .h5 or .mat allowed."}), 400

@app.route('/status/<dataset_id>')
def get_status(dataset_id):
    if dataset_id in processing_status:
        return jsonify(processing_status[dataset_id])
    if dataset_id in datasets:
        return jsonify({'status': 'done', 'dataset_id': dataset_id})
    return jsonify({'status': 'not_found'}), 404

@app.route('/datasets')
def list_datasets():
    res = []
    # Return all datasets known by name, even if they are still loading in background
    for d_id in dataset_names.keys():
        res.append({
            "id": d_id,
            "name": dataset_names.get(d_id, d_id)
        })
    return jsonify({"datasets": res})

@app.route('/update_pixel/<dataset_id>/<pixel_key>', methods=['POST'])
def update_pixel(dataset_id, pixel_key):
    data = request.json
    if dataset_id in datasets and pixel_key in datasets[dataset_id]['pixels']:
        pixel = datasets[dataset_id]['pixels'][pixel_key]
        if 'num_peaks' in data:
            pixel['expected_num_peaks'] = int(data['num_peaks'])
            pixel['needs_refit'] = True
            pixel['changed'] = True
        return jsonify({"success": True})
    return jsonify({"error": "Dataset or pixel not found"}), 404

@app.route('/reset_all_fits/<dataset_id>', methods=['POST'])
def reset_all_fits(dataset_id):
    if dataset_id not in datasets:
        return jsonify({"error": "Dataset not found"}), 404
        
    dataset = datasets[dataset_id]
    for key, pixel in dataset['pixels'].items():
        if pixel.get('changed', False):
            pixel['fit_success'] = False
            pixel['needs_refit'] = True
            pixel['needs_original_peaks_reset'] = True
            pixel['changed'] = False
            pixel['fit_curves'] = []
            pixel['total_fit_curve'] = []
            pixel['r_squared'] = 0.0
        
    return jsonify({"success": True})

@app.route('/rename/<dataset_id>', methods=['POST'])
def rename_dataset(dataset_id):
    data = request.json
    if not data or 'name' not in data:
        return jsonify({"error": "No name provided"}), 400
    if dataset_id in dataset_names or dataset_id in datasets:
        dataset_names[dataset_id] = data['name']
        save_names_db()
        return jsonify({"success": True, "name": data['name']})
    return jsonify({"error": "Dataset not found"}), 404

@app.route('/dataset/<dataset_id>', methods=['DELETE'])
def delete_dataset(dataset_id):
    if dataset_id == 'default':
        return jsonify({"error": "Cannot delete default dataset"}), 403
    
    if dataset_id in datasets:
        del datasets[dataset_id]
        if dataset_id in dataset_names:
            del dataset_names[dataset_id]
            save_names_db()
            
        # Remove from disk
        json_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{dataset_id}.json")
        if os.path.exists(json_path):
            os.remove(json_path)
            
        # Try to find and remove the h5/mat file
        for filename in os.listdir(app.config['UPLOAD_FOLDER']):
            if filename.startswith(f"{dataset_id}_") and (filename.endswith('.h5') or filename.endswith('.mat')):
                h5_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                if os.path.exists(h5_path):
                    os.remove(h5_path)
                    
        return jsonify({"success": True})
    return jsonify({"error": "Dataset not found"}), 404

@app.route('/api/data/<dataset_id>')
def get_dataset(dataset_id):
    # Wait for the dataset to finish background processing/loading
    for _ in range(600): # up to 60 seconds
        if dataset_id in datasets:
            return jsonify(datasets[dataset_id])
        if dataset_id in processing_status and processing_status[dataset_id].get('status') == 'error':
            return jsonify({"error": processing_status[dataset_id].get('error')}), 500
        time.sleep(0.1)
    return jsonify({"error": "Dataset not found or still loading"}), 404

@app.route('/fit_stream/<dataset_id>')
def fit_stream(dataset_id):
    def generate():
        # Using SSE to stream fit results
        try:
            for result in perform_fits(dataset_id, datasets):
                yield f"data: {json.dumps(result)}\n\n"
            
            # Flush to disk exactly once at the end
            if dataset_id in datasets:
                json_filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"{dataset_id}.json")
                if dataset_id == 'default':
                    json_filepath = default_data_path
                with open(json_filepath, 'w') as f:
                    json.dump(datasets[dataset_id], f, separators=(',', ':'))
                    
            yield "data: {\"done\": true}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(generate(), mimetype='text/event-stream')

@app.route('/')
def serve_index():
    return app.send_static_file('index.html')

@app.route('/<path:path>')
def serve_static(path):
    return app.send_static_file(path)

if __name__ == '__main__':
    print("Starting server...")
    app.run(host='0.0.0.0', debug=True, port=8080)
