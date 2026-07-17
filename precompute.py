import os
import h5py
import numpy as np
import scipy.signal
import time
import warnings
import json
from scipy.signal import find_peaks
from scipy.ndimage import median_filter, label

# Laser line FWHM in nm: no real spectral feature can be narrower than this,
# so anything narrower is a cosmic ray / readout artifact.
LASER_FWHM_NM = 0.5

def remove_cosmic_rays(specs, wls, laser_fwhm_nm=LASER_FWHM_NM, threshold_sigma=8.0):
    """Remove cosmic-ray spikes from an (n_spectra, n_channels) array.

    A median filter spanning 2x the laser FWHM erases any feature
    narrower than the laser line, giving a spike-free reference. Points
    more than threshold_sigma noise-sigmas above the reference are spike
    candidates; candidate runs at least as wide as the laser FWHM are
    real (laser-limited) lines and are kept, narrower runs cannot be
    real signal and get replaced with the reference value.
    Returns (cleaned_specs, spikes_removed_per_spectrum).
    """
    specs = np.asarray(specs, dtype=np.float64)
    dwl = np.median(np.abs(np.diff(np.asarray(wls, dtype=np.float64))))
    if not np.isfinite(dwl) or dwl <= 0:
        return specs, np.zeros(len(specs), dtype=int)
    w_laser = laser_fwhm_nm / dwl  # laser FWHM in channels
    win = min(31, max(5, int(np.ceil(2 * w_laser)) | 1))
    filtered = median_filter(specs, size=(1, win), mode='nearest')
    resid = specs - filtered
    # Per-spectrum noise from first differences — immune to peaks and to
    # the zero-inflated distribution of median-filter residuals.
    dz = np.diff(specs, axis=1)
    noise = 1.4826 * np.median(np.abs(dz - np.median(dz, axis=1, keepdims=True)),
                               axis=1, keepdims=True) / np.sqrt(2)
    noise[noise <= 0] = np.inf  # flat spectra: nothing to flag
    spikes = resid > threshold_sigma * noise  # cosmic rays are always positive
    if spikes.any():
        # Contiguous flagged runs as wide as the laser line are real peaks
        along_row = np.array([[0, 0, 0], [1, 1, 1], [0, 0, 0]])
        run_labels, n_runs = label(spikes, structure=along_row)
        if n_runs:
            run_sizes = np.bincount(run_labels.ravel())
            is_real = run_sizes >= w_laser
            is_real[0] = False
            spikes &= ~is_real[run_labels]
    cleaned = np.where(spikes, filtered, specs)
    return cleaned, spikes.sum(axis=1).astype(int)

