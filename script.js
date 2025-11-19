/**
 * The Library of Babel Simulation
 * 
 *
 * Grid Topology: 10x10 Rhombus grid with Periodic Boundary Conditions (Torus).
 * Coordinates: Axial (q, r).
 */

const GRID_SIZE = 10; // Default, will be updated from backend
// HEX_RADIUS is now dynamic

class Renderer {
    constructor(canvas) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.resize();
        window.addEventListener('resize', () => this.resize());
        this.hexRadius = 25; // Default
    }

    resize() {
        const rect = this.canvas.parentElement.getBoundingClientRect();
        this.canvas.width = rect.width;
        this.canvas.height = rect.height;
        if (this.lastData) this.draw(this.lastData);
    }

    hexToPixel(col, row) {
        const size = this.hexRadius;
        // Flat topped hexes, Odd-Q layout

        const width = size * 2;
        const height = size * Math.sqrt(3);
        const horizSpacing = size * 1.5;
        const vertSpacing = height;

        const x = horizSpacing * col;
        const y = vertSpacing * (row + 0.5 * (col % 2));

        // Center the grid
        const totalW = horizSpacing * this.gridSize + size * 0.5;
        const totalH = vertSpacing * (this.gridSize + 0.5);

        const offsetX = (this.canvas.width - totalW) / 2;
        const offsetY = (this.canvas.height - totalH) / 2;

        return { x: x + offsetX + size, y: y + offsetY + height / 2 };
    }

    hexToPixelDelta(dq, dr) {
        const size = this.hexRadius;
        const height = size * Math.sqrt(3);
        const horizSpacing = size * 1.5;

        const x = horizSpacing * dq;
        const y = height * (dr + 0.5 * dq); // Approximation
        return { x, y };
    }

    draw(data) {
        if (!data) return;
        this.lastData = data; // Store for redraws
        this.gridSize = data.size;
        const cells = data.cells;
        let loops = data.loops;

        // Calculate dynamic HEX_RADIUS to fit the canvas
        // Max width available: this.canvas.width
        // Max height available: this.canvas.height
        // Grid width approx: size * 1.5 * N
        // Grid height approx: size * sqrt(3) * N

        const padding = 40;
        const availW = this.canvas.width - padding * 2;
        const availH = this.canvas.height - padding * 2;

        const wPerHex = 1.5; // roughly
        const hPerHex = Math.sqrt(3);

        // We need to fit N columns and N rows
        const maxR_W = availW / (this.gridSize * 1.5 + 0.5);
        const maxR_H = availH / (this.gridSize * Math.sqrt(3) + Math.sqrt(3) / 2);

        this.hexRadius = Math.min(maxR_W, maxR_H);
        // Clamp min size for visibility? Or let it get small for N=50
        // For N=50, radius might be ~10px on a large screen.

        const HEX_RADIUS = this.hexRadius;

        // Filter loops if "Show Longest Only" is checked and NOT scrambling
        const showLongestOnly = document.getElementById('chkLongestOnly').checked;
        // We need to know if we are scrambling. 
        // Ideally pass this state in or check the global variable (though global is messy).
        // Let's check the global isScrambling variable.
        if (showLongestOnly && !window.isScrambling) {
            if (loops.length > 0) {
                const maxLen = Math.max(...loops.map(l => l.length));
                loops = loops.filter(l => l.length === maxLen);
            }
        }

        const ctx = this.ctx;
        ctx.fillStyle = '#ffffff'; // Light background
        ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

        // Update stats (use original data for stats)
        document.getElementById('roomCount').innerText = this.gridSize * this.gridSize;
        document.getElementById('loopCount').innerText = data.loops.length;
        const maxLen = data.loops.length > 0 ? Math.max(...data.loops.map(l => l.length)) : 0;
        document.getElementById('longestPath').innerText = maxLen;

        // Draw Cells (Walls)
        ctx.strokeStyle = '#1d1d1f'; // Dark walls
        ctx.lineWidth = Math.max(1, HEX_RADIUS / 10); // Scale wall thickness
        for (let key in cells) {
            const cell = cells[key];
            const center = this.hexToPixel(cell.q, cell.r);
            // Only fill if it's part of a visible loop? 
            // Or just draw all cells as background structure?
            // User asked to "hide all except the longest continuous loop".
            // This implies hiding the *paths* of others. The rooms probably stay?
            // Let's keep the rooms visible as the "library" structure.
            this.drawHex(center.x, center.y, HEX_RADIUS, '#f5f5f7');
        }

        // Draw Paths (Connections)
        ctx.lineWidth = Math.max(2, HEX_RADIUS / 5); // Scale path thickness
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
        ctx.shadowBlur = 0;

        // Create 8 log-spaced bins for discrete coloring (matching PDF)
        const numColorBins = 8;
        const lMin = 1.0 / this.gridSize;  // Rescaled min: 1/N
        const lMax = this.gridSize;         // Rescaled max: N
        const logMin = Math.log(lMin);
        const logMax = Math.log(lMax);

        // Create bin edges
        const binEdges = [];
        for (let i = 0; i <= numColorBins; i++) {
            const logVal = logMin + (i / numColorBins) * (logMax - logMin);
            binEdges.push(Math.exp(logVal));
        }

        // 8-color palette: dark blue -> bright red
        const colorPalette = [
            'hsl(240, 100%, 25%)',  // Dark blue (shortest loops)
            'hsl(220, 100%, 35%)',  // Blue
            'hsl(200, 100%, 45%)',  // Light blue
            'hsl(180, 80%, 50%)',   // Cyan
            'hsl(120, 70%, 45%)',   // Green
            'hsl(60, 90%, 50%)',    // Yellow
            'hsl(30, 100%, 55%)',   // Orange
            'hsl(0, 100%, 50%)'     // Bright red (longest loops)
        ];

        loops.forEach((loop, i) => {
            const len = loop.length;
            const l = len / this.gridSize;  // Rescaled length

            // Find which bin this loop belongs to
            let binIndex = 0;
            for (let b = 0; b < numColorBins; b++) {
                if (l >= binEdges[b] && l < binEdges[b + 1]) {
                    binIndex = b;
                    break;
                }
            }
            // Handle edge case: l exactly equals lMax
            if (l >= binEdges[numColorBins]) {
                binIndex = numColorBins - 1;
            }

            const color = colorPalette[binIndex];
            ctx.strokeStyle = color;

            // We need to draw segments individually to handle jumps
            for (let j = 0; j < loop.length; j++) {
                const cell = loop[j];
                const next = loop[(j + 1) % loop.length];

                const p1 = this.hexToPixel(cell.q, cell.r);
                const p2 = this.hexToPixel(next.q, next.r);

                const dist = Math.hypot(p1.x - p2.x, p1.y - p2.y);

                if (dist < HEX_RADIUS * 3) {
                    // Normal connection
                    ctx.beginPath();
                    ctx.moveTo(p1.x, p1.y);
                    ctx.lineTo(p2.x, p2.y);
                    ctx.stroke();
                } else {
                    // Wrapped connection
                    // Calculate logical delta
                    let dq = next.q - cell.q;
                    let dr = next.r - cell.r;

                    if (dq > this.gridSize / 2) dq -= this.gridSize;
                    if (dq < -this.gridSize / 2) dq += this.gridSize;
                    if (dr > this.gridSize / 2) dr -= this.gridSize;
                    if (dr < -this.gridSize / 2) dr += this.gridSize;

                    const delta = this.hexToPixelDelta(dq, dr);
                    const angle = Math.atan2(delta.y, delta.x);

                    // Draw half-line from cell
                    ctx.beginPath();
                    ctx.moveTo(p1.x, p1.y);
                    ctx.lineTo(p1.x + Math.cos(angle) * HEX_RADIUS, p1.y + Math.sin(angle) * HEX_RADIUS);
                    ctx.stroke();

                    // Draw half-line from next (incoming)
                    const angleBack = Math.atan2(-delta.y, -delta.x);

                    ctx.beginPath();
                    ctx.moveTo(p2.x, p2.y);
                    ctx.lineTo(p2.x + Math.cos(angleBack) * HEX_RADIUS, p2.y + Math.sin(angleBack) * HEX_RADIUS);
                    ctx.stroke();
                }
            }
        });
    }

    drawHex(x, y, size, fillColor) {
        const ctx = this.ctx;
        ctx.beginPath();
        for (let i = 0; i < 6; i++) {
            // Flat topped: start at 0 degrees
            const angle = 2 * Math.PI / 6 * i;
            const px = x + size * Math.cos(angle);
            const py = y + size * Math.sin(angle);
            if (i === 0) ctx.moveTo(px, py);
            else ctx.lineTo(px, py);
        }
        ctx.closePath();
        if (fillColor) {
            ctx.fillStyle = fillColor;
            ctx.fill();
        }
        ctx.stroke();
    }
}

