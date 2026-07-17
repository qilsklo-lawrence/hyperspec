import './style.css'
import Plotly from 'plotly.js-dist-min'

document.querySelector('#app').innerHTML = `
  <div class="left-panel">
      <h2>Hyperspectral Map Grid</h2>
      <div id="identity-bar" style="margin-bottom: 8px; font-size: 12px; color: #aaa; display: flex; gap: 8px; align-items: center; flex-wrap: wrap;"></div>

      <div style="margin-bottom: 10px; display: flex; flex-direction: column; gap: 5px; width: 100%;">
          <div style="display: flex; gap: 5px; width: 100%;">
              <select id="dataset-select" style="padding: 5px; background: #333; color: white; border: 1px solid #555; flex: 1;">
                  <option value="">Loading datasets...</option>
              </select>
              <button id="rename-btn" style="padding: 5px; background: #555; border: none; color: white; cursor: pointer; border-radius: 3px;">Rename</button>
              <button id="delete-btn" style="padding: 5px; background: #cc0000; border: none; color: white; cursor: pointer; border-radius: 3px;">Delete</button>
          </div>
          <div style="display: flex; gap: 5px; width: 100%;">
              <input type="file" id="file-upload" accept=".h5,.mat" style="display: none;" />
              <button id="upload-btn" style="padding: 5px 10px; background: #4d4dff; border: none; color: white; cursor: pointer; border-radius: 3px; flex: 1;">Upload Data</button>
              <select id="fit-mode-select" style="padding: 5px; background: #333; color: white; border: 1px solid #555; border-radius: 3px; display: none;" title="Line shape used for every peak in the whole image">
                  <option value="pseudo_voigt">Pseudo-Voigt (free η)</option>
                  <option value="lorentzian">Lorentzian (η=1)</option>
                  <option value="gaussian">Gaussian (η=0)</option>
              </select>
              <button id="fit-btn" style="padding: 5px 10px; background: #ff4d4d; border: none; color: white; cursor: pointer; border-radius: 3px; display: none;">Fit!</button>
              <button id="reset-fits-btn" style="padding: 5px 10px; background: #ff8c00; border: none; color: white; cursor: pointer; border-radius: 3px; display: none;">Reset Fits</button>
              <button id="toggle-fits-btn" style="padding: 5px 10px; background: #888; border: none; color: white; cursor: pointer; border-radius: 3px; display: none;">Hide Fits</button>
              <button id="export-png-btn" style="padding: 5px 10px; background: #009933; border: none; color: white; cursor: pointer; border-radius: 3px;">Export PNG</button>
              <button id="detect-flake-btn" style="padding: 5px 10px; background: #8a2be2; border: none; color: white; cursor: pointer; border-radius: 3px;">Outline Flake</button>
              <button id="draw-flake-btn" style="padding: 5px 10px; background: #b8860b; border: none; color: white; cursor: pointer; border-radius: 3px;" title="Click to place polygon vertices; click the first vertex or double-click to close; Esc cancels">Draw Flake</button>
          </div>
          <div id="upload-status" style="font-size: 12px; color: #aaa; text-align: center;"></div>
      </div>
      
      <div style="margin-bottom: 10px; display: flex; flex-direction: column; gap: 5px; width: 100%; border: 1px solid #444; padding: 10px; border-radius: 4px; box-sizing: border-box;">
          <div style="display: flex; gap: 5px; width: 100%; align-items: center;">
              <label style="color: #ccc; font-size: 12px; width: 80px;">Map Type:</label>
              <select id="map-type-select" style="padding: 3px; background: #333; color: white; border: 1px solid #555; flex: 1;">
                  <option value="integrated_intensity">Integrated Intensity</option>
                  <option value="l_max">Max Intensity</option>
                  <option value="sharpness">Sharpness</option>
                  <option value="peak_pos">Peak Position (fit)</option>
                  <option value="peak_fwhm">Peak FWHM (fit)</option>
              </select>
          </div>
          <div id="int-range-row" style="display: flex; gap: 5px; width: 100%; align-items: center;">
              <label style="color: #ccc; font-size: 12px; width: 80px;" title="Only spectrum values inside this x-range are summed for the Integrated Intensity map">Int. Range:</label>
              <input type="number" id="int-range-min" placeholder="min" step="any" style="width: 70px; background: #333; color: #fff; border: 1px solid #555; padding: 2px;">
              <span style="color: #888;">–</span>
              <input type="number" id="int-range-max" placeholder="max" step="any" style="width: 70px; background: #333; color: #fff; border: 1px solid #555; padding: 2px;">
              <span id="int-range-unit" style="color: #ccc; font-size: 12px;">cm⁻¹</span>
              <button id="int-range-reset" style="padding: 2px 8px; background: #555; border: none; color: white; cursor: pointer; border-radius: 3px; font-size: 12px;">Full</button>
          </div>
          <div style="display: flex; gap: 5px; width: 100%; align-items: center;">
              <label style="color: #ccc; font-size: 12px; width: 80px;">Min %:</label>
              <input type="range" id="contrast-min" min="0" max="100" step="0.1" value="0" style="flex: 1;">
              <span id="contrast-min-val" style="color: #ccc; font-size: 12px; width: 40px; cursor: text;" title="Double click to edit">0%</span>
          </div>
          <div style="display: flex; gap: 5px; width: 100%; align-items: center;">
              <label style="color: #ccc; font-size: 12px; width: 80px;">Max %:</label>
              <input type="range" id="contrast-max" min="0" max="100" step="0.1" value="100" style="flex: 1;">
              <span id="contrast-max-val" style="color: #ccc; font-size: 12px; width: 40px; cursor: text;" title="Double click to edit">100%</span>
          </div>
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
          <div style="display: flex; gap: 5px; align-items: center;">
              <button id="show-flake-avg-btn" style="padding: 5px 10px; background: #8a2be2; border: none; color: white; cursor: pointer; border-radius: 3px; display: none;">Show Flake Avg</button>
              <button id="export-chart-btn" style="padding: 5px 10px; background: #009933; border: none; color: white; cursor: pointer; border-radius: 3px;">Export Chart PNG</button>
              <button id="reset-zoom-btn" style="padding: 5px 10px; background: #444; border: none; color: white; cursor: pointer; border-radius: 3px;">Reset Axes View</button>
          </div>
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
const resetFitsBtn = document.getElementById('reset-fits-btn')
const fileUpload = document.getElementById('file-upload')
const uploadStatus = document.getElementById('upload-status')
const unitSelect = document.getElementById('unit-select')
const resetZoomBtn = document.getElementById('reset-zoom-btn')
const renameBtn = document.getElementById('rename-btn')
const toggleFitsBtn = document.getElementById('toggle-fits-btn')
const exportPngBtn = document.getElementById('export-png-btn')
const detectFlakeBtn = document.getElementById('detect-flake-btn')
const showFlakeAvgBtn = document.getElementById('show-flake-avg-btn')
const exportChartBtn = document.getElementById('export-chart-btn')
const mapTypeSelect = document.getElementById('map-type-select')
const fitModeSelect = document.getElementById('fit-mode-select')
const drawFlakeBtn = document.getElementById('draw-flake-btn')
const intRangeMin = document.getElementById('int-range-min')
const intRangeMax = document.getElementById('int-range-max')
const intRangeUnit = document.getElementById('int-range-unit')
const intRangeReset = document.getElementById('int-range-reset')
const contrastMin = document.getElementById('contrast-min')
const contrastMax = document.getElementById('contrast-max')
const contrastMinVal = document.getElementById('contrast-min-val')
const contrastMaxVal = document.getElementById('contrast-max-val')

exportPngBtn.addEventListener('click', () => {
    if (!precomputedData || !precomputedData.pixels) return;
    
    const width = precomputedData.global_axes.width || 51;
    const height = precomputedData.global_axes.height || 51;
    
    const cellSize = 10;
    
    const canvas = document.createElement('canvas');
    canvas.width = width * cellSize;
    canvas.height = height * cellSize;
    const ctx = canvas.getContext('2d');
    
    for (let y = 0; y < height; y++) {
        for (let x = 0; x < width; x++) {
            const h_idx = (width - 1) - x;
            const key = `${h_idx}_${y}`;
            const pixelEl = pixelElements[key];
            if (pixelEl) {
                ctx.fillStyle = pixelEl.style.backgroundColor || 'black';
                ctx.fillRect(x * cellSize, y * cellSize, cellSize, cellSize);
            }
        }
    }
    
    const dataUrl = canvas.toDataURL('image/png');
    const a = document.createElement('a');
    a.href = dataUrl;
    a.download = `hyperspectral_map_${datasetSelect.value}_${mapTypeSelect.value}.png`;
    a.click();
});

exportChartBtn.addEventListener('click', () => {
    Plotly.downloadImage('chart', {
        format: 'png',
        filename: `spectrum_chart_${datasetSelect.value}`,
        width: 800,
        height: 600
    });
});

let currentFlakeSvg = null;
let flakeAvgData = null;

showFlakeAvgBtn.addEventListener('click', () => {
    if (!flakeAvgData || !flakeAvgData.mean || flakeAvgData.mean.length === 0) return;
    
    isLocked = true;
    currentX = -1;
    currentY = -1;
    coordText.innerText = `(LOCKED) Flake Average Spectrum`;
    
    const xAxisData = currentUnit === 'rs' ? precomputedData.global_axes.rs : precomputedData.global_axes.wls;
    const xTitle = currentUnit === 'rs' ? 'Raman Shift (cm⁻¹)' : 'Wavelength (nm)';
    
    const mean = flakeAvgData.mean;
    const std = flakeAvgData.std;
    
    const upper = mean.map((val, i) => val + std[i]);
    const lower = mean.map((val, i) => val - std[i]);
    
    const traces = [
        {
            x: xAxisData,
            y: mean,
            mode: 'lines',
            type: 'scatter',
            name: 'Flake Mean',
            line: { color: 'rgba(31, 119, 180, 1)' }
        },
        {
            x: xAxisData,
            y: upper,
            mode: 'lines',
            type: 'scatter',
            name: '+1 Std Dev',
            line: { width: 0 },
            showlegend: false
        },
        {
            x: xAxisData,
            y: lower,
            mode: 'lines',
            type: 'scatter',
            name: '-1 Std Dev',
            fill: 'tonexty',
            fillcolor: 'rgba(31, 119, 180, 0.2)',
            line: { width: 0 },
            showlegend: false
        }
    ];
    
    const layout = {
        title: `Flake Average Spectrum`,
        uirevision: Math.random(), 
        paper_bgcolor: '#1e1e1e',
        plot_bgcolor: '#252525',
        font: { color: '#e0e0e0' },
        xaxis: { 
            title: { text: xTitle, standoff: 15 },
            gridcolor: '#444',
            automargin: true
        },
        yaxis: { 
            title: { text: 'Normalized Intensity (a.u.)', standoff: 15 },
            gridcolor: '#444',
            automargin: true
        },
        legend: { x: 1, xanchor: 'right', y: 1 },
        margin: { l: 60, r: 20, t: 40, b: 60 }
    };
    
    const regionDesc = flakeAvgData.source === 'manual'
        ? `the hand-drawn polygon (${flakeAvgData.n} pixels)`
        : 'the detected flake contour';
    document.getElementById('stats-table').innerHTML = `
        <div class="stats-box" style="width: 100%;">
            <b>Flake Average</b><br>
            Showing average spectrum over ${regionDesc} with ±1 standard deviation shaded.<br>
            <i style="color: #888; font-size: 11px;">You can export this plot using the Export Chart PNG button.</i>
        </div>
    `;
    
    Plotly.react('chart', traces, layout, {responsive: true});
});

detectFlakeBtn.addEventListener('click', async () => {
    if (!datasetSelect.value) return;
    
    if (currentFlakeSvg) {
        currentFlakeSvg.remove();
        currentFlakeSvg = null;
    }
    
    detectFlakeBtn.textContent = 'Detecting...';
    detectFlakeBtn.disabled = true;
    
    try {
        const res = await fetch(`/detect_flake/${datasetSelect.value}?map_type=${mapTypeSelect.value}`);
        if (!res.ok) {
            const err = await res.json();
            alert("Error: " + err.error);
        } else {
            const data = await res.json();
            const points = data.points;
            
            const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
            svg.style.position = 'absolute';
            svg.style.top = '0';
            svg.style.left = '0';
            svg.style.width = '100%';
            svg.style.height = '100%';
            svg.style.pointerEvents = 'none';
            svg.style.zIndex = '10';
            
            const cellSize = gridCellSize;

            autoContourCellPts = points.map(p => ({ x: p.x + 0.5, y: p.y + 0.5 }));

            let pointsStr = points.map(p => {
                // OpenCV x is col, y is row. Our grid draws left-to-right, top-to-bottom.
                // However, in updateHeatmap, the x index shown in UI is (width - 1 - original_x).
                // Wait! The grid in updateHeatmap has keys: h_idx = (width - 1) - x.
                // When we reconstructed the grid in python: 
                // key = f"{h_idx}_{y}". grid[y, x] = dataset['pixels'][key].
                // This means the grid array in python matches the 'x' index of the grid visually.
                // Let's just scale by cellSize. 
                // Since points are pixel vertices, adding 0.5 * cellSize shifts to center of pixel.
                return `${p.x * cellSize + cellSize/2},${p.y * cellSize + cellSize/2}`;
            }).join(' ');
            
            const polygon = document.createElementNS("http://www.w3.org/2000/svg", "polygon");
            polygon.setAttribute("points", pointsStr);
            polygon.setAttribute("fill", "none");
            polygon.setAttribute("stroke", "#00ffff");
            polygon.setAttribute("stroke-width", "3");
            polygon.setAttribute("stroke-dasharray", "5 5");
            
            svg.appendChild(polygon);
            
            grid.style.position = 'relative';
            grid.appendChild(svg);
            currentFlakeSvg = svg;
            
            if (data.mean_spec && data.mean_spec.length > 0) {
                flakeAvgData = {
                    mean: data.mean_spec,
                    std: data.std_spec,
                    n: null,
                    source: 'auto'
                };
                showFlakeAvgBtn.style.display = 'inline-block';
            } else {
                flakeAvgData = null;
                showFlakeAvgBtn.style.display = 'none';
            }
        }
    } catch (e) {
        console.error(e);
        alert("Failed to detect flake");
    }
    
    detectFlakeBtn.textContent = 'Outline Flake';
    detectFlakeBtn.disabled = false;
});

// ---- Manual flake polygon drawing ----

function makeGridOverlay() {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.style.position = 'absolute';
    svg.style.top = '0';
    svg.style.left = '0';
    svg.style.width = '100%';
    svg.style.height = '100%';
    svg.style.pointerEvents = 'none';
    svg.style.zIndex = '11';
    grid.style.position = 'relative';
    grid.appendChild(svg);
    return svg;
}

function gridEventToCell(e) {
    const rect = grid.getBoundingClientRect();
    return { x: (e.clientX - rect.left) / gridCellSize, y: (e.clientY - rect.top) / gridCellSize };
}

// Snap priority: auto-detected contour vertex (trace-and-correct), then
// pixel corner, else the raw cursor position.
function snapCellPoint(p) {
    if (autoContourCellPts) {
        let best = null, bestD = 1.0;
        for (const q of autoContourCellPts) {
            const d = Math.hypot(p.x - q.x, p.y - q.y);
            if (d < bestD) { bestD = d; best = q; }
        }
        if (best) return { x: best.x, y: best.y };
    }
    const rx = Math.round(p.x), ry = Math.round(p.y);
    if (Math.hypot(p.x - rx, p.y - ry) < 0.35) return { x: rx, y: ry };
    return p;
}

function pointInPoly(px, py, verts) {
    let inside = false;
    for (let i = 0, j = verts.length - 1; i < verts.length; j = i++) {
        const xi = verts[i].x, yi = verts[i].y;
        const xj = verts[j].x, yj = verts[j].y;
        if (((yi > py) !== (yj > py)) && (px < (xj - xi) * (py - yi) / (yj - yi) + xi)) {
            inside = !inside;
        }
    }
    return inside;
}

function startDraw() {
    if (manualFlakeSvg) { manualFlakeSvg.remove(); manualFlakeSvg = null; }
    drawMode = true;
    drawVertices = [];
    drawFlakeBtn.textContent = 'Cancel Draw';
    grid.style.cursor = 'crosshair';

    drawSvg = makeGridOverlay();
    drawPolyline = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
    drawPolyline.setAttribute("fill", "none");
    drawPolyline.setAttribute("stroke", "#ffd700");
    drawPolyline.setAttribute("stroke-width", "2");
    drawPreviewLine = document.createElementNS("http://www.w3.org/2000/svg", "line");
    drawPreviewLine.setAttribute("stroke", "#ffd700");
    drawPreviewLine.setAttribute("stroke-width", "1");
    drawPreviewLine.setAttribute("stroke-dasharray", "4 3");
    drawSnapDot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    drawSnapDot.setAttribute("r", "3");
    drawSnapDot.setAttribute("fill", "#ffd700");
    drawSvg.appendChild(drawPolyline);
    drawSvg.appendChild(drawPreviewLine);
    drawSvg.appendChild(drawSnapDot);
}

function cancelDraw() {
    drawMode = false;
    drawVertices = [];
    if (drawSvg) { drawSvg.remove(); drawSvg = null; }
    drawFlakeBtn.textContent = 'Draw Flake';
    grid.style.cursor = '';
}

function finishDraw() {
    if (!precomputedData || drawVertices.length < 3) { cancelDraw(); return; }
    const verts = drawVertices.slice();
    lastDrawFinish = Date.now();

    const width = precomputedData.global_axes.width || 51;
    const height = precomputedData.global_axes.height || 51;
    const specs = [];
    for (let y = 0; y < height; y++) {
        for (let x = 0; x < width; x++) {
            if (!pointInPoly(x + 0.5, y + 0.5, verts)) continue;
            const key = `${(width - 1) - x}_${y}`;
            const d = precomputedData.pixels[key];
            if (d && d.norm_spec) specs.push(d.norm_spec);
        }
    }

    if (specs.length === 0) {
        alert("No pixels inside the polygon.");
        cancelDraw();
        return;
    }

    const L = specs[0].length;
    const mean = new Array(L).fill(0);
    const std = new Array(L).fill(0);
    for (const s of specs) for (let i = 0; i < L; i++) mean[i] += s[i];
    for (let i = 0; i < L; i++) mean[i] /= specs.length;
    for (const s of specs) for (let i = 0; i < L; i++) std[i] += (s[i] - mean[i]) ** 2;
    for (let i = 0; i < L; i++) std[i] = Math.sqrt(std[i] / specs.length);

    flakeAvgData = { mean, std, n: specs.length, source: 'manual' };

    // Freeze the overlay as the final closed polygon
    drawPolyline.remove();
    drawPreviewLine.remove();
    drawSnapDot.remove();
    const polygon = document.createElementNS("http://www.w3.org/2000/svg", "polygon");
    polygon.setAttribute("points", verts.map(v => `${v.x * gridCellSize},${v.y * gridCellSize}`).join(' '));
    polygon.setAttribute("fill", "rgba(255, 215, 0, 0.08)");
    polygon.setAttribute("stroke", "#ffd700");
    polygon.setAttribute("stroke-width", "2");
    drawSvg.appendChild(polygon);
    manualFlakeSvg = drawSvg;
    drawSvg = null;
    drawMode = false;
    drawVertices = [];
    drawFlakeBtn.textContent = 'Draw Flake';
    grid.style.cursor = '';

    showFlakeAvgBtn.style.display = 'inline-block';
    showFlakeAvgBtn.click();
}

drawFlakeBtn.addEventListener('click', () => {
    if (drawMode) { cancelDraw(); return; }
    if (!precomputedData) return;
    startDraw();
});

grid.addEventListener('click', (e) => {
    if (!drawMode) return;
    const raw = gridEventToCell(e);
    if (drawVertices.length >= 3) {
        const f = drawVertices[0];
        if (Math.hypot(raw.x - f.x, raw.y - f.y) < 0.75) { finishDraw(); return; }
    }
    const p = snapCellPoint(raw);
    const last = drawVertices[drawVertices.length - 1];
    if (last && Math.hypot(p.x - last.x, p.y - last.y) < 0.2) return; // dblclick double-fires click
    drawVertices.push(p);
    drawPolyline.setAttribute('points', drawVertices.map(v => `${v.x * gridCellSize},${v.y * gridCellSize}`).join(' '));
});

grid.addEventListener('mousemove', (e) => {
    if (!drawMode || !drawSvg) return;
    const p = snapCellPoint(gridEventToCell(e));
    drawSnapDot.setAttribute('cx', p.x * gridCellSize);
    drawSnapDot.setAttribute('cy', p.y * gridCellSize);
    if (drawVertices.length > 0) {
        const last = drawVertices[drawVertices.length - 1];
        drawPreviewLine.setAttribute('x1', last.x * gridCellSize);
        drawPreviewLine.setAttribute('y1', last.y * gridCellSize);
        drawPreviewLine.setAttribute('x2', p.x * gridCellSize);
        drawPreviewLine.setAttribute('y2', p.y * gridCellSize);
    }
});

grid.addEventListener('dblclick', (e) => {
    if (!drawMode) return;
    if (drawVertices.length >= 3) finishDraw();
});

document.addEventListener('keydown', (e) => {
    if (drawMode && e.key === 'Escape') cancelDraw();
});

mapTypeSelect.addEventListener('change', () => updateHeatmap())
contrastMin.addEventListener('input', () => {
    contrastMinVal.textContent = parseFloat(contrastMin.value).toFixed(1).replace(/\.0$/, '') + '%';
    updateHeatmap();
})
contrastMax.addEventListener('input', () => {
    contrastMaxVal.textContent = parseFloat(contrastMax.value).toFixed(1).replace(/\.0$/, '') + '%';
    updateHeatmap();
})

function makeEditable(spanEl, inputEl, callback) {
    spanEl.addEventListener('dblclick', () => {
        const currentVal = parseFloat(inputEl.value);
        const input = document.createElement('input');
        input.type = 'number';
        input.step = '0.1';
        input.style.width = '45px';
        input.style.fontSize = '12px';
        input.style.background = '#333';
        input.style.color = '#fff';
        input.style.border = '1px solid #555';
        input.value = currentVal;
        
        const save = () => {
            let val = parseFloat(input.value);
            if (isNaN(val)) val = currentVal;
            if (val < 0) val = 0;
            if (val > 100) val = 100;
            val = Math.floor(val * 10) / 10; // truncate to tenths place
            inputEl.value = val;
            spanEl.textContent = val.toFixed(1).replace(/\.0$/, '') + '%';
            spanEl.style.display = '';
            if (input.parentNode) input.parentNode.removeChild(input);
            callback();
        };
        
        input.addEventListener('blur', save);
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') save();
            if (e.key === 'Escape') {
                spanEl.style.display = '';
                if (input.parentNode) input.parentNode.removeChild(input);
            }
        });
        
        spanEl.style.display = 'none';
        spanEl.parentNode.insertBefore(input, spanEl.nextSibling);
        input.focus();
        input.select();
    });
}

makeEditable(contrastMinVal, contrastMin, updateHeatmap);
makeEditable(contrastMaxVal, contrastMax, updateHeatmap);

// 532 nm excitation, matching the backend conversion
function rsToWl(rs) { return 1.0 / (1.0 / 532.0 - rs / 1e7); }
function wlToRs(wl) { return (1.0 / 532.0 - 1.0 / wl) * 1e7; }

// Indices of the x-axis inside the user's integration range, or null for
// the full spectrum. The range inputs are interpreted in the current unit.
function getIntMask() {
    if (!precomputedData) return null;
    let lo = parseFloat(intRangeMin.value);
    let hi = parseFloat(intRangeMax.value);
    if (isNaN(lo) && isNaN(hi)) return null;
    const axis = precomputedData.global_axes[currentUnit];
    if (isNaN(lo)) lo = -Infinity;
    if (isNaN(hi)) hi = Infinity;
    if (lo > hi) [lo, hi] = [hi, lo];
    const mask = [];
    for (let i = 0; i < axis.length; i++) {
        if (axis[i] >= lo && axis[i] <= hi) mask.push(i);
    }
    return mask;
}

function integratedIntensity(pixelData, mask) {
    if (!mask) return pixelData.integrated_intensity;
    let s = 0;
    for (let k = 0; k < mask.length; k++) s += pixelData.norm_spec[mask[k]];
    return s * (pixelData.l_max || 1);
}

// Strongest fitted peak (largest amplitude), or null if the pixel has no fit
function getMainPeak(d) {
    if (!d || !d.fit_success || !d.fit_curves || d.fit_curves.length === 0) return null;
    let best = d.fit_curves[0];
    for (const c of d.fit_curves) if (c.a > best.a) best = c;
    return best;
}

function getMapValue(pixelData, mapType, mask) {
    if (mapType === 'integrated_intensity') return integratedIntensity(pixelData, mask);
    if (mapType === 'peak_pos' || mapType === 'peak_fwhm') {
        const main = getMainPeak(pixelData);
        if (!main) return null;
        return mapType === 'peak_pos' ? main.c : main.w;
    }
    return pixelData[mapType];
}

function updateHeatmap() {
    if (!precomputedData || !precomputedData.pixels) return;
    const mapType = mapTypeSelect.value;
    const minPercent = parseFloat(contrastMin.value) / 100;
    const maxPercent = parseFloat(contrastMax.value) / 100;
    const mask = mapType === 'integrated_intensity' ? getIntMask() : null;

    const valueByKey = {};
    let vals = [];
    for (const key in precomputedData.pixels) {
        const v = getMapValue(precomputedData.pixels[key], mapType, mask);
        valueByKey[key] = v;
        if (v !== null && v !== undefined && isFinite(v)) vals.push(v);
    }

    vals.sort((a, b) => a - b);

    let boundMin = vals.length ? vals[Math.floor(minPercent * (vals.length - 1))] : 0;
    let boundMax = vals.length ? vals[Math.floor(maxPercent * (vals.length - 1))] : 1;

    if (boundMin >= boundMax) {
        boundMax = boundMin + 1e-9;
    }

    const width = precomputedData.global_axes.width || 51;
    const height = precomputedData.global_axes.height || 51;

    for (let y = 0; y < height; y++) {
        for (let x = 0; x < width; x++) {
            const h_idx = (width - 1) - x;
            const key = `${h_idx}_${y}`;
            const pixelData = precomputedData.pixels[key];
            if (!pixelData || !pixelElements[key]) continue;

            let val = valueByKey[key];

            if (val === null || val === undefined || !isFinite(val)) {
                // No value for this map (e.g. pixel not fitted yet)
                pixelElements[key].style.backgroundColor = '#333';
            } else {
                if (val < boundMin) val = boundMin;
                if (val > boundMax) val = boundMax;

                const ratio = (val - boundMin) / (boundMax - boundMin);
                const r = Math.floor(255 * ratio);
                const b = Math.floor(255 * (1 - ratio));
                pixelElements[key].style.backgroundColor = `rgb(${r}, 0, ${b})`;
            }

            if (pixelData.changed) {
                pixelElements[key].style.border = '1px solid #ff8c00';
                pixelElements[key].style.boxSizing = 'border-box';
            } else {
                pixelElements[key].style.border = 'none';
            }
        }
    }
}

intRangeMin.addEventListener('change', updateHeatmap);
intRangeMax.addEventListener('change', updateHeatmap);
intRangeReset.addEventListener('click', () => {
    intRangeMin.value = '';
    intRangeMax.value = '';
    updateHeatmap();
});

let currentX = -1
let currentY = -1
let isLocked = false
let showFits = true
let precomputedData = null
let pollInterval = null
let currentUnit = 'rs'
let fitEventSource = null;
let pixelElements = {};

// Manual flake-polygon drawing state. Coordinates are in grid-cell units
// (floats), converted to px via gridCellSize only when rendering.
let gridCellSize = 10;
let autoContourCellPts = null;
let drawMode = false;
let drawVertices = [];
let drawSvg = null;
let drawPolyline = null;
let drawPreviewLine = null;
let drawSnapDot = null;
let manualFlakeSvg = null;
let lastDrawFinish = 0;

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
        const res = await fetch(`/datasets?t=${Date.now()}`)
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
    
    try {
        // Step 1: Generate Signed URL
        const genRes = await fetch('/generate_upload_url', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename: file.name })
        });
        const genData = await genRes.json();
        if (!genRes.ok) throw new Error(genData.error || "Failed to generate upload URL");
        
        // Step 2: Upload to GCS
        uploadStatus.innerText = 'Uploading to Cloud Storage...';
        const uploadRes = await fetch(genData.signed_url, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/octet-stream' },
            body: file
        });
        if (!uploadRes.ok) throw new Error("Cloud Storage upload failed");
        
        // Step 3: Tell backend to process it
        uploadStatus.innerText = 'Processing file...';
        const procRes = await fetch('/process_gcs_file', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ object_name: genData.object_name, filename: genData.filename })
        });
        const data = await procRes.json();
        if (!procRes.ok) throw new Error(data.error || "Processing failed");
        
        if (data.duplicate) {
            alert(data.message);
            await loadDatasets(data.dataset_id);
            finishUpload();
        } else {
            pollStatus(data.dataset_id);
        }
    } catch (err) {
        alert(err.message)
        finishUpload()
    }
})

function finishUpload() {
    uploadBtn.textContent = 'Upload Data'
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
    
    activeFitStreams[dsId] = new EventSource(`/fit_stream/${dsId}?mode=${encodeURIComponent(fitModeSelect.value)}`);
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
                updateHeatmap(); // fit-derived maps (peak position/FWHM) are now valid
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
                precomputedData.pixels[data.key].fit_mode = data.fit_mode;
                precomputedData.pixels[data.key].fit_curves = data.fit_curves;
                precomputedData.pixels[data.key].total_fit_curve = data.total_fit_curve;
                precomputedData.pixels[data.key].r_squared = data.r_squared;
                precomputedData.pixels[data.key].changed = true;
                
                // Flash animation for the pixel
                const pixelEl = pixelElements[data.key];
                if (pixelEl) {
                    pixelEl.style.border = '1px solid #ff8c00';
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
                    updateChart(precomputedData.pixels[data.key], x, y);
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

resetFitsBtn.addEventListener('click', async () => {
    if (!datasetSelect.value) return;
    
    resetFitsBtn.disabled = true;
    try {
        const res = await fetch(`/reset_all_fits/${datasetSelect.value}`, { method: 'POST' });
        if (res.ok) {
            // Re-fetch the dataset with cache-busting to clear the frontend cache
            await initGrid(datasetSelect.value);
        } else {
            console.error("Failed to reset fits.");
        }
    } catch (e) {
        console.error("Error resetting fits.", e);
    }
    resetFitsBtn.disabled = false;
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
    flakeAvgData = null;
    showFlakeAvgBtn.style.display = 'none';
    if (currentFlakeSvg) {
        currentFlakeSvg.remove();
        currentFlakeSvg = null;
    }
    cancelDraw();
    if (manualFlakeSvg) {
        manualFlakeSvg.remove();
        manualFlakeSvg = null;
    }
    autoContourCellPts = null;
    
    try {
        const response = await fetch(`/api/data/${datasetId}`)
        if (!response.ok) throw new Error("Could not load dataset")
        precomputedData = await response.json()
        
        grid.innerHTML = '' // Clear loading text
        
        const width = precomputedData.global_axes.width || 51;
        const height = precomputedData.global_axes.height || 51;
        
        const container = document.querySelector('.left-panel');
        const maxW = container.clientWidth - 60; // 60px for padding
        const maxH = window.innerHeight - 300; // room for top controls and bottom legend
        
        let cellSize = Math.floor(Math.min(maxW / width, maxH / height));
        if (cellSize < 1) cellSize = 1;
        if (cellSize > 15) cellSize = 15;
        gridCellSize = cellSize;

        grid.style.gridTemplateColumns = `repeat(${width}, ${cellSize}px)`;
        grid.style.gridTemplateRows = `repeat(${height}, ${cellSize}px)`;
        grid.style.width = `${width * cellSize}px`;
        grid.style.height = `${height * cellSize}px`;
        
        // Add double click listener to the grid to unlock if clicking anywhere in the plane
        grid.addEventListener('dblclick', () => {
            if (drawMode || Date.now() - lastDrawFinish < 300) return;
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
                    if (drawMode) return; // let it bubble so the draw handler closes the polygon
                    e.stopPropagation(); // prevent grid dblclick from firing immediately
                    if (!isLocked) {
                        isLocked = true;
                        currentX = x;
                        currentY = y;
                        coordText.innerText = `(LOCKED) (${x}, ${y}) - Recommended Peaks: ${pixelData ? pixelData.num_peaks : 0}`
                        fetchSpectrum(x, y);
                    } else {
                        isLocked = false;
                        coordText.innerText = `(${x}, ${y}) - Recommended Peaks: ${pixelData ? pixelData.num_peaks : 0}`
                    }
                });
                
                grid.appendChild(pixel)
            }
        }
        
        updateHeatmap();
        fitBtn.style.display = 'inline-block';
        fitModeSelect.style.display = 'inline-block';
        resetFitsBtn.style.display = 'inline-block';
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
        fitModeSelect.style.display = 'none';
        resetFitsBtn.style.display = 'none';
        toggleFitsBtn.style.display = 'none';
    }
}

unitSelect.addEventListener('change', () => {
    const oldUnit = currentUnit;
    currentUnit = unitSelect.value;
    if (oldUnit !== currentUnit) {
        // Keep the integration range physically identical across units.
        // rs↔wl conversion is monotonic increasing, so min/max order holds.
        const convert = currentUnit === 'wls' ? rsToWl : wlToRs;
        for (const input of [intRangeMin, intRangeMax]) {
            const v = parseFloat(input.value);
            if (!isNaN(v)) input.value = convert(v).toFixed(2);
        }
        intRangeUnit.textContent = currentUnit === 'rs' ? 'cm⁻¹' : 'nm';
    }
    if (currentX !== -1 && currentY !== -1 && precomputedData) {
        const width = precomputedData.global_axes.width;
        // When changing units, force relayout so it rescales to new unit ranges
        updateChart(precomputedData.pixels[`${(width - 1) - currentX}_${currentY}`], currentX, currentY, true)
    } else if (flakeAvgData && isLocked && currentX === -1 && currentY === -1) {
        // Trigger the flake average render again
        showFlakeAvgBtn.click();
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
            Expected Peaks: <span id="num-peaks-val" style="color: #4d4dff; cursor: pointer; text-decoration: underline;" title="Click to edit">${data.expected_num_peaks || data.num_peaks}</span>
            <input type="number" id="num-peaks-input" style="display: none; width: 40px; background: #333; color: white; border: 1px solid #555;" min="1" max="10" step="1"><br>
            Total Int = ${data.integrated_intensity ? data.integrated_intensity.toExponential(2) : '0.00e+0'}<br>`;
    const intMask = getIntMask();
    if (intMask) {
        statsHtml += `Int (range) = ${integratedIntensity(data, intMask).toExponential(2)}<br>`;
    }
    statsHtml += `
            Sharpness = ${data.sharpness !== undefined && data.sharpness !== null ? data.sharpness.toFixed(3) : 'N/A'}<br>
            Bg Level = ${data.bg_noise !== undefined ? data.bg_noise.toFixed(2) : '0.00'} a.u.`;
    if (data.cosmic_removed) {
        statsHtml += `<br>Cosmic rays removed = ${data.cosmic_removed}`;
    }
    const mainPeak = getMainPeak(data);
    if (mainPeak) {
        const posLabel = currentUnit === 'wls'
            ? `${rsToWl(mainPeak.c).toFixed(2)} nm`
            : `${mainPeak.c.toFixed(1)} cm⁻¹`;
        statsHtml += `<br>Main Peak = ${posLabel} (FWHM ${mainPeak.w.toFixed(1)} cm⁻¹)`;
    }
    statsHtml += `
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

    const numPeaksVal = document.getElementById('num-peaks-val');
    const numPeaksInput = document.getElementById('num-peaks-input');
    if (numPeaksVal && numPeaksInput) {
        numPeaksVal.addEventListener('click', () => {
            numPeaksInput.value = data.expected_num_peaks || data.num_peaks;
            numPeaksVal.style.display = 'none';
            numPeaksInput.style.display = 'inline-block';
            numPeaksInput.focus();
        });
        
        const savePeaks = async () => {
            let val = parseInt(numPeaksInput.value);
            if (!isNaN(val) && val > 0) {
                data.expected_num_peaks = val;
                data.changed = true;
                numPeaksVal.textContent = val;
                
                const width = precomputedData.global_axes.width;
                const h_idx = (width - 1) - x;
                const key = `${h_idx}_${y}`;
                
                if (pixelElements[key]) {
                    pixelElements[key].style.border = '1px solid #ff8c00';
                    pixelElements[key].style.boxSizing = 'border-box';
                }
                
                await fetch(`/update_pixel/${datasetSelect.value}/${key}`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({num_peaks: val})
                });
            }
            numPeaksInput.style.display = 'none';
            numPeaksVal.style.display = 'inline-block';
        };
        numPeaksInput.addEventListener('blur', savePeaks);
        numPeaksInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') savePeaks();
            if (e.key === 'Escape') {
                numPeaksInput.style.display = 'none';
                numPeaksVal.style.display = 'inline-block';
            }
        });
    }

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
            title: { text: xTitle, standoff: 15 },
            gridcolor: '#444',
            automargin: true
        },
        yaxis: { 
            title: { text: 'Normalized Intensity (a.u.)', standoff: 15 },
            gridcolor: '#444',
            automargin: true
        },
        legend: { x: 1, xanchor: 'right', y: 1 },
        margin: { l: 60, r: 20, t: 40, b: 60 }
    };
    
    if (xRange && yRange) {
        layout.xaxis.range = xRange;
        layout.yaxis.range = yRange;
        layout.uirevision = forceRelayout ? Math.random() : currentUnit;
    }

    Plotly.react('chart', traces, layout, {responsive: true});
}

// Identity badge: who this session is (Crucible ORCiD or anonymous).
// Identity is decided server-side from the signed session cookie — this is
// purely informational UI.
async function loadIdentity() {
    const bar = document.getElementById('identity-bar')
    try {
        const res = await fetch('/config')
        const cfg = await res.json()
        bar.innerHTML = ''
        const label = document.createElement('span')
        if (cfg.identity && cfg.identity.type === 'orcid') {
            label.textContent = `Signed in via Crucible: ${cfg.identity.name || cfg.identity.orcid} (${cfg.identity.orcid})`
            label.style.color = '#8fbf6f'
            bar.appendChild(label)
            const out = document.createElement('a')
            out.textContent = 'Sign out'
            out.href = '#'
            out.style.color = '#888'
            out.addEventListener('click', async (e) => {
                e.preventDefault()
                await fetch('/logout', { method: 'POST' })
                window.location.href = '/'
            })
            bar.appendChild(out)
        } else {
            label.textContent = 'Anonymous session — your uploads are private to this browser'
            bar.appendChild(label)
            if (cfg.sign_in_url) {
                const a = document.createElement('a')
                a.textContent = 'Sign in via Crucible'
                a.href = cfg.sign_in_url
                a.style.color = '#7fb3ff'
                bar.appendChild(a)
            }
        }
    } catch (e) {
        console.error(e)
    }
}

// Start app
// Supports deep-linking (?dataset=<id>), e.g. the redirect after a
// Crucible-signed /import. Datasets only appear if they belong to this
// session's principal — there is no way to pull arbitrary GCS objects.
async function startApp() {
    loadIdentity()
    const params = new URLSearchParams(window.location.search)
    const requestedId = params.get('dataset')

    if (!requestedId) {
        loadDatasets()
        return
    }

    try {
        const res = await fetch(`/status/${requestedId}`)
        const data = await res.json()
        if (data.status === 'done') {
            await loadDatasets(requestedId)
            return
        }
        if (data.status === 'processing') {
            await loadDatasets(requestedId)
            pollStatus(requestedId)
            return
        }
    } catch (e) {
        console.error(e)
    }

    await loadDatasets()
    uploadStatus.innerText = `Dataset ${requestedId} not found`
}
startApp()
