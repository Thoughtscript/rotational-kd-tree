from itertools import product
from math import ceil, floor
from statistics import median
from time import perf_counter
from typing import Callable

import numpy as np
from scipy.spatial import KDTree

from example import (
    CHARACTER_VALUES,
    FIXED_QUERY,
    PARAGRAPH,
    WORD_SEQUENCE,
    WORD_VALUES,
    FixedDataset,
    RotationKey,
    RotationPath,
    build_fixed_dataset,
    build_rotation_key_table,
    encode_values,
    query_value,
    rotation_key_for_index,
)

REPEATS = 5
MESSAGE_REPEATS = 100
GRID_CELL_WIDTH = 0.25
KEY_BYTES = 3 * np.dtype(np.float64).itemsize
POINT_BYTES = 3 * np.dtype(np.float64).itemsize


def build_uniform_grid(
    dataset: FixedDataset,
) -> tuple[float, dict[tuple[int, int, int], list[int]]]:
    cell_width = GRID_CELL_WIDTH
    cells: dict[tuple[int, int, int], list[int]] = {}
    for index, point in enumerate(dataset.points):
        cell = tuple(floor(float(value) / cell_width) for value in point)
        cells.setdefault(cell, []).append(index)
    return cell_width, cells


def query_uniform_grid(
    key: RotationKey,
    dataset: FixedDataset,
    cell_width: float,
    cells: dict[tuple[int, int, int], list[int]],
) -> str:
    query = key.to_rotation().inv().apply(dataset.query_vector)
    query_cell = tuple(floor(float(value) / cell_width) for value in query)
    max_shell = max(
        max(abs(cell[axis] - query_cell[axis]) for axis in range(3))
        for cell in cells
    )
    best_index = -1
    best_distance_squared = float("inf")

    for shell in range(max_shell + 1):
        offsets = range(-shell, shell + 1)
        for offset in product(offsets, repeat=3):
            if max(abs(value) for value in offset) != shell:
                continue
            cell = tuple(query_cell[axis] + offset[axis] for axis in range(3))
            for index in cells.get(cell, ()):
                delta = dataset.points[index] - query
                distance_squared = float(np.dot(delta, delta))
                if distance_squared < best_distance_squared:
                    best_index = index
                    best_distance_squared = distance_squared

        lower = np.asarray(
            [(query_cell[axis] - shell) * cell_width for axis in range(3)]
        )
        upper = np.asarray(
            [(query_cell[axis] + shell + 1) * cell_width for axis in range(3)]
        )
        if np.all(query >= lower) and np.all(query <= upper):
            distance_to_unsearched_cells = float(
                np.min(np.minimum(query - lower, upper - query))
            )
            if best_distance_squared <= distance_to_unsearched_cells**2:
                break

    if best_index < 0:
        raise RuntimeError("Uniform grid search did not visit any dataset point")
    return dataset.values[best_index]


def decode_with_tree(
    path: RotationPath, dataset: FixedDataset
) -> tuple[str, ...]:
    return tuple(query_value(node.key, dataset)[0] for node in path)


def decode_with_rotated_array(
    path: RotationPath, dataset: FixedDataset
) -> tuple[str, ...]:
    decoded = []
    query = dataset.query_vector
    for node in path:
        rotated_points = node.key.to_rotation().apply(dataset.points)
        distances_squared = np.einsum(
            "ij,ij->i", rotated_points - query, rotated_points - query
        )
        decoded.append(dataset.values[int(np.argmin(distances_squared))])
    return tuple(decoded)


def decode_with_grid(
    path: RotationPath,
    dataset: FixedDataset,
    cell_width: float,
    cells: dict[tuple[int, int, int], list[int]],
) -> tuple[str, ...]:
    return tuple(
        query_uniform_grid(node.key, dataset, cell_width, cells) for node in path
    )


def median_seconds(action: Callable[[], object]) -> float:
    samples = []
    for _ in range(REPEATS):
        start = perf_counter()
        action()
        samples.append(perf_counter() - start)
    return median(samples)


def format_bytes(byte_count: float) -> str:
    units = ("B", "KiB", "MiB", "GiB")
    value = float(byte_count)
    for unit in units:
        if value < 1024.0 or unit == units[-1]:
            return f"{value:.2f} {unit}" if unit != "B" else f"{int(value):,} B"
        value /= 1024.0
    raise RuntimeError("Unreachable byte unit")


