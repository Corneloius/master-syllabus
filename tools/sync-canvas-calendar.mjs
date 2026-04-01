#!/usr/bin/env node
/**
 * Parse a Canvas-exported .ics calendar and inject rows into index.html /
 * Master_Syllabus_Spring_2026.html between HTML comment markers.
 *
 * Usage:
 *   node tools/sync-canvas-calendar.mjs <path-to-calendar.ics> [repo-root]
 *
 * Default repo-root is the parent of the directory containing this script.
 * Also copies the .ics to data/canvas-calendar.ics when data/ exists.
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

const COURSE_CLASS = {
  "BSAD-50": "bsad50",
  "BSAD-222": "bsad222",
  "MATH-101": "math101",
  "GEOG-155": "geog155",
  "MNGT-101": "mngt101",
  "MRKT-257": "mrkt257",
};

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function unfoldIcs(text) {
  const raw = text.split(/\r?\n/);
  const lines = [];
  for (const line of raw) {
    if (line.length === 0) continue;
    if ((line[0] === " " || line[0] === "\t") && lines.length) {
      lines[lines.length - 1] += line.slice(1);
    } else {
      lines.push(line);
    }
  }
  return lines.join("\n");
}

/** @returns {{ type: 'date', y: number, mo: number, d: number } | { type: 'utc', ms: number } | null} */
function parseDtstart(line) {
  const idx = line.indexOf(":");
  if (idx === -1) return null;
  const v = line.slice(idx + 1).trim();
  if (/^\d{8}$/.test(v)) {
    return { type: "date", y: +v.slice(0, 4), mo: +v.slice(4, 6), d: +v.slice(6, 8) };
  }
  const utc = v.match(/^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z$/);
  if (utc) {
    const iso = `${utc[1]}-${utc[2]}-${utc[3]}T${utc[4]}:${utc[5]}:${utc[6]}Z`;
    const ms = Date.parse(iso);
    return Number.isNaN(ms) ? null : { type: "utc", ms };
  }
  const local = v.match(/^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})$/);
  if (local) {
    const iso = `${local[1]}-${local[2]}-${local[3]}T${local[4]}:${local[5]}:${local[6]}`;
    const ms = Date.parse(`${iso}-06:00`);
    return Number.isNaN(ms) ? null : { type: "utc", ms };
  }
  return null;
}

function sortKey(p) {
  if (p.type === "date") return Date.UTC(p.y, p.mo - 1, p.d, 7, 0, 0);
  return p.ms;
}

function formatDue(p) {
  if (p.type === "date") {
    return `${MONTHS[p.mo - 1]} ${p.d}, 11:59pm`;
  }
  const d = new Date(p.ms);
  const fmt = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/Chicago",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });
  const parts = fmt.formatToParts(d);
  const m = {};
  for (const { type, value } of parts) {
    if (type !== "literal") m[type] = value;
  }
  const ap = (m.dayPeriod || "").toLowerCase();
  return `${m.month} ${m.day}, ${m.hour}:${m.minute}${ap}`;
}

function parseEvents(text) {
  const body = unfoldIcs(text);
  const chunks = body.split(/BEGIN:VEVENT\r?\n/);
  const out = [];
  for (const chunk of chunks) {
    if (!chunk.trim()) continue;
    const end = chunk.indexOf("END:VEVENT");
    const block = end === -1 ? chunk : chunk.slice(0, end);
    const lines = block.split(/\n/);
    /** @type {Record<string, string>} */
    const props = {};
    for (const ln of lines) {
      const c = ln.indexOf(":");
      if (c === -1) continue;
      const key = ln.slice(0, c).split(";")[0];
      const val = ln.slice(c + 1);
      if (key === "SUMMARY" || key === "UID" || key === "URL") {
        props[key] = val;
      }
      if (key === "DTSTART") {
        props.DTSTART_LINE = ln;
      }
    }
    const summary = props.SUMMARY;
    if (!summary || !props.DTSTART_LINE) continue;
    const start = parseDtstart(props.DTSTART_LINE);
    if (!start) continue;
    const match = summary.trim().match(/\[([A-Z]+)-(\d+)-[^\]]+\]\s*$/);
    let dept = "";
    let num = "";
    let css = "";
    let courseLabel = "";
    if (match) {
      dept = match[1];
      num = match[2];
      const key = `${dept}-${num}`;
      css = COURSE_CLASS[key] || "";
      courseLabel = `${dept} ${num}`;
    } else {
      courseLabel = "Other";
    }
    let title = summary.replace(/\s*\[[A-Z]+-\d+-[^\]]+\]\s*$/, "").trim();
    title = title.replace(/\s+/g, " ");
    const url = props.URL || "";
    out.push({
      uid: props.UID || `${title}-${sortKey(start)}`,
      start,
      courseLabel,
      css,
      title,
      url,
    });
  }
  out.sort((a, b) => sortKey(a.start) - sortKey(b.start));
  const seen = new Set();
  return out.filter((e) => {
    if (seen.has(e.uid)) return false;
    seen.add(e.uid);
    return true;
  });
}

