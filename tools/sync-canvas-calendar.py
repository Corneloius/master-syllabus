#!/usr/bin/env python3
"""
Parse a Canvas-exported .ics and inject rows into index.html /
Master_Syllabus_Spring_2026.html between HTML comment markers.

Also rebuilds GEOG 155 lecture rows in the Semester-at-a-Glance table
(static weekly topics + Canvas due dates for section GEOG-155-250).

Usage:
  python tools/sync-canvas-calendar.py <path-to-calendar.ics> [repo-root]

Copies the .ics to data/canvas-calendar.ics.
"""

from __future__ import annotations

import re
import shutil
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None  # type: ignore

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTH_INDEX = {m: i + 1 for i, m in enumerate(MONTHS)}

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


# Semester-at-a-Glance: static GEOG lecture themes (assignments merged from Canvas).
GEOG_SEMESTER_WEEKS: list[tuple[str, str, str]] = [
    ("1", "Jan 12-16", "Introductions, Introduction to the Earth"),
    ("2", "Jan 19-23", "Portraying Earth"),
    ("3", "Jan 26-30", "Intro to the Atmosphere"),
    ("4", "Feb 2-6", "Insolation and Temperature"),
    ("5", "Feb 9-13", "Atmospheric Pressure and Wind"),
    ("6", "Feb 16-20", "Atmospheric Moisture; EXAM 1"),
    ("7", "Feb 23-27", "Atmospheric Disturbances"),
    ("8", "Mar 2-6", "Climate and Climate Change"),
    ("9", "Mar 9-13", "The Hydrosphere"),
    ("10", "Mar 16-20", "SPRING BREAK - NO CLASS"),
    ("11", "Mar 23-27", "Cycles and Patterns in the Biosphere; Terrestrial Flora and Fauna; Soils; EXAM 2"),
    ("12", "Mar 30-Apr 3", "Introduction to Landform Study"),
    ("13", "Apr 6-10", "Rivers and Fluvial Processes"),
    ("14", "Apr 13-17", "Dynamic Earth"),
    ("15", "Apr 20-24", "Volcanoes / Earthquakes / Glacial Landforms"),
    ("16", "Apr 27-May 1", "Glacial landforms / Study session / Make up work"),
    ("Finals", "May 4", "FINAL EXAM (Exam 3) Monday, May 4, 10am-12pm"),
]


def parse_week_date_range(dr: str, year: int = 2026) -> tuple[date, date]:
    dr = dr.strip()
    m = re.match(r"^([A-Za-z]+)\s+(\d+)\s*-\s*([A-Za-z]+)\s+(\d+)$", dr)
    if m:
        mo1, d1, mo2, d2 = (
            MONTH_INDEX[m.group(1)],
            int(m.group(2)),
            MONTH_INDEX[m.group(3)],
            int(m.group(4)),
        )
        return date(year, mo1, d1), date(year, mo2, d2)
    m = re.match(r"^([A-Za-z]+)\s+(\d+)\s*-\s*(\d+)$", dr)
    if m:
        mo = MONTH_INDEX[m.group(1)]
        d1, d2 = int(m.group(2)), int(m.group(3))
        return date(year, mo, d1), date(year, mo, d2)
    m = re.match(r"^([A-Za-z]+)\s+(\d+)$", dr)
    if m:
        mo = MONTH_INDEX[m.group(1)]
        d = int(m.group(2))
        dd = date(year, mo, d)
        return dd, dd
    raise ValueError(f"unparsed date range: {dr!r}")


def event_to_date(e: dict) -> date:
    kind = e["start"][0]
    if kind == "date":
        _, y, mo, d = e["start"]
        return date(y, mo, d)
    dt_utc: datetime = e["start"][1]
    if ZoneInfo:
        local = dt_utc.astimezone(ZoneInfo("America/Chicago"))
    else:
        local = dt_utc.astimezone(timezone(timedelta(hours=-6)))
    return date(local.year, local.month, local.day)


