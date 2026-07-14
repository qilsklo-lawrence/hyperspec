import os
import glob
import h5py
import numpy as np
import time
import json
import threading
import uuid
import hashlib
from werkzeug.utils import secure_filename
from flask import Flask, jsonify, send_from_directory, request, Response
from precompute import process_h5, recommend_peak_count
from fit import perform_fits
import datetime
from google.cloud import storage

BUCKET_NAME = 'app-hyperspec'

app = Flask(__name__, static_folder='frontend/dist', static_url_path='')

datasets = {}
file_hashes = {}
dataset_names = {}
processing_status = {}  # Store background task status

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Local development: use the service-account key kept next to this file for
# GCS access. The key is dockerignored, so this never triggers on Cloud Run,
# which authenticates through its runtime service account instead.
if 'GOOGLE_APPLICATION_CREDENTIALS' not in os.environ:
    _local_keys = glob.glob(os.path.join(BASE_DIR, 'mf-crucible*.json'))
    if _local_keys:
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = _local_keys[0]
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


def generate_signed_put_url(blob):
    """
    Sign a V4 PUT URL for the blob.

    In production (Cloud Run) the default credentials are token-only — there is
    no private key on the box — so signing MUST go through the IAM SignBlob API.
    This requires the runtime service account to have
    roles/iam.serviceAccountTokenCreator on itself.

    In local development, credentials from a service-account JSON key
    (GOOGLE_APPLICATION_CREDENTIALS) carry a private key and can sign directly.
    """
    import google.auth
    from google.auth import credentials as gauth_credentials
    from google.auth.transport import requests as gauth_requests

    kwargs = dict(
        version="v4",
        expiration=datetime.timedelta(minutes=15),
        method="PUT",
        content_type="application/octet-stream",
    )

    credentials, _ = google.auth.default()
    if isinstance(credentials, gauth_credentials.Signing):
        # Local development: key-based credentials sign directly
        return blob.generate_signed_url(**kwargs)

    # Production path: token-only credentials, sign via IAM SignBlob
    credentials.refresh(gauth_requests.Request())
    return blob.generate_signed_url(
        **kwargs,
        service_account_email=credentials.service_account_email,
        access_token=credentials.token,
    )

@app.route('/generate_upload_url', methods=['POST'])
def generate_upload_url():
    data = request.json
    filename = data.get('filename', 'upload.h5')
    filename = secure_filename(filename)
    object_name = f"{uuid.uuid4()}_{filename}"

    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(object_name)

        url = generate_signed_put_url(blob)
        return jsonify({"signed_url": url, "object_name": object_name, "filename": filename})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/process_gcs_file', methods=['POST'])
def process_gcs_file():
    data = request.json
    object_name = data.get('object_name')
    filename = data.get('filename')
    
    if not object_name or not filename:
        return jsonify({"error": "Missing object_name or filename"}), 400
        
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(object_name)
        
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(object_name))
        blob.download_to_filename(filepath)
        
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
            "message": "File processing started",
            "dataset_id": dataset_id,
            "filename": filename,
            "duplicate": False
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
    rs = dataset['global_axes']['rs']
    for key, pixel in dataset['pixels'].items():
        if pixel.get('changed', False):
            pixel['fit_success'] = False
            pixel['needs_refit'] = True
            pixel['changed'] = False
            pixel.pop('expected_num_peaks', None)
            pixel['fit_curves'] = []
            pixel['total_fit_curve'] = []
            pixel['r_squared'] = 0.0
            
            n_peaks, p_indices = recommend_peak_count(rs, pixel['norm_spec'])
            pixel['num_peaks'] = n_peaks
            pixel['peak_indices'] = p_indices
        
    return jsonify({"success": True})

@app.route('/detect_flake/<dataset_id>', methods=['GET'])
def detect_flake(dataset_id):
    if dataset_id not in datasets:
        return jsonify({"error": "Dataset not found"}), 404
        
    try:
        import cv2
        import numpy as np
    except ImportError:
        return jsonify({"error": "OpenCV not installed on server"}), 500
        
    map_type = request.args.get('map_type', 'integrated_intensity')
    dataset = datasets[dataset_id]
    
    width = dataset['global_axes']['width']
    height = dataset['global_axes']['height']
    
    # Reconstruct the 2D grid
    grid = np.zeros((height, width), dtype=np.float32)
    valid_pixels = 0
    for y in range(height):
        for x in range(width):
            h_idx = (width - 1) - x
            key = f"{h_idx}_{y}"
            if key in dataset['pixels']:
                val = dataset['pixels'][key].get(map_type)
                if val is None:
                    val = 0.0
                grid[y, x] = float(val)
                valid_pixels += 1
                
    if valid_pixels == 0:
        return jsonify({"error": "No valid data"}), 400
        
    min_val = np.min(grid)
    max_val = np.max(grid)
    if max_val > min_val:
        grid_norm = np.uint8(255 * (grid - min_val) / (max_val - min_val))
    else:
        grid_norm = np.zeros_like(grid, dtype=np.uint8)
        
    blurred = cv2.GaussianBlur(grid_norm, (0, 0), 1.0)
    
    # Otsu's thresholding
    _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Morphological Cleanup
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=2)
    cleaned = cv2.morphologyEx(closed, cv2.MORPH_OPEN, kernel, iterations=1)
    
    contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    best_contour = None
    best_area = 0
    total_area = width * height
    
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < total_area * 0.02:
            continue
            
        hull = cv2.convexHull(cnt)
        hull_area = cv2.contourArea(hull)
        if hull_area == 0:
            continue
            
        solidity = area / hull_area
        
        if solidity > 0.5:
            if area > best_area:
                best_area = area
                best_contour = cnt
                
    if best_contour is None:
        return jsonify({"error": "Shape not found. Try switching to a different Map Type."}), 404
        
    # Simplify contour for frontend rendering
    epsilon = 0.01 * cv2.arcLength(best_contour, True)
    approx = cv2.approxPolyDP(best_contour, epsilon, True)
    
    points = []
    for pt in approx:
        x, y = pt[0]
        points.append({"x": int(x), "y": int(y)})
        
    # Calculate average spectrum for the flake
    flake_mask = np.zeros((height, width), dtype=np.uint8)
    cv2.drawContours(flake_mask, [best_contour], -1, 255, -1)
    
    specs = []
    for y in range(height):
        for x in range(width):
            if flake_mask[y, x] == 255:
                h_idx = (width - 1) - x
                key = f"{h_idx}_{y}"
                if key in dataset['pixels']:
                    spec = dataset['pixels'][key].get('norm_spec')
                    if spec is not None:
                        specs.append(spec)
                        
    if len(specs) > 0:
        specs_arr = np.array(specs)
        mean_spec = np.mean(specs_arr, axis=0).tolist()
        std_spec = np.std(specs_arr, axis=0).tolist()
    else:
        mean_spec = []
        std_spec = []
        
    return jsonify({
        "points": points,
        "mean_spec": mean_spec,
        "std_spec": std_spec
    })

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
            def generate():
                yield json.dumps(datasets[dataset_id])
            return Response(generate(), mimetype='application/json')
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
