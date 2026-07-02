import os
import h5py
import numpy as np
import scipy.signal
import time
import warnings
import json
from scipy.signal import find_peaks
from scipy.ndimage import median_filter

def recommend_peak_count(x, y, min_distance=20):
    y = np.asarray(y)
    x = np.asarray(x)

    # Mask out the laser line (rs < 100)
    mask = x > 100
    if not np.any(mask):
        mask = np.ones_like(x, dtype=bool)
        
    y_masked = y[mask]
    
    # Estimate baseline using median filter
    baseline = median_filter(y_masked, size=max(5, len(y_masked)//50))
    z = y_masked - baseline
    
    # robust noise estimate using MAD
    dz = np.diff(z)
    noise = 1.4826 * np.median(np.abs(dz - np.median(dz))) / np.sqrt(2)
    
    # Adaptive prominence
    prom = max(8 * noise, 0.05 * np.ptp(z))
    
    peaks_masked, props = find_peaks(z, prominence=prom, distance=min_distance)
    
    # map back to original indices
    valid_indices = np.where(mask)[0]
    peaks = valid_indices[peaks_masked].tolist()
    
    # If no peaks found, assume it's one broad envelope (like PL)
    if len(peaks) == 0:
        peaks = [int(valid_indices[np.argmax(y_masked)])]
        
    return len(peaks), peaks

def process_h5(h5_path, progress_callback=None):
    print(f"Loading dataset {h5_path} for fast preview...")
    start_time = time.time()
    f = h5py.File(h5_path, 'r')
    if 'measurement' not in f:
        raise ValueError("Invalid H5 file format. Expected 'measurement' group.")
        
    if 'hyperspec_picam_mcl' in f['measurement']:
        meas = f['measurement']['hyperspec_picam_mcl']
        rs_raw = meas['raman_shifts'][:]
        spec_map_raw = meas['spec_map'][:]
        spec_map = spec_map_raw[0]
        # Estimate wls (assuming 532 nm excitation)
        wls = 1.0 / (1/532.0 - rs_raw / 1e7)
    elif 'piezo_hyperspec' in f['measurement']:
        meas = f['measurement']['piezo_hyperspec']
        wls = meas['wls'][:]
        rs_raw = (1/532.0 - 1/wls) * 1e7
        spec_map_raw = meas['spec_map'][:]
        spec_map = spec_map_raw[0, :, :, 0, :]
    else:
        raise ValueError("Invalid H5 file format. Expected 'hyperspec_picam_mcl' or 'piezo_hyperspec' inside 'measurement'.")
        
    v_steps, h_steps, _ = spec_map.shape

    rs = rs_raw
    precomputed_data = {'pixels': {}}
    
    total_pixels = v_steps * h_steps
    pixel_count = 0

    global_min_y = float('inf')
    global_max_y = float('-inf')

    for v in range(v_steps):
        for h in range(h_steps):
            pixel_count += 1
            if progress_callback and pixel_count % 200 == 0:
                progress_callback(pixel_count, total_pixels, f"Processing pixel {h}, {v}")

            spec = spec_map[v, h, :]
            
            # Simple baseline subtraction and normalization for preview
            bg_noise = np.percentile(spec, 5) 
            spec_sub = spec - bg_noise
            l_max = np.max(spec_sub) if np.max(spec_sub) > 0 else 1.0
            norm_spec = spec_sub / l_max
            
            # Magic number for heatmap: Total integrated intensity
            magic_number = float(np.sum(spec_sub))
            
            current_max_y = np.max(norm_spec)
            if current_max_y > global_max_y: global_max_y = current_max_y
            if np.min(norm_spec) < global_min_y: global_min_y = np.min(norm_spec)
            
            # Fast Peak Recommendations
            num_peaks, peak_indices = recommend_peak_count(rs, norm_spec)

            precomputed_data['pixels'][f"{h}_{v}"] = {
                'norm_spec': np.round(norm_spec, 3).tolist(),
                'integrated_intensity': magic_number,
                'bg_noise': round(float(bg_noise), 2),
                'l_max': round(float(l_max), 2),
                'num_peaks': num_peaks,
                'peak_indices': peak_indices,
                # Fit fields initialized empty
                'fit_curves': [],
                'fit_success': False
            }

    precomputed_data['global_axes'] = {
        'rs': np.round(rs, 3).tolist(),
        'wls': np.round(wls, 3).tolist(),
        'width': h_steps,
        'height': v_steps,
        'min_y': float(global_min_y),
        'max_y': float(global_max_y)
    }

    if progress_callback:
        progress_callback(total_pixels, total_pixels, "Finished precomputing")

    end_time = time.time()
    print(f"Fast initial processing complete! Took {end_time - start_time:.2f} seconds.")
    return precomputed_data

def main():
    pass

if __name__ == '__main__':
    main()
