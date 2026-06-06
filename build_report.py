#!/usr/bin/env python3
"""Build attendance report from Google Sheets — No Name School."""
import csv, io, re, urllib.parse, urllib.request, sys
from datetime import datetime
from pathlib import Path

SHEET_ID = "1zyma_6St8I1MArkh_0U2biHfc29uIwvs"
OUT = Path(__file__).parent / "index.html"

SHEETS = [
    ("3-5 (Meto Pema)",              "Meto Pema",     "3–5 yrs · Old Batch"),
    ("3-5 (Ser Nya)",                "Ser Nya",        "3–5 yrs · New Batch"),
    ("6-7 (Bumpa)",                  "Bumpa",          "6–7 yrs · Old Batch"),
    ("6-7 (Dungkar)",                "Dungkar",        "6–7 yrs · New Batch"),
    ("8-9 (Drami)",                  "Drami",          "8–9 yrs · Old Batch"),
    ("8-9 Group (Dhug)",             "Dhug",           "8–9 yrs · New Batch"),
    ("8-9 Group (Gawa)",             "Gawa",           "8–9 yrs"),
    ("10-12 (Gyeltshen)",            "Gyeltshen",      "10–12 yrs · Old Batch"),
    ("10-12 Group (Khorlo)",         "Khorlo",         "10–12 yrs · New Batch"),
    ("10-12 Group(Nyingje)",         "Nyingje",        "10–12 yrs"),
    ("13-15 Group (Bhuram Shingpa)", "Buram Shingpa",  "13–15 yrs · Batch"),
]

HEADER_VALS = {"child name", "name", "names", "student", "students", "child"}

