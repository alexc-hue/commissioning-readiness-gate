"""Size test for commissioning-readiness-gate: run by hand, not part of CI or the test suite.

Builds the three sample halls repeated and renumbered (7 devices, 4 racks and about 24 commissioning records per hall) at each size, runs `gate.py` end to end on it in a fresh
Python process, and prints the wall time and peak memory. Everything runs in
a temporary copy of the repo, so assets/ and data/ here are never touched.
Inputs are generated with fixed seeds: the same size always gives the same
files.

    python benchmarks/size_test.py
    python benchmarks/size_test.py --sizes 100 1000

Peak memory needs psutil (pip install psutil) on Windows; without it only
time is shown there. Timings depend on the machine. The measured numbers in
the README's Limitations section say which machine they came from.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SIZES = [3, 30, 100, 300, 1000]
UNIT = "halls"

def _write(df: pd.DataFrame, data_dir: str, name: str) -> None:
    df.to_csv(os.path.join(data_dir, name), index=False)

def generate(n_halls, data_dir, sample_dir):
    """Tile the three sample halls (DH1-DH3, 7 devices and 4 racks each) into
    n_halls halls, renumbering halls, device IDs, rack IDs and names."""
    s = {name: pd.read_csv(os.path.join(sample_dir, name), dtype=str, keep_default_na=False)
         for name in ["commissioning.csv", "punch_list.csv", "hall_capacity.csv", "hall_gates.csv",
                      "rack_design_load.csv", "waivers.csv"]}
    nb = {name: pd.read_csv(os.path.join(sample_dir, "netbox", name), dtype=str, keep_default_na=False)
          for name in ["devices.csv", "racks.csv"]}

    def rename(text: str, src: int, dst: int) -> str:
        return text.replace(f"DH{src}", f"DH{dst}")

    def device_id(value: str, dst: int) -> str:
        return str(dst * 100 + int(value) % 100) if value else value

    def rack_id(value: str, dst: int) -> str:
        return str(dst * 10 + int(value) % 10) if value else value

    out = {k: [] for k in list(s) + list(nb)}
    for h in range(1, n_halls + 1):
        src = (h - 1) % 3 + 1
        d = nb["devices.csv"][nb["devices.csv"]["Location"] == f"DH{src}"].copy()
        d["ID"] = [device_id(v, h) for v in d["ID"]]
        for c in ("Name", "Location", "Rack"):
            d[c] = [rename(t, src, h) for t in d[c]]
        out["devices.csv"].append(d)
        r = nb["racks.csv"][nb["racks.csv"]["Location"] == f"DH{src}"].copy()
        r["ID"] = [rack_id(v, h) for v in r["ID"]]
        for c in ("Name", "Location"):
            r[c] = [rename(t, src, h) for t in r[c]]
        out["racks.csv"].append(r)
        loads = s["rack_design_load.csv"]
        rl = loads[[int(v) // 10 == src for v in loads["rack_id"]]].copy()
        rl["rack_id"] = [rack_id(v, h) for v in rl["rack_id"]]
        out["rack_design_load.csv"].append(rl)
        for name in ("commissioning.csv", "punch_list.csv", "hall_capacity.csv", "hall_gates.csv"):
            df = s[name][s[name]["hall"] == f"DH{src}"].copy()
            df["hall"] = f"DH{h}"
            if "device_id" in df:
                df["device_id"] = [device_id(v, h) for v in df["device_id"]]
            for c in ("evidence_ref", "item_id"):
                if c in df:
                    df[c] = [rename(t, src, h).replace(f"P-{src}", f"P-{h}-") for t in df[c]]
            out[name].append(df)
    for name, parts in out.items():
        df = pd.concat(parts, ignore_index=True) if parts else s.get(name, nb.get(name))
        sub = "netbox" if name in nb else ""
        df.to_csv(os.path.join(data_dir, sub, name), index=False)
    s["waivers.csv"].to_csv(os.path.join(data_dir, "waivers.csv"), index=False)

CHILD = r"""
import contextlib, io, json, os, sys, time
os.environ["MPLBACKEND"] = "Agg"
sys.path.insert(0, __ROOT__); os.chdir(__ROOT__)
mod = __import__("gate")
t0 = time.perf_counter()
with contextlib.redirect_stdout(io.StringIO()):
    mod.main([])
seconds = time.perf_counter() - t0
peak_mb = None
try:
    import resource
    kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak_mb = kb / 1024 / (1024 if sys.platform == "darwin" else 1)
except ImportError:
    try:
        import psutil
        info = psutil.Process().memory_info()
        peak_mb = getattr(info, "peak_wset", info.rss) / 2**20
    except ImportError:
        pass
print("RESULT" + json.dumps({"seconds": seconds, "peak_mb": peak_mb}))
"""


def run_once(n: int) -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="size-test-"))
    try:
        root = tmp / ROOT.name
        shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", "*.png"))
        generate(n, str(root / "data"), str(ROOT / "data"))
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        proc = subprocess.run([sys.executable, "-c", CHILD.replace("__ROOT__", repr(str(root)))],
                              capture_output=True, text=True, encoding="utf-8", env=env)
        line = next((ln for ln in proc.stdout.splitlines() if ln.startswith("RESULT")), None)
        if line is None:
            return {"error": (proc.stderr.strip().splitlines() or ["no output"])[-1]}
        return json.loads(line[len("RESULT"):])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sizes", type=int, nargs="+", default=DEFAULT_SIZES, help=f"sizes in {UNIT}")
    args = parser.parse_args()
    print(f"{UNIT:>24}  {'seconds':>9}  {'peak MB':>8}")
    for n in args.sizes:
        result = run_once(n)
        if "error" in result:
            print(f"{n:>24,}  failed: {result['error']}")
            continue
        peak = f"{result['peak_mb']:8.0f}" if result["peak_mb"] is not None else "     n/a"
        print(f"{n:>24,}  {result['seconds']:9.2f}  {peak}", flush=True)


if __name__ == "__main__":
    main()
