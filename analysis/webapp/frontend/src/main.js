import './style.css'
// Note: We use window.Plotly instead of importing it because it's massive.
// We can just include it via CDN in index.html, or we ran `npm install plotly.js-dist-min`.
import Plotly from 'plotly.js-dist-min'

document.querySelector('#app').innerHTML = `
  <div class="left-panel">
      <h2>Hyperspectral Map Grid (Hover to Analyze)</h2>
      <div style="margin-bottom: 10px; display: flex; gap: 10px; align-items: center;">
          <select id="dataset-select" style="padding: 5px; background: #333; color: white; border: 1px solid #555; flex: 1;">
              <option value="">Loading datasets...</option>
          </select>
          <input type="file" id="file-upload" accept=".h5" style="display: none;" />
          <button id="upload-btn" style="padding: 5px 10px; background: #4d4dff; border: none; color: white; cursor: pointer; border-radius: 3px;">Upload .h5</button>
      </div>
      <div class="grid-container" id="grid">
        <!-- Pixels will be injected here -->
      </div>
      <div class="legend">
        <div class="legend-item"><div class="color-box" style="background: #ff4d4d;"></div> Monolayer (18-19.5)</div>
        <div class="legend-item"><div class="color-box" style="background: #4dff4d;"></div> Bilayer (19.5-22)</div>
        <div class="legend-item"><div class="color-box" style="background: #4d4dff;"></div> Bulk (>22)</div>
        <div class="legend-item"><div class="color-box" style="background: #222;"></div> Other</div>
      </div>
      <div class="coords">Pixel: <span id="coord-text">Hover over grid</span></div>
  </div>
  <div class="right-panel">
      <div id="chart"></div>
      <div id="stats-table" class="stats-table">
          Hover over a pixel to see data
      </div>
  </div>
`

const grid = document.getElementById('grid')
const coordText = document.getElementById('coord-text')
const datasetSelect = document.getElementById('dataset-select')
const uploadBtn = document.getElementById('upload-btn')
const fileUpload = document.getElementById('file-upload')

// Initialize empty chart
Plotly.newPlot('chart', [], {
    title: 'Hover over a pixel to view spectra',
    paper_bgcolor: '#1e1e1e',
    plot_bgcolor: '#1e1e1e',
    font: { color: '#e0e0e0' }
})

let currentX = -1
let currentY = -1
let precomputedData = null

function getColorForDelta(delta) {
    if (delta >= 17.5 && delta < 19.5) return '#ff4d4d' // Red
    if (delta >= 19.5 && delta < 22) return '#4dff4d'   // Green
    if (delta >= 22 && delta < 30) return '#4d4dff'     // Blue
    return '#222' // Other / Substrate
}

async function loadDatasets() {
    try {
        const res = await fetch('/datasets')
        const data = await res.json()
        datasetSelect.innerHTML = ''
        if (data.datasets.length === 0) {
            datasetSelect.innerHTML = '<option value="">No datasets available</option>'
            return
        }
        data.datasets.forEach(id => {
            const opt = document.createElement('option')
            opt.value = id
            opt.textContent = id
            datasetSelect.appendChild(opt)
        })
        datasetSelect.value = data.datasets.includes('default') ? 'default' : data.datasets[0]
        initGrid(datasetSelect.value)
    } catch (e) {
        console.error(e)
    }
}

datasetSelect.addEventListener('change', () => {
    if (datasetSelect.value) initGrid(datasetSelect.value)
})

uploadBtn.addEventListener('click', () => fileUpload.click())

fileUpload.addEventListener('change', async (e) => {
    const file = e.target.files[0]
    if (!file) return
    
    uploadBtn.textContent = 'Uploading/Processing...'
    uploadBtn.disabled = true
    
    const formData = new FormData()
    formData.append('file', file)
    
    try {
        const res = await fetch('/upload', { method: 'POST', body: formData })
        if (!res.ok) throw new Error("Upload failed")
        const data = await res.json()
        if (data.duplicate) {
            alert(data.message)
        }
        await loadDatasets()
        datasetSelect.value = data.dataset_id
        initGrid(data.dataset_id)
    } catch (err) {
        alert(err.message)
    } finally {
        uploadBtn.textContent = 'Upload .h5'
        uploadBtn.disabled = false
        fileUpload.value = ''
    }
})

