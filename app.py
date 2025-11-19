import random
from flask import Flask, jsonify, request, send_from_directory
import numpy as np
from numba import jit

app = Flask(__name__, static_folder='.', static_url_path='')

GRID_SIZE = 10
# Directions for Odd-Q Offset Coordinates (Flat Topped)
# Even cols (c%2 == 0):
#   N (0, -1), NE (1, -1), SE (1, 0), S (0, 1), SW (-1, 0), NW (-1, -1)
# Odd cols (c%2 == 1):
#   N (0, -1), NE (1, 0), SE (1, 1), S (0, 1), SW (-1, 1), NW (-1, 0)

# Direction Indices:
# 0: North
# 1: NE
# 2: SE
# 3: South
# 4: SW
# 5: NW

EVEN_COL_DIRS = [
    (0, -1),  # 0: N
    (1, -1),  # 1: NE
    (1, 0),   # 2: SE
    (0, 1),   # 3: S
    (-1, 0),  # 4: SW
    (-1, -1)  # 5: NW
]

ODD_COL_DIRS = [
    (0, -1),  # 0: N
    (1, 0),   # 1: NE
    (1, 1),   # 2: SE
    (0, 1),   # 3: S
    (-1, 1),  # 4: SW
    (-1, 0)   # 5: NW
]

@jit(nopython=True, cache=True)
def _find_loops_numba(cells_array, neighbor_table, size):
    """Numba-optimized core loop finding logic"""
    visited = np.zeros((size, size), dtype=np.bool_)

    # Store all loops as list of coordinate arrays
    # We can't return a list of lists directly from nopython mode easily if they are irregular
    # So we'll return a list of arrays, where each array is a loop
    # Numba supports lists of arrays in nopython mode
    all_loops = []

    for start_c in range(size):
        for start_r in range(size):
            if visited[start_c, start_r]:
                continue

            # Pre-allocate loop storage
            # Max loop size is size*size
            loop_coords = np.empty((size * size, 2), dtype=np.int16)
            loop_len = 0

            curr_c, curr_r = start_c, start_r
            prev_c, prev_r = np.int16(-1), np.int16(-1)

            # Traverse loop
            # Use a safe upper bound for iterations to avoid infinite loops in case of bugs
            for _ in range(size * size + 1):
                # Check termination
                if visited[curr_c, curr_r]:
                    if curr_c == start_c and curr_r == start_r and loop_len > 0:
                        break  # Completed loop
                    else:
                        loop_len = 0  # Hit another loop or merged into existing path
                        break

                # Mark visited and record
                visited[curr_c, curr_r] = True
                loop_coords[loop_len, 0] = curr_c
                loop_coords[loop_len, 1] = curr_r
                loop_len += 1

                # Extract doors from bit flags
                bits = cells_array[curr_c, curr_r]
                doors = np.empty(6, dtype=np.int8)
                door_count = 0
                for dir_idx in range(6):
                    if bits & (1 << dir_idx):
                        doors[door_count] = dir_idx
                        door_count += 1

                if door_count == 0:
                    loop_len = 0
                    break

                # Find next cell (avoiding backtrack)
                next_c, next_r = np.int16(-1), np.int16(-1)
                
                # Default to first door
                found_next = False
                
                for i in range(door_count):
                    dir_idx = doors[i]
                    nc = np.int16(neighbor_table[curr_c, curr_r, dir_idx, 0])
                    nr = np.int16(neighbor_table[curr_c, curr_r, dir_idx, 1])

                    # Skip if this is where we came from
                    if prev_c >= 0 and nc == prev_c and nr == prev_r:
                        continue

                    next_c, next_r = nc, nr
                    found_next = True
                    break
                
                if not found_next:
                     loop_len = 0
                     break

                prev_c, prev_r = curr_c, curr_r
                curr_c, curr_r = next_c, next_r

            # Store valid loop
            if loop_len > 0:
                # We must copy the slice to a new array to store it
                all_loops.append(loop_coords[:loop_len].copy())

    return all_loops

