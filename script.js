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

        // Color Scale Parameters
        // Min length is typically around N (gridSize) in the organized state.
        // Max length is N*N (gridSize * gridSize).
        const minScale = this.gridSize;
        const maxScale = this.gridSize * this.gridSize;

        loops.forEach((loop, i) => {
            const len = loop.length;

            // Calculate normalized position t in [0, 1]
            // We clamp it to ensure bounds
            let t = (len - minScale) / (maxScale - minScale);
            t = Math.max(0, Math.min(1, t));

            // Map t to Hue: 240 (Blue) -> 0 (Red)
            const hue = 240 * (1 - t);

            // Map t to Lightness: 30% (Dark) -> 50% (Bright)
            const lightness = 30 + 20 * t;

            const color = `hsl(${hue}, 100%, ${lightness}%)`;
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
        this.ctx = canvas.getContext('2d');
        this.counts = {}; // Map length -> count
        this.maxCount = 0;
        this.resize();
        window.addEventListener('resize', () => this.resize());
    }

    resize() {
        const rect = this.canvas.parentElement.getBoundingClientRect();
        // Account for padding in parent
        this.canvas.width = rect.width - 32;
        this.canvas.height = rect.height - 40;
        this.draw();
    }

    reset() {
        this.counts = {};
        this.maxCount = 0;
        this.draw();
    }

    update(loops) {
        if (!loops) return;
        loops.forEach(loop => {
            const len = loop.length;
            this.counts[len] = (this.counts[len] || 0) + 1;
            if (this.counts[len] > this.maxCount) {
                this.maxCount = this.counts[len];
            }
        });
        this.draw();
    }

    draw() {
        const ctx = this.ctx;
        const w = this.canvas.width;
        const h = this.canvas.height;

        ctx.clearRect(0, 0, w, h);

        const lengths = Object.keys(this.counts).map(Number).sort((a, b) => a - b);
        if (lengths.length === 0) return;

        const minLen = lengths[0];
        const maxLen = lengths[lengths.length - 1];
        // X-axis range: 0 to maxLen (or slightly more)
        const xMax = Math.max(maxLen, 10);

        const barWidth = w / (xMax + 1);

        ctx.fillStyle = '#0071e3';

        lengths.forEach(len => {
            const count = this.counts[len];
            const barHeight = (count / this.maxCount) * h;
            const x = (len / xMax) * w;
            const y = h - barHeight;

            ctx.fillRect(x, y, Math.max(1, barWidth - 1), barHeight);
        });

        // Draw labels (simplified)
        ctx.fillStyle = '#86868b';
        ctx.font = '10px Inter';
        ctx.textAlign = 'right';
        ctx.fillText(this.maxCount, w - 2, 10);
        ctx.textAlign = 'left';
        ctx.fillText('0', 2, h - 2);
        ctx.textAlign = 'right';
        ctx.fillText(xMax, w - 2, h - 2);
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
    // Don't update histogram on initial fetch to avoid double counting or counting organized state too much?
    // Actually, user wants "sampled path lengths as the simulation is running".
    // So maybe only update during scramble?
    // But seeing the initial state distribution is also useful.
    // Let's update it.
    histogram.update(data.loops);
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
    histogram.reset();
    histogram.update(data.loops);
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
    histogram.reset();
    histogram.update(data.loops);
});
