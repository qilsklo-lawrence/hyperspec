import os
import h5py
import numpy as np
import scipy.signal
import time
import warnings
import json
from scipy.optimize import curve_fit, OptimizeWarning

import warnings
warnings.simplefilter("ignore", OptimizeWarning)

import uuid
import hashlib
from werkzeug.utils import secure_filename
from flask import Flask, jsonify, send_from_directory, request
from precompute import process_h5

app = Flask(__name__, static_folder='frontend/dist', static_url_path='')

datasets = {}
file_hashes = {}
dataset_names = {}

# Load default data if exists
default_data_path = 'precomputed_data.json'
if os.path.exists(default_data_path):
    with open(default_data_path, 'r') as f:
        datasets['default'] = json.load(f)
        dataset_names['default'] = 'default (MAPPING.h5)'
        # If we wanted to track the hash of the default, we could hash MAPPING.h5 here, 
        # but it might not be available relative to the backend. We'll just track uploaded file hashes.

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def get_file_hash(filepath):
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def load_persisted_datasets():
    print("Scanning uploads directory for datasets...")
    for filename in os.listdir(UPLOAD_FOLDER):
        if filename.endswith('.h5'):
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file_hash = get_file_hash(filepath)
            dataset_id = file_hash[:8]
            
            file_hashes[file_hash] = dataset_id
            dataset_names[dataset_id] = filename
            
            json_filepath = os.path.join(UPLOAD_FOLDER, f"{dataset_id}.json")
            if os.path.exists(json_filepath):
                print(f"Loading cached fits for {dataset_id}...")
                with open(json_filepath, 'r') as f:
                    datasets[dataset_id] = json.load(f)
            else:
                print(f"Precomputing fits for new file {filename}...")
                try:
                    data = process_h5(filepath)
                    datasets[dataset_id] = data
                    with open(json_filepath, 'w') as f:
                        json.dump(data, f, separators=(',', ':'))
                except Exception as e:
                    print(f"Failed to process {filename}: {e}")

load_persisted_datasets()

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if file and file.filename.endswith('.h5'):
        filename = secure_filename(file.filename)
        temp_id = str(uuid.uuid4())
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"{temp_id}_{filename}")
        file.save(filepath)
        
        file_hash = get_file_hash(filepath)
        
        if file_hash in file_hashes:
            os.remove(filepath) # Remove the duplicate we just saved
            existing_id = file_hashes[file_hash]
            original_name = dataset_names.get(existing_id, existing_id)
            return jsonify({
                "message": f"Duplicate file detected. This file is identical to '{original_name}'.",
                "dataset_id": existing_id,
                "filename": filename,
                "duplicate": True
            })
            
        dataset_id = file_hash[:8] # Use short hash as ID for neatness
        new_filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"{dataset_id}_{filename}")
        os.rename(filepath, new_filepath)
        
        try:
            # Process the file
            data = process_h5(new_filepath)
            datasets[dataset_id] = data
            file_hashes[file_hash] = dataset_id
            dataset_names[dataset_id] = filename
            
            # Save the processed data to disk to save time on next startup
            json_filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"{dataset_id}.json")
            with open(json_filepath, 'w') as f:
                json.dump(data, f, separators=(',', ':'))
            
            return jsonify({
                "message": "File processed successfully",
                "dataset_id": dataset_id,
                "filename": filename,
                "duplicate": False
            })
        except Exception as e:
            if os.path.exists(new_filepath):
                os.remove(new_filepath)
            return jsonify({"error": str(e)}), 500
    return jsonify({"error": "Invalid file type. Only .h5 allowed."}), 400

@app.route('/datasets')
def list_datasets():
    return jsonify({"datasets": list(datasets.keys())})

@app.route('/api/data/<dataset_id>')
def get_dataset(dataset_id):
    if dataset_id in datasets:
        return jsonify(datasets[dataset_id])
    return jsonify({"error": "Dataset not found"}), 404

@app.route('/')
def serve_index():
    return app.send_static_file('index.html')

@app.route('/<path:path>')
def serve_static(path):
    # Try to serve the static file. If it fails, fallback to something else if needed.
    return app.send_static_file(path)

if __name__ == '__main__':
    print("Starting server...")
    app.run(host='0.0.0.0', debug=True, port=8080)
