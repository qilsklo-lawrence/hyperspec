import os
import h5py
import numpy as np
import scipy.signal
import time
import warnings
import json
from scipy.optimize import curve_fit, OptimizeWarning

warnings.simplefilter("ignore", OptimizeWarning)

def double_lorentzian(x, a0, a1, c1, w1, a2, c2, w2):
    L1 = a1 * w1**2 / ((x - c1)**2 + w1**2)
    L2 = a2 * w2**2 / ((x - c2)**2 + w2**2)
    return a0 + L1 + L2

def clean_cosmic_rays(rs, y):
    mask = rs > 530
    med = scipy.signal.medfilt(y, 3)
    diff = np.abs(y - med)
    threshold = 5 * np.std(diff[mask]) if np.std(diff[mask]) > 0 else 1
    
    cleaned_y = y.copy()
    spike_idx = mask & (diff > threshold)
    cleaned_y[spike_idx] = med[spike_idx]
    return cleaned_y

def process_h5(h5_path):
    print(f"Loading dataset {h5_path} and pre-computing fits...")
    start_time = time.time()
    f = h5py.File(h5_path, 'r')
    if 'measurement' not in f:
        raise ValueError("Invalid H5 file format. Expected 'measurement' group.")
        
    if 'hyperspec_picam_mcl' in f['measurement']:
        meas = f['measurement']['hyperspec_picam_mcl']
        rs_raw = meas['raman_shifts'][:]
        spec_map_raw = meas['spec_map'][:]
        spec_map = spec_map_raw[0]
    elif 'piezo_hyperspec' in f['measurement']:
        meas = f['measurement']['piezo_hyperspec']
        wls = meas['wls'][:]
        rs_raw = (1/532.0 - 1/wls) * 1e7
        spec_map_raw = meas['spec_map'][:]
        spec_map = spec_map_raw[0, :, :, 0, :]
    else:
        raise ValueError("Invalid H5 file format. Expected 'hyperspec_picam_mcl' or 'piezo_hyperspec' inside 'measurement'.")
        
    v_steps, h_steps, _ = spec_map.shape

    # Calculate global Si calibration shift for this dataset
    mean_spec = np.mean(spec_map, axis=(0, 1))
    si_mask = (rs_raw > 490) & (rs_raw < 550)
    measured_si = rs_raw[si_mask][np.argmax(mean_spec[si_mask])]
    calibration_shift = measured_si - 520.45
    print(f"Measured Si Peak: {measured_si:.2f} cm^-1")
    print(f"Calibration Shift: {calibration_shift:.2f} cm^-1")

    rs = rs_raw - calibration_shift

    precomputed_data = {'pixels': {}}
    
    # Define physical bounds to prevent peak collapse
    bounds = (
        [-np.inf, 0, 370, 0, 0, 395, 0],
        [np.inf, np.inf, 395, 20, np.inf, 420, 20]
    )

    for v in range(v_steps):
        for h in range(h_steps):
            spec = spec_map[v, h, :]
            spec = clean_cosmic_rays(rs, spec)
            
            # Background subtraction
            bg_mask = ((rs > 330) & (rs < 360)) | ((rs > 430) & (rs < 460))
            bg_noise = np.mean(spec[bg_mask])
            spec_sub = spec - bg_noise
            
            # Si Fit Region
            si_mask = (rs > 500) & (rs < 540)
            x_si = rs[si_mask]
            y_si = spec[si_mask]
            si_bg = np.min(y_si) if len(y_si) > 0 else 0
            si_amp = np.max(y_si) - si_bg if len(y_si) > 0 else 0
            si_c_guess = x_si[np.argmax(y_si)] if len(y_si) > 0 else 520.45
            try:
                popt_si, _ = curve_fit(
                    lambda x, a, c, w, bg: a * w**2 / ((x - c)**2 + w**2) + bg, 
                    x_si, y_si, 
                    p0=[si_amp, si_c_guess, 2, si_bg],
                    bounds=([0, 510, 0, -np.inf], [np.inf, 535, 15, np.inf]),
                    maxfev=1000
                )
                a_si, c_si, w_si, bg_si = popt_si
                y_si_curve = a_si * w_si**2 / ((x_si - c_si)**2 + w_si**2) + bg_si
                ss_res_si = np.sum((y_si - y_si_curve)**2)
                ss_tot_si = np.sum((y_si - np.mean(y_si))**2)
                r2_si = 1 - (ss_res_si / ss_tot_si) if ss_tot_si > 0 else 0
            except Exception:
                a_si, c_si, w_si, bg_si = 0, 520.45, 0, 0
                y_si_curve = np.zeros_like(x_si)
                r2_si = 0
            
            # Normalization
            norm_mask = (rs >= 370) & (rs <= 415)
            l_max = np.max(spec_sub[norm_mask]) if np.sum(norm_mask) > 0 else 1.0
            std_noise = np.std(spec[bg_mask]) if np.sum(bg_mask) > 0 else 1.0
            if l_max <= 0: l_max = 1.0
            norm_spec = spec_sub / l_max
            
            # Fit Region
            fit_mask = (rs > 360) & (rs < 430)
            x_fit = rs[fit_mask]
            y_fit = norm_spec[fit_mask]
            
            # Skip MoS2 fit if it's just pure substrate noise (SNR < 3)
            if l_max < 3 * std_noise:
                a0, a1, c1, w1, a2, c2, w2 = 0, 0, 383, 0, 0, 405, 0
                fwhm1, fwhm2, integrated_intensity, magic_number = 0, 0, 0, 0
                y_fit_curve = np.zeros_like(x_fit)
                L1_curve = np.zeros_like(x_fit)
                L2_curve = np.zeros_like(x_fit)
                r2_mos2 = 0
                fit_success = False
            else:
                # Guesses
                mask1 = (x_fit > 370) & (x_fit < 395)
                mask2 = (x_fit > 395) & (x_fit < 420)
                amp1_guess = np.max(y_fit[mask1]) if np.sum(mask1) > 0 else 1.0
                c1_guess = x_fit[mask1][np.argmax(y_fit[mask1])] if np.sum(mask1) > 0 else 383.0
                amp2_guess = np.max(y_fit[mask2]) if np.sum(mask2) > 0 else 1.0
                c2_guess = x_fit[mask2][np.argmax(y_fit[mask2])] if np.sum(mask2) > 0 else 405.0
                
                p0 = [0, amp1_guess, c1_guess, 2, amp2_guess, c2_guess, 2]
                
                try:
                    popt, _ = curve_fit(double_lorentzian, x_fit, y_fit, p0=p0, bounds=bounds, maxfev=10000)
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
                    
                    ss_res_mos2 = np.sum((y_fit - y_fit_curve)**2)
                    ss_tot_mos2 = np.sum((y_fit - np.mean(y_fit))**2)
                    r2_mos2 = 1 - (ss_res_mos2 / ss_tot_mos2) if ss_tot_mos2 > 0 else 0
                    
                    fit_success = True
                except Exception:
                    popt = p0
                    a0, a1, c1, w1, a2, c2, w2 = p0
                    fwhm1, fwhm2, integrated_intensity, magic_number = 0, 0, 0, 0
                    y_fit_curve = np.zeros_like(x_fit)
                    L1_curve = np.zeros_like(x_fit)
                    L2_curve = np.zeros_like(x_fit)
                    r2_mos2 = 0
                    fit_success = False
            
            # Round data to 3 decimal places to drastically reduce JSON string size
            precomputed_data['pixels'][f"{h}_{v}"] = {
                'norm_spec': np.round(norm_spec, 3).tolist(),
                'y_fit_curve': np.round(y_fit_curve, 3).tolist(),
                'L1_curve': np.round(L1_curve, 3).tolist(),
                'L2_curve': np.round(L2_curve, 3).tolist(),
                'y_si': np.round((np.array(y_si) - bg_noise) / l_max, 3).tolist(),
                'y_si_curve': np.round((np.array(y_si_curve) - bg_noise) / l_max, 3).tolist(),
                'si_c': round(float(c_si), 3),
                'si_fwhm': round(float(2 * abs(w_si)), 3),
                'r2_si': round(float(r2_si), 4),
                'r2_mos2': round(float(r2_mos2), 4),
                'bg_noise': round(float(bg_noise), 2),
                'c1': round(float(c1), 3),
                'fwhm1': round(float(fwhm1), 3),
                'c2': round(float(c2), 3),
                'fwhm2': round(float(fwhm2), 3),
                'integrated_intensity': float(integrated_intensity),
                'magic_number': round(float(magic_number), 3),
                'fit_success': fit_success
            }
            
            # Store the x-axis arrays only once globally to save space
            if 'global_axes' not in precomputed_data:
                precomputed_data['global_axes'] = {
                    'rs': np.round(rs, 3).tolist(),
                    'x_fit': np.round(x_fit, 3).tolist(),
                    'x_si': np.round(x_si, 3).tolist(),
                    'width': h_steps,
                    'height': v_steps
                }

    end_time = time.time()
    print(f"Pre-computation complete! Took {end_time - start_time:.2f} seconds.")
    return precomputed_data

def main():
    h5_path = '../../MAPPING.h5'
    precomputed_data = process_h5(h5_path)
    with open('precomputed_data.tmp.json', 'w') as out_f:
        json.dump(precomputed_data, out_f, separators=(',', ':'))
    os.rename('precomputed_data.tmp.json', 'precomputed_data.json')
    print("Saved to disk as precomputed_data.json")

if __name__ == '__main__':
    main()