const canvas = document.getElementById('simCanvas');
const renderer = new Renderer(canvas);

// Animation Loop for "Scramble"
window.isScrambling = false;

document.getElementById('btnReset').addEventListener('click', async () => {
    window.isScrambling = false;
    document.getElementById('btnScramble').innerText = "Scramble (MCMC)";
    document.getElementById('btnScramble').classList.remove('active');

    const size = parseInt(document.getElementById('rngSize').value);
    const response = await fetch('/reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ size: size })
    });
    const data = await response.json();
    renderer.draw(data);
});

document.getElementById('chkLongestOnly').addEventListener('change', () => {
    renderer.draw(renderer.lastData);
});

document.getElementById('rngSize').addEventListener('input', (e) => {
    document.getElementById('lblSize').innerText = e.target.value;
});

document.getElementById('rngSize').addEventListener('change', async (e) => {
    // When slider is released/changed, trigger reset with new size
    window.isScrambling = false;
    document.getElementById('btnScramble').innerText = "Scramble (MCMC)";
    document.getElementById('btnScramble').classList.remove('active');

    const size = parseInt(e.target.value);
    const response = await fetch('/reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ size: size })
    });
    const data = await response.json();
    renderer.draw(data);
});

// Initial load
fetchState();

class Histogram {
    constructor(canvas) {
        this.canvas = canvas;
        this.numBins = 100;
        this.gridSize = 10; // Default, will be updated
        this.bins = new Float32Array(this.numBins);
        this.binEdges = [];
        this.binCenters = [];
        this.totalSamples = 0;

        this.initializeBins();

        // 8-color palette (matching loop colors) with transparency
        const colorPalette = [
            'hsla(240, 100%, 25%, 0.15)',  // Dark blue
            'hsla(220, 100%, 35%, 0.15)',  // Blue
            'hsla(200, 100%, 45%, 0.15)',  // Light blue
            'hsla(180, 80%, 50%, 0.15)',   // Cyan
            'hsla(120, 70%, 45%, 0.15)',   // Green
            'hsla(60, 90%, 50%, 0.15)',    // Yellow
            'hsla(30, 100%, 55%, 0.15)',   // Orange
            'hsla(0, 100%, 50%, 0.15)'     // Bright red
        ];

        // Calculate initial color bin edges
        const colorBinEdges = this.calculateColorBinEdges();

        // Build annotation objects for 8 color boxes
        const annotations = {
            maxPathLine: {
                type: 'line',
                xMin: this.gridSize,
                xMax: this.gridSize,
                borderColor: 'red',
                borderWidth: 2,
                borderDash: [5, 5],
                label: {
                    display: true,
                    content: 'Max Path (N)',
                    position: 'start',
                    backgroundColor: 'rgba(255, 0, 0, 0.8)',
                    color: 'white',
                    font: { size: 9 }
                }
            }
        };

        // Add 8 color box annotations
        for (let i = 0; i < 8; i++) {
            annotations[`colorBox${i}`] = {
                type: 'box',
                xMin: colorBinEdges[i],
                xMax: colorBinEdges[i + 1],
                yMin: 0,
                yMax: 1e10,  // Large value to cover full y-axis
                backgroundColor: colorPalette[i],
                borderWidth: 0,
                drawTime: 'beforeDatasetsDraw'  // Draw behind data
            };
        }

        // Create Chart.js instance
        this.chart = new Chart(canvas, {
            type: 'line',
            data: {
                labels: this.binCenters,
                datasets: [{
                    label: 'PDF',
                    data: [],
                    backgroundColor: 'rgba(0, 113, 227, 0.2)',
                    borderColor: 'rgba(0, 113, 227, 1)',
                    borderWidth: 2,
                    pointStyle: 'circle',
                    pointRadius: 4,
                    pointBackgroundColor: 'rgba(0, 113, 227, 1)',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 1,
                    showLine: true,
                    tension: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        type: 'logarithmic',
                        title: {
                            display: true,
                            text: 'Rescaled Length (l = length/N)',
                            font: { size: 10 }
                        },
                        ticks: { font: { size: 8 } }
                    },
                    y: {
                        type: 'logarithmic',
                        title: {
                            display: true,
                            text: 'Probability Density',
                            font: { size: 10 }
                        },
                        ticks: { font: { size: 8 } }
                    }
                },
                plugins: {
                    legend: { display: false },
                    annotation: {
                        annotations: annotations
                    }
                }
            }
        });
    }

