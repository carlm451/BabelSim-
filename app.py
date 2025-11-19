import random
from flask import Flask, jsonify, request, send_from_directory
import numpy as np

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

class HexGrid:
    def __init__(self, size):
        self.size = size
        self.cells = {} # Key: (col, row), Value: list of doors

        # Precompute neighbor lookup table for performance
        # Shape: (size, size, 6, 2) -> neighbor coords for each cell and direction
        self.neighbor_table = np.zeros((size, size, 6, 2), dtype=np.int16)
        self._init_neighbor_table()

        # Cache for JSON serialization
        self._cached_dict = None
        self._dict_dirty = True

        self.reset_to_organized()

    def reset_to_organized(self):
        self.cells = {}
        for c in range(self.size):
            for r in range(self.size):
                # Vertical connections: 0 (North) and 3 (South)
                self.cells[(c, r)] = [0, 3]
        self._dict_dirty = True

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
        wc = ((c % self.size) + self.size) % self.size
        wr = ((r % self.size) + self.size) % self.size
        return self.cells.get((wc, wr), [])

    def get_neighbor_coords(self, c, r, dir_idx):
        """Fast neighbor lookup using precomputed table"""
        return int(self.neighbor_table[c, r, dir_idx, 0]), int(self.neighbor_table[c, r, dir_idx, 1])

    def has_connection(self, c, r, dir_idx):
        doors = self.get_cell_doors(c, r)
        return dir_idx in doors

    def add_connection(self, c, r, dir_idx):
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

    def remove_connection(self, c, r, dir_idx):
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

    def get_direction(self, c1, r1, c2, r2):
        # Check all 6 neighbors of (c1, r1)
        for i in range(6):
            nc, nr = self.get_neighbor_coords(c1, r1, i)
            if nc == c2 and nr == r2:
                return i
        return -1

    def scramble(self, steps=1):
        swaps = 0
        attempts = 0
        max_attempts = steps * 20
        
        while swaps < steps and attempts < max_attempts:
            attempts += 1
            if self.perform_swap():
                swaps += 1
        return swaps

    def perform_swap(self):
        # Pick random cell u
        uc = random.randint(0, self.size - 1)
        ur = random.randint(0, self.size - 1)
        u_doors = self.get_cell_doors(uc, ur)
        
        if not u_doors: return False
        
        # Pick random door from u to v
        dir_uv = random.choice(u_doors)
        vc, vr = self.get_neighbor_coords(uc, ur, dir_uv)
        
        # Pick random cell x
        xc = random.randint(0, self.size - 1)
        xr = random.randint(0, self.size - 1)
        x_doors = self.get_cell_doors(xc, xr)
        
        if not x_doors: return False
        
        # Pick random door from x to y
        dir_xy = random.choice(x_doors)
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
        visited = set()
        loops = []
        
        for c in range(self.size):
            for r in range(self.size):
                cell_key = (c, r)
                if cell_key in visited:
                    continue
                
                loop = []
                curr = cell_key
                prev = None
                
                while True:
                    if curr in visited and curr != cell_key:
                        break
                    if curr in visited and curr == cell_key and len(loop) > 0:
                        break
                    
                    visited.add(curr)
                    loop.append({"q": curr[0], "r": curr[1]}) # Keeping key names q/r for frontend compat for now, but values are c,r
                    
                    doors = self.get_cell_doors(curr[0], curr[1])
                    if not doors: break
                    
                    next_dir = doors[0]
                    nc, nr = self.get_neighbor_coords(curr[0], curr[1], next_dir)
                    next_cell = (nc, nr)
                    
                    if prev is not None and next_cell == prev:
                        if len(doors) > 1:
                            next_dir = doors[1]
                            nc, nr = self.get_neighbor_coords(curr[0], curr[1], next_dir)
                            next_cell = (nc, nr)
                        else:
                            break
                    
                    prev = curr
                    curr = next_cell
                
                if loop:
                    loops.append(loop)
        return loops

    def to_dict(self):
        """Convert grid to dict format with caching"""
        if not self._dict_dirty and self._cached_dict is not None:
            return self._cached_dict

        self._cached_dict = {f"{k[0]},{k[1]}": {"q": k[0], "r": k[1], "doors": v} for k, v in self.cells.items()}
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
                # Reinitialize neighbor table for new size
                grid.neighbor_table = np.zeros((new_size, new_size, 6, 2), dtype=np.int16)
                grid._init_neighbor_table()
        except ValueError:
            pass # Keep current size if invalid
            
    grid.reset_to_organized()
    return jsonify({
        "cells": grid.to_dict(),
        "loops": grid.find_loops(),
        "size": grid.size
    })

if __name__ == '__main__':
    app.run(port=3000, debug=True)
