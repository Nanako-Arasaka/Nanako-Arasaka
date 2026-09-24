#!/usr/bin/env python3
"""Generate contrib/calendar.svg from the GitHub GraphQL contributions API."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "contrib" / "calendar.svg"
LOGIN = os.environ.get("GITHUB_LOGIN", "Nanako-Arasaka")

# Pink theme matching the profile cards
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
        [
            "gh",
            "api",
            "graphql",
            "-f",
            f"query={QUERY}",
            "-f",
            f"login={LOGIN}",
        ],
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
    cell = 12
    gap = 3
    step = cell + gap
    left = 36
    top = 36
    right = 16
    bottom = 48
    cols = len(weeks)
    rows = 7
    width = left + cols * step - gap + right
    height = top + rows * step - gap + bottom

    months = [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    ]
    weekdays = ["Mon", "", "Wed", "", "Fri", "", ""]

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="{esc(f"{total} contributions in the last year")}">'
    )
    parts.append(
        f'<title>{esc(f"{LOGIN} · {total} contributions in the last year")}</title>'
    )
    parts.append(
        f'<text x="{left}" y="18" fill="{TITLE}" '
        f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif" '
        f'font-size="13" font-weight="600">{total} contributions in the last year</text>'
    )

    # Month labels (first week that starts a month)
    last_month = None
    for col, week in enumerate(weeks):
        day0 = date.fromisoformat(week["contributionDays"][0]["date"])
        if last_month is None or day0.month != last_month:
            if col < cols - 1:
                label = months[day0.month - 1]
                # skip Jan label crowding on first column edge cases
                parts.append(
                    f'<text x="{left + col * step}" y="{top - 8}" fill="{MUTED}" '
                    f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif" '
                    f'font-size="11">{label}</text>'
                )
            last_month = day0.month

    # Weekday labels
    for row, name in enumerate(weekdays):
        if name:
            parts.append(
                f'<text x="{left - 10}" y="{top + row * step + cell}" fill="{MUTED}" '
                f'text-anchor="end" dominant-baseline="middle" '
                f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif" '
                f'font-size="10">{name}</text>'
            )

    # Cells
    for col, week in enumerate(weeks):
        for row, day in enumerate(week["contributionDays"]):
            level = day["contributionLevel"]
            count = day["contributionCount"]
            date_s = day["date"]
            x = left + col * step
            y = top + row * step
            fill = LEVEL_FILL.get(level, LEVEL_FILL["NONE"])
            unit = "contribution" if count == 1 else "contributions"
            tip = esc(f"{count} {unit} on {date_s}")
            parts.append(
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{fill}">'
                f"<title>{tip}</title></rect>"
            )

    # Legend
    legend_y = height - 18
    parts.append(
        f'<text x="{left}" y="{legend_y + cell}" fill="{MUTED}" '
        f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif" '
        f'font-size="10">Less</text>'
    )
    lx = left + 28
    for level in (
        "NONE",
        "FIRST_QUARTILE",
        "SECOND_QUARTILE",
        "THIRD_QUARTILE",
        "FOURTH_QUARTILE",
    ):
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


def main() -> int:
    if "--from-json" in sys.argv:
        path = Path(sys.argv[sys.argv.index("--from-json") + 1])
        calendar = json.loads(path.read_text())
        if "contributionCalendar" in calendar:
            calendar = calendar["contributionCalendar"]
    else:
        calendar = fetch_calendar()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render_svg(calendar), encoding="utf-8")
    readme = ROOT / "README.md"
    if readme.exists():
        text = readme.read_text(encoding="utf-8")
        updated = re.sub(
            r"(\*\*)\d+(\s+contributions\*\* in the last year)",
            rf"\g<1>{calendar['totalContributions']}\g<2>",
            text,
            count=1,
        )
        if updated != text:
            readme.write_text(updated, encoding="utf-8")
            print(f"updated README contribution count -> {calendar['totalContributions']}")
    print(f"wrote {OUT} · total={calendar['totalContributions']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
