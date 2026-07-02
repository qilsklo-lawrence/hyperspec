import './style.css'
import Plotly from 'plotly.js-dist-min'

document.querySelector('#app').innerHTML = `
  <div class="left-panel">
      <h2>Hyperspectral Map Grid</h2>
      
      <div style="margin-bottom: 10px; display: flex; flex-direction: column; gap: 5px; width: 100%;">
          <div style="display: flex; gap: 5px; width: 100%;">
              <select id="dataset-select" style="padding: 5px; background: #333; color: white; border: 1px solid #555; flex: 1;">
                  <option value="">Loading datasets...</option>
              </select>
              <button id="rename-btn" style="padding: 5px; background: #555; border: none; color: white; cursor: pointer; border-radius: 3px;">Rename</button>
              <button id="delete-btn" style="padding: 5px; background: #cc0000; border: none; color: white; cursor: pointer; border-radius: 3px;">Delete</button>
          </div>
          <div style="display: flex; gap: 5px; width: 100%;">
              <input type="file" id="file-upload" accept=".h5" style="display: none;" />
              <button id="upload-btn" style="padding: 5px 10px; background: #4d4dff; border: none; color: white; cursor: pointer; border-radius: 3px; flex: 1;">Upload .h5</button>
              <button id="fit-btn" style="padding: 5px 10px; background: #ff4d4d; border: none; color: white; cursor: pointer; border-radius: 3px; display: none;">Fit!</button>
              <button id="toggle-fits-btn" style="padding: 5px 10px; background: #888; border: none; color: white; cursor: pointer; border-radius: 3px; display: none;">Hide Fits</button>
          </div>
          <div id="upload-status" style="font-size: 12px; color: #aaa; text-align: center;"></div>
      </div>
      
      <div class="grid-container" id="grid">
        <!-- Pixels will be injected here -->
      </div>
      
      <div class="legend" id="legend">
          <div class="legend-item" style="display: flex; align-items: center; gap: 5px;">
              Low Int <div style="width: 100px; height: 15px; background: linear-gradient(to right, rgb(0,0,255), rgb(255,0,0));"></div> High Int
          </div>
      </div>
      <div class="coords">Pixel: <span id="coord-text">Hover over grid</span></div>
  </div>
  <div class="right-panel">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
          <div style="display: flex; gap: 10px; align-items: center;">
              <span style="font-size: 14px;">X-Axis Unit:</span>
              <select id="unit-select" style="padding: 3px; background: #333; color: white; border: 1px solid #555;">
                  <option value="rs">Raman Shift (cm⁻¹)</option>
                  <option value="wls">Wavelength (nm)</option>
              </select>
          </div>
          <button id="reset-zoom-btn" style="padding: 5px 10px; background: #444; border: none; color: white; cursor: pointer; border-radius: 3px;">Reset Axes View</button>
      </div>
      <div id="chart" style="flex: 1; width: 100%; min-height: 0;"></div>
      <div id="stats-table" class="stats-table">
          Hover over a pixel to see data
      </div>
  </div>
  
  <div id="info-modal" style="display: none; position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: rgba(0,0,0,0.7); z-index: 1000; justify-content: center; align-items: center;">
      <div style="background: #222; padding: 20px; border-radius: 8px; max-width: 600px; max-height: 80vh; overflow-y: auto; color: #ddd; border: 1px solid #444; position: relative;">
          <button id="close-modal-btn" style="position: absolute; top: 10px; right: 10px; background: transparent; border: none; color: #aaa; cursor: pointer; font-size: 16px;">×</button>
          <h3 style="margin-top: 0;">Model Fitting Engine</h3>
          <p style="font-size: 14px; line-height: 1.5;">
              This fitting process is a <b>Non-Linear Least Squares Regression</b>. The optimizer minimizes the Sum of Squared Residuals (SSR) between the raw data and a parameterized deterministic math model.
          </p>
          <p style="font-size: 14px; line-height: 1.5;">
              <b>The Optimizer:</b> We use the <b>Trust Region Reflective (TRF)</b> algorithm (a bounded Levenberg-Marquardt variant). TRF is a second-order, Hessian-based solver that takes massive, highly accurate steps toward the global minimum, usually converging in &lt;50 iterations.
          </p>
          <p style="font-size: 14px; line-height: 1.5;">
              <b>Heuristic Warm Start:</b> Because second-order solvers can get trapped in local minima if initialized purely at random, the backend uses a heuristic prior (via <code>scipy.signal.find_peaks</code>) to generate initial center and amplitude weights.
          </p>
          <p style="font-size: 14px; line-height: 1.5;">
              <b>The Model Architecture:</b> The engine fits a <b>linear baseline</b> and one or more <b>Pseudo-Voigt</b> profiles. A Pseudo-Voigt is a linear combination of a Lorentzian (ideal for sharp Raman lines) and a Gaussian (ideal for broad, inhomogeneous PL bands).
          </p>
          <ul style="font-size: 14px; line-height: 1.5;">
              <li><b>c (Center)</b>: The physical location of the peak maximum.</li>
              <li><b>w (FWHM)</b>: The Full Width at Half Maximum (how broad the peak is).</li>
              <li><b>η (Eta)</b>: The Lorentzian fraction (0 to 1). If η = 1, it is purely Lorentzian. If η = 0, it is purely Gaussian.</li>
          </ul>
      </div>
  </div>
`

