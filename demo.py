#!/usr/bin/env python3
"""
demo.py — VerticalBarChart showcase

This demo:
- generates deterministic sample values (optionally bounded)
- shows baseline and styled renderings
- demonstrates mixed-sign, positive-only, and negative-only data
- demonstrates ANSI styling, including borders, labels, and heatmap coloring
"""

from __future__ import annotations

import math
from typing import List

from vbchart import VerticalBarChart


def make_sample_values(
    n: int = 100,
    vmin: float = -100.0,
    vmax: float = 100.0,
) -> List[float]:
    """
    Deterministic, non-random signal generator.

    Parameters:
      n    : number of values
      vmin : minimum output value
      vmax : maximum output value

    Produces a smooth signal, scaled and clamped into [vmin, vmax].
    """
    if vmax <= vmin:
        raise ValueError("vmax must be greater than vmin")

    span = vmax - vmin
    mid = (vmax + vmin) / 2.0

    out: List[float] = []
    for i in range(n):
        # base waveform in approximately [-1, 1]
        w = (
            0.65 * math.sin(i * 0.22) +
            0.35 * math.sin(i * 0.07 + 1.2)
        )

        # gentle ramp in roughly [-0.25, 0.25]
        ramp = ((i % 40) - 20) / 80.0

        # combine and clamp to [-1, 1]
        x = max(-1.0, min(1.0, w + ramp))

        # scale into [vmin, vmax]
        v = mid + x * (span / 2.0)

        out.append(v)

    return out


def heatmap_sgr(v: float, vmax: float) -> str:
    """
    ANSI 256-color heatmap:
      negative -> red
      positive -> green → yellow → orange → red
    """
    if vmax <= 0:
        vmax = 1.0

    if v < 0:
        return "38;5;196"  # red

    t = max(0.0, min(1.0, v / vmax))

    # green(46) -> yellow(226) -> orange(208) -> red(196)
    if t < 0.33:
        return "38;5;46"
    if t < 0.66:
        return "38;5;226"
    if t < 0.85:
        return "38;5;208"
    return "38;5;196"


def main() -> None:
    # ---------------- Mixed-sign data ----------------
    values = make_sample_values(100, -100, 100)

    print(VerticalBarChart(
        values,
        title="Mixed-sign values (auto-scaled)",
        show_y_axis=True,
        unicode=True,
    ))

    print()
    print(VerticalBarChart(
        values,
        title="Mixed-sign (forced scale, dollars)",
        max_value=100,
        y_label_fmt="$%+4.0f ",
        show_y_axis=True,
        unicode=True,
    ))

    # ---------------- Styled mixed-sign ----------------
    print()

    styled = VerticalBarChart(
        values,
        title="Styled: heatmap positives + red negatives",
        max_value=100,
        y_label_fmt="$%+4.0f ",
        show_y_axis=True,
        unicode=True,
    )

    styled.SetBorder(True, sgr="38;5;240", charset="single")
    styled.SetLabelSgr("38;5;252")
    styled.SetAxisSgr("38;5;244")
    styled.SetBarSgr("38;5;39")

    def value2sgr(**ctx):
        glyph = ctx["glyph"]
        if glyph == " ":
            return "38;5;238"

        vl = float(ctx["value_left"])
        vr = float(ctx["value_right"])

        if ctx["row_kind"] == "pos":
            candidates = [v for v in (vl, vr) if v > 0]
            if not candidates:
                return "38;5;238"
            return heatmap_sgr(max(candidates), vmax=100.0)

        candidates = [v for v in (vl, vr) if v < 0]
        if not candidates:
            return "38;5;238"
        return "38;5;196"

    styled.SetValueColorCallback(value2sgr)
    print(styled)

    # ---------------- Positive-only data ----------------
    print()

    pos_values = make_sample_values(100, 0, 100)

    print(VerticalBarChart(
        pos_values,
        title="Positive-only values",
        max_value=100,
        y_label_fmt="%3.0f ",
        show_y_axis=True,
        unicode=True,
    ))

    # ---------------- Negative-only data ----------------
    print()

    neg_values = make_sample_values(100, -100, 0)

    print(VerticalBarChart(
        neg_values,
        title="Negative-only values",
        max_value=100,
        y_label_fmt="%3.0f ",
        show_y_axis=True,
        unicode=True,
    ))

    # ---------------- New demo: high-contrast double border ----------------
    print()

    hi_contrast = VerticalBarChart(
        values,
        title="High-contrast: double border (bold red fg) + heatmap values",
        max_value=100,
        y_label_fmt="$%+4.0f ",
        show_y_axis=True,
        unicode=True,
    )

    hi_contrast.SetBorder(True, sgr="1;38;5;196", charset="double")
    hi_contrast.SetAxisSgr("38;5;88")
    hi_contrast.SetBarSgr("38;5;39")

    def hi_contrast_heat(**ctx):
        glyph = ctx["glyph"]
        if glyph == " ":
            return "38;5;250"

        vl = float(ctx["value_left"])
        vr = float(ctx["value_right"])

        if ctx["row_kind"] == "pos":
            candidates = [v for v in (vl, vr) if v > 0]
            if not candidates:
                return "38;5;250"
            fg = heatmap_sgr(max(candidates), vmax=100.0)
            return f"1;{fg}"

        candidates = [v for v in (vl, vr) if v < 0]
        if not candidates:
            return "38;5;250"
        return "1;38;5;196"

    hi_contrast.SetValueColorCallback(hi_contrast_heat)
    print(hi_contrast)


if __name__ == "__main__":
    main()