def fetch_csv(sheet_name):
    url = (f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"
           f"/gviz/tq?tqx=out:csv&sheet={urllib.parse.quote(sheet_name)}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as exc:
        print(f"  WARNING: {exc}", file=sys.stderr)
        return ""

def is_date_like(s):
    s = s.strip()
    return bool(s and re.match(r'\d', s) and re.search(r'[/\.\-]', s))

def parse_sheet(csv_text):
    """Returns (dates, students) where students = list of (name, [P/A/''...])."""
    if not csv_text.strip():
        return [], []

    rows = list(csv.reader(io.StringIO(csv_text)))

    # Find header row — row where col 1 is a recognised name-column header
    header_row, header_idx = None, None
    for i, row in enumerate(rows):
        if len(row) > 1 and row[1].strip().lower() in HEADER_VALS:
            header_row, header_idx = row, i
            break

    if header_row is None:
        return [], []

    # Find date columns (header cell looks like a date)
    dates, date_cols = [], []
    for col_idx, cell in enumerate(header_row):
        if col_idx <= 1:
            continue
        if is_date_like(cell):
            dates.append(cell.strip())
            date_cols.append(col_idx)

    # Parse student rows (after header, col 1 must be a non-trivial name)
    students = []
    for row in rows[header_idx + 1:]:
        if len(row) < 2:
            continue
        name = row[1].strip()
        if not name or len(name) <= 2 or name.lower() in HEADER_VALS:
            continue
        if name.isdigit():
            continue

        attendance = []
        for col_idx in date_cols:
            raw = row[col_idx].strip().upper() if col_idx < len(row) else ""
            if raw.startswith("P"):
                val = "P"
            elif raw.startswith("A"):
                val = "A"
            else:
                val = ""
            attendance.append(val)

        students.append((name, attendance))

    return dates, students

def _e(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def main():
    print("Fetching Google Sheet data...")
    groups = []
    for sheet_name, label, sub in SHEETS:
        print(f"  {label}...", end=" ", flush=True)
        raw = fetch_csv(sheet_name)
        dates, students = parse_sheet(raw)
        print(f"{len(students)} students, {len(dates)} sessions")
        groups.append({"label": label, "sub": sub, "dates": dates, "students": students})

    today = datetime.now().strftime("%d %B %Y")
    total_students = sum(len(g["students"]) for g in groups)

    # ── Summary cards ────────────────────────────────────────────────────────
    summary_cards = []
    for g in groups:
        students = g["students"]
        if not students:
            continue
        all_p = sum(att.count("P") for _, att in students)
        all_rec = sum(len([a for a in att if a in ("P","A")]) for _, att in students)
        pct = f"{all_p/all_rec*100:.0f}%" if all_rec else "—"
        summary_cards.append(
            f'<div class="card">'
            f'<div class="card-title">{_e(g["label"])}</div>'
            f'<div class="card-sub">{_e(g["sub"])}</div>'
            f'<div class="card-stats">'
            f'<span class="badge blue">{len(students)} students</span>'
            f'<span class="badge green">{len(g["dates"])} sessions</span>'
            f'</div>'
            f'<div class="card-pct">{pct} attendance</div>'
            f'</div>'
        )

    # ── Per-group sections ───────────────────────────────────────────────────
    sections = []
    for g in groups:
        lbl     = _e(g["label"])
        sub     = _e(g["sub"])
        dates   = g["dates"]
        students = g["students"]

        if not students:
            sections.append(f'<section class="grp"><div class="grp-hd"><h2>{lbl}</h2>'
                            f'<span class="gsub">{sub}</span></div>'
                            f'<p class="no-data">No data available.</p></section>')
            continue

        all_p   = sum(att.count("P") for _, att in students)
        all_rec = sum(len([a for a in att if a in ("P","A")]) for _, att in students)
        grp_pct = f"{all_p/all_rec*100:.0f}%" if all_rec else "—"

        date_ths = "".join(f'<th class="date-h">{_e(d)}</th>' for d in dates)

        rows_html = []
        for name, att in students:
            present = att.count("P")
            recorded = len([a for a in att if a in ("P","A")])
            pct_val  = present / recorded * 100 if recorded else -1
            pct_str  = f"{pct_val:.0f}%" if pct_val >= 0 else "—"
            pct_cls  = ("pct-good" if pct_val >= 80 else
                        "pct-ok"   if pct_val >= 60 else
                        "pct-low"  if pct_val >= 0  else "")

            cells = "".join(
                f'<td class="att-{"p" if a=="P" else "a" if a=="A" else "blank"}">'
                f'{"P" if a=="P" else "A" if a=="A" else ""}</td>'
                for a in att
            )
            rows_html.append(
                f'<tr><td class="s-name">{_e(name)}</td>{cells}'
                f'<td class="att-count">{present}/{recorded if recorded else len(dates)}</td>'
                f'<td class="att-pct {pct_cls}">{pct_str}</td></tr>'
            )

        sections.append(f"""
<section class="grp" id="grp-{_e(g['label']).replace(' ','-')}">
  <div class="grp-hd">
    <h2>{lbl}</h2>
    <span class="gsub">{sub}</span>
    <div class="cnts">
      <span class="badge blue">{len(students)} students</span>
      &nbsp;·&nbsp;
      <span class="badge green">{len(dates)} sessions</span>
      &nbsp;·&nbsp;
      Overall: <strong>{grp_pct}</strong>
    </div>
  </div>
  <div class="table-wrap">
    <table class="att-table">
      <thead>
        <tr>
          <th class="s-name-h">Student Name</th>
          {date_ths}
          <th class="att-h">Attended</th>
          <th class="att-h">%</th>
        </tr>
      </thead>
      <tbody>{"".join(rows_html)}</tbody>
    </table>
  </div>
</section>""")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Attendance Report — No Name School</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f4f5f7;color:#1a1a2e;font-size:13px}}
header{{background:#1a1a2e;color:#fff;padding:24px 32px}}
header h1{{font-size:22px;font-weight:700;margin-bottom:4px}}
header p{{opacity:.7;font-size:13px}}
main{{padding:28px 32px;max-width:1400px;margin:0 auto}}
.summary{{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:14px;margin-bottom:32px}}
.card{{background:#fff;border-radius:12px;padding:18px;box-shadow:0 1px 4px rgba(0,0,0,.08)}}
.card-title{{font-size:15px;font-weight:700;margin-bottom:2px}}
.card-sub{{font-size:11px;color:#888;margin-bottom:10px}}
.card-stats{{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px}}
.card-pct{{font-size:20px;font-weight:700;color:#1a7a45}}
.grp{{background:#fff;border-radius:12px;padding:24px;margin-bottom:24px;box-shadow:0 1px 4px rgba(0,0,0,.08)}}
.grp-hd{{display:flex;align-items:center;flex-wrap:wrap;gap:10px;margin-bottom:16px;padding-bottom:12px;border-bottom:2px solid #e8eaf0}}
.grp-hd h2{{font-size:18px;font-weight:700}}
.gsub{{font-size:12px;color:#888;background:#f0f0f6;padding:3px 8px;border-radius:20px}}
.cnts{{margin-left:auto;font-size:12px;color:#555}}
.table-wrap{{overflow-x:auto}}
.att-table{{border-collapse:collapse;min-width:400px}}
.att-table th{{background:#f0f2f8;padding:6px 10px;font-size:11px;font-weight:600;color:#555;text-align:center;border:1px solid #e0e3ef;white-space:nowrap}}
th.s-name-h{{text-align:left;min-width:180px}}
th.date-h{{min-width:72px}}
th.att-h{{min-width:60px}}
.att-table td{{padding:5px 10px;border:1px solid #eee;text-align:center;font-size:12px}}
td.s-name{{text-align:left;font-weight:500;white-space:nowrap}}
td.att-p{{background:#e6f9f0;color:#1a7a45;font-weight:700}}
td.att-a{{background:#fde8e8;color:#c0392b;font-weight:700}}
td.att-blank{{background:#fafafa;color:#ddd}}
td.att-count{{color:#777;font-size:11px}}
td.att-pct{{font-weight:700}}
td.pct-good{{color:#1a7a45}}
td.pct-ok{{color:#d35400}}
td.pct-low{{color:#c0392b}}
.badge{{display:inline-block;padding:2px 8px;border-radius:20px;font-size:11px;font-weight:600;vertical-align:middle}}
.badge.green{{background:#e6f9f0;color:#1a7a45}}
.badge.blue{{background:#e8f0fe;color:#1a5cbf}}
.no-data{{color:#aaa;font-style:italic;padding:8px}}
footer{{text-align:center;padding:24px;color:#aaa;font-size:12px}}
</style>
</head>
<body>
<header>
  <h1>Attendance Report — No Name School</h1>
  <p>Generated {today} &nbsp;·&nbsp; {total_students} students across {len(groups)} groups &nbsp;·&nbsp; Auto-updated from Google Sheets</p>
</header>
<main>
<div class="summary">{"".join(summary_cards)}</div>
{"".join(sections)}
</main>
<footer>
  No Name School &nbsp;·&nbsp; {today}<br>
  <span style="font-size:11px">P = Present &nbsp;·&nbsp; A = Absent &nbsp;·&nbsp; Updated automatically every Sunday from Google Sheets</span>
</footer>
</body>
</html>"""

    OUT.write_text(html, encoding="utf-8")
    print(f"\nReport saved: {OUT}")

if __name__ == "__main__":
    main()
