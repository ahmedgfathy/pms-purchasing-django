"""Dashboard chart helpers — SVG donuts built without JS or a CDN.

The Win95 screen has to work offline, and every label has to stay
translatable, so only the geometry lives here: each slice is one stroked
circle (a stroke-dasharray arc) and the legend stays in the template.
"""

from __future__ import annotations

import math

# Slice order = legend order. Blue/amber come first so the local/foreign
# pies match the market badges used on every other screen.
PALETTE = (
    "#1d4ed8",  # accent blue
    "#f59e0b",  # amber
    "#16a34a",  # green
    "#94a3b8",  # slate
    "#ef4444",  # red
    "#a855f7",  # violet
    "#14b8a6",  # teal
    "#60a5fa",  # light blue
)


def donut(values, colors=None, size=152, thickness=28):
    """Return the ``<svg>`` markup for a donut chart.

    ``values`` are the slice sizes, ``colors`` the optional per-slice
    colours (defaulting to :data:`PALETTE`). A slice covering the whole
    circle is fine — dash-array arcs handle it — and empty data returns
    an empty string so the template can show a placeholder instead.
    """
    palette = colors or PALETTE
    data = [
        (value, palette[index % len(palette)])
        for index, value in enumerate(values)
        if value > 0
    ]
    total = sum(value for value, _ in data)
    if not total:
        return ""

    radius = (size - thickness) / 2
    centre = size / 2
    circumference = 2 * math.pi * radius
    offset = 0.0
    arcs = []
    for value, color in data:
        dash = value / total * circumference
        arcs.append(
            '<circle cx="{c}" cy="{c}" r="{r}" fill="none" stroke="{color}" '
            'stroke-width="{width}" stroke-dasharray="{dash:.2f} {rest:.2f}" '
            'stroke-dashoffset="{off:.2f}"/>'.format(
                c=centre, r=radius, color=color, width=thickness,
                dash=dash, rest=max(circumference - dash, 0.0), off=-offset,
            )
        )
        offset += dash
    return (
        '<svg class="donut" viewBox="0 0 {size} {size}" aria-hidden="true">'
        '<g transform="rotate(-90 {c} {c})">{arcs}</g></svg>'
    ).format(size=size, c=centre, arcs="".join(arcs))


def abbrev(value):
    """848300227.68 -> ``848.3M`` (stat-card figures only)."""
    value = float(value or 0)
    for divisor, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(value) >= divisor:
            return "%.1f%s" % (value / divisor, suffix)
    return "%.0f" % value
