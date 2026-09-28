"""Each gate rule, on a small hand-built hall, one rule at a time.

The baseline hall (H1, two devices, two racks) is ready for L5: every device
has L1 to L4 closed and signed, no punch items, and its design load fits.
Each test breaks exactly one thing and checks the verdict and the reason.
"""

from __future__ import annotations

import os

import pandas as pd
import pytest

from src.inputs import Inputs, load_levels
from src.rules import BLOCKS, CONDITIONAL, INFO, evaluate_hall

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEVELS = load_levels(os.path.join(ROOT, "config", "levels.yaml"))
SETTINGS = {"status_date": pd.Timestamp("2026-10-05"), "site": "S", "allow_waivers": False}


def _records(levels_by_device: dict[int, list[str]], signed: bool = True) -> list[dict]:
    return [
        {"device_id": d, "hall": "H1", "level": lv, "status": "closed",
         "signed_by": "CxA" if signed else "", "signed_date": pd.Timestamp("2026-09-01"),
         "evidence_ref": ""}
        for d, lvs in levels_by_device.items() for lv in lvs
    ]


def make_inputs(target="L5", records=None, punch=(), design_kw=(40.0, 40.0),
                power=100.0, cooling=100.0, waivers=()) -> Inputs:
    all_four = ["L1", "L2", "L3", "L4"]
    records = records if records is not None else _records({1: all_four, 2: all_four})
    devices = pd.DataFrame([
        {"device_id": 1, "name": "H1-UPS-01", "status": "Active", "site": "S", "hall": "H1",
         "rack": "", "role": "UPS", "manufacturer": "Generic", "device_type": "UPS"},
        {"device_id": 2, "name": "H1-CRAH-01", "status": "Active", "site": "S", "hall": "H1",
         "rack": "", "role": "Cooling", "manufacturer": "Generic", "device_type": "CRAH"},
    ])
    racks = pd.DataFrame([
        {"rack_id": 11, "name": "H1-R01", "status": "Active", "site": "S", "hall": "H1"},
        {"rack_id": 12, "name": "H1-R02", "status": "Active", "site": "S", "hall": "H1"},
    ])
    commissioning = pd.DataFrame(
        records, columns=["device_id", "hall", "level", "status", "signed_by", "signed_date", "evidence_ref"]
    )
    commissioning["device_id"] = commissioning["device_id"].astype("Int64")
    punch_df = pd.DataFrame(
        list(punch), columns=["item_id", "hall", "device_id", "category", "status"]
    )
    waivers_df = pd.DataFrame(list(waivers), columns=["device_id", "level", "reason", "approved_by"])
    return Inputs(
        devices=devices,
        racks=racks,
        commissioning=commissioning,
        punch=punch_df,
        capacity=pd.DataFrame([{"hall": "H1", "provisioned_power_kw": power,
                                "provisioned_cooling_kw": cooling}]),
        rack_load=pd.DataFrame({"rack_id": [11, 12], "design_it_kw": list(design_kw)}),
        gates=pd.DataFrame([{"hall": "H1", "target_level": target,
                             "planned_date": pd.Timestamp("2026-11-02")}]),
        waivers=waivers_df,
    )


def _rules(result, effect=None):
    return [r.rule for r in result.reasons if effect is None or r.effect == effect]


def test_baseline_hall_is_ready_for_ist():
    result = evaluate_hall("H1", make_inputs(), LEVELS, SETTINGS)
    assert result.verdict == "ready"
    assert _rules(result, BLOCKS) == [] and _rules(result, CONDITIONAL) == []
    assert result.days_to_planned == 28


def test_ist_is_blocked_until_l4_is_closed_on_every_device():
    records = _records({1: ["L1", "L2", "L3", "L4"], 2: ["L1", "L2", "L3"]})
    result = evaluate_hall("H1", make_inputs(records=records), LEVELS, SETTINGS)
    assert result.verdict == "not-ready"
    assert any(r.rule == "PREREQ" and "H1-CRAH-01: L4 not started" in r.detail for r in result.reasons)


def test_a_level_closed_out_of_sequence_blocks():
    records = _records({1: ["L1", "L2", "L3", "L4"], 2: ["L1", "L3", "L4"]})
    result = evaluate_hall("H1", make_inputs(records=records), LEVELS, SETTINGS)
    assert result.verdict == "not-ready"
    assert any(r.rule == "SEQUENCE" and "H1-CRAH-01: L3 recorded closed while L2" in r.detail
               for r in result.reasons)


