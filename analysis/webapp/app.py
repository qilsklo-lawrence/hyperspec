import os
import h5py
import numpy as np
import scipy.signal
import time
import warnings
import json
from scipy.optimize import curve_fit, OptimizeWarning
from flask import Flask, jsonify, send_from_directory

warnings.simplefilter("ignore", OptimizeWarning)

app = Flask(__name__, static_folder='.')

# Load pre-computed data from disk
precomputed_data_path = 'precomputed_data.json'
print("Loading pre-computed data from disk...")
start_time = time.time()

if not os.path.exists(precomputed_data_path):
    print("Error: precomputed_data.json not found! Please run 'python precompute.py' first.")
    precomputed_data = {}
else:
    with open(precomputed_data_path, 'r') as f:
        precomputed_data = json.load(f)

end_time = time.time()
print(f"Data loaded! Took {end_time - start_time:.2f} seconds.")

@app.route('/data/<int:x>/<int:y>')
def get_data(x, y):
    # Invert mapping as requested: MAPPING.h5 is inverted horizontally and vertically
    # Assuming x is horizontal (0 to 50, left to right) and y is vertical (0 to 50, top to bottom)
    # Dataset populated "downward and to the left" means [0,0] is top-right.
    h_idx = 50 - x
    v_idx = y
    
    key = f"{h_idx}_{v_idx}"
    if key in precomputed_data:
        return jsonify(precomputed_data[key])
    return jsonify({"error": "Pixel out of bounds"}), 404

@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

@app.route('/data/all_deltas')
def get_all_deltas():
    # Return a 2D array (51x51) of magic_number (Delta) values
    # x is horizontal, y is vertical
    deltas = []
    for y in range(51):
        row = []
        for x in range(51):
            h_idx = 50 - x
            v_idx = y
            key = f"{h_idx}_{v_idx}"
            if key in precomputed_data:
                row.append(precomputed_data[key]['magic_number'])
            else:
                row.append(0)
        deltas.append(row)
    return jsonify({"deltas": deltas})

if __name__ == '__main__':
    print("Starting server...")
    app.run(debug=True, port=8080, extra_files=[precomputed_data_path])
