import os
import h5py
import numpy as np
import scipy.signal
from scipy.optimize import curve_fit
from flask import Flask, jsonify, send_from_directory

app = Flask(__name__, static_folder='.')

def double_lorentzian(x, a0, a1, c1, w1, a2, c2, w2):
    L1 = a1 * w1**2 / ((x - c1)**2 + w1**2)
    L2 = a2 * w2**2 / ((x - c2)**2 + w2**2)
    return a0 + L1 + L2

def clean_cosmic_rays(rs, y):
    # Only despike for Raman Shift > 530 cm^-1 to preserve MoS2 (380-410) and Si (~520) peaks
    mask = rs > 530
    med = scipy.signal.medfilt(y, 3)
    diff = np.abs(y - med)
    threshold = 5 * np.std(diff[mask]) if np.std(diff[mask]) > 0 else 1
    
    cleaned_y = y.copy()
    spike_idx = mask & (diff > threshold)
    cleaned_y[spike_idx] = med[spike_idx]
    return cleaned_y

print("Loading dataset and pre-computing fits (this takes ~1-2 seconds)...")
h5_path = '../../MAPPING.h5'
f = h5py.File(h5_path, 'r')
rs_raw = f['measurement']['hyperspec_picam_mcl']['raman_shifts'][:]
spec_map = f['measurement']['hyperspec_picam_mcl']['spec_map'][0]

rs = rs_raw - (-6.72) # Apply Si calibration shift

# Precompute data structure
precomputed_data = {}

for v in range(51):
    for h in range(51):
        spec = spec_map[v, h, :]
        spec = clean_cosmic_rays(rs, spec)
        
        # Background subtraction
        bg_mask = ((rs > 330) & (rs < 360)) | ((rs > 430) & (rs < 460))
        bg_noise = np.mean(spec[bg_mask])
        spec_sub = spec - bg_noise
        
        # Normalization
        norm_mask = (rs >= 370) & (rs <= 415)
        l_max = np.max(spec_sub[norm_mask]) if np.sum(norm_mask) > 0 else 1.0
        if l_max <= 0: l_max = 1.0
        norm_spec = spec_sub / l_max
        
        # Fit Region
        fit_mask = (rs > 360) & (rs < 430)
        x_fit = rs[fit_mask]
        y_fit = norm_spec[fit_mask]
        
        # Guesses
        mask1 = (x_fit > 370) & (x_fit < 395)
        mask2 = (x_fit > 395) & (x_fit < 420)
        amp1_guess = np.max(y_fit[mask1]) if np.sum(mask1) > 0 else 1.0
        c1_guess = x_fit[mask1][np.argmax(y_fit[mask1])] if np.sum(mask1) > 0 else 383.0
        amp2_guess = np.max(y_fit[mask2]) if np.sum(mask2) > 0 else 1.0
        c2_guess = x_fit[mask2][np.argmax(y_fit[mask2])] if np.sum(mask2) > 0 else 405.0
        
        p0 = [0, amp1_guess, c1_guess, 2, amp2_guess, c2_guess, 2]
        
        try:
            popt, _ = curve_fit(double_lorentzian, x_fit, y_fit, p0=p0, maxfev=10000)
            a0, a1, c1, w1, a2, c2, w2 = popt
            
            fwhm1 = 2 * abs(w1)
            fwhm2 = 2 * abs(w2)
            # Area calculated on un-normalized scale
            int1 = a1 * l_max * abs(w1) * np.pi
            int2 = a2 * l_max * abs(w2) * np.pi
            integrated_intensity = int1 + int2
            magic_number = c2 - c1
            
            # Generate curve data
            y_fit_curve = double_lorentzian(x_fit, *popt)
            L1_curve = a1 * w1**2 / ((x_fit - c1)**2 + w1**2) + a0
            L2_curve = a2 * w2**2 / ((x_fit - c2)**2 + w2**2) + a0
            
            fit_success = True
        except Exception:
            popt = p0
            a0, a1, c1, w1, a2, c2, w2 = p0
            fwhm1, fwhm2, integrated_intensity, magic_number = 0, 0, 0, 0
            y_fit_curve = np.zeros_like(x_fit)
            L1_curve = np.zeros_like(x_fit)
            L2_curve = np.zeros_like(x_fit)
            fit_success = False
            
        precomputed_data[f"{h}_{v}"] = {
            'rs': rs.tolist(),
            'norm_spec': norm_spec.tolist(),
            'x_fit': x_fit.tolist(),
            'y_fit_curve': y_fit_curve.tolist(),
            'L1_curve': L1_curve.tolist(),
            'L2_curve': L2_curve.tolist(),
            'bg_noise': float(bg_noise),
            'c1': float(c1),
            'fwhm1': float(fwhm1),
            'c2': float(c2),
            'fwhm2': float(fwhm2),
            'integrated_intensity': float(integrated_intensity),
            'magic_number': float(magic_number),
            'fit_success': fit_success
        }

print("Pre-computation complete!")

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

if __name__ == '__main__':
    app.run(port=8080)