def geog_lecture_events(events: list[dict]) -> list[dict]:
    return [e for e in events if e["css"] == "geog155" and "GEOG-155-250" in e.get("summaryLine", "")]


def format_canvas_link(url: str) -> str:
    if not url:
        return ""
    u = url.replace("\n", "").replace("\r", "").strip()
    return f' <a href="{escape_html(u)}" target="_blank" rel="noopener">Canvas</a>'


def assignment_cell_for_geog_week(week_key: str, dr: str, lecture_events: list[dict]) -> str:
    d0, d1 = parse_week_date_range(dr)
    in_week = [e for e in lecture_events if d0 <= event_to_date(e) <= d1]
    in_week.sort(key=sort_key)
    parts: list[str] = []
    if week_key == "1":
        parts.append("Major Assign. Gathering Weather Data, Part 1 due Jan 16, 11:59pm")
    for e in in_week:
        due = format_due_central(e["start"])
        parts.append(
            f"{escape_html(e['title'])} due {escape_html(due)}{format_canvas_link(e.get('url', ''))}"
        )
    return "<br>".join(parts) if parts else ""


def build_geog_semester_row(wk: str, dr: str, topic: str, lecture_events: list[dict]) -> str:
    assign = assignment_cell_for_geog_week(wk, dr, lecture_events)
    cls = ' class="geog155"'
    return (
        f'                <tr><td>{escape_html(wk)}</td><td>{escape_html(dr)}</td>'
        f"<td{cls}>GEOG 155</td><td{cls}>{escape_html(topic)}</td><td{cls}>{assign}</td></tr>"
    )


def replace_semester_calendar_geog(html: str, lecture_events: list[dict]) -> str:
    """Update GEOG 155 rows in the Semester-at-a-Glance table in place (order preserved)."""
    cap = 'aria-label="Semester-at-a-Glance Calendar"'
    i = html.find(cap)
    if i == -1:
        print("Warning: Semester-at-a-Glance table not found; skip GEOG merge", file=sys.stderr)
        return html
    tbody_start = html.find("<tbody>", i)
    if tbody_start == -1:
        return html
    tbody_end = html.find("</tbody>", tbody_start)
    if tbody_end == -1:
        return html
    inner = html[tbody_start + len("<tbody>") : tbody_end]
    allowed = {(w, d) for w, d, _ in GEOG_SEMESTER_WEEKS}

    def geog_row_key(tr: str) -> tuple[str, str] | None:
        if 'class="geog155">GEOG 155</td>' not in tr:
            return None
        m = re.match(
            r"\s*<tr><td>([^<]*)</td><td>([^<]*)</td><td class=\"geog155\">GEOG 155</td>",
            tr,
        )
        if not m:
            return None
        return (m.group(1).strip(), m.group(2).strip())

    row_pat = re.compile(r"<tr>.*?</tr>", re.DOTALL)
    parts: list[str] = []
    for tr in row_pat.findall(inner):
        gk = geog_row_key(tr)
        if gk is not None and gk not in allowed:
            continue
        if gk is not None:
            wk, dr = gk
            topic = next(t for w, d, t in GEOG_SEMESTER_WEEKS if w == wk and d == dr)
            tr = build_geog_semester_row(wk, dr, topic, lecture_events)
        parts.append(tr)
    new_inner = "\n" + "\n".join(parts) + "\n            "
    return html[: tbody_start + len("<tbody>")] + new_inner + html[tbody_end:]


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
        summary_raw = props.get("SUMMARY")
        if not summary_raw or not dt_line:
            continue
        summary = re.sub(r"\s+", " ", summary_raw.strip())
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
        title = title.replace("\\,", ",").replace("\\;", ";")
        out.append(
            {
                "uid": props.get("UID") or f"{title}-{sort_key({'start': parsed_start})}",
                "start": parsed_start,
                "courseLabel": course_label,
                "css": css,
                "title": title,
                "url": props.get("URL") or "",
                "summaryLine": summary,
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
        html = replace_semester_calendar_geog(html, geog_lecture_events(events))
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
