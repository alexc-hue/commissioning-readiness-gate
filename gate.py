"""Entry point: per-hall commissioning readiness verdicts with reasons.

Reads NetBox assets (CSV export by default, or live with --netbox-url),
commissioning records, the punch list and the capacity figures, applies the
gate rules in src/rules.py, prints a summary and writes assets/report.md and
assets/readiness_matrix.png.

    python gate.py
    python gate.py --netbox-url https://netbox.example.com   # token from NETBOX_TOKEN
"""

from __future__ import annotations

import argparse
import os

from src import inputs as inp
from src.report import summary_lines, write_chart, write_report
from src.rules import evaluate_site

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")
CONFIG_DIR = os.path.join(ROOT, "config")
ASSETS_DIR = os.path.join(ROOT, "assets")


def _shown(path: str) -> str:
    try:
        path = os.path.relpath(path, ROOT)
    except ValueError:  # different drive on Windows; show it as-is
        pass
    return path.replace(os.sep, "/")


def main(argv: list[str] | None = None) -> list:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--netbox-url", help="read devices and racks live from this NetBox")
    parser.add_argument("--site-slug", help="NetBox site slug for --netbox-url (default: site name, lowercased)")
    args = parser.parse_args(argv)

    levels = inp.load_levels(os.path.join(CONFIG_DIR, "levels.yaml"))
    settings = inp.load_settings(os.path.join(CONFIG_DIR, "gate.yaml"))

    if args.netbox_url:
        from src import netbox_adapter

        api = netbox_adapter.connect(args.netbox_url, os.environ["NETBOX_TOKEN"])
        slug = args.site_slug or settings["site"].lower()
        devices = netbox_adapter.fetch_devices(api, slug)
        racks = netbox_adapter.fetch_racks(api, slug)
    else:
        devices = inp.load_netbox_devices_csv(os.path.join(DATA_DIR, "netbox", "devices.csv"))
        racks = inp.load_netbox_racks_csv(os.path.join(DATA_DIR, "netbox", "racks.csv"))

    inputs = inp.load_records(DATA_DIR, devices, racks)
    results = evaluate_site(inputs, levels, settings)

    os.makedirs(ASSETS_DIR, exist_ok=True)
    report_path = os.path.join(ASSETS_DIR, "report.md")
    chart_path = os.path.join(ASSETS_DIR, "readiness_matrix.png")
    write_report(results, levels, settings, report_path)
    write_chart(results, levels, chart_path)

    print("\n".join(summary_lines(results, levels, settings)))
    print()
    print(f"Wrote {_shown(report_path)}")
    print(f"Wrote {_shown(chart_path)}")
    return results


if __name__ == "__main__":
    main()