document.getElementById('close-modal-btn').addEventListener('click', () => {
    document.getElementById('info-modal').style.display = 'none';
});

const grid = document.getElementById('grid')
const coordText = document.getElementById('coord-text')
const datasetSelect = document.getElementById('dataset-select')
const uploadBtn = document.getElementById('upload-btn')
const fitBtn = document.getElementById('fit-btn')
const fileUpload = document.getElementById('file-upload')
const uploadStatus = document.getElementById('upload-status')
const unitSelect = document.getElementById('unit-select')
const resetZoomBtn = document.getElementById('reset-zoom-btn')
const renameBtn = document.getElementById('rename-btn')
const toggleFitsBtn = document.getElementById('toggle-fits-btn')

let currentX = -1
let currentY = -1
let isLocked = false
let showFits = true
let precomputedData = null
let pollInterval = null
let currentUnit = 'rs'
let fitEventSource = null;
let pixelElements = {};

Plotly.newPlot('chart', [], {
    title: 'Hover over a pixel to view spectra',
    paper_bgcolor: '#1e1e1e',
    plot_bgcolor: '#1e1e1e',
    font: { color: '#e0e0e0' }
})

function getColorForIntensity(l_max) {
    const max_val = precomputedData && precomputedData.global_axes.max_y ? precomputedData.global_axes.max_y : 1.0;
    const ratio = Math.min(1.0, l_max / max_val);
    const r = Math.floor(255 * ratio);
    const b = Math.floor(255 * (1 - ratio));
    return `rgb(${r}, 0, ${b})`
}

const deleteBtn = document.getElementById('delete-btn')

async function loadDatasets(selectId = null) {
    try {
        const res = await fetch('/datasets')
        const data = await res.json()
        datasetSelect.innerHTML = ''
        if (data.datasets.length === 0) {
            datasetSelect.innerHTML = '<option value="">No datasets available</option>'
            return
        }
        data.datasets.forEach(d => {
            const opt = document.createElement('option')
            opt.value = d.id
            opt.textContent = d.name
            datasetSelect.appendChild(opt)
        })
        if (selectId && data.datasets.find(d => d.id === selectId)) {
            datasetSelect.value = selectId
        } else {
            datasetSelect.value = data.datasets.includes('default') ? 'default' : data.datasets[0].id
        }
        
        if (datasetSelect.value === 'default') {
            deleteBtn.style.display = 'none';
        } else {
            deleteBtn.style.display = 'inline-block';
        }
        
        initGrid(datasetSelect.value)
    } catch (e) {
        console.error(e)
    }
}

datasetSelect.addEventListener('change', () => {
    if (datasetSelect.value) {
        initGrid(datasetSelect.value)
        if (datasetSelect.value === 'default') {
            deleteBtn.style.display = 'none';
        } else {
            deleteBtn.style.display = 'inline-block';
        }
    }
})