    initializeBins() {
        // Create log-spaced bins from 1/N to N
        const lMin = 1.0 / this.gridSize;
        const lMax = this.gridSize;
        const logMin = Math.log(lMin);
        const logMax = Math.log(lMax);

        this.binEdges = [];
        this.binCenters = [];

        // Create numBins + 1 edges
        for (let i = 0; i <= this.numBins; i++) {
            const logVal = logMin + (i / this.numBins) * (logMax - logMin);
            this.binEdges.push(Math.exp(logVal));
        }

        // Compute bin centers (geometric mean of edges)
        for (let i = 0; i < this.numBins; i++) {
            this.binCenters[i] = Math.sqrt(this.binEdges[i] * this.binEdges[i + 1]);
        }
    }

    calculateColorBinEdges() {
        // Calculate 8 log-spaced bins for color regions (matching loop colors)
        const numColorBins = 8;
        const lMin = 1.0 / this.gridSize;
        const lMax = this.gridSize;
        const logMin = Math.log(lMin);
        const logMax = Math.log(lMax);

        const colorBinEdges = [];
        for (let i = 0; i <= numColorBins; i++) {
            const logVal = logMin + (i / numColorBins) * (logMax - logMin);
            colorBinEdges.push(Math.exp(logVal));
        }
        return colorBinEdges;
    }

