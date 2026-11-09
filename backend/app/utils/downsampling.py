import math
from typing import List, Tuple, Any, Optional

def downsample_min_max(
    timestamps: List[str],
    values: List[Optional[float]],
    max_points: int = 1500
) -> Tuple[List[List[Any]], bool, str]:
    """
    Min-Max Bucket Downsampling algorithm that preserves peaks, valleys, and endpoints.
    Returns:
        points: list of [iso_timestamp, float_or_null_value]
        is_aggregated: bool
        method: "min_max_bucket" or "none"
    """
    n = len(timestamps)
    if n == 0:
        return [], False, "none"
    
    if n <= max_points:
        result = []
        for t, v in zip(timestamps, values):
            val = None if (v is None or math.isnan(v) or math.isinf(v)) else round(float(v), 4)
            result.append([t, val])
        return result, False, "none"

    # We need to reduce n down to <= max_points.
    # We allocate 2 points per bucket (min and max)
    # Target number of buckets:
    num_buckets = max(1, (max_points - 2) // 2)
    bucket_size = n / num_buckets

    downsampled: List[Tuple[int, str, Optional[float]]] = []

    # Always include first point
    v0 = values[0]
    val0 = None if (v0 is None or math.isnan(v0) or math.isinf(v0)) else round(float(v0), 4)
    downsampled.append((0, timestamps[0], val0))

    for b in range(num_buckets):
        start_idx = int(b * bucket_size)
        end_idx = int(min(n, (b + 1) * bucket_size))
        if start_idx >= end_idx:
            continue

        min_val = float("inf")
        min_idx = -1
        max_val = float("-inf")
        max_idx = -1

        for i in range(start_idx, end_idx):
            v = values[i]
            if v is None or math.isnan(v) or math.isinf(v):
                continue
            if v < min_val:
                min_val = v
                min_idx = i
            if v > max_val:
                max_val = v
                max_idx = i

        if min_idx != -1 and max_idx != -1:
            if min_idx == max_idx:
                downsampled.append((min_idx, timestamps[min_idx], round(min_val, 4)))
            elif min_idx < max_idx:
                downsampled.append((min_idx, timestamps[min_idx], round(min_val, 4)))
                downsampled.append((max_idx, timestamps[max_idx], round(max_val, 4)))
            else:
                downsampled.append((max_idx, timestamps[max_idx], round(max_val, 4)))
                downsampled.append((min_idx, timestamps[min_idx], round(min_val, 4)))
        else:
            # Bucket had only nulls: record middle point with null
            mid = (start_idx + end_idx) // 2
            downsampled.append((mid, timestamps[mid], None))

    # Always include last point if not already last
    last_idx = n - 1
    if not downsampled or downsampled[-1][0] != last_idx:
        v_last = values[last_idx]
        val_last = None if (v_last is None or math.isnan(v_last) or math.isinf(v_last)) else round(float(v_last), 4)
        downsampled.append((last_idx, timestamps[last_idx], val_last))

    # Sort strictly by original index and deduplicate by index
    seen_indices = set()
    cleaned_points: List[List[Any]] = []
    for idx, t, val in sorted(downsampled, key=lambda x: x[0]):
        if idx not in seen_indices:
            seen_indices.add(idx)
            cleaned_points.append([t, val])

    return cleaned_points, True, "min_max_bucket"
