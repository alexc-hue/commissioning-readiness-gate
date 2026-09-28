"""The README's Result block and the committed report have to match the code.

Runs the real entry script (gate.py) end to end against the sample data,
writing its outputs to a temp directory so assets/ is left alone. Then:

- every line of the fenced block under "## Result" in README.md must appear,
  in order and unbroken, in what the script printed;
- the report.md it wrote must be identical to assets/report.md;
- the chart must be a PNG.
"""

from __future__ import annotations

import re
from pathlib import Path

import gate as tool

ROOT = Path(__file__).resolve().parents[1]


def _readme_result_block() -> list[str]:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "\n## Result" in text, "README.md has no '## Result' section"
    section = text.split("\n## Result", 1)[1].split("\n## ", 1)[0]
    match = re.search(r"```[^\n]*\n(.*?)```", section, re.S)
    assert match, "No fenced code block under '## Result' in README.md"
    return [line.rstrip() for line in match.group(1).rstrip("\n").splitlines()]


def _run(monkeypatch, tmp_path, capsys) -> list[str]:
    monkeypatch.setattr(tool, "ASSETS_DIR", str(tmp_path))
    tool.main([])
    return [line.rstrip() for line in capsys.readouterr().out.splitlines()]


def test_readme_result_block_matches_script_output(monkeypatch, tmp_path, capsys):
    # "Wrote" lines name wherever the outputs went, a temp dir in this test.
    expected = [ln for ln in _readme_result_block() if not ln.startswith("Wrote ")]
    output = [ln for ln in _run(monkeypatch, tmp_path, capsys) if not ln.startswith("Wrote ")]
    n = len(expected)
    assert any(output[i:i + n] == expected for i in range(len(output) - n + 1)), (
        "README.md's Result block no longer matches the script's output.\n"
        "Actual output:\n" + "\n".join(output)
    )


def test_committed_report_matches_a_fresh_run(monkeypatch, tmp_path, capsys):
    _run(monkeypatch, tmp_path, capsys)
    fresh = (tmp_path / "report.md").read_text(encoding="utf-8")
    committed = (ROOT / "assets" / "report.md").read_text(encoding="utf-8")
    assert fresh == committed, "assets/report.md is out of date: run python gate.py"
    assert (tmp_path / "readiness_matrix.png").read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_sample_data_gives_one_of_each_verdict(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(tool, "ASSETS_DIR", str(tmp_path))
    results = tool.main([])
    assert {r.hall: r.verdict for r in results} == {
        "DH1": "ready", "DH2": "conditional", "DH3": "not-ready",
    }
