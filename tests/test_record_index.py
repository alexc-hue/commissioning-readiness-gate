"""evaluate_hall looks record states up from an index built once per hall.
Every lookup has to give the same answer as filtering the records directly
(_record_state), including duplicates, unsigned closes and missing pairs."""

from __future__ import annotations

import pandas as pd

from src.rules import _lookup, _record_state, _record_states

LEVELS = ["L1", "L2", "L3", "L4"]


def _records() -> pd.DataFrame:
    rows = [
        (1, "L1", "closed", "Vendor/CxA"), (1, "L2", "closed", ""), (1, "L3", "open", ""),
        (2, "L1", "closed", "Vendor/CxA"), (2, "L1", "open", ""),  # later record wins
        (2, "L2", "", ""), (3, "L4", "closed", "CxA/Owner"),
        (None, "L5", "closed", "CxA/Owner"),  # hall-level IST row, no device
    ]
    df = pd.DataFrame(rows, columns=["device_id", "level", "status", "signed_by"])
    df["device_id"] = df["device_id"].astype("Int64")
    return df


def test_index_matches_direct_filtering_for_every_pair():
    records = _records()
    states = _record_states(records)
    for device_id in (1, 2, 3, 4):
        for level in LEVELS:
            assert _lookup(states, device_id, level) == _record_state(records, device_id, level), (device_id, level)


def test_index_covers_the_record_kinds():
    states = _record_states(_records())
    assert _lookup(states, 1, "L1") == "closed"
    assert _lookup(states, 1, "L2") == "closed but unsigned"
    assert _lookup(states, 2, "L1") == "open"
    assert _lookup(states, 2, "L2") == "open"
    assert _lookup(states, 4, "L1") == "not started"