    setGridSize(N) {
        if (N !== this.gridSize) {
            this.gridSize = N;
            this.initializeBins();

            // Recalculate color bin edges
            const colorBinEdges = this.calculateColorBinEdges();

            // Update the annotation line position
            this.chart.options.plugins.annotation.annotations.maxPathLine.xMin = N;
            this.chart.options.plugins.annotation.annotations.maxPathLine.xMax = N;

            // Update the 8 color box positions
            for (let i = 0; i < 8; i++) {
                const boxAnnotation = this.chart.options.plugins.annotation.annotations[`colorBox${i}`];
                boxAnnotation.xMin = colorBinEdges[i];
                boxAnnotation.xMax = colorBinEdges[i + 1];
            }

            this.reset();
        }
    }

    reset() {
        this.bins.fill(0);
        this.totalSamples = 0;
        this.updateChart();
    }

    update(loops) {
        if (!loops) return;

        loops.forEach(loop => {
            const length = loop.length;
            const l = length / this.gridSize; // Rescaled variable

            // Find bin index using binary search
            let binIndex = -1;
            for (let i = 0; i < this.numBins; i++) {
                if (l >= this.binEdges[i] && l < this.binEdges[i + 1]) {
                    binIndex = i;
                    break;
                }
            }

            // Handle edge case: l exactly equals lMax
            if (l === this.binEdges[this.numBins]) {
                binIndex = this.numBins - 1;
            }

            if (binIndex >= 0 && binIndex < this.numBins) {
                this.bins[binIndex]++;
                this.totalSamples++;
            }
        });
    }

