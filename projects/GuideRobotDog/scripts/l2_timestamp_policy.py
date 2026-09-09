"""Clean-room anchored L2 timestamp scale policy (behavioral reference only)."""
from __future__ import annotations

def anchored_scale(raw_anchor: float, raw_timestamp: float, scale_num: int = 2, scale_den: int = 1) -> float:
    return raw_anchor + (raw_timestamp - raw_anchor) * scale_num / scale_den

def ratio_from_period(nominal_period: float, valid_samples: int, host_elapsed: float, missing: int = 0):
    if valid_samples < 30 or nominal_period <= 0 or host_elapsed <= 0:
        return None
    return ((valid_samples + missing - 1) * nominal_period) / host_elapsed

def gap_time_consistent(seq_delta: int, raw_delta: float, nominal_period: float, valid_samples: int, tolerance: float = .20):
    if valid_samples < 30 or seq_delta <= 0 or raw_delta <= 0 or nominal_period <= 0:
        return None
    ratio = raw_delta / (seq_delta * nominal_period)
    return (1.0 - tolerance) <= ratio <= (1.0 + tolerance)