def snip_baseline(specs, max_half_window=None):
    """Per-spectrum background via the SNIP algorithm (min-of-neighbor-
    averages with a shrinking window), vectorized across all spectra.

    Runs in the linear domain: the min operator alone keeps the baseline
    from climbing peaks, while the usual LLS transform's concavity would
    bias sloped backgrounds low. The baseline can only contain features
    wider than max_half_window channels (default: a quarter of the
    spectrum), so peaks — including broad PL bands — survive.
    float32 halves memory traffic; precision is far below the noise floor.
    """
    specs = np.asarray(specs, dtype=np.float64)
    n = specs.shape[1]
    if max_half_window is None:
        max_half_window = max(1, n // 4)
    v = specs.astype(np.float32)
    for p in range(max_half_window, 0, -1):
        avg = 0.5 * (v[:, :-2 * p] + v[:, 2 * p:])
        core = v[:, p:-p]
        np.minimum(core, avg, out=core)
    return v.astype(np.float64)

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
    if h5_path.lower().endswith('.mat'):
        return process_mat(h5_path, progress_callback)
        
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

    # Whole-map cleanup before the per-pixel loop: despike, then estimate
    # a per-pixel SNIP background. Row index = v * h_steps + h.
    spec_flat = spec_map.reshape(total_pixels, -1).astype(np.float64)
    if progress_callback:
        progress_callback(0, total_pixels, "Removing cosmic rays")
    spec_flat, spike_counts = remove_cosmic_rays(spec_flat, wls)
    if progress_callback:
        progress_callback(0, total_pixels, "Estimating background (SNIP)")
    baselines = snip_baseline(spec_flat)

    for v in range(v_steps):
        for h in range(h_steps):
            pixel_count += 1
            if progress_callback and pixel_count % 200 == 0:
                progress_callback(pixel_count, total_pixels, f"Processing pixel {h}, {v}")

            row = v * h_steps + h
            bg_noise = float(np.mean(baselines[row]))
            spec_sub = spec_flat[row] - baselines[row]
            l_max = np.max(spec_sub) if np.max(spec_sub) > 0 else 1.0
            norm_spec = spec_sub / l_max
            norm_spec = np.nan_to_num(norm_spec, nan=0.0)
            
            # Magic number for heatmap: Total integrated intensity
            magic_number = float(np.sum(spec_sub))
            if np.isnan(magic_number): magic_number = 0.0
            
            # Compute sharpness
            sharpness = float(np.max(spec_sub) / magic_number) if magic_number > 0 else 0.0
            if np.isnan(sharpness): sharpness = 0.0
            bg_noise = 0.0 if np.isnan(bg_noise) else float(bg_noise)
            l_max = 0.0 if np.isnan(l_max) else float(l_max)
            
            current_max_y = np.max(norm_spec)
            if current_max_y > global_max_y: global_max_y = current_max_y
            if np.min(norm_spec) < global_min_y: global_min_y = np.min(norm_spec)
            
            # Fast Peak Recommendations
            num_peaks, peak_indices = recommend_peak_count(rs, norm_spec)

            precomputed_data['pixels'][f"{h}_{v}"] = {
                'norm_spec': np.round(norm_spec, 3).tolist(),
                'integrated_intensity': magic_number,
                'sharpness': sharpness,
                'bg_noise': round(float(bg_noise), 2),
                'l_max': round(float(l_max), 2),
                'num_peaks': num_peaks,
                'peak_indices': peak_indices,
                'cosmic_removed': int(spike_counts[row]),
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

def process_mat(mat_path, progress_callback=None):
    print(f"Loading dataset {mat_path} for fast preview...")
    start_time = time.time()
    
    import scipy.io as sio
    try:
        mat = sio.loadmat(mat_path)
        share = mat['share'][0, 0]
        
        uniqueX = share['uniqueX'].flatten()
        uniqueY = share['uniqueY'].flatten()
        index_map = share['index_map']
        raw = share['raw']
        wls = share['wl'].flatten()
        
        if 'sharpness_map' in share.dtype.names:
            sharpness_map = share['sharpness_map'].flatten()
        else:
            sharpness_map = None
            
        is_h5 = False
    except NotImplementedError:
        # Fallback to h5py for v7.3 .mat files
        f = h5py.File(mat_path, 'r')
        share = f['share']
        
        uniqueX = share['uniqueX'][:].flatten()
        uniqueY = share['uniqueY'][:].flatten()
        index_map = share['index_map'][:].T # HDF5 transposes
        raw = share['raw'][:].T # HDF5 transposes
        wls = share['wl'][:].flatten()
        
        if 'sharpness_map' in share:
            sharpness_map = share['sharpness_map'][:].flatten()
        else:
            sharpness_map = None
            
        is_h5 = True

    h_steps = len(uniqueX)
    v_steps = len(uniqueY)
    
    precomputed_data = {'pixels': {}}
    
    total_pixels = v_steps * h_steps
    pixel_count = 0

    global_min_y = float('inf')
    global_max_y = float('-inf')

    # Convert wls to rs roughly if needed
    rs = (1/532.0 - 1/wls) * 1e7

    # Whole-map cleanup: despike, then per-pixel SNIP background.
    raw = np.asarray(raw, dtype=np.float64)
    if progress_callback:
        progress_callback(0, total_pixels, "Removing cosmic rays")
    raw, spike_counts = remove_cosmic_rays(raw, wls)
    if progress_callback:
        progress_callback(0, total_pixels, "Estimating background (SNIP)")
    baselines = snip_baseline(raw)

    for y_idx in range(v_steps):
        for x_idx in range(h_steps):
            pixel_count += 1
            if progress_callback and pixel_count % 200 == 0:
                progress_callback(pixel_count, total_pixels, f"Processing pixel {x_idx}, {y_idx}")

            mat_idx = index_map[y_idx, x_idx]
            
            if np.isnan(mat_idx):
                continue
                
            idx = int(mat_idx) - 1 # 1-based indexing in Matlab
            bg_noise = float(np.mean(baselines[idx]))
            spec_sub = raw[idx, :] - baselines[idx]
            l_max = np.max(spec_sub) if np.max(spec_sub) > 0 else 1.0
            norm_spec = spec_sub / l_max
            norm_spec = np.nan_to_num(norm_spec, nan=0.0)
            
            magic_number = float(np.sum(spec_sub))
            if np.isnan(magic_number): magic_number = 0.0
            
            if sharpness_map is not None:
                s_val = float(sharpness_map[idx])
                sharpness = 0.0 if np.isnan(s_val) else s_val
            else:
                sharpness = float(np.max(spec_sub) / magic_number) if magic_number > 0 else 0.0
                if np.isnan(sharpness): sharpness = 0.0
            bg_noise = 0.0 if np.isnan(bg_noise) else float(bg_noise)
            l_max = 0.0 if np.isnan(l_max) else float(l_max)
            
            current_max_y = np.max(norm_spec)
            if current_max_y > global_max_y: global_max_y = current_max_y
            if np.min(norm_spec) < global_min_y: global_min_y = np.min(norm_spec)
            
            num_peaks, peak_indices = recommend_peak_count(rs, norm_spec)

            precomputed_data['pixels'][f"{x_idx}_{y_idx}"] = {
                'norm_spec': np.round(norm_spec, 3).tolist(),
                'integrated_intensity': magic_number,
                'sharpness': sharpness,
                'bg_noise': round(float(bg_noise), 2),
                'l_max': round(float(l_max), 2),
                'num_peaks': num_peaks,
                'peak_indices': peak_indices,
                'cosmic_removed': int(spike_counts[idx]),
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