def print_storage_break_even(
    point_count: int, orientation_count: int, point_bytes: int, key_bytes: int
) -> None:
    base_and_keys = point_count * point_bytes + orientation_count * key_bytes
    snapshots = orientation_count * point_count * point_bytes
    threshold = (
        orientation_count * key_bytes
        / ((orientation_count - 1) * point_bytes)
        if orientation_count > 1
        else None
    )

    print("Dataset/key storage break-even (payload only):")
    print(
        "  Retain the base dataset plus orientation keys instead of one full "
        "rotated point snapshot per step when:"
    )
    print("    N*P + M*H < M*N*P")
    if threshold is None:
        print("  With M=1, base dataset + key is never smaller than one snapshot.")
    else:
        print(
            f"  Equivalent for M>1: N > M*H / ((M-1)*P) = "
            f"{threshold:.3f} points."
        )
    print(
        f"  This run: N={point_count}, M={orientation_count}, "
        f"P={point_bytes} B, H={key_bytes} B."
    )
    print(
        f"  Base + keys: {base_and_keys:,} B; M snapshots: {snapshots:,} B."
    )
    if threshold is not None:
        print(
            f"  Snapshot-storage break-even threshold: N > {threshold:.3f} "
            "points. This compares full rotated point snapshots, not compact "
            "strings of values."
        )
    print("  Concrete payload comparisons (base + keys vs. M full snapshots):")
    for example_points, example_steps in (
        (1_000, 100),
        (100_000, 1_000),
        (1_000_000, 100),
    ):
        retained = example_points * point_bytes + example_steps * key_bytes
        copies = example_steps * example_points * point_bytes
        savings = copies / retained
        print(
            f"    N={example_points:,}, M={example_steps:,}: "
            f"{format_bytes(retained)} vs. {format_bytes(copies)} "
            f"({savings:.1f}x less payload)."
        )
    print(
        "  Excludes index nodes, linked-list objects, lookup tables, and "
        "allocator overhead; measure process memory for real deployments."
    )
    print(
        "  Orientation-key capacity is limited by precision, not a finite "
        "hash space. To preserve nearest-neighbor identity, total angular/"
        "query error ε should satisfy 2ε < δ_min, the minimum point separation."
    )