class HexGrid:
    def __init__(self, size):
        self.size = size

        # Phase 2A: Parallel backend implementation
        # OLD: Dict-based (Phase 1)
        self.cells_dict = {} # Key: (col, row), Value: list of doors
        # NEW: Array-based (Phase 2A) - 6 bits for 6 door directions
        self.cells_array = np.zeros((size, size), dtype=np.uint8)
        # Feature flag to switch backends (True = use array backend)
        # Array backend: ~10-20% slower but ~30% memory savings
        # Dict backend: Faster for degree-2 graphs, more memory
        # Keeping dict backend for best performance
        self._use_array = True

        # Precompute neighbor lookup table for performance
        # Shape: (size, size, 6, 2) -> neighbor coords for each cell and direction
        self.neighbor_table = np.zeros((size, size, 6, 2), dtype=np.int16)
        self._init_neighbor_table()

        if self._use_array:
             # Warmup Numba compilation
             _find_loops_numba(self.cells_array, self.neighbor_table, self.size)

        # Cache for JSON serialization
        self._cached_dict = None
        self._dict_dirty = True

        self.reset_to_organized()

    @property
    def cells(self):
        """Backward compatibility property - returns active backend"""
        return self.cells_dict if not self._use_array else self._build_dict_from_array()

    def _build_dict_from_array(self):
        """Convert array backend to dict format"""
        result = {}
        for c in range(self.size):
            for r in range(self.size):
                doors = []
                for dir_idx in range(6):
                    if self.cells_array[c, r] & (1 << dir_idx):
                        doors.append(dir_idx)
                result[(c, r)] = doors
        return result

    def reset_to_organized(self, pattern="vertical"):
        # Reset both backends
        self.cells_dict = {}
        self.cells_array.fill(0)

        if pattern == "vertical":
            self._init_vertical()
        elif pattern == "diagonal_1":
            self._init_diagonal_1()
        elif pattern == "diagonal_2":
            self._init_diagonal_2()
        elif pattern == "concentric":
            self._init_concentric()
        else:
            self._init_vertical() # Fallback

        self._dict_dirty = True

    def _init_vertical(self):
        """Vertical lines (North-South)"""
        for c in range(self.size):
            for r in range(self.size):
                # Vertical connections: 0 (North) and 3 (South)
                self.cells_dict[(c, r)] = [0, 3]
                self.cells_array[c, r] = (1 << 0) | (1 << 3)

    def _init_diagonal_1(self):
        """Diagonal lines (NE-SW)"""
        # Directions: 1 (NE) and 4 (SW)
        for c in range(self.size):
            for r in range(self.size):
                self.cells_dict[(c, r)] = [1, 4]
                self.cells_array[c, r] = (1 << 1) | (1 << 4)

    def _init_diagonal_2(self):
        """Diagonal lines (NW-SE)"""
        # Directions: 2 (SE) and 5 (NW)
        # Note: "SE" is direction 2, "NW" is direction 5
        for c in range(self.size):
            for r in range(self.size):
                self.cells_dict[(c, r)] = [2, 5]
                self.cells_array[c, r] = (1 << 2) | (1 << 5)

    def _init_concentric(self):
        """Zig-Zag / Waves (Alternating Columns)"""
        # Pattern:
        # Even Cols: [1, 5] (NE, NW)
        # Odd Cols: [2, 4] (SE, SW)
        # Exception: If N is Odd, the last column (N-1, Even) must bridge to Col 0.
        # It uses [2, 5] (SE, NW) to connect N-2(Odd) -> N-1 -> 0(Even).
        
        for c in range(self.size):
            dirs = []
            if self.size % 2 != 0 and c == self.size - 1:
                # Last column for Odd N
                dirs = [2, 5]
            elif c % 2 == 0:
                # Even columns
                dirs = [1, 5]
            else:
                # Odd columns
                dirs = [2, 4]
                
            for r in range(self.size):
                self.cells_dict[(c, r)] = dirs
                self.cells_array[c, r] = (1 << dirs[0]) | (1 << dirs[1])

    def _init_neighbor_table(self):
        """Precompute all neighbor coordinates for fast lookup"""
        for c in range(self.size):
            for r in range(self.size):
                dirs = EVEN_COL_DIRS if c % 2 == 0 else ODD_COL_DIRS
                for dir_idx, (dc, dr) in enumerate(dirs):
                    nc = c + dc
                    nr = r + dr
                    # Apply wrapping
                    wc = ((nc % self.size) + self.size) % self.size
                    wr = ((nr % self.size) + self.size) % self.size
                    self.neighbor_table[c, r, dir_idx, 0] = wc
                    self.neighbor_table[c, r, dir_idx, 1] = wr

    def get_cell_doors(self, c, r):
        if self._use_array:
            return self._get_cell_doors_array(c, r)
        wc = ((c % self.size) + self.size) % self.size
        wr = ((r % self.size) + self.size) % self.size
        return self.cells_dict.get((wc, wr), [])

    def _get_cell_doors_array(self, c, r):
        """Array backend: Extract doors from bit flags"""
        wc = ((c % self.size) + self.size) % self.size
        wr = ((r % self.size) + self.size) % self.size
        doors = []
        bits = self.cells_array[wc, wr]
        for dir_idx in range(6):
            if bits & (1 << dir_idx):
                doors.append(dir_idx)
        return doors

    def get_neighbor_coords(self, c, r, dir_idx):
        """Fast neighbor lookup using precomputed table"""
        return int(self.neighbor_table[c, r, dir_idx, 0]), int(self.neighbor_table[c, r, dir_idx, 1])

    def has_connection(self, c, r, dir_idx):
        if self._use_array:
            return self._has_connection_array(c, r, dir_idx)
        doors = self.get_cell_doors(c, r)
        return dir_idx in doors

    def _has_connection_array(self, c, r, dir_idx):
        """Array backend: Check bit flag"""
        wc = ((c % self.size) + self.size) % self.size
        wr = ((r % self.size) + self.size) % self.size
        return bool(self.cells_array[wc, wr] & (1 << dir_idx))

    def add_connection(self, c, r, dir_idx):
        if self._use_array:
            self._add_connection_array(c, r, dir_idx)
            return

        doors = self.get_cell_doors(c, r)
        if dir_idx not in doors:
            doors.append(dir_idx)
            # Symmetric
            nc, nr = self.get_neighbor_coords(c, r, dir_idx)
            opp_dir = (dir_idx + 3) % 6
            n_doors = self.get_cell_doors(nc, nr)
            if opp_dir not in n_doors:
                n_doors.append(opp_dir)
            self._dict_dirty = True

    def _add_connection_array(self, c, r, dir_idx):
        """Array backend: Set bit flags symmetrically"""
        wc = ((c % self.size) + self.size) % self.size
        wr = ((r % self.size) + self.size) % self.size

        # Set bit in current cell
        self.cells_array[wc, wr] |= (1 << dir_idx)

        # Symmetric: set bit in neighbor
        nc, nr = self.get_neighbor_coords(c, r, dir_idx)
        opp_dir = (dir_idx + 3) % 6
        self.cells_array[nc, nr] |= (1 << opp_dir)

        self._dict_dirty = True

    def remove_connection(self, c, r, dir_idx):
        if self._use_array:
            self._remove_connection_array(c, r, dir_idx)
            return

        doors = self.get_cell_doors(c, r)
        if dir_idx in doors:
            doors.remove(dir_idx)
            # Symmetric
            nc, nr = self.get_neighbor_coords(c, r, dir_idx)
            opp_dir = (dir_idx + 3) % 6
            n_doors = self.get_cell_doors(nc, nr)
            if opp_dir in n_doors:
                n_doors.remove(opp_dir)
            self._dict_dirty = True

    def _remove_connection_array(self, c, r, dir_idx):
        """Array backend: Clear bit flags symmetrically"""
        wc = ((c % self.size) + self.size) % self.size
        wr = ((r % self.size) + self.size) % self.size

        # Clear bit in current cell using XOR with 0xFF
        mask = np.uint8(0xFF ^ (1 << dir_idx))
        self.cells_array[wc, wr] &= mask

        # Symmetric: clear bit in neighbor
        nc, nr = self.get_neighbor_coords(c, r, dir_idx)
        opp_dir = (dir_idx + 3) % 6
        mask_opp = np.uint8(0xFF ^ (1 << opp_dir))
        self.cells_array[nc, nr] &= mask_opp

        self._dict_dirty = True

    def get_direction(self, c1, r1, c2, r2):
        # Check all 6 neighbors of (c1, r1)
        for i in range(6):
            nc, nr = self.get_neighbor_coords(c1, r1, i)
            if nc == c2 and nr == r2:
                return i
        return -1

    def scramble(self, steps=1):
        # Phase 3 optimization: Pre-generate all random numbers with NumPy
        max_attempts = steps * 20

        # Generate batch of random cell coordinates (col, row for cells u and x)
        # Shape: (max_attempts, 4) = [uc, ur, xc, xr] for each attempt
        random_cells = np.random.randint(0, self.size, size=(max_attempts, 4), dtype=np.int16)

        # Generate random direction indices (for selecting which door to use)
        # Shape: (max_attempts, 2) = [dir_idx_u, dir_idx_x] for each attempt
        random_dir_indices = np.random.randint(0, 2, size=(max_attempts, 2), dtype=np.uint8)

        swaps = 0
        for attempt in range(max_attempts):
            if swaps >= steps:
                break
            if self.perform_swap_vectorized(random_cells[attempt], random_dir_indices[attempt]):
                swaps += 1
        return swaps

    def perform_swap_vectorized(self, cell_coords, dir_indices):
        """Vectorized swap using pre-generated random numbers"""
        # Unpack pre-generated random coordinates (convert to Python int for speed)
        uc = int(cell_coords[0])
        ur = int(cell_coords[1])
        xc = int(cell_coords[2])
        xr = int(cell_coords[3])

        u_doors = self.get_cell_doors(uc, ur)
        if not u_doors: return False

        # Use pre-generated random index to select door (modulo to handle varying door counts)
        dir_uv = u_doors[int(dir_indices[0]) % len(u_doors)]
        vc, vr = self.get_neighbor_coords(uc, ur, dir_uv)

        x_doors = self.get_cell_doors(xc, xr)
        if not x_doors: return False

        # Use pre-generated random index to select door
        dir_xy = x_doors[int(dir_indices[1]) % len(x_doors)]
        yc, yr = self.get_neighbor_coords(xc, xr, dir_xy)
        
        # Ensure distinct vertices
        u = (uc, ur)
        v = (vc, vr)
        x = (xc, xr)
        y = (yc, yr)
        
        if len({u, v, x, y}) < 4:
            return False

        # Try pairing (u, x) and (v, y)
        dir_ux = self.get_direction(uc, ur, xc, xr)
        dir_vy = self.get_direction(vc, vr, yc, yr)
        
        if dir_ux != -1 and dir_vy != -1:
            if not self.has_connection(uc, ur, dir_ux) and not self.has_connection(vc, vr, dir_vy):
                self.remove_connection(uc, ur, dir_uv)
                self.remove_connection(xc, xr, dir_xy)
                self.add_connection(uc, ur, dir_ux)
                self.add_connection(vc, vr, dir_vy)
                return True

        # Try pairing (u, y) and (v, x)
        dir_uy = self.get_direction(uc, ur, yc, yr)
        dir_vx = self.get_direction(vc, vr, xc, xr)
        
        if dir_uy != -1 and dir_vx != -1:
            if not self.has_connection(uc, ur, dir_uy) and not self.has_connection(vc, vr, dir_vx):
                self.remove_connection(uc, ur, dir_uv)
                self.remove_connection(xc, xr, dir_xy)
                self.add_connection(uc, ur, dir_uy)
                self.add_connection(vc, vr, dir_vx)
                return True
                
        return False
    
    def find_loops(self):
        if self._use_array:
            # Call Numba-optimized function
            loops_numba = _find_loops_numba(
                self.cells_array,
                self.neighbor_table,
                self.size
            )

            # Convert to JSON-compatible format
            loops = []
            for loop_coords in loops_numba:
                loop = [{"q": int(loop_coords[i, 0]), "r": int(loop_coords[i, 1])}
                        for i in range(len(loop_coords))]
                loops.append(loop)
            return loops

        # Phase 3 optimization: NumPy boolean array for O(1) visited checks
        visited = np.zeros((self.size, self.size), dtype=bool)
        loops = []

        # Pre-allocate loop storage (worst case: all cells in one loop)
        max_loop_size = self.size * self.size
        loop_coords = np.zeros((max_loop_size, 2), dtype=np.int16)

        for c in range(self.size):
            for r in range(self.size):
                if visited[c, r]:
                    continue

                loop_idx = 0
                curr_c, curr_r = c, r
                prev_c, prev_r = -1, -1

                while True:
                    # Check if already visited (except for starting cell on first iteration)
                    if visited[curr_c, curr_r]:
                        if curr_c == c and curr_r == r and loop_idx > 0:
                            break  # Completed the loop
                        else:
                            break  # Hit another loop

                    visited[curr_c, curr_r] = True
                    loop_coords[loop_idx, 0] = curr_c
                    loop_coords[loop_idx, 1] = curr_r
                    loop_idx += 1

                    doors = self.get_cell_doors(curr_c, curr_r)
                    if not doors: break

                    next_dir = doors[0]
                    nc, nr = self.get_neighbor_coords(curr_c, curr_r, next_dir)

                    # Avoid backtracking
                    if prev_c != -1 and nc == prev_c and nr == prev_r:
                        if len(doors) > 1:
                            next_dir = doors[1]
                            nc, nr = self.get_neighbor_coords(curr_c, curr_r, next_dir)
                        else:
                            break

                    prev_c, prev_r = curr_c, curr_r
                    curr_c, curr_r = nc, nr

                # Convert to list format for JSON compatibility
                if loop_idx > 0:
                    loop = [{"q": int(loop_coords[i, 0]), "r": int(loop_coords[i, 1])}
                            for i in range(loop_idx)]
                    loops.append(loop)

        return loops

    def to_dict(self):
        """Convert grid to dict format with caching"""
        if not self._dict_dirty and self._cached_dict is not None:
            return self._cached_dict

        if self._use_array:
            # Phase 3 optimization: Vectorized bit extraction with NumPy broadcasting
            # Create mask for each direction: shape (6, 1, 1) for broadcasting
            dir_masks = np.array([1 << i for i in range(6)], dtype=np.uint8)[:, None, None]

            # Broadcasting: (6, size, size) & (6, 1, 1) -> (6, size, size)
            # has_door[dir, c, r] = True if cell (c,r) has door in direction dir
            has_door = (self.cells_array[None, :, :] & dir_masks) != 0

            # Build dict with vectorized door extraction
            self._cached_dict = {}
            for c in range(self.size):
                for r in range(self.size):
                    # Extract doors for this cell using boolean indexing
                    doors = np.where(has_door[:, c, r])[0].tolist()
                    self._cached_dict[f"{c},{r}"] = {"q": c, "r": r, "doors": doors}
        else:
            # Build from dict backend (already optimal)
            self._cached_dict = {f"{k[0]},{k[1]}": {"q": k[0], "r": k[1], "doors": v}
                                 for k, v in self.cells_dict.items()}

        self._dict_dirty = False
        return self._cached_dict

