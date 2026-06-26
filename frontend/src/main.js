import './style.css'
// Note: We use window.Plotly instead of importing it because it's massive.
// We can just include it via CDN in index.html, or we ran `npm install plotly.js-dist-min`.
import Plotly from 'plotly.js-dist-min'

document.querySelector('#app').innerHTML = `
  <div class="left-panel">
      <h2>Hyperspectral Map Grid (Hover to Analyze)</h2>
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
      <h2>Spectra Details Page</h2>
      <div id="chart"></div>
  </div>
`

const grid = document.getElementById('grid')
const coordText = document.getElementById('coord-text')

// Initialize empty chart
Plotly.newPlot('chart', [], {
    title: 'Hover over a pixel to view spectra',
    paper_bgcolor: '#1e1e1e',
    plot_bgcolor: '#1e1e1e',
    font: { color: '#e0e0e0' }
})

let currentX = -1
let currentY = -1

function getColorForDelta(delta) {
    if (delta >= 17.5 && delta < 19.5) return '#ff4d4d' // Red
    if (delta >= 19.5 && delta < 22) return '#4dff4d'   // Green
    if (delta >= 22 && delta < 30) return '#4d4dff'     // Blue
    return '#222' // Other / Substrate
}

async function initGrid() {
    try {
        const response = await fetch('/data/all_deltas')
        const data = await response.json()
        const deltas = data.deltas // 51x51 array (y, x)

        for (let y = 0; y < 51; y++) {
            for (let x = 0; x < 51; x++) {
                const pixel = document.createElement('div')
                pixel.className = 'grid-pixel'
                
                const delta = deltas[y][x]
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
        console.error("Failed to load deltas", e)
    }
}

async function fetchSpectrum(x, y) {
    try {
        const response = await fetch(`/data/${x}/${y}`);
        if (!response.ok) return;
        const data = await response.json();
        updateChart(data, x, y);
    } catch (error) {
        console.error("Error fetching spectrum data:", error);
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

    const annotText = 
        `<b>Peak 1 (E2g):</b><br>` +
        `  C = ${data.c1.toFixed(2)} cm<sup>-1</sup><br>` +
        `  FWHM = ${data.fwhm1.toFixed(2)} cm<sup>-1</sup><br><br>` +
        `<b>Peak 2 (A1g):</b><br>` +
        `  C = ${data.c2.toFixed(2)} cm<sup>-1</sup><br>` +
        `  FWHM = ${data.fwhm2.toFixed(2)} cm<sup>-1</sup><br><br>` +
        `<b>Integrated Intensity:</b> ${data.integrated_intensity.toExponential(2)}<br>` +
        `<b>Δ:</b> ${data.magic_number.toFixed(2)} cm<sup>-1</sup><br>` +
        `<b>Bg:</b> ${data.bg_noise.toFixed(2)} a.u.`;

    const layout = {
        title: `Pixel (${x}, ${y}) Spectra & Fits`,
        paper_bgcolor: '#1e1e1e',
        plot_bgcolor: '#252525',
        font: { color: '#e0e0e0' },
        xaxis: { 
            title: 'Raman Shift (cm⁻¹)',
            gridcolor: '#444',
            range: [360, 430] // focus on fit region
        },
        yaxis: { 
            title: 'Normalized Intensity (a.u.)',
            gridcolor: '#444',
            range: [0, Math.max(1.2, Math.max(...data.y_fit_curve) * 1.1)]
        },
        legend: { x: 1, xanchor: 'right', y: 1 },
        annotations: [{
            x: 0.05,
            y: 0.95,
            xref: 'paper',
            yref: 'paper',
            text: annotText,
            showarrow: false,
            bgcolor: 'rgba(30, 30, 30, 0.8)',
            bordercolor: '#555',
            borderwidth: 1,
            borderpad: 8,
            align: 'left',
            font: { size: 12, family: 'monospace' }
        }],
        margin: { l: 60, r: 20, t: 60, b: 60 }
    };

    Plotly.react('chart', [traceData, fitCurve, l1Curve, l2Curve], layout, {responsive: true});
}

// Start app
initGrid()
