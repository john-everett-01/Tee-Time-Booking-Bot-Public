# Searches the real, currently-open slot list by actual clock-time distance rather than
# generating synthetic candidate times — real slot spacing isn't guaranteed to match any
# assumed step size (observed 10-minute spacing on one course, not the nominal 8), so
# matching against the real list is the only way this stays correct regardless of spacing.

from __future__ import annotations

from datetime import datetime, timedelta

MAX_OFFSET_MINUTES = 32


def _parse_slot_time(time_label: str, on_date) -> datetime:
    return datetime.strptime(f"{on_date:%m/%d/%Y} {time_label}", "%m/%d/%Y %I:%M %p")


def find_best_slot(slots: list[dict], on_date, target_time=None, window=None) -> dict | None:
    """slots: from teesheet.list_slots(). Exactly one of target_time (a time) or
    window (a (start_time, end_time) tuple) must be given."""
    if (target_time is None) == (window is None):
        raise ValueError("pass exactly one of target_time or window")

    open_slots = [s for s in slots if s["status"] == "Empty"]
    if not open_slots:
        return None

    timed = [(_parse_slot_time(s["time"], on_date), s) for s in open_slots]
    max_offset = timedelta(minutes=MAX_OFFSET_MINUTES)

    if target_time is not None:
        target_dt = datetime.combine(on_date, target_time)
        candidates = [(abs(dt - target_dt), s) for dt, s in timed if abs(dt - target_dt) <= max_offset]
        if not candidates:
            return None
        candidates.sort(key=lambda pair: pair[0])
        return candidates[0][1]

    start_dt = datetime.combine(on_date, window[0])
    end_dt = datetime.combine(on_date, window[1])

    inside = sorted((dt, s) for dt, s in timed if start_dt <= dt <= end_dt)
    if inside:
        return inside[0][1]

    outside = []
    for dt, s in timed:
        if dt < start_dt:
            dist = start_dt - dt
        elif dt > end_dt:
            dist = dt - end_dt
        else:
            continue
        if dist <= max_offset:
            outside.append((dist, s))
    if not outside:
        return None
    outside.sort(key=lambda pair: pair[0])
    return outside[0][1]
