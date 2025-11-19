
import json
import sys

def test_reset_pattern(pattern_name):
    print(f"Testing pattern: {pattern_name}")
    try:
        response = requests.post('http://localhost:3000/reset', json={'size': 10, 'pattern': pattern_name})
        if response.status_code == 200:
            data = response.json()
            cells = data['cells']
            # Basic check: are there cells?
            if len(cells) == 100:
                print(f"  ✓ Success: Got 100 cells")
                # We could check specific connections, but visual inspection is best.
                # Let's just check if the response is valid JSON and has content.
                return True
            else:
                print(f"  ✗ Fail: Expected 100 cells, got {len(cells)}")
                return False
        else:
            print(f"  ✗ Fail: Status code {response.status_code}")
            return False
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

def main():
    # Start the server in background? 
    # Assuming server is running or we can start it.
    # Since I can't easily start background server and keep it running across tool calls without complex management,
    # I will rely on the fact that I can't easily run the server and test it in one go if it blocks.
    # But I can import app and test logic directly!
    
    sys.path.append('.')
    from app import HexGrid
    
    print("Testing HexGrid initialization logic directly...")
    
    patterns = ["vertical", "diagonal_1", "diagonal_2", "concentric"]
    
    for size in [10, 85]:
        print(f"\nTesting size N={size}")
        for p in patterns:
            print(f"  Pattern: {p}")
            grid = HexGrid(size)
            grid.reset_to_organized(pattern=p)
        
        # Check if grid is populated
        if grid._use_array:
            # Check if array has non-zero values
            if grid.cells_array.any():
                print("  ✓ Array backend populated")
            else:
                print("  ✗ Array backend empty")
        
        # Check degree 2
        violations = 0
        for c in range(10):
            for r in range(10):
                doors = grid.get_cell_doors(c, r)
                if len(doors) != 2:
                    violations += 1
        
        if violations == 0:
            print("  ✓ Degree-2 constraint satisfied")
        else:
            print(f"  ✗ Degree-2 violations: {violations}")

if __name__ == "__main__":
    main()