grid = HexGrid(GRID_SIZE)

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/state')
def get_state():
    return jsonify({
        "cells": grid.to_dict(),
        "loops": grid.find_loops(),
        "size": grid.size
    })

@app.route('/scramble', methods=['POST'])
def scramble():
    data = request.json
    steps = data.get('steps', 1)
    swaps = grid.scramble(steps)
    return jsonify({
        "swaps": swaps, 
        "cells": grid.to_dict(),
        "loops": grid.find_loops(),
        "size": grid.size
    })

@app.route('/reset', methods=['POST'])
def reset():
    data = request.get_json() or {}
    new_size = data.get('size')
    
    if new_size:
        try:
            new_size = int(new_size)
            # Clamp size to safe limits
            new_size = max(5, min(200, new_size))
            if new_size != grid.size:
                grid.size = new_size
                # Reinitialize arrays for new size
                grid.neighbor_table = np.zeros((new_size, new_size, 6, 2), dtype=np.int16)
                grid.cells_array = np.zeros((new_size, new_size), dtype=np.uint8)
                grid._init_neighbor_table()
        except ValueError:
            pass # Keep current size if invalid
            
    grid.reset_to_organized(pattern=data.get('pattern', 'vertical'))
    return jsonify({
        "cells": grid.to_dict(),
        "loops": grid.find_loops(),
        "size": grid.size
    })

if __name__ == '__main__':
    app.run(port=3000, debug=True)