def benchmark_scenario(
    label: str,
    values: tuple[str, ...],
    message: tuple[str, ...],
    message_text: str,
) -> None:
    orientation_count = len(message)
    print(f"\n\n========== {label.upper()} PERFORMANCE TESTS BEGIN ==========\n")
    print(
        f"Fixed dataset: {len(values)} distinct values across {len(values)} "
        f"3D points; invariant query: {dataset_query_repr(FIXED_QUERY)}; "
        f"rotation sequence: {orientation_count:,} steps."
    )
    print(
        "The KD-Tree indexes numeric 3D coordinates; an immutable parallel "
        "value table maps each point index to its character or whole word."
    )
    print(
        "The stored orientation key is the spherical coordinate triple "
        "(rotation angle, axis azimuth, axis inclination), precomputed once "
        "per supported dataset value and reused for encoding."
    )
    print(
        "AOT KEY ENCODING COMPARISON: calculate each value's orientation "
        "on demand versus reusing a precomputed value-to-key table. Both "
        "produce the same linked path."
    )
    print(
        "A) ROTATED KD-TREE: keep the index and world query fixed; "
        "inverse-rotate the query for each lookup."
    )
    print(
        f"B) ROTATED ARRAY: allocate a rotated copy of all {len(values)} "
        "value points for each step, then scan for the fixed query."
    )
    print(
        f"C) UNIFORM GRID / FIXED SPATIAL HASH: bucket the unchanged points "
        f"into {GRID_CELL_WIDTH}-unit 3D cells; inverse-rotate the query and "
        "search neighboring buckets outward until no unvisited cell can "
        "contain a closer point. This uses no KD-Tree."
    )
    print(
        "All three methods use the same rotation sequence and must return "
        "the same value sequence."
    )

    dataset_seconds = median_seconds(lambda: build_fixed_dataset(values))
    dataset = build_fixed_dataset(values)
    tree_build_seconds = median_seconds(
        lambda: KDTree(dataset.points, copy_data=True)
    )
    key_table_seconds = median_seconds(lambda: build_rotation_key_table(dataset))
    key_table = build_rotation_key_table(dataset)
    aot_encode_seconds = median_seconds(
        lambda: encode_values(message, dataset, key_table)
    )
    on_demand_encode_seconds = median_seconds(
        lambda: encode_values(message, dataset)
    )
    path = encode_values(message, dataset, key_table)

    grid_build_seconds = median_seconds(lambda: build_uniform_grid(dataset))
    cell_width, cells = build_uniform_grid(dataset)

    tree_result = decode_with_tree(path, dataset)
    array_result = decode_with_rotated_array(path, dataset)
    grid_result = decode_with_grid(path, dataset, cell_width, cells)
    if not (tree_result == array_result == grid_result == message):
        raise RuntimeError(f"{label}: lookup strategies produced different data")

    all_values_path = encode_values(dataset.values, dataset, key_table)
    all_values_results = (
        decode_with_tree(all_values_path, dataset),
        decode_with_rotated_array(all_values_path, dataset),
        decode_with_grid(all_values_path, dataset, cell_width, cells),
    )
    if any(result != dataset.values for result in all_values_results):
        raise RuntimeError(f"{label}: an index failed to retrieve every fixed value")

    tree_decode_seconds = median_seconds(lambda: decode_with_tree(path, dataset))
    array_decode_seconds = median_seconds(
        lambda: decode_with_rotated_array(path, dataset)
    )
    grid_decode_seconds = median_seconds(
        lambda: decode_with_grid(path, dataset, cell_width, cells)
    )
    lookup_times = {
        "A) Rotated KD-Tree": tree_build_seconds + tree_decode_seconds,
        "B) Rotate points + array scan": array_decode_seconds,
        "C) Uniform grid": grid_build_seconds + grid_decode_seconds,
    }
    fastest_lookup = min(lookup_times, key=lookup_times.get)

    per_key_bytes = 3 * np.dtype(np.float64).itemsize
    points_bytes = dataset.points.nbytes
    path_key_payload_bytes = len(message) * per_key_bytes
    full_snapshot_payload_bytes = len(message) * points_bytes
    if on_demand_encode_seconds > aot_encode_seconds:
        amortized_reuses = ceil(
            key_table_seconds / (on_demand_encode_seconds - aot_encode_seconds)
        )
    else:
        amortized_reuses = None

    print("AOT key preparation and message encoding (median):")
    print(f"  Build fixed dataset/tree:       {dataset_seconds:.6f} s")
    print(
        f"  D) Precompute {len(values)} unique value keys once: "
        f"{key_table_seconds:.6f} s"
    )
    print(
        f"  D) Encode {orientation_count:,} values, calculating each key: "
        f"{on_demand_encode_seconds:.6f} s"
    )
    print(
        f"  D) Encode {orientation_count:,} values, reusing AOT keys: "
        f"{aot_encode_seconds:.6f} s"
    )
    aot_total_seconds = key_table_seconds + aot_encode_seconds
    print(
        f"  D) AOT precompute + one encoding: {aot_total_seconds:.6f} s"
    )
    if aot_encode_seconds > 0:
        print(
            f"  D) Encoding-only speedup after precompute: "
            f"{on_demand_encode_seconds / aot_encode_seconds:.2f}x"
        )
    if amortized_reuses is None:
        print("  D) Precompute break-even: not measured for this message")
    else:
        print(
            f"  D) Precompute amortizes after about {amortized_reuses} "
            "encoding(s) of this sequence length."
        )
    if aot_total_seconds <= on_demand_encode_seconds:
        print(
            "  D) Best for one encoding including setup: "
            "AOT precompute + encode."
        )
    else:
        print(
            "  D) Best for one encoding including setup: "
            "on-demand key calculation."
        )
    print("  D) Best after table is built and reused: AOT precomputed keys.")

    print("MEASURED ELAPSED TIME (median of 5 runs)")
    print(f"  A) Build Rotated KD-Tree once:          {tree_build_seconds:.6f} s")
    print(f"  A) Inverse-query + Rotated KD-Tree:     {tree_decode_seconds:.6f} s")
    print(
        f"  A) Build + query total:                 "
        f"{tree_build_seconds + tree_decode_seconds:.6f} s"
    )
    print(f"  B) Rotate array + scan:                 {array_decode_seconds:.6f} s")
    print(f"  C) Build uniform grid once:             {grid_build_seconds:.6f} s")
    print(f"  C) Inverse-query + grid lookups:        {grid_decode_seconds:.6f} s")
    print(f"  C) Build + query total:                 {grid_build_seconds + grid_decode_seconds:.6f} s")
    print("All three returned the exact same sequence.")
    print(f"Fastest lookup for this scenario: {fastest_lookup}.")
    print(
        "Rotated KD-Tree complexity (fixed 3D space, n indexed values, "
        "m orientation queries):"
    )
    print(
        "  Build: O(n log n) expected time and O(n) index space for a "
        "balanced tree."
    )
    print(
        "  One inverse rotation: O(1); one nearest-neighbor lookup: "
        "O(log n) expected in low dimensions, O(n) worst case."
    )
    print(
        "  m lookups: O(m log n) expected, O(mn) worst case; including "
        "construction: O(n log n + m log n) expected."
    )
    print(
        "  AOT key table: O(n) build time and O(n) space; encoding m values "
        "with precomputed keys: O(m) plus O(m) path storage."
    )

    print("Storage payload comparison (object/index overhead excluded):")
    print(f"Rotation-sequence storage payload (object overhead excluded)")
    print(f"  Encoded values' UTF-8 payload:  {len(message_text.encode('utf-8')):,} B")
    print(f"  Three float64 coordinates/step: {per_key_bytes} B")
    print(f"  Linked path rotation keys:      {path_key_payload_bytes:,} B")
    print(f"  AOT lookup table payload:       {len(values)} keys x {per_key_bytes} B = {len(values) * per_key_bytes:,} B")
    print(
        "  Spherical coordinates are orientation keys, not cryptographic "
        "hashes or compression."
    )
    print_storage_break_even(
        len(values), orientation_count, POINT_BYTES, per_key_bytes
    )
    print(
        f"  C) Uniform grid: O(n) build and O(n + g) space for point indices "
        f"and g occupied buckets; expected near O(1) query under bounded "
        f"density, worst-case O(n) point checks."
    )
    print(
        f"     Outward cell search is exact; cost depends on cells visited "
        f"(cell width {GRID_CELL_WIDTH})."
    )
    print(
        "\nBEST FOR THIS MEASURED LOOKUP: "
        f"{fastest_lookup} ({lookup_times[fastest_lookup]:.6f} s total "
        "including index construction where applicable)."
    )
    print(
        "This timing is specific to the dataset size and machine; the "
        "invariant query and indexed data remain unchanged."
    )