async function initGrid(datasetId) {
    grid.innerHTML = '<div style="color: #ccc; padding: 20px;">Downloading data payload...</div>'
    precomputedData = null
    Plotly.react('chart', [], {
        title: 'Hover over a pixel to view spectra',
        paper_bgcolor: '#1e1e1e',
        plot_bgcolor: '#1e1e1e',
        font: { color: '#e0e0e0' }
    })
    
    try {
        const response = await fetch(`/api/data/${datasetId}`)
        if (!response.ok) throw new Error("Could not load dataset")
        precomputedData = await response.json()
        
        grid.innerHTML = '' // Clear loading text
        
        for (let y = 0; y < 51; y++) {
            for (let x = 0; x < 51; x++) {
                const pixel = document.createElement('div')
                pixel.className = 'grid-pixel'
                
                const h_idx = 50 - x;
                const key = `${h_idx}_${y}`;
                const pixelData = precomputedData.pixels ? precomputedData.pixels[key] : null;
                const delta = pixelData ? pixelData.magic_number : 0;

                pixel.style.backgroundColor = getColorForDelta(delta)
                
                pixel.addEventListener('mouseenter', () => {
                    if (currentX !== x || currentY !== y) {
                        currentX = x
                        currentY = y
                        coordText.innerText = `(${x}, ${y}) - Δ: ${delta.toFixed(2)} cm⁻¹`
                        fetchSpectrum(x, y)
                    }
                })
                
                grid.appendChild(pixel)
            }
        }
    } catch (e) {
        console.error("Failed to load static data:", e)
        grid.innerHTML = '<div style="color: #ff4d4d; padding: 20px;">Failed to load dataset.</div>'
    }
}

function fetchSpectrum(x, y) {
    if (!precomputedData || !precomputedData.pixels) return;
    const h_idx = 50 - x;
    const key = `${h_idx}_${y}`;
    const data = precomputedData.pixels[key];
    if (data) {
        data.rs = precomputedData.global_axes.rs;
        data.x_fit = precomputedData.global_axes.x_fit;
        data.x_si = precomputedData.global_axes.x_si;
        updateChart(data, x, y);
    }
}

function updateChart(data, x, y) {
    const traceData = {
        x: data.rs,
        y: data.norm_spec,
        mode: 'markers',
        type: 'scatter',
        name: 'Data (bg sub)',
        marker: { color: 'rgba(31, 119, 180, 0.5)', size: 4 }
    };

    const fitCurve = {
        x: data.x_fit,
        y: data.y_fit_curve,
        mode: 'lines',
        type: 'scatter',
        name: 'Double Lorentzian Fit',
        line: { color: 'red', width: 2 }
    };

    const l1Curve = {
        x: data.x_fit,
        y: data.L1_curve,
        mode: 'lines',
        type: 'scatter',
        name: 'Peak 1 (E2g) Component',
        line: { color: 'green', dash: 'dash' }
    };

    const l2Curve = {
        x: data.x_fit,
        y: data.L2_curve,
        mode: 'lines',
        type: 'scatter',
        name: 'Peak 2 (A1g) Component',
        line: { color: 'blue', dash: 'dash' }
    };

    const siCurve = {
        x: data.x_si,
        y: data.y_si_curve,
        mode: 'lines',
        type: 'scatter',
        name: 'Si Substrate Peak',
        line: { color: 'orange', width: 2 }
    };

    const statsHtml = `
        <div class="stats-box">
            <b style="color: #4dff4d;">Peak 1 (E2g)</b><br>
            C = ${data.c1.toFixed(2)} cm⁻¹<br>
            FWHM = ${data.fwhm1.toFixed(2)} cm⁻¹<br>
            R² = ${data.r2_mos2 ? data.r2_mos2.toFixed(4) : 'N/A'}
        </div>
        <div class="stats-box">
            <b style="color: #4d4dff;">Peak 2 (A1g)</b><br>
            C = ${data.c2.toFixed(2)} cm⁻¹<br>
            FWHM = ${data.fwhm2.toFixed(2)} cm⁻¹<br>
            R² = ${data.r2_mos2 ? data.r2_mos2.toFixed(4) : 'N/A'}
        </div>
        <div class="stats-box">
            <b style="color: orange;">Si Peak</b><br>
            C = ${data.si_c.toFixed(2)} cm⁻¹<br>
            FWHM = ${data.si_fwhm.toFixed(2)} cm⁻¹<br>
            R² = ${data.r2_si ? data.r2_si.toFixed(4) : 'N/A'}
        </div>
        <div class="stats-box">
            <b>General Stats</b><br>
            Δ = ${data.magic_number.toFixed(2)} cm⁻¹<br>
            Int. Intensity = ${data.integrated_intensity.toExponential(2)}<br>
            Bg = ${data.bg_noise.toFixed(2)} a.u.
        </div>
    `;
    document.getElementById('stats-table').innerHTML = statsHtml;

    const layout = {
        title: `Pixel (${x}, ${y}) Spectra & Fits`,
        paper_bgcolor: '#1e1e1e',
        plot_bgcolor: '#252525',
        font: { color: '#e0e0e0' },
        xaxis: { 
            title: 'Raman Shift (cm⁻¹)',
            gridcolor: '#444',
            range: [360, 540] // focus on fit region + Si peak
        },
        yaxis: { 
            title: 'Normalized Intensity (a.u.)',
            gridcolor: '#444',
            range: [0, Math.max(1.2, Math.max(...data.y_fit_curve) * 1.1)]
        },
        legend: { x: 1, xanchor: 'right', y: 1 },
        margin: { l: 50, r: 20, t: 40, b: 40 }
    };

    Plotly.react('chart', [traceData, fitCurve, l1Curve, l2Curve, siCurve], layout, {responsive: true});
}

// Start app
loadDatasets()
