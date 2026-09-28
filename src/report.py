"""Turns the per-hall results into report.md and one chart."""

from __future__ import annotations

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

from src.chart_style import (
    INK,
    NOT_STARTED,
    STATUS_CRITICAL,
    STATUS_GOOD,
    STATUS_WARNING,
    apply_chrome,
)
from src.inputs import Levels
from src.rules import BLOCKS, CONDITIONAL, NOT_READY, READY, HallResult

VERDICT_COLOR = {READY: STATUS_GOOD, "conditional": STATUS_WARNING, NOT_READY: STATUS_CRITICAL}
EFFECT_ORDER = {BLOCKS: 0, CONDITIONAL: 1, "info": 2}


def verdict_label(verdict: str) -> str:
    return verdict.upper().replace("-", " ")


def summary_lines(results: list[HallResult], levels: Levels, settings: dict) -> list[str]:
    """The console summary: one line per hall, then its blocking/conditional reasons."""
    lines = [
        f"Commissioning readiness as of {settings['status_date']:%Y-%m-%d} "
        f"(site {settings['site']}, {len(results)} halls)",
        "",
    ]
    for r in results:
        lines.append(
            f"{r.hall}  next: {r.target_level} {levels.name(r.target_level)}, "
            f"planned {r.planned_date:%Y-%m-%d} ({r.days_to_planned} days)  "
            f"{verdict_label(r.verdict)}"
        )
        for reason in sorted(r.reasons, key=lambda x: EFFECT_ORDER[x.effect]):
            if reason.effect != "info":
                lines.append(f"  - {reason.rule}: {reason.detail}")
    return lines


def write_report(results: list[HallResult], levels: Levels, settings: dict, path: str) -> None:
    out = [
        "# Commissioning readiness report",
        "",
        f"Site {settings['site']}, status date {settings['status_date']:%Y-%m-%d}. "
        "Sample data, all synthetic.",
        "",
        "| Hall | Next level | Planned start | Days to go | Design IT load | Verdict |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        out.append(
            f"| {r.hall} | {r.target_level} {levels.name(r.target_level)} | "
            f"{r.planned_date:%Y-%m-%d} | {r.days_to_planned} | {r.design_it_kw:.0f} kW | "
            f"**{verdict_label(r.verdict)}** |"
        )
    for r in results:
        out += ["", f"## {r.hall}: {verdict_label(r.verdict)}", ""]
        if r.reasons:
            out += ["| Rule | Effect | Detail |", "|---|---|---|"]
            for reason in sorted(r.reasons, key=lambda x: EFFECT_ORDER[x.effect]):
                out.append(f"| {reason.rule} | {reason.effect} | {reason.detail} |")
        else:
            out.append("No open reasons against the next level.")
        out += ["", "Level progress (closed and signed / total):", ""]
        out.append("| " + " | ".join(levels.order) + " |")
        out.append("|" + "---|" * len(levels.order))
        out.append("| " + " | ".join(f"{c}/{t}" for c, t in (r.progress[lv] for lv in levels.order)) + " |")
    out += [
        "",
        "Levels as defined in config/levels.yaml. The L1 to L5 numbering is "
        "industry convention, not a standard; see the README for sources.",
        "",
    ]
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out))


def _cell_color(closed: int, total: int) -> str:
    if closed == total:
        return STATUS_GOOD
    return STATUS_WARNING if closed else NOT_STARTED


# The readiness chart shows at most this many halls. Its height grows with
# every hall, so a site with hundreds of halls produced a very tall image
# and most of the run's memory. Every hall is still in report.md.
CHART_TOP_N = 30
_VERDICT_PRIORITY = {NOT_READY: 0, "conditional": 1, READY: 2}


def chart_halls(results: list[HallResult]) -> list[HallResult]:
    """The halls the chart shows: all of them, or the CHART_TOP_N furthest
    from ready (not ready, then conditional, soonest planned date first),
    kept in their usual order."""
    if len(results) <= CHART_TOP_N:
        return results
    ranked = sorted(range(len(results)),
                    key=lambda i: (_VERDICT_PRIORITY.get(results[i].verdict, 3), results[i].days_to_planned, i))
    keep = set(ranked[:CHART_TOP_N])
    return [r for i, r in enumerate(results) if i in keep]


def write_chart(results: list[HallResult], levels: Levels, path: str) -> None:
    """Halls by level: closed/total per cell, the next level outlined, then the verdict."""
    total = len(results)
    results = chart_halls(results)
    cols = levels.order + ["Verdict"]
    fig, ax = plt.subplots(figsize=(9, 1.2 + 0.8 * len(results)))
    for row, r in enumerate(results):
        for col, lv in enumerate(levels.order):
            closed, total = r.progress[lv]
            is_target = lv == r.target_level
            ax.add_patch(Rectangle(
                (col, row), 0.94, 0.86, facecolor=_cell_color(closed, total),
                edgecolor=INK, linewidth=2.2 if is_target else 0.4,
            ))
            text_color = "white" if closed == total else INK
            ax.text(col + 0.47, row + 0.43, f"{closed}/{total}", ha="center", va="center",
                    fontsize=10, color=text_color)
        ax.add_patch(Rectangle(
            (len(levels.order), row), 1.6, 0.86, facecolor=VERDICT_COLOR[r.verdict],
            edgecolor=INK, linewidth=0.4,
        ))
        ax.text(len(levels.order) + 0.8, row + 0.43, verdict_label(r.verdict), ha="center",
                va="center", fontsize=10, fontweight="bold",
                color=INK if r.verdict == "conditional" else "white")
        ax.text(-0.15, row + 0.43, r.hall, ha="right", va="center", fontsize=10, color=INK)
    for col, name in enumerate(cols):
        x = col + (0.47 if name != "Verdict" else 0.8)
        ax.text(x, -0.25, name, ha="center", va="bottom", fontsize=10, color=INK)
    ax.set_xlim(-0.9, len(levels.order) + 1.7)
    ax.set_ylim(len(results) + 0.1, -0.7)
    ax.set_axis_off()
    apply_chrome(fig, ax)
    ax.set_title(
        "Commissioning progress by hall (devices closed and signed / total; "
        "outlined = next level)"
        + (f", {len(results)} furthest from ready of {total} halls" if len(results) < total else ""),
        fontsize=10, color=INK,
    )
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