function rowDeadlines(e) {
  const cls = e.css ? ` class="${e.css}"` : "";
  const assign = escapeHtml(e.title);
  const notes = e.url
    ? `<a href="${escapeHtml(e.url)}" target="_blank" rel="noopener">Canvas</a>`
    : "";
  const type = "Canvas";
  return `                <tr><td>${escapeHtml(formatDue(e.start))}</td><td${cls}>${escapeHtml(e.courseLabel)}</td><td${cls}>${assign}</td><td>${type}</td><td>${notes}</td></tr>`;
}

function rowCalendar(e) {
  const cls = e.css ? ` class="${e.css}"` : "";
  const assign = escapeHtml(e.title);
  const link = e.url
    ? `<a href="${escapeHtml(e.url)}" target="_blank" rel="noopener">Open</a>`
    : "";
  return `                <tr><td>${escapeHtml(formatDue(e.start))}</td><td${cls}>${escapeHtml(e.courseLabel)}</td><td${cls}>${assign}</td><td>${link}</td></tr>`;
}

function replaceRegion(html, startTag, endTag, innerLines) {
  const re = new RegExp(`(${startTag})[\\s\\S]*?(${endTag})`);
  if (!re.test(html)) {
    throw new Error(`Missing markers ${startTag} … ${endTag}`);
  }
  return html.replace(re, `$1\n${innerLines}\n$2`);
}

function main() {
  const icsArg = process.argv[2];
  if (!icsArg) {
    console.error("Usage: node tools/sync-canvas-calendar.mjs <file.ics> [repo-root]");
    process.exit(1);
  }
  const repoRoot = path.resolve(process.argv[3] || path.join(__dirname, ".."));
  const icsPath = path.resolve(icsArg);
  if (!fs.existsSync(icsPath)) {
    console.error("ICS file not found:", icsPath);
    process.exit(1);
  }

  const icsText = fs.readFileSync(icsPath, "utf8");
  const events = parseEvents(icsText);
  const deadlineRows = events.map(rowDeadlines).join("\n");
  const calendarRows = events.map(rowCalendar).join("\n");

  const htmlNames = ["index.html", "Master_Syllabus_Spring_2026.html"];
  for (const name of htmlNames) {
    const fp = path.join(repoRoot, name);
    if (!fs.existsSync(fp)) {
      console.warn("Skip missing file:", fp);
      continue;
    }
    let html = fs.readFileSync(fp, "utf8");
    html = replaceRegion(
      html,
      "<!-- CANVAS-DEADLINES:AUTO-START -->",
      "<!-- CANVAS-DEADLINES:AUTO-END -->",
      deadlineRows,
    );
    html = replaceRegion(
      html,
      "<!-- CANVAS-CALENDAR-ROWS:AUTO-START -->",
      "<!-- CANVAS-CALENDAR-ROWS:AUTO-END -->",
      calendarRows,
    );
    fs.writeFileSync(fp, html, "utf8");
    console.log("Updated", fp, `(${events.length} events)`);
  }

  const dataDir = path.join(repoRoot, "data");
  if (!fs.existsSync(dataDir)) {
    fs.mkdirSync(dataDir, { recursive: true });
  }
  const destIcs = path.join(dataDir, "canvas-calendar.ics");
  fs.copyFileSync(icsPath, destIcs);
  console.log("Copied ICS to", destIcs);
}

main();