renameBtn.addEventListener('click', async () => {
    if (!datasetSelect.value) return;
    const newName = prompt("Enter new name for dataset:");
    if (!newName) return;
    try {
        const res = await fetch(`/rename/${datasetSelect.value}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name: newName})
        })
        if (res.ok) {
            await loadDatasets(datasetSelect.value)
        }
    } catch(e) {
        console.error(e)
    }
})

deleteBtn.addEventListener('click', async () => {
    if (!datasetSelect.value) return;
    if (datasetSelect.value === 'default') {
        alert("Cannot delete the default dataset.");
        return;
    }
    if (!confirm("Are you sure you want to delete this dataset?")) return;
    
    try {
        const res = await fetch(`/dataset/${datasetSelect.value}`, {
            method: 'DELETE'
        })
        if (res.ok) {
            await loadDatasets('default');
        } else {
            const data = await res.json();
            alert(data.error || "Failed to delete");
        }
    } catch(e) {
        console.error(e)
    }
})

uploadBtn.addEventListener('click', () => fileUpload.click())

fileUpload.addEventListener('change', async (e) => {
    const file = e.target.files[0]
    if (!file) return
    
    uploadBtn.textContent = 'Uploading...'
    uploadBtn.disabled = true
    
    const formData = new FormData()
    formData.append('file', file)
    
    try {
        const res = await fetch('/upload', { method: 'POST', body: formData })
        const data = await res.json()
        if (!res.ok) throw new Error(data.error || "Upload failed")
        if (data.duplicate) {
            alert(data.message)
            await loadDatasets(data.dataset_id)
            finishUpload()
        } else {
            pollStatus(data.dataset_id)
        }
    } catch (err) {
        alert(err.message)
        finishUpload()
    }
})

function finishUpload() {
    uploadBtn.textContent = 'Upload .h5'
    uploadBtn.disabled = false
    fileUpload.value = ''
    uploadStatus.innerText = ''
    if (pollInterval) clearInterval(pollInterval)
}

function pollStatus(datasetId) {
    uploadStatus.innerText = 'Initializing...'
    pollInterval = setInterval(async () => {
        try {
            const res = await fetch(`/status/${datasetId}`)
            const data = await res.json()
            if (data.status === 'processing') {
                uploadStatus.innerText = `${data.message} (${data.current} / ${data.total})`
            } else if (data.status === 'done') {
                finishUpload()
                await loadDatasets(datasetId)
            } else if (data.status === 'error') {
                alert("Processing failed: " + data.error)
                finishUpload()
            }
        } catch (e) {
            console.error(e)
        }
    }, 500)
}

const activeFitStreams = {};

fitBtn.addEventListener('click', async () => {
    const dsId = datasetSelect.value;
    const dsName = datasetSelect.options[datasetSelect.selectedIndex].text;
    
    if (activeFitStreams[dsId]) return; // Already fitting this one
    
    fitBtn.disabled = true;
    fitBtn.textContent = "Fitting...";
    
    activeFitStreams[dsId] = new EventSource(`/fit_stream/${dsId}`);
    let count = 0;
    
    activeFitStreams[dsId].onmessage = (e) => {
        const data = JSON.parse(e.data);
        const isCurrentDataset = (datasetSelect.value === dsId);
        
        if (data.done) {
            activeFitStreams[dsId].close();
            delete activeFitStreams[dsId];
            
            if (isCurrentDataset) {
                fitBtn.disabled = false;
                fitBtn.textContent = "Fit!";
                uploadStatus.innerText = `Fitting complete for ${dsName}! ${count} pixels processed.`;
            }
            return;
        }
        if (data.error) {
            activeFitStreams[dsId].close();
            delete activeFitStreams[dsId];
            if (isCurrentDataset) {
                alert("Fit error: " + data.error);
                fitBtn.disabled = false;
                fitBtn.textContent = "Fit!";
            }
            return;
        }
        
        count++;
        
        if (isCurrentDataset) {
            uploadStatus.innerText = `Fitting ${dsName}: ${count} pixels...`;
            
            // Update local RAM cache
            if (precomputedData && precomputedData.pixels[data.key]) {
                precomputedData.pixels[data.key].fit_success = data.fit_success;
                precomputedData.pixels[data.key].fit_curves = data.fit_curves;
                precomputedData.pixels[data.key].total_fit_curve = data.total_fit_curve;
                precomputedData.pixels[data.key].r_squared = data.r_squared;
                
                // Flash animation for the pixel
                const pixelEl = pixelElements[data.key];
                if (pixelEl) {
                    const oldBg = pixelEl.style.backgroundColor;
                    pixelEl.style.backgroundColor = 'white';
                    setTimeout(() => { pixelEl.style.backgroundColor = oldBg; }, 100);
                }
                
                // If we are currently hovering over this pixel, update chart instantly
                const width = precomputedData.global_axes.width;
                const parts = data.key.split('_');
                const x = width - 1 - parseInt(parts[0]);
                const y = parseInt(parts[1]);
                if (currentX === x && currentY === y) {
                    updateChart(x, y, precomputedData.pixels[data.key]);
                }
            }
        }
    };
    
    activeFitStreams[dsId].onerror = (e) => {
        console.error("SSE Error", e);
        activeFitStreams[dsId].close();
        delete activeFitStreams[dsId];
        
        if (datasetSelect.value === dsId) {
            fitBtn.disabled = false;
            fitBtn.textContent = "Fit!";
            uploadStatus.innerText = "Fitting disconnected.";
        }
    };
});

toggleFitsBtn.addEventListener('click', () => {
    showFits = !showFits;
    toggleFitsBtn.textContent = showFits ? "Hide Fits" : "Show Fits";
    if (currentX !== -1 && currentY !== -1) {
        fetchSpectrum(currentX, currentY);
    }
});

async function initGrid(datasetId) {
    grid.innerHTML = '<div style="color: #ccc; padding: 20px;">Downloading data payload...</div>'
    precomputedData = null
    Plotly.react('chart', [], {
        title: 'Hover over a pixel to view spectra',
        paper_bgcolor: '#1e1e1e',
        plot_bgcolor: '#1e1e1e',
        font: { color: '#e0e0e0' }
    })
    document.getElementById('stats-table').innerHTML = 'Hover over a pixel to see data'
    currentX = -1
    currentY = -1
    pixelElements = {};
    
    try {
        const response = await fetch(`/api/data/${datasetId}`)
        if (!response.ok) throw new Error("Could not load dataset")
        precomputedData = await response.json()
        
        grid.innerHTML = '' // Clear loading text
        
        const width = precomputedData.global_axes.width || 51;
        const height = precomputedData.global_axes.height || 51;
        
        let heatmap_max = 1.0;
        for (const key in precomputedData.pixels) {
            if (precomputedData.pixels[key].l_max > heatmap_max) {
                heatmap_max = precomputedData.pixels[key].l_max;
            }
        }
        
        grid.style.gridTemplateColumns = `repeat(${width}, 10px)`;
        grid.style.gridTemplateRows = `repeat(${height}, 10px)`;
        grid.style.width = `${width * 10}px`;
        grid.style.height = `${height * 10}px`;
        
        // Add double click listener to the grid to unlock if clicking anywhere in the plane
        grid.addEventListener('dblclick', () => {
            if (isLocked) {
                isLocked = false;
                coordText.innerText = `(Unlocked) Pixel ${currentX}, ${currentY}`;
            }
        });
        
        for (let y = 0; y < height; y++) {
            for (let x = 0; x < width; x++) {
                const pixel = document.createElement('div')
                pixel.className = 'grid-pixel'
                
                const h_idx = (width - 1) - x;
                const key = `${h_idx}_${y}`;
                const pixelData = precomputedData.pixels ? precomputedData.pixels[key] : null;
                const l_max = pixelData && pixelData.l_max ? pixelData.l_max : 0;
                const num_peaks = pixelData ? pixelData.num_peaks : 0;

                // getColorForIntensity now uses heatmap_max instead of overwriting global_axes.max_y
                const ratio = Math.min(1.0, l_max / heatmap_max);
                const r = Math.floor(255 * ratio);
                const b = Math.floor(255 * (1 - ratio));
                pixel.style.backgroundColor = `rgb(${r}, 0, ${b})`;
                
                pixelElements[key] = pixel;
                
                pixel.addEventListener('mouseenter', () => {
                    if (!isLocked && (currentX !== x || currentY !== y)) {
                        currentX = x
                        currentY = y
                        coordText.innerText = `(${x}, ${y}) - Recommended Peaks: ${num_peaks}`
                        fetchSpectrum(x, y)
                    }
                })
                
                pixel.addEventListener('dblclick', (e) => {
                    e.stopPropagation(); // prevent grid dblclick from firing immediately
                    if (!isLocked) {
                        isLocked = true;
                        currentX = x;
                        currentY = y;
                        coordText.innerText = `(LOCKED) (${x}, ${y}) - Recommended Peaks: ${num_peaks}`
                        fetchSpectrum(x, y);
                    } else {
                        isLocked = false;
                        coordText.innerText = `(${x}, ${y}) - Recommended Peaks: ${num_peaks}`
                    }
                });
                
                grid.appendChild(pixel)
            }
        }
        
        fitBtn.style.display = 'inline-block';
        toggleFitsBtn.style.display = 'inline-block';
        
        resetZoomBtn.onclick = () => {
            if (currentX !== -1 && currentY !== -1) {
                updateChart(precomputedData.pixels[`${(width - 1) - currentX}_${currentY}`], currentX, currentY, true)
            }
        }
        
    } catch (e) {
        console.error("Failed to load data:", e)
        grid.innerHTML = '<div style="color: #ff4d4d; padding: 20px;">Failed to load dataset.</div>'
        fitBtn.style.display = 'none';
        toggleFitsBtn.style.display = 'none';
    }
}

unitSelect.addEventListener('change', () => {
    currentUnit = unitSelect.value;
    if (currentX !== -1 && currentY !== -1 && precomputedData) {
        const width = precomputedData.global_axes.width;
        // When changing units, force relayout so it rescales to new unit ranges
        updateChart(precomputedData.pixels[`${(width - 1) - currentX}_${currentY}`], currentX, currentY, true)
    }
})

function fetchSpectrum(x, y) {
    if (!precomputedData || !precomputedData.pixels) return;
    const width = precomputedData.global_axes.width || 51;
    const h_idx = (width - 1) - x;
    const key = `${h_idx}_${y}`;
    const data = precomputedData.pixels[key];
    if (data) {
        updateChart(data, x, y, false);
    }
}

function updateChart(data, x, y, forceRelayout) {
    const xAxisData = currentUnit === 'rs' ? precomputedData.global_axes.rs : precomputedData.global_axes.wls;
    
    const traces = [];
    
    traces.push({
        x: xAxisData,
        y: data.norm_spec,
        mode: 'markers',
        type: 'scatter',
        name: 'Data (bg sub)',
        marker: { color: 'rgba(31, 119, 180, 0.5)', size: 4 }
    });

    if (showFits && data.fit_success && data.total_fit_curve.length > 0) {
        traces.push({
            x: xAxisData,
            y: data.total_fit_curve,
            mode: 'lines',
            type: 'scatter',
            name: 'Total Pseudo-Voigt Fit',
            line: { color: 'red', width: 2 }
        });
        
        data.fit_curves.forEach((c, idx) => {
            traces.push({
                x: xAxisData,
                y: c.curve,
                mode: 'lines',
                type: 'scatter',
                name: `Peak ${idx+1}`,
                line: { dash: 'dash' }
            });
        });
    }

    let statsHtml = `
        <div class="stats-box">
            <b>Pixel (${x}, ${y})</b><br>
            Recommended Peaks: ${data.num_peaks}<br>
            Total Int = ${data.integrated_intensity.toExponential(2)}<br>
            Bg Noise = ${data.bg_noise.toFixed(2)} a.u.
        </div>
    `;
    
    if (data.fit_success) {
        const r2 = data.r_squared !== undefined ? data.r_squared.toFixed(4) : "N/A";
        statsHtml += `<div class="stats-box" style="grid-column: span 1; overflow-y: auto; max-height: 100px;">
            <b style="display: flex; justify-content: space-between; align-items: center;">
                Pseudo-Voigt Fit Params
                <button id="info-btn" style="background: transparent; border: 1px solid #888; color: #888; border-radius: 50%; width: 18px; height: 18px; font-size: 10px; cursor: pointer;">?</button>
            </b>
            R² = ${r2}<br>`;
        data.fit_curves.forEach((c, idx) => {
            statsHtml += `P${idx+1}: c=${c.c.toFixed(1)}, w=${c.w.toFixed(1)}, η=${c.eta.toFixed(2)}<br>`;
        });
        statsHtml += `</div>`;
    }

    document.getElementById('stats-table').innerHTML = statsHtml;

    if (data.fit_success) {
        document.getElementById('info-btn').addEventListener('click', () => {
            const modal = document.getElementById('info-modal');
            modal.style.display = 'flex';
        });
    }

    const xTitle = currentUnit === 'rs' ? 'Raman Shift (cm⁻¹)' : 'Wavelength (nm)';
    
    // Determine bounds dynamically for reset
    let xRange = null;
    let yRange = null;
    if (forceRelayout) {
        const minX = Math.min(...xAxisData);
        const maxX = Math.max(...xAxisData);
        xRange = [minX, maxX];
        yRange = [precomputedData.global_axes.min_y, precomputedData.global_axes.max_y * 1.05];
        if (yRange[1] < 1.2) {
            yRange[1] = 1.05; 
        }
    }

    const layout = {
        title: `Pixel (${x}, ${y}) Spectrum`,
        uirevision: currentUnit, 
        paper_bgcolor: '#1e1e1e',
        plot_bgcolor: '#252525',
        font: { color: '#e0e0e0' },
        xaxis: { 
            title: xTitle,
            gridcolor: '#444'
        },
        yaxis: { 
            title: 'Normalized Intensity (a.u.)',
            gridcolor: '#444'
        },
        legend: { x: 1, xanchor: 'right', y: 1 },
        margin: { l: 50, r: 20, t: 40, b: 40 }
    };
    
    if (xRange && yRange) {
        layout.xaxis.range = xRange;
        layout.yaxis.range = yRange;
        layout.uirevision = forceRelayout ? Math.random() : currentUnit;
    }

    Plotly.react('chart', traces, layout, {responsive: true});
}

// Start app
loadDatasets()
