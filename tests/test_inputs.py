"""The NetBox CSV loaders, the optional live adapter, and levels.yaml checks.

The adapter is run against NetBox-shaped API responses in
tests/fixtures/netbox_api/ through a stand-in for pynetbox's API object, so
no NetBox server (and no pynetbox) is needed. It has to give exactly the
same DataFrames as the CSV export loaders do for the same assets.
"""

from __future__ import annotations

import json
import os
from types import SimpleNamespace

import pandas as pd
import pytest

from src import inputs as inp
from src import netbox_adapter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(ROOT, "tests", "fixtures", "netbox_api")
DEVICES_CSV = os.path.join(ROOT, "data", "netbox", "devices.csv")
RACKS_CSV = os.path.join(ROOT, "data", "netbox", "racks.csv")


def _obj(value):
    """JSON -> attribute access, the way pynetbox Records behave."""
    if isinstance(value, dict):
        return SimpleNamespace(**{k: _obj(v) for k, v in value.items()})
    if isinstance(value, list):
        return [_obj(v) for v in value]
    return value


class _Endpoint:
    def __init__(self, fixture: str):
        with open(os.path.join(FIXTURES, fixture), encoding="utf-8") as f:
            self.results = json.load(f)["results"]
        self.filters: list[dict] = []

    def filter(self, **kwargs):
        self.filters.append(kwargs)
        return [_obj(r) for r in self.results if r["site"]["slug"] == kwargs.get("site")]


def _fake_api():
    return SimpleNamespace(dcim=SimpleNamespace(
        devices=_Endpoint("devices.json"), racks=_Endpoint("racks.json"),
    ))


def test_device_csv_loads_into_the_schema():
    df = inp.load_netbox_devices_csv(DEVICES_CSV)
    assert list(df.columns) == inp.DEVICE_SCHEMA
    assert df["device_id"].is_monotonic_increasing
    assert set(df["hall"]) == {"DH1", "DH2", "DH3"}


def test_csv_missing_an_export_column_is_an_error(tmp_path):
    bad = tmp_path / "devices.csv"
    pd.read_csv(DEVICES_CSV).drop(columns=["Location"]).to_csv(bad, index=False)
    with pytest.raises(ValueError, match="Location"):
        inp.load_netbox_devices_csv(str(bad))


def test_adapter_devices_match_the_csv_export():
    api = _fake_api()
    live = netbox_adapter.fetch_devices(api, "dc-sample")
    pd.testing.assert_frame_equal(live, inp.load_netbox_devices_csv(DEVICES_CSV))
    assert api.dcim.devices.filters == [{"site": "dc-sample"}]


def test_adapter_racks_match_the_csv_export():
    live = netbox_adapter.fetch_racks(_fake_api(), "dc-sample")
    pd.testing.assert_frame_equal(live, inp.load_netbox_racks_csv(RACKS_CSV))


def _write_levels(tmp_path, ids, energisation="L3", hall="L5"):
    levels = "\n".join(f"  - {{id: {i}, name: n}}" for i in ids)
    path = tmp_path / "levels.yaml"
    path.write_text(f"energisation_level: {energisation}\nhall_level: {hall}\nlevels:\n{levels}\n")
    return str(path)


def test_levels_file_loads_in_order():
    levels = inp.load_levels(os.path.join(ROOT, "config", "levels.yaml"))
    assert levels.order == ["L1", "L2", "L3", "L4", "L5"]
    assert levels.energisation_level == "L3" and levels.hall_level == "L5"


def test_duplicate_level_ids_are_an_error(tmp_path):
    with pytest.raises(ValueError, match="unique"):
        inp.load_levels(_write_levels(tmp_path, ["L1", "L2", "L2", "L5"]))


def test_hall_level_has_to_be_last(tmp_path):
    with pytest.raises(ValueError, match="last level"):
        inp.load_levels(_write_levels(tmp_path, ["L1", "L2", "L3", "L5", "L6"]))


def test_energisation_level_has_to_exist(tmp_path):
    with pytest.raises(ValueError, match="energisation_level"):
        inp.load_levels(_write_levels(tmp_path, ["L1", "L2", "L5"], energisation="L3"))
