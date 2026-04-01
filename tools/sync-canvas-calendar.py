#!/usr/bin/env python3
"""
Parse a Canvas-exported .ics and inject rows into index.html /
Master_Syllabus_Spring_2026.html between HTML comment markers.

Usage:
  python tools/sync-canvas-calendar.py <path-to-calendar.ics> [repo-root]

Copies the .ics to data/canvas-calendar.ics.
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

COURSE_CLASS = {
    "BSAD-50": "bsad50",
    "BSAD-222": "bsad222",
    "MATH-101": "math101",
    "GEOG-155": "geog155",
    "MNGT-101": "mngt101",
    "MRKT-257": "mrkt257",
}


def escape_html(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def unfold_ics(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        if not line:
            continue
        if line[0] in " \t" and lines:
            lines[-1] += line[1:]
        else:
            lines.append(line)
    return "\n".join(lines)


def parse_dtstart(line: str):
    if ":" not in line:
        return None
    key, _, v = line.partition(":")
    v = v.strip()
    if re.fullmatch(r"\d{8}", v):
        return ("date", int(v[0:4]), int(v[4:6]), int(v[6:8]))
    m = re.fullmatch(r"(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z", v)
    if m:
        iso = f"{m[1]}-{m[2]}-{m[3]}T{m[4]}:{m[5]}:{m[6]}+00:00"
        from datetime import datetime

        dt = datetime.fromisoformat(iso)
        return ("utc", dt)
    m = re.fullmatch(r"(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})", v)
    if m:
        from datetime import datetime, timezone

        dt = datetime(
            int(m[1]),
            int(m[2]),
            int(m[3]),
            int(m[4]),
            int(m[5]),
            int(m[6]),
            tzinfo=timezone.utc,
        )
        return ("utc", dt)
    return None


def sort_key(p):
    kind = p["start"][0]
    if kind == "date":
        _, y, mo, d = p["start"]
        from datetime import datetime, timezone

        return datetime(y, mo, d, 7, 0, tzinfo=timezone.utc).timestamp()
    return p["start"][1].timestamp()


def format_due_central(start) -> str:
    from datetime import datetime, timedelta, timezone

    try:
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("America/Chicago")
    except ImportError:
        tz = timezone(timedelta(hours=-6))

    kind = start[0]
    if kind == "date":
        _, _y, mo, d = start
        return f"{MONTHS[mo - 1]} {d}, 11:59pm"
    dt_utc: datetime = start[1]
    local = dt_utc.astimezone(tz)
    mon = MONTHS[local.month - 1]
    day = local.day
    hour12 = local.hour % 12 or 12
    mi = local.minute
    ap = "am" if local.hour < 12 else "pm"
    return f"{mon} {day}, {hour12}:{mi:02d}{ap}"


def parse_events(text: str) -> list[dict]:
    body = unfold_ics(text)
    chunks = re.split(r"BEGIN:VEVENT\r?\n", body)
    out: list[dict] = []
    summary_re = re.compile(r"\[([A-Z]+)-(\d+)-[^\]]+\]\s*$")

    for chunk in chunks:
        if "END:VEVENT" not in chunk:
            continue
        block = chunk.split("END:VEVENT", 1)[0]
        props: dict = {}
        dt_line = None
        for ln in block.split("\n"):
            if ":" not in ln:
                continue
            key_full, _, val = ln.partition(":")
            key = key_full.split(";")[0]
            if key in ("SUMMARY", "UID", "URL"):
                props[key] = val
            elif key == "DTSTART":
                dt_line = ln
        summary = props.get("SUMMARY")
        if not summary or not dt_line:
            continue
        parsed_start = parse_dtstart(dt_line)
        if not parsed_start:
            continue
        m = summary_re.search(summary.strip())
        if m:
            dept, num = m.group(1), m.group(2)
            ck = f"{dept}-{num}"
            css = COURSE_CLASS.get(ck, "")
            course_label = f"{dept} {num}"
        else:
            css = ""
            course_label = "Other"
        title = summary_re.sub("", summary).strip()
        title = re.sub(r"\s+", " ", title)
        out.append(
            {
                "uid": props.get("UID") or f"{title}-{sort_key({'start': parsed_start})}",
                "start": parsed_start,
                "courseLabel": course_label,
                "css": css,
                "title": title,
                "url": props.get("URL") or "",
            }
        )

    out.sort(key=sort_key)
    seen: set[str] = set()
    uniq = []
    for e in out:
        u = e["uid"]
        if u in seen:
            continue
        seen.add(u)
        uniq.append(e)
    return uniq


def row_deadlines(e: dict) -> str:
    cls = f' class="{e["css"]}"' if e["css"] else ""
    assign = escape_html(e["title"])
    notes = (
        f'<a href="{escape_html(e["url"])}" target="_blank" rel="noopener">Canvas</a>'
        if e["url"]
        else ""
    )
    due = format_due_central(e["start"])
    return f'                <tr><td>{escape_html(due)}</td><td{cls}>{escape_html(e["courseLabel"])}</td><td{cls}>{assign}</td><td>Canvas</td><td>{notes}</td></tr>'


def row_calendar(e: dict) -> str:
    cls = f' class="{e["css"]}"' if e["css"] else ""
    assign = escape_html(e["title"])
    link = (
        f'<a href="{escape_html(e["url"])}" target="_blank" rel="noopener">Open</a>'
        if e["url"]
        else ""
    )
    due = format_due_central(e["start"])
    return f'                <tr><td>{escape_html(due)}</td><td{cls}>{escape_html(e["courseLabel"])}</td><td{cls}>{assign}</td><td>{link}</td></tr>'


def replace_region(html: str, start_tag: str, end_tag: str, inner: str) -> str:
    pattern = re.compile(re.escape(start_tag) + r"[\s\S]*?" + re.escape(end_tag))
    if not pattern.search(html):
        raise SystemExit(f"Missing markers: {start_tag} … {end_tag}")
    return pattern.sub(f"{start_tag}\n{inner}\n{end_tag}", html, count=1)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python tools/sync-canvas-calendar.py <file.ics> [repo-root]", file=sys.stderr)
        sys.exit(1)
    ics_path = Path(sys.argv[1]).resolve()
    repo = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else Path(__file__).resolve().parent.parent
    if not ics_path.is_file():
        print("ICS not found:", ics_path, file=sys.stderr)
        sys.exit(1)

    events = parse_events(ics_path.read_text(encoding="utf-8", errors="replace"))
    deadline_rows = "\n".join(row_deadlines(e) for e in events)
    calendar_rows = "\n".join(row_calendar(e) for e in events)

    for name in ("index.html", "Master_Syllabus_Spring_2026.html"):
        fp = repo / name
        if not fp.is_file():
            print("Skip:", fp)
            continue
        html = fp.read_text(encoding="utf-8")
        html = replace_region(
            html,
            "<!-- CANVAS-DEADLINES:AUTO-START -->",
            "<!-- CANVAS-DEADLINES:AUTO-END -->",
            deadline_rows,
        )
        html = replace_region(
            html,
            "<!-- CANVAS-CALENDAR-ROWS:AUTO-START -->",
            "<!-- CANVAS-CALENDAR-ROWS:AUTO-END -->",
            calendar_rows,
        )
        fp.write_text(html, encoding="utf-8")
        print("Updated", fp, f"({len(events)} events)")

    data_dir = repo / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    dest = data_dir / "canvas-calendar.ics"
    shutil.copy2(ics_path, dest)
    print("Copied ICS to", dest)


if __name__ == "__main__":
    main()
