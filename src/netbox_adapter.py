"""Optional live input: reads devices and racks from a NetBox instance.

Read-only, through pynetbox (`pip install pynetbox`, not needed otherwise).
Returns exactly the schema src/inputs.py builds from a NetBox CSV export, so
the gate logic works the same either way. The tests run these functions
against NetBox-shaped API responses in tests/fixtures/, so CI never needs a
running NetBox.
"""

from __future__ import annotations

import pandas as pd

from src.inputs import normalize_devices, normalize_racks


def _name(obj) -> str:
    """Name of a nested NetBox object (site, location, rack, role), or '' if unset."""
    return "" if obj is None else str(obj.name)


def fetch_devices(api, site_slug: str) -> pd.DataFrame:
    rows = [
        {
            "device_id": d.id,
            "name": d.name or "",
            "status": d.status.label,
            "site": _name(d.site),
            "hall": _name(d.location),
            "rack": _name(d.rack),
            "role": _name(d.role),
            "manufacturer": d.device_type.manufacturer.name,
            "device_type": d.device_type.model,
        }
        for d in api.dcim.devices.filter(site=site_slug)
    ]
    return normalize_devices(pd.DataFrame(rows))


def fetch_racks(api, site_slug: str) -> pd.DataFrame:
    rows = [
        {
            "rack_id": r.id,
            "name": r.name,
            "status": r.status.label,
            "site": _name(r.site),
            "hall": _name(r.location),
        }
        for r in api.dcim.racks.filter(site=site_slug)
    ]
    return normalize_racks(pd.DataFrame(rows))


def connect(url: str, token: str):
    """A read-only pynetbox API handle. Imported here so pynetbox stays optional."""
    import pynetbox

    return pynetbox.api(url, token=token)
