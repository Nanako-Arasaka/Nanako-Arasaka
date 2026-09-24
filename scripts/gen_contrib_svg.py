#!/usr/bin/env python3
"""Generate contrib/calendar.svg and refresh the README contribution block."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SVG_OUT = ROOT / "contrib" / "calendar.svg"
README = ROOT / "README.md"
LOGIN = os.environ.get("GITHUB_LOGIN", "Nanako-Arasaka")

LEVEL_FILL = {
    "NONE": "#ffe0e6",
    "FIRST_QUARTILE": "#ffb3c1",
    "SECOND_QUARTILE": "#fd79a8",
    "THIRD_QUARTILE": "#f368a0",
    "FOURTH_QUARTILE": "#e84393",
}
TEXT = "#2d3436"
MUTED = "#636e72"
TITLE = "#e84393"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
BEGIN = "<!-- contrib-calendar:begin -->"
END = "<!-- contrib-calendar:end -->"

QUERY = """
query($login:String!){
  user(login:$login){
    contributionsCollection{
      contributionCalendar{
        totalContributions
        weeks{ contributionDays{ date contributionCount contributionLevel weekday } }
      }
    }
  }
}
"""


def fetch_calendar() -> dict:
    result = subprocess.run(
        ["gh", "api", "graphql", "-f", f"query={QUERY}", "-f", f"login={LOGIN}"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    return payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]


def esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def render_svg(calendar: dict) -> str:
    weeks = calendar["weeks"]
    total = calendar["totalContributions"]
    cell, gap = 12, 3
    step = cell + gap
    left, top, right, bottom = 36, 36, 16, 48
    cols, rows = len(weeks), 7
    width = left + cols * step - gap + right
    height = top + rows * step - gap + bottom
    weekdays = ["Mon", "", "Wed", "", "Fri", "", ""]

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="{esc(f"{total} contributions in the last year")}">',
        f"<title>{esc(f'{LOGIN} · {total} contributions in the last year')}</title>",
        f'<text x="{left}" y="18" fill="{TITLE}" '
        f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif" '
        f'font-size="13" font-weight="600">{total} contributions in the last year</text>',
    ]

    last_month = None
    for col, week in enumerate(weeks):
        day0 = date.fromisoformat(week["contributionDays"][0]["date"])
        if last_month is None or day0.month != last_month:
            if col < cols - 1:
                parts.append(
                    f'<text x="{left + col * step}" y="{top - 8}" fill="{MUTED}" '
                    f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif" '
                    f'font-size="11">{MONTHS[day0.month - 1]}</text>'
                )
            last_month = day0.month

    for row, name in enumerate(weekdays):
        if name:
            parts.append(
                f'<text x="{left - 10}" y="{top + row * step + cell}" fill="{MUTED}" '
                f'text-anchor="end" dominant-baseline="middle" '
                f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif" '
                f'font-size="10">{name}</text>'
            )

    for col, week in enumerate(weeks):
        for row, day in enumerate(week["contributionDays"]):
            fill = LEVEL_FILL.get(day["contributionLevel"], LEVEL_FILL["NONE"])
            unit = "contribution" if day["contributionCount"] == 1 else "contributions"
            tip = esc(f"{day['contributionCount']} {unit} on {day['date']}")
            parts.append(
                f'<rect x="{left + col * step}" y="{top + row * step}" width="{cell}" '
                f'height="{cell}" rx="2" fill="{fill}"><title>{tip}</title></rect>'
            )

    legend_y = height - 18
    parts.append(
        f'<text x="{left}" y="{legend_y + cell}" fill="{MUTED}" '
        f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif" '
        f'font-size="10">Less</text>'
    )
    lx = left + 28
    for level in ("NONE", "FIRST_QUARTILE", "SECOND_QUARTILE", "THIRD_QUARTILE", "FOURTH_QUARTILE"):
        parts.append(
            f'<rect x="{lx}" y="{legend_y}" width="{cell}" height="{cell}" rx="2" '
            f'fill="{LEVEL_FILL[level]}"/>'
        )
        lx += step
    parts.append(
        f'<text x="{lx + 4}" y="{legend_y + cell}" fill="{MUTED}" '
        f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif" '
        f'font-size="10">More</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def render_block(calendar: dict) -> str:
    total = calendar["totalContributions"]
    alt = esc(f"{total} contributions in the last year")
    return "\n".join(
        [
            BEGIN,
            f"<p><b>{total} contributions</b> in the last year</p>",
            "",
            '<div align="center">',
            f'  <img src="./contrib/calendar.svg" alt="{alt}" />',
            "</div>",
            END,
        ]
    )


def update_readme(calendar: dict) -> None:
    if not README.exists():
        return
    text = README.read_text(encoding="utf-8")
    block = render_block(calendar)
    if BEGIN in text and END in text:
        updated = re.sub(
            re.escape(BEGIN) + r".*?" + re.escape(END),
            block,
            text,
            count=1,
            flags=re.S,
        )
    else:
        updated = text
    updated = updated.replace(" · 悬停查看每日详情", "").replace("悬停查看每日详情", "")
    if updated != text:
        README.write_text(updated, encoding="utf-8")
        print(f"updated README · total={calendar['totalContributions']}")
    else:
        print("README already up to date")


def main() -> int:
    if "--from-json" in sys.argv:
        path = Path(sys.argv[sys.argv.index("--from-json") + 1])
        calendar = json.loads(path.read_text())
        if "contributionCalendar" in calendar:
            calendar = calendar["contributionCalendar"]
    else:
        calendar = fetch_calendar()

    SVG_OUT.parent.mkdir(parents=True, exist_ok=True)
    SVG_OUT.write_text(render_svg(calendar), encoding="utf-8")
    update_readme(calendar)
    print(f"wrote {SVG_OUT} · total={calendar['totalContributions']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
