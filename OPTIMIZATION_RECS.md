# Optimization Recommendations for Babel Simulation

**Goal**: Achieve 30+ FPS at N=150 (currently 20 FPS / 50.2ms, target: ~33ms)

---

## Current Performance Baseline

**Phase 1-3 Complete** (as of latest benchmark):
- Phase 1: Neighbor table precomputation + JSON caching
- Phase 2A: NumPy array backend (available but not default)
- Phase 3: NumPy vectorization optimizations

**N=150 Performance Breakdown**:
- **Total**: 50.2ms (20 FPS)
- **Loop finding**: 24.1ms (48%) ← BIGGEST BOTTLENECK
- **Serialization**: 13.2ms (26%)
- **Scramble**: 12.9ms (26%)

**Required improvement**: Need to reduce total time by ~17ms (34%) to hit 33ms target

---

## Priority 1: Numba JIT Compilation on `find_loops()` ⭐️

**Impact**: HIGH | **Effort**: MEDIUM | **Expected Reduction**: 12-18ms

### Why This Works
Numba compiles Python functions to optimized machine code using LLVM. Loop finding is the perfect candidate:
- Pure numerical operations (array indexing, bitwise ops)
- Tight inner loops
- Already uses NumPy arrays
- Minimal Python object overhead needed

### Expected Performance
- **Current**: 24.1ms
- **After Numba**: 6-12ms (2-4x speedup)
- **Net gain**: 12-18ms reduction
- **Projected total**: 32-38ms (26-31 FPS) ✓ **Target reached!**

### Implementation Strategy

#### Step 1: Switch to Array Backend Exclusively
Since Numba works best with NumPy arrays, enable array backend:

```python
# In app.py line 53:
self._use_array = True  # Changed from False
```

**Note**: This may cause a temporary 10-20% slowdown before Numba is applied.

#### Step 2: Extract Core Logic to Numba Function

```python
from numba import jit
import numpy as np

@jit(nopython=True, cache=True)
def _find_loops_numba(cells_array, neighbor_table, size):
    """Numba-optimized core loop finding logic"""
    visited = np.zeros((size, size), dtype=np.bool_)

    # Store all loops as list of coordinate arrays
    all_loops = []

    for start_c in range(size):
        for start_r in range(size):
            if visited[start_c, start_r]:
                continue

            # Pre-allocate loop storage
            loop_coords = np.empty((size * size, 2), dtype=np.int16)
            loop_len = 0

            curr_c, curr_r = start_c, start_r
            prev_c, prev_r = np.int16(-1), np.int16(-1)

            # Traverse loop
            for _ in range(size * size + 1):  # Safety limit
                # Check termination
                if visited[curr_c, curr_r]:
                    if curr_c == start_c and curr_r == start_r and loop_len > 0:
                        break  # Completed loop
                    else:
                        loop_len = 0  # Hit another loop
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
                for i in range(door_count):
                    dir_idx = doors[i]
                    nc = np.int16(neighbor_table[curr_c, curr_r, dir_idx, 0])
                    nr = np.int16(neighbor_table[curr_c, curr_r, dir_idx, 1])

                    # Skip if this is where we came from
                    if prev_c >= 0 and nc == prev_c and nr == prev_r:
                        continue

                    next_c, next_r = nc, nr
                    break

                if next_c < 0:  # No valid next cell
                    loop_len = 0
                    break

                prev_c, prev_r = curr_c, curr_r
                curr_c, curr_r = next_c, next_r

            # Store valid loop
            if loop_len > 0:
                all_loops.append(loop_coords[:loop_len].copy())

    return all_loops


def find_loops(self):
    """Wrapper that calls Numba version and formats output"""
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
```

#### Step 3: Test and Benchmark

```bash
# Run validation
python validate_array_backend.py

# Run benchmark
python benchmark.py
```

### Potential Issues and Solutions

**Issue 1: First call is slow (JIT compilation overhead)**
- **Solution**: Warmup call during initialization
```python
# In HexGrid.__init__():
if self._use_array:
    # Warmup Numba compilation
    _find_loops_numba(self.cells_array, self.neighbor_table, self.size)
```

**Issue 2: Numba doesn't support Python lists well**
- **Solution**: Use NumPy arrays throughout, convert at the end
- Already handled in example above

**Issue 3: Debugging Numba errors is hard**
- **Solution**: Test with `@jit(nopython=False)` first for better error messages
- Once working, switch to `nopython=True` for maximum speed