def test_out_of_sequence_close_does_not_count_as_progress():
    records = _records({1: ["L1", "L2", "L3", "L4"], 2: ["L1", "L3", "L4"]})
    result = evaluate_hall("H1", make_inputs(records=records), LEVELS, SETTINGS)
    assert result.progress["L3"] == (1, 2)
    assert result.progress["L4"] == (1, 2)


def test_a_closed_but_unsigned_record_does_not_count():
    records = _records({1: ["L1", "L2", "L3", "L4"], 2: ["L1", "L2", "L3"]})
    records += _records({2: ["L4"]}, signed=False)
    result = evaluate_hall("H1", make_inputs(records=records), LEVELS, SETTINGS)
    assert result.verdict == "not-ready"
    assert any("L4 closed but unsigned" in r.detail for r in result.reasons)


@pytest.mark.parametrize("category, verdict, effect", [
    ("A", "not-ready", BLOCKS),
    ("B", "conditional", CONDITIONAL),
    ("C", "ready", INFO),
])
def test_open_punch_items_by_category(category, verdict, effect):
    punch = [{"item_id": "P-1", "hall": "H1", "device_id": 1, "category": category, "status": "open"}]
    result = evaluate_hall("H1", make_inputs(punch=punch), LEVELS, SETTINGS)
    assert result.verdict == verdict
    assert f"PUNCH_{category}" in _rules(result, effect)


def test_closed_punch_items_are_ignored():
    punch = [{"item_id": "P-1", "hall": "H1", "device_id": 1, "category": "A", "status": "closed"}]
    result = evaluate_hall("H1", make_inputs(punch=punch), LEVELS, SETTINGS)
    assert result.verdict == "ready"


@pytest.mark.parametrize("power, cooling, which", [(70.0, 100.0, "power"), (100.0, 70.0, "cooling")])
def test_design_load_above_provisioned_capacity_blocks(power, cooling, which):
    result = evaluate_hall("H1", make_inputs(power=power, cooling=cooling), LEVELS, SETTINGS)
    assert result.verdict == "not-ready"
    assert any(r.rule == "CAPACITY" and r.effect == BLOCKS and f"provisioned {which} 70 kW" in r.detail
               for r in result.reasons)


def test_design_load_equal_to_capacity_passes():
    result = evaluate_hall("H1", make_inputs(power=80.0, cooling=80.0), LEVELS, SETTINGS)
    assert result.verdict == "ready"
    assert "CAPACITY" in _rules(result, INFO)


def test_capacity_is_not_checked_before_energisation():
    records = _records({1: ["L1"], 2: ["L1"]})
    inputs = make_inputs(target="L2", records=records, power=10.0, cooling=10.0)
    result = evaluate_hall("H1", inputs, LEVELS, SETTINGS)
    assert result.verdict == "ready"
    assert "CAPACITY" not in _rules(result)


def test_capacity_is_checked_at_the_energisation_level():
    records = _records({1: ["L1", "L2"], 2: ["L1", "L2"]})
    inputs = make_inputs(target="L3", records=records, power=10.0)
    result = evaluate_hall("H1", inputs, LEVELS, SETTINGS)
    assert "CAPACITY" in _rules(result, BLOCKS)


def test_waivers_are_ignored_when_switched_off():
    records = _records({1: ["L1", "L2", "L3", "L4"], 2: ["L1", "L2", "L3"]})
    waivers = [{"device_id": 2, "level": "L4", "reason": "r", "approved_by": "Owner"}]
    result = evaluate_hall("H1", make_inputs(records=records, waivers=waivers), LEVELS, SETTINGS)
    assert result.verdict == "not-ready"


def test_a_waiver_gives_conditional_never_ready():
    records = _records({1: ["L1", "L2", "L3", "L4"], 2: ["L1", "L2", "L3"]})
    waivers = [{"device_id": 2, "level": "L4", "reason": "r", "approved_by": "Owner"}]
    settings = {**SETTINGS, "allow_waivers": True}
    result = evaluate_hall("H1", make_inputs(records=records, waivers=waivers), LEVELS, settings)
    assert result.verdict == "conditional"
    assert _rules(result, CONDITIONAL) == ["WAIVED"]


def test_unknown_target_level_is_an_error():
    with pytest.raises(ValueError, match="not in levels.yaml"):
        evaluate_hall("H1", make_inputs(target="L9"), LEVELS, SETTINGS)
