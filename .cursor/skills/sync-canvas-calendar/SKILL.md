---
name: sync-canvas-calendar
description: >-
  Updates syllabus HTML from a Canvas calendar export (.ics): run paths, committed
  copy at data/canvas-calendar.ics, injected table regions, and how to verify
  Semester-at-a-Glance vs Canvas-generated tables. Use when syncing Canvas,
  refreshing calendar rows, ICS exports, deadlines tables, or GEOG 155
  assignment merges in the master syllabus repo.
---

# Sync Canvas calendar into syllabus HTML

## ICS source

- Export the calendar from Canvas to a local `.ics` file (any path). The sync script copies the **same bytes** to the repo as `data/canvas-calendar.ics` (created if needed).
- Canonical path after sync: `data/canvas-calendar.ics`.

## Commands (from repo root unless you pass `[repo-root]`)

**Preferred (Python):**

```bash
python tools/sync-canvas-calendar.py <path-to-export.ics>
```

**Optional second argument** — absolute path to repo root if the shell is not already there:

```bash
python tools/sync-canvas-calendar.py <path-to-export.ics> <repo-root>
```

**Alternative:** `node tools/sync-canvas-calendar.mjs <path-to-export.ics> [repo-root]` (same markers and `data/` copy).

Requires: Python 3 with `zoneinfo` (stdlib) for America/Chicago due times.

## Files the tool changes

| File | What happens |
|------|----------------|
| `Master_Syllabus_Spring_2026.html` | GEOG merge + both Canvas marker blocks rewritten if file exists |
| `index.html` | Same updates (kept in lockstep with master when both exist) |
| `data/canvas-calendar.ics` | Copy of the input `.ics` |

**HTML markers** (do not remove or duplicate):

- `<!-- CANVAS-CALENDAR-ROWS:AUTO-START -->` … `<!-- CANVAS-CALENDAR-ROWS:AUTO-END -->` — rows for the **Semester-at-a-Glance** section’s *Canvas-sourced* assignment calendar table (columns: due, course, assignment, link).
- `<!-- CANVAS-DEADLINES:AUTO-START -->` … `<!-- CANVAS-DEADLINES:AUTO-END -->` — rows for the **Important assignment due dates** table (includes Canvas note column).

**Semester-at-a-Glance GEOG 155 rows:** The script finds the table with `aria-label="Semester-at-a-Glance Calendar"`, replaces only rows where `GEOG 155` appears with `class="geog155"`, and fills the assignments column from Canvas events whose summary matches course code in `SUMMARY` and section **`GEOG-155-250`** (see `geog_lecture_events()` in `tools/sync-canvas-calendar.py`). Week/theme structure comes from the in-script `GEOG_SEMESTER_WEEKS` list—not from ICS.

## Manual edits vs sync

For syllabus content **outside** the auto regions, follow repo convention: edit `Master_Syllabus_Spring_2026.html` first, then mirror to `index.html`. The sync script overwrites **only** the GEOG-row merge in the glance table and the two comment-marked regions in **both** files.

## Verify after sync

1. **Script output:** Each updated HTML file should print `Updated <path> (N events)`; `Copied ICS to data/canvas-calendar.ics`.
2. **`data/canvas-calendar.ics`:** Open or diff—should match the export you passed in (timestamp may change from `copy2`).
3. **Semester-at-a-Glance (`#calendar`):**
   - Scroll to **SEMESTER-AT-A-GLANCE CALENDAR**.
   - **Other course rows** (BSAD, MATH, etc.): unchanged by sync except the injected **Canvas calendar** table body between `CANVAS-CALENDAR-ROWS` markers—spot-check row count vs Canvas and due dates (Central).
   - **GEOG 155 rows:** Same weekly labels; **Assignments** cells should list items from the export that fall in each week and show **Canvas** links when `URL` is present in the event.
4. **Important assignment due dates:** Table between `CANVAS-DEADLINES` markers—courses with recognized `[DEPT-NNN-SECTION]` summaries get CSS classes; **Other** for unmatched summaries.
5. **Quick grep:** `rg "CANVAS-CALENDAR-ROWS:AUTO" Master_Syllabus_Spring_2026.html` — exactly one START and one END; same for `CANVAS-DEADLINES`.

## If something breaks

- **"Missing markers"** — restore `<!-- CANVAS-*:AUTO-START/END -->` pairs in both HTML files (copy from git history).
- **Empty or wrong rows** — Confirm Canvas export includes `SUMMARY` and `DTSTART`; course styling requires trailing `[XXX-###-SECTION]` pattern on the summary line in the `.ics`.

For implementation details, read `tools/sync-canvas-calendar.py` (single source of truth).
