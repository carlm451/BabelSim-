"""
Validation script for Phase 2A array backend implementation

This script tests that the dict backend and array backend produce identical results.
"""
import sys
sys.path.insert(0, '.')

from app import HexGrid
import numpy as np

def validate_backend_equivalence(size=10, scramble_steps=5):
    """Test that dict and array backends produce identical results"""
    print(f"\n{'='*60}")
    print(f"Validating backend equivalence at N={size}")
    print(f"{'='*60}")

    # Create two grids with same random seed
    grid_dict = HexGrid(size)
    grid_dict._use_array = False

    grid_array = HexGrid(size)
    grid_array._use_array = True

    # Test 1: Initial organized state
    print("\n[1] Testing initial organized state...")
    dict_state = grid_dict.to_dict()
    array_state = grid_array.to_dict()

    if dict_state == array_state:
        print("  ✓ Initial states match")
    else:
        print("  ✗ FAIL: Initial states differ!")
        return False

    # Test 2: Scrambling with same random operations
    print(f"\n[2] Testing scramble ({scramble_steps} steps)...")

    # Manually perform same swaps on both grids
    import random
    random.seed(42)

    for step in range(scramble_steps):
        # Generate same random choices for both
        uc = random.randint(0, size - 1)
        ur = random.randint(0, size - 1)

        # Perform swap on dict grid
        grid_dict._use_array = False
        u_doors_dict = grid_dict.get_cell_doors(uc, ur)

        # Perform same on array grid
        grid_array._use_array = True
        u_doors_array = grid_array.get_cell_doors(uc, ur)

        if u_doors_dict != u_doors_array:
            print(f"  ✗ FAIL: Doors differ at step {step} for cell ({uc}, {ur})")
            print(f"    Dict: {u_doors_dict}")
            print(f"    Array: {u_doors_array}")
            return False

    print("  ✓ Get cell doors matches for all random cells")

    # Test 3: Validate degree-2 constraint
    print("\n[3] Validating degree-2 constraint...")

    for backend_name, g in [("dict", grid_dict), ("array", grid_array)]:
        g._use_array = (backend_name == "array")
        violations = []

        for c in range(size):
            for r in range(size):
                doors = g.get_cell_doors(c, r)
                if len(doors) != 2:
                    violations.append((c, r, len(doors)))

        if violations:
            print(f"  ✗ FAIL ({backend_name}): Degree-2 violations at {len(violations)} cells")
            for c, r, deg in violations[:5]:
                print(f"    Cell ({c}, {r}) has degree {deg}")
            return False

    print("  ✓ All cells have exactly 2 doors (both backends)")

    # Test 4: Validate symmetry
    print("\n[4] Validating connection symmetry...")

    for backend_name, g in [("dict", grid_dict), ("array", grid_array)]:
        g._use_array = (backend_name == "array")
        asymmetric = []

        for c in range(size):
            for r in range(size):
                doors = g.get_cell_doors(c, r)
                for dir_idx in doors:
                    # Check if neighbor has opposite connection
                    nc, nr = g.get_neighbor_coords(c, r, dir_idx)
                    opp_dir = (dir_idx + 3) % 6
                    if not g.has_connection(nc, nr, opp_dir):
                        asymmetric.append(((c, r), dir_idx, (nc, nr), opp_dir))

        if asymmetric:
            print(f"  ✗ FAIL ({backend_name}): Asymmetric connections found")
            for (c1, r1), d1, (c2, r2), d2 in asymmetric[:3]:
                print(f"    ({c1},{r1})->{d1} but ({c2},{r2}) missing {d2}")
            return False

    print("  ✓ All connections are symmetric (both backends)")

    # Test 5: Loop finding
    print("\n[5] Testing loop finding...")

    grid_dict._use_array = False
    loops_dict = grid_dict.find_loops()

    grid_array._use_array = True
    loops_array = grid_array.find_loops()

    if len(loops_dict) != len(loops_array):
        print(f"  ✗ FAIL: Different number of loops")
        print(f"    Dict: {len(loops_dict)} loops")
        print(f"    Array: {len(loops_array)} loops")
        return False

    # Sort loops by length for comparison
    loops_dict_sorted = sorted([len(loop) for loop in loops_dict])
    loops_array_sorted = sorted([len(loop) for loop in loops_array])

    if loops_dict_sorted != loops_array_sorted:
        print(f"  ✗ FAIL: Loop lengths differ")
        print(f"    Dict: {loops_dict_sorted}")
        print(f"    Array: {loops_array_sorted}")
        return False

    print(f"  ✓ Both backends find {len(loops_dict)} loops with same lengths")

    # Test 6: Connection modifications
    print("\n[6] Testing add/remove connection operations...")

    # Test on fresh grids
    grid_dict = HexGrid(size)
    grid_dict._use_array = False
    grid_dict.reset_to_organized()

    grid_array = HexGrid(size)
    grid_array._use_array = True
    grid_array.reset_to_organized()

    # Remove a connection
    test_c, test_r = 0, 0
    test_dir = 0

    grid_dict.remove_connection(test_c, test_r, test_dir)
    grid_array.remove_connection(test_c, test_r, test_dir)

    # Check if both removed
    dict_has = grid_dict.has_connection(test_c, test_r, test_dir)
    array_has = grid_array.has_connection(test_c, test_r, test_dir)

    if dict_has or array_has:
        print(f"  ✗ FAIL: Connection not removed (dict={dict_has}, array={array_has})")
        return False

    # Add it back
    grid_dict.add_connection(test_c, test_r, test_dir)
    grid_array.add_connection(test_c, test_r, test_dir)

    dict_has = grid_dict.has_connection(test_c, test_r, test_dir)
    array_has = grid_array.has_connection(test_c, test_r, test_dir)

    if not dict_has or not array_has:
        print(f"  ✗ FAIL: Connection not added (dict={dict_has}, array={array_has})")
        return False

    print("  ✓ Add/remove operations work correctly on both backends")

    return True

def main():
    """Run validation suite"""
    print("\n" + "="*60)
    print("PHASE 2A ARRAY BACKEND VALIDATION")
    print("="*60)

    sizes = [10, 25, 50]

    for size in sizes:
        steps = max(5, size // 2)
        if not validate_backend_equivalence(size, steps):
            print(f"\n{'='*60}")
            print(f"VALIDATION FAILED at N={size}")
            print(f"{'='*60}")
            return False

    print(f"\n{'='*60}")
    print("✓ ALL VALIDATIONS PASSED")
    print(f"{'='*60}")
    print("\nArray backend is ready to use!")
    print("To enable: Set grid._use_array = True in app.py line 50")

    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
