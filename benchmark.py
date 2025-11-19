"""
Benchmark script to test performance improvements

Run this to compare performance at different grid sizes.
"""
import time
import sys
sys.path.insert(0, '.')

from app import HexGrid

def benchmark_grid(size, scramble_steps):
    """Benchmark a single grid size"""
    print(f"\n{'='*60}")
    print(f"Benchmarking N={size} (Total cells: {size*size})")
    print(f"{'='*60}")

    # Initialize grid
    start = time.perf_counter()
    grid = HexGrid(size)
    init_time = time.perf_counter() - start
    print(f"  Init time: {init_time*1000:.2f} ms")

    # Test scramble performance
    start = time.perf_counter()
    swaps = grid.scramble(scramble_steps)
    scramble_time = time.perf_counter() - start
    print(f"  Scramble ({scramble_steps} steps): {scramble_time*1000:.2f} ms")
    print(f"    Successful swaps: {swaps}")
    print(f"    Time per swap: {scramble_time*1000/swaps if swaps > 0 else 0:.3f} ms")

    # Test loop finding
    start = time.perf_counter()
    loops = grid.find_loops()
    loop_time = time.perf_counter() - start
    print(f"  Loop finding: {loop_time*1000:.2f} ms")
    print(f"    Loops found: {len(loops)}")

    # Test serialization
    start = time.perf_counter()
    data = grid.to_dict()
    serialize_time = time.perf_counter() - start
    print(f"  Serialization (first): {serialize_time*1000:.2f} ms")

    # Test cached serialization
    start = time.perf_counter()
    data = grid.to_dict()
    cached_time = time.perf_counter() - start
    print(f"  Serialization (cached): {cached_time*1000:.2f} ms")
    print(f"    Cache speedup: {serialize_time/cached_time if cached_time > 0 else 'inf'}x")

    # Total time
    total_time = scramble_time + loop_time + serialize_time
    print(f"\n  TOTAL REQUEST TIME: {total_time*1000:.2f} ms")

    return {
        'size': size,
        'scramble_ms': scramble_time * 1000,
        'loop_find_ms': loop_time * 1000,
        'serialize_ms': serialize_time * 1000,
        'total_ms': total_time * 1000
    }

def main():
    """Run benchmarks for various grid sizes"""
    print("\n" + "="*60)
    print("BABEL SIMULATION PERFORMANCE BENCHMARK")
    print("Phase 1 Optimizations: Neighbor table + JSON caching")
    print("="*60)

    sizes = [10, 25, 50, 75, 100, 125, 150]
    results = []

    for size in sizes:
        steps = max(5, size // 2)  # Same as production
        try:
            result = benchmark_grid(size, steps)
            results.append(result)
        except Exception as e:
            print(f"\n  ERROR at N={size}: {e}")
            break

    # Summary table
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"{'N':<6} {'Cells':<8} {'Scramble':<12} {'Loops':<12} {'Total':<12}")
    print("-"*60)
    for r in results:
        cells = r['size'] ** 2
        print(f"{r['size']:<6} {cells:<8} {r['scramble_ms']:>10.1f}ms {r['loop_find_ms']:>10.1f}ms {r['total_ms']:>10.1f}ms")

    print("\n" + "="*60)
    print("ANALYSIS")
    print("="*60)
    if len(results) >= 2:
        n10 = next((r for r in results if r['size'] == 10), None)
        n100 = next((r for r in results if r['size'] == 100), None)

        if n10 and n100:
            scaling = n100['total_ms'] / n10['total_ms']
            theoretical = (100/10)**2  # O(N²) would be 100x
            print(f"  N=10 → N=100 scaling: {scaling:.1f}x")
            print(f"  Theoretical O(N²): {theoretical:.1f}x")
            print(f"  Performance: {'EXCELLENT' if scaling < theoretical * 0.5 else 'GOOD' if scaling < theoretical else 'NEEDS WORK'}")

        largest = results[-1]
        if largest['total_ms'] < 100:
            print(f"\n  ✓ N={largest['size']} runs at {1000/largest['total_ms']:.0f} FPS - REAL-TIME!")
        elif largest['total_ms'] < 500:
            print(f"\n  ✓ N={largest['size']} runs at {1000/largest['total_ms']:.1f} FPS - Smooth")
        else:
            print(f"\n  ⚠ N={largest['size']} at {largest['total_ms']:.0f}ms - Consider Phase 2 optimizations")

if __name__ == '__main__':
    main()