def dataset_query_repr(query: tuple[float, float, float]) -> str:
    return repr(tuple(float(value) for value in query))


def main() -> None:
    print("\n========== INVARIANT-QUERY ROTATION PERFORMANCE TESTS ==========")
    print(
        f"Fixed world-space query: {tuple(float(v) for v in (0.0, 0.0, 1.0))}. "
        "The value/point dataset is fixed; only its orientation key varies."
    )
    print(
        "A) Fixed Rotated KD-Tree: inverse-transform the invariant query and "
        "query the unchanged index."
    )
    print(
        "B) Rotate points + array scan: physically rotate every point into a "
        "new temporary array, then search that array around the unchanged query."
    )
    print(
        "C) Fixed uniform grid: retain points in fixed spatial hash cells; "
        "inverse-transform the invariant query and expand neighboring cells "
        "until the nearest result is proven."
    )
    print(
        "Expected complexity for n points and m keys: A) O(n log n) build, "
        "O(m log n) expected / O(mn) worst-case lookup; "
        "B) O(mn) lookup and O(n) temporary array; "
        "C) O(n) grid build, typically near O(m) lookup for bounded cell "
        "occupancy / O(mn) worst case."
    )
    print("All three indexes/point sets require O(n) persistent space.")
    print(
        "The spherical-coordinate triple (angle, axis azimuth, axis "
        "inclination) is the rotation key."
    )

    benchmark_scenario(
        "Character-to-paragraph",
        CHARACTER_VALUES,
        tuple(PARAGRAPH) * MESSAGE_REPEATS,
        PARAGRAPH * MESSAGE_REPEATS,
    )
    benchmark_scenario(
        "Word-to-sentence",
        WORD_VALUES,
        WORD_SEQUENCE * MESSAGE_REPEATS,
        "".join(WORD_SEQUENCE * MESSAGE_REPEATS),
    )


if __name__ == "__main__":
    main()
