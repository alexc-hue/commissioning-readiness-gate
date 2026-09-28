"""Loads every input into a DataFrame with a fixed schema.

Assets come from NetBox. The default is NetBox's own table export (Devices
and Racks lists, Export > Current view) saved as CSV, with at least the
columns in NETBOX_DEVICE_COLUMNS / NETBOX_RACK_COLUMNS visible. The optional
live adapter (src/netbox_adapter.py) returns exactly the same schema, so the
rest of the tool can't tell the two apart.

Everything else (commissioning records, punch list, capacity, gate targets,
waivers) lives in plain CSV files keyed to NetBox IDs. Nothing is written
back to NetBox.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import pandas as pd
import yaml

# NetBox export column label -> this tool's column name.
NETBOX_DEVICE_COLUMNS = {
    "ID": "device_id",
    "Name": "name",
    "Status": "status",
    "Site": "site",
    "Location": "hall",
    "Rack": "rack",
    "Role": "role",
    "Manufacturer": "manufacturer",
    "Type": "device_type",
}
NETBOX_RACK_COLUMNS = {
    "ID": "rack_id",
    "Name": "name",
    "Status": "status",
    "Site": "site",
    "Location": "hall",
}
DEVICE_SCHEMA = list(NETBOX_DEVICE_COLUMNS.values())
RACK_SCHEMA = list(NETBOX_RACK_COLUMNS.values())


def normalize_devices(df: pd.DataFrame) -> pd.DataFrame:
    """Fixed column order and types, sorted by NetBox ID."""
    df = df[DEVICE_SCHEMA].copy()
    df["device_id"] = df["device_id"].astype(int)
    for col in DEVICE_SCHEMA[1:]:
        df[col] = df[col].fillna("").astype(str)
    return df.sort_values("device_id").reset_index(drop=True)


def normalize_racks(df: pd.DataFrame) -> pd.DataFrame:
    df = df[RACK_SCHEMA].copy()
    df["rack_id"] = df["rack_id"].astype(int)
    for col in RACK_SCHEMA[1:]:
        df[col] = df[col].fillna("").astype(str)
    return df.sort_values("rack_id").reset_index(drop=True)


def load_netbox_devices_csv(path: str) -> pd.DataFrame:
    raw = pd.read_csv(path, dtype=str, keep_default_na=False)
    missing = set(NETBOX_DEVICE_COLUMNS) - set(raw.columns)
    if missing:
        raise ValueError(f"{path} is missing NetBox export columns: {sorted(missing)}")
    return normalize_devices(raw.rename(columns=NETBOX_DEVICE_COLUMNS))


def load_netbox_racks_csv(path: str) -> pd.DataFrame:
    raw = pd.read_csv(path, dtype=str, keep_default_na=False)
    missing = set(NETBOX_RACK_COLUMNS) - set(raw.columns)
    if missing:
        raise ValueError(f"{path} is missing NetBox export columns: {sorted(missing)}")
    return normalize_racks(raw.rename(columns=NETBOX_RACK_COLUMNS))


@dataclass
class Levels:
    order: list[str]
    energisation_level: str
    hall_level: str
    details: dict[str, dict]

    def index(self, level: str) -> int:
        return self.order.index(level)

    def name(self, level: str) -> str:
        return self.details[level]["name"]


def load_levels(path: str) -> Levels:
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    order = [lv["id"] for lv in raw["levels"]]
    if len(set(order)) != len(order):
        raise ValueError(f"{path}: level ids must be unique, got {order}")
    for key in ("energisation_level", "hall_level"):
        if raw[key] not in order:
            raise ValueError(f"{path}: {key} {raw[key]!r} is not one of the levels {order}")
    if raw["hall_level"] != order[-1]:
        raise ValueError(f"{path}: hall_level has to be the last level ({order[-1]})")
    return Levels(
        order=order,
        energisation_level=raw["energisation_level"],
        hall_level=raw["hall_level"],
        details={lv["id"]: lv for lv in raw["levels"]},
    )


def load_settings(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    raw["status_date"] = pd.Timestamp(raw["status_date"])
    raw["allow_waivers"] = bool(raw.get("allow_waivers", False))
    return raw


def _read(path: str, int_cols: tuple[str, ...] = (), date_cols: tuple[str, ...] = ()) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    for col in int_cols:
        df[col] = pd.to_numeric(df[col].replace("", pd.NA)).astype("Int64")
    for col in date_cols:
        df[col] = pd.to_datetime(df[col].replace("", pd.NA))
    return df


@dataclass
class Inputs:
    devices: pd.DataFrame
    racks: pd.DataFrame
    commissioning: pd.DataFrame
    punch: pd.DataFrame
    capacity: pd.DataFrame
    rack_load: pd.DataFrame
    gates: pd.DataFrame
    waivers: pd.DataFrame


def load_records(data_dir: str, devices: pd.DataFrame, racks: pd.DataFrame) -> Inputs:
    """Everything except the NetBox assets, which are passed in already loaded."""
    capacity = _read(os.path.join(data_dir, "hall_capacity.csv"))
    for col in ("provisioned_power_kw", "provisioned_cooling_kw"):
        capacity[col] = capacity[col].astype(float)
    rack_load = _read(os.path.join(data_dir, "rack_design_load.csv"), int_cols=("rack_id",))
    rack_load["design_it_kw"] = rack_load["design_it_kw"].astype(float)
    return Inputs(
        devices=devices,
        racks=racks,
        commissioning=_read(
            os.path.join(data_dir, "commissioning.csv"),
            int_cols=("device_id",), date_cols=("signed_date",),
        ),
        punch=_read(os.path.join(data_dir, "punch_list.csv"), int_cols=("device_id",)),
        capacity=capacity,
        rack_load=rack_load,
        gates=_read(os.path.join(data_dir, "hall_gates.csv"), date_cols=("planned_date",)),
        waivers=_read(os.path.join(data_dir, "waivers.csv"), int_cols=("device_id",)),
    )
