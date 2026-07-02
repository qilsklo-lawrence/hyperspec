import numpy as np
from scipy.optimize import curve_fit
import json
import warnings
from scipy.optimize import OptimizeWarning

warnings.simplefilter("ignore", OptimizeWarning)

def pseudo_voigt(x, a, c, w, eta):
    L = (w**2 / 4) / ((x - c)**2 + w**2 / 4)
    G = np.exp(-4 * np.log(2) * (x - c)**2 / w**2)
    return a * (eta * L + (1 - eta) * G)

def multi_pv(x, *params):
    b0 = params[0]
    b1 = params[1]
    
    y = b0 + b1 * x
    for i in range(2, len(params), 4):
        y += pseudo_voigt(x, params[i], params[i+1], params[i+2], params[i+3])
    return y

def perform_fits(dataset_id, datasets):
    """
    Generator that yields JSON-serializable fit results for each pixel as they are computed.
    """
    if dataset_id not in datasets:
        yield {"error": "Dataset not found"}
        return
        
    dataset = datasets[dataset_id]
    x_data = np.array(dataset['global_axes']['rs'])
    
    for key, pixel in dataset['pixels'].items():
        norm_spec = np.array(pixel['norm_spec'])
        peak_indices = pixel['peak_indices']
        
        # Mask laser line (rs > 100)
        mask = x_data > 100
        if not np.any(mask):
            mask = np.ones_like(x_data, dtype=bool)
            
        x_fit = x_data[mask]
        y_fit = norm_spec[mask]
        
        # Linear Baseline guesses
        b0_guess = np.min(y_fit)
        b1_guess = 0.0
        p0 = [b0_guess, b1_guess]
        bounds_lower = [-np.inf, -np.inf]
        bounds_upper = [np.inf, np.inf]
        
        for idx in peak_indices:
            if not mask[idx]: continue
            c_guess = x_data[idx]
            a_guess = max(0.001, norm_spec[idx] - b0_guess)
            w_guess = 20.0
            eta_guess = 0.5
            p0.extend([a_guess, c_guess, w_guess, eta_guess])
            bounds_lower.extend([0, c_guess - 50, 0, 0])
            bounds_upper.extend([np.inf, c_guess + 50, 2000, 1])
            
        try:
            popt, _ = curve_fit(multi_pv, x_fit, y_fit, p0=p0, bounds=(bounds_lower, bounds_upper), maxfev=10000)
            
            total_fit = multi_pv(x_data, *popt)
            bg_fit = popt[0] + popt[1] * x_data
            
            ss_res = np.sum((norm_spec - total_fit) ** 2)
            ss_tot = np.sum((norm_spec - np.mean(norm_spec)) ** 2)
            r_squared = 1 - (ss_res / ss_tot)
            
            fit_curves = []
            for i in range(2, len(popt), 4):
                a = popt[i]
                c = popt[i+1]
                w = popt[i+2]
                eta = popt[i+3]
                curve = pseudo_voigt(x_data, a, c, w, eta) + bg_fit
                fit_curves.append({
                    'a': round(float(a), 3),
                    'c': round(float(c), 3),
                    'w': round(float(w), 3),
                    'eta': round(float(eta), 3),
                    'curve': np.round(curve, 3).tolist()
                })
                
            result = {
                'key': key,
                'fit_success': True,
                'fit_curves': fit_curves,
                'total_fit_curve': np.round(total_fit, 3).tolist(),
                'r_squared': float(r_squared)
            }
        except Exception as e:
            result = {
                'key': key,
                'fit_success': False,
                'fit_curves': [],
                'total_fit_curve': [],
                'r_squared': 0.0
            }
            
        # Update cache in RAM
        pixel.update(result)
        
        yield result