    updateChart() {
        if (this.totalSamples === 0) {
            this.chart.data.datasets[0].data = [];
            this.chart.update('none'); // 'none' mode skips animation
            return;
        }

        // Compute probability density function
        const pdfData = [];
        for (let i = 0; i < this.numBins; i++) {
            const binWidth = this.binEdges[i + 1] - this.binEdges[i];
            const density = this.bins[i] / (this.totalSamples * binWidth);

            // Only add non-zero values for cleaner log plot
            if (density > 0) {
                pdfData.push({ x: this.binCenters[i], y: density });
            }
        }

        this.chart.data.datasets[0].data = pdfData;
        this.chart.update('none'); // Skip animation for performance
    }

    // Keep draw() for compatibility, but it just calls updateChart()
    draw() {
        this.updateChart();
    }
}

const histogram = new Histogram(document.getElementById('histogramCanvas'));

async function fetchState() {
    const response = await fetch('/state');
    const data = await response.json();
    renderer.draw(data);
    // Update slider to match backend state
    document.getElementById('rngSize').value = data.size;
    document.getElementById('lblSize').innerText = data.size;
    // Set histogram grid size and update
    histogram.setGridSize(data.size);
    histogram.update(data.loops);
    histogram.updateChart();
}

let scrambleFrameCount = 0;

async function scrambleStep() {
    if (!window.isScrambling) return;

    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 2000); // 2s timeout

        // Scale steps based on grid size
        const currentSize = parseInt(document.getElementById('rngSize').value);
        const steps = Math.max(1, Math.floor(currentSize / 2));

        const response = await fetch('/scramble', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ steps: steps }),
            signal: controller.signal
        });
        clearTimeout(timeoutId);

        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

        const data = await response.json();
        renderer.draw(data);

        scrambleFrameCount++;
        if (scrambleFrameCount % 10 === 0) {
            histogram.update(data.loops);
            histogram.updateChart();
        }
    } catch (e) {
        console.error("Scramble loop error:", e);
    }

    if (window.isScrambling) {
        requestAnimationFrame(scrambleStep);
    }
}

document.getElementById('btnScramble').addEventListener('click', () => {
    window.isScrambling = !window.isScrambling;
    const btn = document.getElementById('btnScramble');
    if (window.isScrambling) {
        btn.innerText = "Stop Scrambling";
        btn.classList.add('active');
        scrambleStep();
    } else {
        btn.innerText = "Scramble (MCMC)";
        btn.classList.remove('active');
        // Redraw to apply filter if needed
        renderer.draw(renderer.lastData);
    }
});

document.getElementById('btnReset').addEventListener('click', async () => {
    window.isScrambling = false;
    document.getElementById('btnScramble').innerText = "Scramble (MCMC)";
    document.getElementById('btnScramble').classList.remove('active');

    const size = parseInt(document.getElementById('rngSize').value);
    const response = await fetch('/reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ size: size })
    });
    const data = await response.json();
    renderer.draw(data);
    histogram.setGridSize(data.size);
    histogram.reset();
    histogram.update(data.loops);
    histogram.updateChart();
});

document.getElementById('chkLongestOnly').addEventListener('change', () => {
    renderer.draw(renderer.lastData);
});

document.getElementById('rngSize').addEventListener('input', (e) => {
    document.getElementById('lblSize').innerText = e.target.value;
});

document.getElementById('rngSize').addEventListener('change', async (e) => {
    // When slider is released/changed, trigger reset with new size
    window.isScrambling = false;
    document.getElementById('btnScramble').innerText = "Scramble (MCMC)";
    document.getElementById('btnScramble').classList.remove('active');

    const size = parseInt(e.target.value);
    const response = await fetch('/reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ size: size })
    });
    const data = await response.json();
    renderer.draw(data);
    histogram.setGridSize(data.size);
    histogram.reset();
    histogram.update(data.loops);
    histogram.updateChart();
});