### Estimated Timeline
- **Implementation**: 2-3 hours
- **Testing**: 1 hour
- **Total**: 3-4 hours

---

## Priority 2: Pre-Extract All Doors (Quick Win)

**Impact**: MEDIUM | **Effort**: LOW | **Expected Reduction**: 2-4ms

### The Optimization
Currently, `find_loops()` extracts doors from bit flags inside the tight loop. Pre-extract once:

```python
def find_loops(self):
    # Pre-extract all doors using vectorization
    dir_masks = np.array([1 << i for i in range(6)], dtype=np.uint8)[:, None, None]
    has_door = (self.cells_array[None, :, :] & dir_masks) != 0

    # Build door list for each cell
    all_doors = {}
    for c in range(self.size):
        for r in range(self.size):
            doors = np.where(has_door[:, c, r])[0]
            all_doors[(c, r)] = doors

    # Use pre-extracted doors in loop traversal
    # ... rest of logic
```

### Estimated Timeline
- **30 minutes**

---

## Priority 3: Numba-Optimize Scramble Operations

**Impact**: MEDIUM | **Effort**: MEDIUM | **Expected Reduction**: 4-8ms

### Why Optimize Scramble
Currently at 12.9ms (26% of total time). Numba can optimize:
- Random number generation (already batched)
- Swap validation logic
- Connection modifications

### Implementation

```python
@jit(nopython=True, cache=True)
def _try_swap_numba(cells_array, neighbor_table, size,
                    uc, ur, xc, xr, dir_u_idx, dir_x_idx):
    """Numba-optimized swap attempt"""

    # Extract doors for u
    u_bits = cells_array[uc, ur]
    u_doors = np.empty(6, dtype=np.int8)
    u_count = 0
    for i in range(6):
        if u_bits & (1 << i):
            u_doors[u_count] = i
            u_count += 1

    if u_count == 0:
        return False

    dir_uv = u_doors[dir_u_idx % u_count]
    vc = int(neighbor_table[uc, ur, dir_uv, 0])
    vr = int(neighbor_table[uc, ur, dir_uv, 1])

    # Similar for x, y...
    # [Rest of swap logic - see full example in research notes]

    return success


@jit(nopython=True, cache=True)
def _scramble_numba(cells_array, neighbor_table, size, steps):
    """Numba-optimized scramble"""
    max_attempts = steps * 20

    # Generate random numbers
    random_cells = np.random.randint(0, size, size=(max_attempts, 4))
    random_dirs = np.random.randint(0, 2, size=(max_attempts, 2))

    swaps = 0
    for attempt in range(max_attempts):
        if swaps >= steps:
            break

        if _try_swap_numba(cells_array, neighbor_table, size,
                          random_cells[attempt, 0],
                          random_cells[attempt, 1],
                          random_cells[attempt, 2],
                          random_cells[attempt, 3],
                          random_dirs[attempt, 0],
                          random_dirs[attempt, 1]):
            swaps += 1

    return swaps


def scramble(self, steps=1):
    """Public method"""
    swaps = _scramble_numba(self.cells_array, self.neighbor_table,
                           self.size, steps)
    self._dict_dirty = True
    return swaps
```

### Expected Results
- **Current**: 12.9ms
- **After Numba**: 5-8ms
- **Gain**: 5-8ms

### Estimated Timeline
- **2-3 hours**

---

## Priority 4: Parallel Loop Finding (Advanced)

**Impact**: MEDIUM-HIGH | **Effort**: HIGH | **Expected Reduction**: 6-12ms (on multi-core)

### The Idea
Numba supports parallel execution with `prange`:

```python
@jit(nopython=True, parallel=True, cache=True)
def _find_loops_parallel(cells_array, neighbor_table, size):
    visited = np.zeros((size, size), dtype=np.bool_)

    # Parallel outer loop
    for start_c in prange(size):  # prange instead of range
        for start_r in range(size):
            # ... loop finding logic
```

### Challenges
- **Race conditions**: Multiple threads marking `visited` simultaneously
- **Synchronization**: Need thread-safe data structures
- **Diminishing returns**: Limited by Amdahl's law

### Recommendation
**Only attempt if Priority 1-3 don't reach 30 FPS**

### Estimated Timeline
- **4-6 hours** (with debugging)

---

## Alternative Approaches (Lower Priority)

### Option A: Cython Compilation
- **Pros**: Similar speedup to Numba, more control
- **Cons**: Requires build step, more complex
- **Verdict**: Try Numba first (easier)

