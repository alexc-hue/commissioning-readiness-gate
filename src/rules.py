"""The gate rules: one hall, one target level, one verdict with reasons.

Each hall has a target level (the next commissioning level it is planned to
start, from data/hall_gates.csv). The question each verdict answers is: can
this hall start that level now?

Rules, each producing reasons with an effect:

- SEQUENCE (blocks): a level recorded closed on a device while an earlier
  level on the same device is not. Levels close in order, no skipping.
- PREREQ (blocks): a device in the hall hasn't closed every level before the
  target. For the hall-level test (L5, IST) that means every device's L4.
  "Closed" means status closed and signed; a closed record with no
  signature doesn't count.
- WAIVED (conditional): a PREREQ gap covered by a waiver. Only when waivers
  are switched on in config/gate.yaml; never gives better than conditional.
- PUNCH_A (blocks), PUNCH_B (conditional), PUNCH_C (info): open punch items
  in the hall, by category.
- CAPACITY (blocks): from the energisation level onward, the hall's design
  IT load (sum of its racks) has to be at or below both provisioned power
  and provisioned cooling. A plain comparison of recorded values.

Verdict: any blocking reason gives not-ready; otherwise any conditional
reason gives conditional; otherwise ready.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from src.inputs import Inputs, Levels

BLOCKS = "blocks"
CONDITIONAL = "conditional"
INFO = "info"

READY = "ready"
CONDITIONAL_VERDICT = "conditional"
NOT_READY = "not-ready"


@dataclass
class Reason:
    rule: str
    effect: str
    detail: str


@dataclass
class HallResult:
    hall: str
    target_level: str
    planned_date: pd.Timestamp
    days_to_planned: int
    verdict: str
    reasons: list[Reason] = field(default_factory=list)
    # level -> (closed, total), devices for device levels, 1 for the hall level
    progress: dict[str, tuple[int, int]] = field(default_factory=dict)
    design_it_kw: float = 0.0


def _is_closed(rec: pd.Series) -> bool:
    return rec["status"] == "closed" and rec["signed_by"].strip() != ""


def _record_state(records: pd.DataFrame, device_id: int, level: str) -> str:
    """'closed', 'closed but unsigned', 'open' or 'not started'."""
    rows = records[(records["device_id"] == device_id) & (records["level"] == level)]
    if rows.empty:
        return "not started"
    rec = rows.iloc[-1]
    if _is_closed(rec):
        return "closed"
    if rec["status"] == "closed":
        return "closed but unsigned"
    return rec["status"] or "open"


def evaluate_hall(hall: str, inputs: Inputs, levels: Levels, settings: dict) -> HallResult:
    gate = inputs.gates[inputs.gates["hall"] == hall]
    if gate.empty:
        raise ValueError(f"No target gate for hall {hall!r} in hall_gates.csv")
    target = gate.iloc[0]["target_level"]
    if target not in levels.order:
        raise ValueError(f"Hall {hall}: target level {target!r} is not in levels.yaml")
    planned = gate.iloc[0]["planned_date"]

    devices = inputs.devices[inputs.devices["hall"] == hall]
    if devices.empty:
        raise ValueError(f"Hall {hall!r} has no devices in the NetBox input")
    records = inputs.commissioning[inputs.commissioning["hall"] == hall]
    device_levels = [lv for lv in levels.order if lv != levels.hall_level]
    reasons: list[Reason] = []

    # SEQUENCE
    for _, dev in devices.iterrows():
        states = {lv: _record_state(records, dev["device_id"], lv) for lv in device_levels}
        for i, lv in enumerate(device_levels):
            if states[lv] != "closed":
                continue
            earlier_gap = next((e for e in device_levels[:i] if states[e] != "closed"), None)
            if earlier_gap:
                reasons.append(Reason(
                    "SEQUENCE", BLOCKS,
                    f"{dev['name']}: {lv} recorded closed while {earlier_gap} is {states[earlier_gap]}",
                ))

    # PREREQ / WAIVED
    required = [lv for lv in device_levels if levels.index(lv) < levels.index(target)]
    waivers = inputs.waivers
    for _, dev in devices.iterrows():
        for lv in required:
            state = _record_state(records, dev["device_id"], lv)
            if state == "closed":
                continue
            waived = settings["allow_waivers"] and not waivers[
                (waivers["device_id"] == dev["device_id"]) & (waivers["level"] == lv)
            ].empty
            if waived:
                reasons.append(Reason(
                    "WAIVED", CONDITIONAL, f"{dev['name']}: {lv} {state}, covered by a waiver",
                ))
            else:
                reasons.append(Reason(
                    "PREREQ", BLOCKS, f"{dev['name']}: {lv} {state}, needed before {target}",
                ))
            break  # the first gap per device is the one that matters

    # PUNCH
    punch = inputs.punch[(inputs.punch["hall"] == hall) & (inputs.punch["status"] == "open")]
    for category, rule, effect in (("A", "PUNCH_A", BLOCKS), ("B", "PUNCH_B", CONDITIONAL),
                                   ("C", "PUNCH_C", INFO)):
        items = punch[punch["category"] == category]
        if not items.empty:
            ids = ", ".join(items["item_id"])
            noun = "item" if len(items) == 1 else "items"
            reasons.append(Reason(
                rule, effect, f"{len(items)} open category {category} punch {noun} ({ids})",
            ))

    # CAPACITY
    hall_racks = inputs.racks[inputs.racks["hall"] == hall]
    design_kw = float(
        inputs.rack_load[inputs.rack_load["rack_id"].isin(hall_racks["rack_id"])]["design_it_kw"].sum()
    )
    if levels.index(target) >= levels.index(levels.energisation_level):
        cap = inputs.capacity[inputs.capacity["hall"] == hall]
        if cap.empty:
            reasons.append(Reason("CAPACITY", BLOCKS, "no provisioned power/cooling recorded"))
        else:
            cap = cap.iloc[0]
            exceeded = False
            for label, col in (("power", "provisioned_power_kw"), ("cooling", "provisioned_cooling_kw")):
                if design_kw > cap[col]:
                    exceeded = True
                    reasons.append(Reason(
                        "CAPACITY", BLOCKS,
                        f"design IT load {design_kw:.0f} kW exceeds provisioned {label} {cap[col]:.0f} kW",
                    ))
            if not exceeded:
                reasons.append(Reason(
                    "CAPACITY", INFO,
                    f"design IT load {design_kw:.0f} kW within provisioned power "
                    f"{cap['provisioned_power_kw']:.0f} kW and cooling {cap['provisioned_cooling_kw']:.0f} kW",
                ))

    if any(r.effect == BLOCKS for r in reasons):
        verdict = NOT_READY
    elif any(r.effect == CONDITIONAL for r in reasons):
        verdict = CONDITIONAL_VERDICT
    else:
        verdict = READY

    # Progress counts a level as closed only if every earlier level on that
    # device is closed too, so an out-of-sequence close doesn't show as progress.
    progress = {}
    for i, lv in enumerate(device_levels):
        closed = sum(
            all(_record_state(records, d, e) == "closed" for e in device_levels[: i + 1])
            for d in devices["device_id"]
        )
        progress[lv] = (closed, len(devices))
    hall_rec = records[(records["level"] == levels.hall_level) & records["device_id"].isna()]
    progress[levels.hall_level] = (int(any(_is_closed(r) for _, r in hall_rec.iterrows())), 1)

    return HallResult(
        hall=hall,
        target_level=target,
        planned_date=planned,
        days_to_planned=int((planned - settings["status_date"]).days),
        verdict=verdict,
        reasons=reasons,
        progress=progress,
        design_it_kw=design_kw,
    )


def evaluate_site(inputs: Inputs, levels: Levels, settings: dict) -> list[HallResult]:
    return [evaluate_hall(h, inputs, levels, settings) for h in sorted(inputs.gates["hall"])]
