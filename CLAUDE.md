# Library of Babel Simulation

A web-based simulation of a 2D hexagonal grid with periodic boundary conditions (torus topology), visualizing the formation of loops using a Monte Carlo Markov Chain (MCMC) algorithm.

## Stack

*   **Backend**: Python 3, Flask, NumPy.
*   **Frontend**: Vanilla JavaScript, HTML5 Canvas, CSS3.
*   **Communication**: REST API (JSON) over HTTP.

## Core Algorithm (`app.py`)

The simulation manages a grid of $N \times N$ hexagonal cells.

*   **Topology**: 10x10 (default, scalable 5-50) Hexagonal Grid using **Odd-Q Offset Coordinates** (Flat-Topped).
*   **Constraints**:
    *   **Degree 2**: Every cell has exactly 2 doorways connecting to neighbors.
    *   **Periodic Boundaries**: Edges wrap around (Torus), creating a finite but unbounded surface.
    *   **2-Factor**: The configuration always forms a set of disjoint loops (cycles).
*   **MCMC Scramble**:
    *   Randomly selects two edges $(u, v)$ and $(x, y)$.
    *   Attempts to swap connections to form $(u, x)$ and $(v, y)$ or $(u, y)$ and $(v, x)$.
    *   Preserves the degree-2 constraint (valid 2-factor).
    *   Ergodic: Can reach any valid configuration from any other.

## Visualization & Logic (`script.js`)

The frontend renders the state and drives the simulation loop.

*   **`Renderer` Class**:
    *   **Dynamic Scaling**: Calculates `HEX_RADIUS` to fit the $N \times N$ grid within the viewport.
    *   **Flat-Topped Hexagons**: Drawn using standard parametric equations (start angle $0^\circ$).
    *   **Periodic Edges**: Detects "wrapped" connections (distance > threshold) and draws "half-lines" pointing towards the boundary to visualize the torus topology.
    *   **Color Mapping**: Loops are colored by length using an HSL scale:
        *   Short loops ($\approx N$): **Dark Blue**
        *   Long loops ($\approx N^2$): **Bright Red**
*   **`Histogram` Class**:
    *   Maintains a cumulative frequency distribution of sampled loop lengths.
    *   Renders a real-time bar chart on a secondary canvas.
*   **Simulation Loop (`scrambleStep`)**:
    *   **Throttled Updates**: Fetches new states recursively using `requestAnimationFrame`.
    *   **Robustness**: Uses `AbortController` for timeouts (2s) and `try-catch` blocks to handle network glitches without stalling the animation.
    *   **Adaptive Step Size**: Scales MCMC steps per frame based on grid size ($Steps \approx N/2$) to maintain visual pacing.

## API Endpoints

*   `GET /state`: Returns current grid configuration (cells, loops, size).
*   `POST /scramble`: Performs MCMC steps. Body: `{ "steps": int }`.
*   `POST /reset`: Resets to organized vertical loops. Body: `{ "size": int }`.