### Option B: Algorithmic Changes
- **Union-Find for connected components**: Doesn't help - we need ordered loops, not just components
- **Simplified traversal**: Already near-optimal
- **Verdict**: Current algorithm is good

### Option C: PyPy
- **Cons**: Slow with NumPy (which we use heavily)
- **Verdict**: Not recommended

### Option D: C Extensions
- **Cons**: Very high complexity
- **Verdict**: Overkill - Numba should suffice

---

## Recommended Implementation Path

### Phase 4A: Numba Loop Finding (2-3 hours)
1. Switch to array backend: `self._use_array = True`
2. Implement `_find_loops_numba()` as shown above
3. Test with `validate_array_backend.py`
4. Benchmark - **expecting 32-38ms (26-31 FPS)** ✓

**If this reaches 30 FPS, STOP HERE!**

### Phase 4B: Numba Scramble (2-3 hours, if needed)
1. Implement `_scramble_numba()` and `_try_swap_numba()`
2. Test and benchmark
3. **Expecting 25-32ms (31-40 FPS)**

### Phase 4C: Further Optimizations (optional)
- Pre-extract doors
- Parallel loop finding
- Only if still not hitting target

---

## Expected Timeline to 30 FPS

### Conservative Estimate
| Phase | Time (ms) | FPS | Development Time |
|-------|-----------|-----|------------------|
| **Current (Phase 3)** | 50.2 | 20 | - |
| Enable array backend | 52 | 19 | 5 min |
| **Phase 4A: Numba loops** | **35** | **28** | 3 hours |
| **Phase 4B: Numba scramble** | **28** | **36** ✓ | 2 hours |

### Aggressive Estimate
| Phase | Time (ms) | FPS | Development Time |
|-------|-----------|-----|------------------|
| **Phase 4A: Numba loops** | **32** | **31** ✓ | 3 hours |
| **Phase 4B: Numba scramble** | **25** | **40** | 2 hours |
| Phase 4C: Parallel | 18 | 55 | 6 hours |

---

## Installation Requirements

```bash
# Numba is already in requirements.txt
source venv/bin/activate
pip install numba  # If not already installed
```

**Note**: First Numba call will have ~1-2s compilation overhead. This is normal and only happens once (or on first call after code changes).

---

## Testing Strategy

### Validation Checklist
1. ✓ All loops found (same count as before)
2. ✓ Loop lengths match
3. ✓ Degree-2 constraint maintained
4. ✓ Connection symmetry preserved
5. ✓ Performance improvement measured

### Benchmark Process
```bash
# Before optimization
python benchmark.py > before.txt

# After optimization
python benchmark.py > after.txt

# Compare
diff before.txt after.txt
```

### Rollback Plan
If Numba causes issues:
1. Keep original Python implementation as `find_loops_python()`
2. Add feature flag: `USE_NUMBA = True`
3. Can switch back instantly if needed

---

## Risk Assessment

### Low Risk ✅
- **Numba loop finding**: Straightforward numerical code, easy to validate
- **Array backend**: Already implemented and tested

### Medium Risk ⚠️
- **Numba scramble**: More complex logic, need careful testing
- **First-call overhead**: May need warmup strategy

### High Risk 🔴
- **Parallel execution**: Race conditions, complex debugging
- **Only attempt if other methods insufficient**

---

## Success Criteria

### Minimum Viable Performance
- **N=150 at 30 FPS** (33ms or better)
- All validation tests pass
- No regressions at smaller grid sizes

### Stretch Goals
- N=150 at 40+ FPS (25ms or better)
- N=200 at 15+ FPS (real-time at larger sizes)
- Smooth animation with minimal frame time variance

---

## Key Takeaway

**Priority 1 (Numba on loop finding) alone should get you to 30 FPS.**

The implementation is straightforward:
- ✅ NumPy arrays already in place
- ✅ Algorithm is Numba-friendly
- ✅ Expected 2-4x speedup on biggest bottleneck
- ✅ Low risk with high reward

Start there, measure results, then decide if further optimization is needed.

**Estimated total development time to 30 FPS: 3-5 hours**

---

## References

- Numba documentation: https://numba.pydata.org/
- Numba performance tips: https://numba.pydata.org/numba-doc/dev/user/performance-tips.html
- Current benchmark script: `benchmark.py`
- Validation script: `validate_array_backend.py`

---

*Document created after Phase 3 completion (1.37x speedup achieved)*
*Next milestone: 30 FPS at N=150 via Numba JIT compilation*
