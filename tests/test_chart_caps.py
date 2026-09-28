"""The readiness chart caps itself at CHART_TOP_N halls; report.md doesn't."""

from __future__ import annotations

from types import SimpleNamespace

from src import report


def _results(n: int):
    verdicts = [report.READY, "conditional", report.NOT_READY]
    return [SimpleNamespace(hall=f"DH{i}", verdict=verdicts[i % 3], days_to_planned=100 - i) for i in range(n)]


def test_small_sites_are_charted_in_full():
    results = _results(10)
    assert report.chart_halls(results) == results


def test_large_sites_chart_the_halls_furthest_from_ready_in_order():
    results = _results(90)
    shown = report.chart_halls(results)
    assert len(shown) == report.CHART_TOP_N
    assert all(r.verdict == report.NOT_READY for r in shown)
    assert [r.hall for r in shown] == [r.hall for r in results if r in shown]
