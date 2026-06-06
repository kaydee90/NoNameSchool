#!/usr/bin/env python3
"""Build attendance report from Google Sheets — No Name School."""
import csv, io, re, json, urllib.parse, urllib.request, sys
from datetime import datetime, date
from pathlib import Path

SHEET_ID = "1zyma_6St8I1MArkh_0U2biHfc29uIwvs"
OUT = Path(__file__).parent / "index.html"

SHEETS = [
    ("3-5 (Meto Pema)",              "Meto Pema",    "meto-pema", "Lotus · 3–5 yrs"),
    ("3-5 (Ser Nya)",                "Ser Nya",       "ser-nya",   "Golden Fish · 3–5 yrs"),
    ("6-7 (Bumpa)",                  "Bumpa",         "bumpa",     "Treasure Vase · 6–7 yrs"),
    ("6-7 (Dungkar)",                "Dungkar",       "dungkar",   "Conch Shell · 6–7 yrs"),
    ("8-9 (Drami)",                  "Drami",         "drami",     "Endless Knot · 8–9 yrs"),
    ("8-9 Group (Dhug)",             "Dhug",          "dhug",      "Parasol · 8–9 yrs"),
    ("8-9 Group (Gawa)",             "Gawa",          "gawa",      "Joy · 8–9 yrs"),
    ("10-12 (Gyeltshen)",            "Gyeltshen",     "gyeltshen", "Victory Banner · 10–12 yrs"),
    ("10-12 Group (Khorlo)",         "Khorlo",        "khorlo",    "Dharma Wheel · 10–12 yrs"),
    ("10-12 Group(Nyingje)",         "Nyingje",       "nyingje",   "Compassion · 10–12 yrs"),
    ("13-15 Group (Bhuram Shingpa)", "Buram Shingpa", "bhuram",    "13–15 yrs · Batch"),
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

def parse_date_header(s):
    s = s.strip()
    for fmt in ('%d/%m/%Y', '%d/%m/%y', '%d.%m.%Y', '%d.%m.%y', '%d-%m-%Y', '%d-%m-%y'):
        try:
            return datetime.strptime(s, fmt).strftime('%d %b')
        except ValueError:
            continue
    return s

def is_date_like(s):
    s = s.strip()
    return bool(s and re.match(r'\d', s) and re.search(r'[/\.\-]', s))

def calc_age(dob_str):
    dob_str = dob_str.strip()
    if not dob_str or '@' in dob_str or len(dob_str) > 20:
        return "—"
    today = date.today()
    for fmt in ('%d/%m/%Y', '%d/%m/%y', '%d.%m.%Y', '%d.%m.%y', '%d-%m-%Y', '%d-%m-%y'):
        try:
            dob = datetime.strptime(dob_str, fmt).date()
            years = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            months = (today.month - dob.month) % 12
            if today.day < dob.day:
                months = (months - 1) % 12
            return f"{years}y {months}m"
        except ValueError:
            continue
    return "—"

def norm_gender(g):
    g = g.strip().upper()
    if g in ('M', 'MALE', 'BOY'):   return 'M'
    if g in ('F', 'FEMALE', 'GIRL'): return 'F'
    return ''

def parse_sheet(csv_text):
    if not csv_text.strip():
        return [], []
    rows = list(csv.reader(io.StringIO(csv_text)))
    header_row, header_idx = None, None
    for i, row in enumerate(rows):
        if len(row) > 1 and row[1].strip().lower() in HEADER_VALS:
            header_row, header_idx = row, i
            break
    if header_row is None:
        return [], []
    dates, date_cols = [], []
    for col_idx, cell in enumerate(header_row):
        if col_idx <= 1:
            continue
        if is_date_like(cell):
            dates.append(parse_date_header(cell))
            date_cols.append(col_idx)
    students = []
    for sl_num, row in enumerate(rows[header_idx + 1:], 1):
        if len(row) < 2:
            continue
        name = row[1].strip()
        if not name or len(name) <= 2 or name.lower() in HEADER_VALS or name.isdigit():
            continue
        gender  = norm_gender(row[2]) if len(row) > 2 else ''
        dob_str = row[3].strip()     if len(row) > 3 else ''
        age     = calc_age(dob_str)
        sl_raw  = row[0].strip()
        sl      = int(sl_raw) if sl_raw.isdigit() else sl_num
        attendance = []
        for col_idx in date_cols:
            raw = row[col_idx].strip().upper() if col_idx < len(row) else ""
            if raw.startswith("P"):   val = "P"
            elif raw.startswith("A"): val = "A"
            else:                     val = ""
            attendance.append(val)
        students.append({"sl": sl, "n": name, "g": gender, "a": age, "att": attendance})
    return dates, students

def main():
    print("Fetching Google Sheet data...")
    groups = []
    for sheet_name, label, grp_id, sub in SHEETS:
        print(f"  {label}...", end=" ", flush=True)
        raw    = fetch_csv(sheet_name)
        dates, students = parse_sheet(raw)
        print(f"{len(students)} students, {len(dates)} sessions")
        groups.append({"id": grp_id, "tab": label, "sub": sub,
                       "dates": dates, "students": students})

    today  = datetime.now().strftime("%d %B %Y")
    G_json = json.dumps(groups, ensure_ascii=False)

    # ── HTML split into 3 parts so JS curly braces need no escaping ──────────
    part1 = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>No Name School – Attendance</title>
<link rel="icon" type="image/png" href="logo.png">
<style>
:root{{--blue:#1a35b8;--blue2:#2d4fd4;--gold:#f5c518;--teal:#0d9488;--green:#16a34a;--red:#dc2626;--amber:#d97706;--bg:#eef2ff;--card:#fff;--border:#c7d2f0;--muted:#6b7280;--text:#1e2a5e}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--text);min-height:100vh}}
header{{background:linear-gradient(135deg,#0f1f7a 0%,#1a35b8 50%,#1d4ed8 100%);color:#fff;position:relative;overflow:hidden}}
header::before{{content:'';position:absolute;inset:0;background:url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.04'%3E%3Ccircle cx='30' cy='30' r='20'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E");pointer-events:none}}
.hdr-inner{{max-width:1160px;margin:0 auto;padding:32px 40px 28px;display:flex;align-items:center;gap:28px;position:relative}}
.hdr-logo{{width:100px;height:100px;border-radius:50%;border:3px solid var(--gold);box-shadow:0 0 0 6px rgba(245,197,24,.2),0 8px 32px rgba(0,0,0,.3);flex-shrink:0;background:#fff;object-fit:cover}}
.hdr-text{{flex:1}}
.hdr-text h1{{font-size:2rem;font-weight:800;letter-spacing:.5px;line-height:1.1}}
.hdr-text h1 span{{color:var(--gold)}}
.hdr-motto{{font-size:1rem;opacity:.85;margin-top:4px;font-style:italic;letter-spacing:.5px}}
.hdr-divider{{width:48px;height:3px;background:var(--gold);border-radius:2px;margin:10px 0}}
.hdr-meta{{display:flex;gap:20px;flex-wrap:wrap;margin-top:2px}}
.hdr-pill{{background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.2);border-radius:20px;padding:4px 14px;font-size:.78rem;font-weight:600;backdrop-filter:blur(4px)}}
.hdr-pill.gold{{background:rgba(245,197,24,.18);border-color:rgba(245,197,24,.4);color:var(--gold)}}
.hdr-strip{{height:5px;background:linear-gradient(90deg,var(--gold) 0%,#f5c518 40%,#0d9488 100%)}}
main{{max-width:1160px;margin:0 auto;padding:28px 20px 60px}}
.summary{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px;margin-bottom:28px}}
.card{{background:var(--card);border-radius:10px;padding:16px;box-shadow:0 2px 8px rgba(26,53,184,.1);border-top:4px solid var(--blue);text-align:center}}
.card.g{{border-color:var(--green)}}.card.r{{border-color:var(--red)}}.card.a{{border-color:var(--amber)}}.card.gold{{border-color:var(--gold)}}
.card .n{{font-size:1.8rem;font-weight:800;color:var(--blue);line-height:1}}
.card.g .n{{color:var(--green)}}.card.r .n{{color:var(--red)}}.card.a .n{{color:var(--amber)}}.card.gold .n{{color:#b45309}}
.card .l{{font-size:.75rem;color:var(--muted);margin-top:5px;text-transform:uppercase;letter-spacing:.5px}}
.tabs-wrap{{overflow-x:auto;-webkit-overflow-scrolling:touch;border-bottom:2px solid var(--blue);padding-bottom:0}}
.tabs{{display:flex;gap:6px;width:max-content;padding:0 2px}}
.tbtn{{padding:8px 16px;border:2px solid var(--border);background:var(--card);border-radius:8px 8px 0 0;cursor:pointer;font-size:.82rem;font-weight:600;color:var(--muted);white-space:nowrap;border-bottom:2px solid var(--border);position:relative;bottom:-2px;transition:all .15s;display:flex;flex-direction:column;align-items:center;gap:1px}}
.tsub{{font-size:.65rem;font-weight:400;opacity:.8;letter-spacing:.2px}}
.tbtn:hover{{background:#eef2ff;color:var(--blue)}}
.tbtn.active{{background:var(--card);border-color:var(--blue);border-bottom-color:var(--card);color:var(--blue);z-index:1}}
.tbtn .cnt{{background:var(--blue2);color:#fff;border-radius:20px;font-size:.7rem;font-weight:700;padding:1px 7px;margin-left:6px}}
.tbtn.active .cnt{{background:var(--blue)}}
.panels{{background:var(--card);border:2px solid var(--blue);border-top:none;border-radius:0 0 12px 12px;padding:24px;box-shadow:0 4px 16px rgba(26,53,184,.1)}}
.panel{{display:none}}.panel.active{{display:block}}
.gh{{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;margin-bottom:18px;padding-bottom:14px;border-bottom:2px solid var(--border)}}
.gt{{font-size:1.1rem;font-weight:700;color:var(--blue)}}.gt span{{font-weight:400;color:var(--muted);font-size:.85rem;margin-left:8px}}
.gstats{{display:flex;gap:16px;flex-wrap:wrap}}
.gs{{text-align:center;padding:6px 14px;border-radius:8px;background:var(--bg)}}
.gs .gn{{font-size:1.3rem;font-weight:800}}.gs .gl{{font-size:.68rem;color:var(--muted);text-transform:uppercase;letter-spacing:.4px}}
.gs.rate .gn{{color:var(--green)}}.gs.ab .gn{{color:var(--red)}}.gs.pf .gn{{color:var(--blue)}}
.tw{{overflow-x:auto}}
table{{width:100%;border-collapse:collapse;font-size:.85rem}}
thead th{{background:var(--blue);color:#fff;padding:10px 8px;text-align:left;font-size:.78rem;font-weight:600;text-transform:uppercase;letter-spacing:.4px;white-space:nowrap}}
thead th.dc{{text-align:center;min-width:62px}}
thead th.rc{{text-align:center;min-width:80px}}
tbody tr:nth-child(even){{background:#f5f7ff}}
tbody tr:hover{{background:#eef2ff}}
td{{padding:9px 8px;border-bottom:1px solid var(--border);vertical-align:middle}}
td.sl{{color:var(--muted);font-size:.75rem;width:30px}}
td.nm{{font-weight:600}}
td.gd,td.ag{{color:var(--muted);font-size:.8rem;white-space:nowrap}}
td.at{{text-align:center}}
.bp{{display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:50%;background:#dcfce7;color:var(--green);font-weight:700;font-size:.75rem}}
.ba{{display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:50%;background:#fee2e2;color:var(--red);font-weight:700;font-size:.75rem}}
.be{{display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:50%;background:#f0f0f0;color:#aaa;font-size:.7rem}}
.rb{{display:flex;align-items:center;gap:6px}}
.bar{{flex:1;height:7px;background:#e0e0e0;border-radius:4px;overflow:hidden;min-width:32px}}
.bf{{height:100%;border-radius:4px}}
.bf.hi{{background:var(--green)}}.bf.mi{{background:var(--amber)}}.bf.lo{{background:var(--red)}}
.rp{{font-size:.78rem;font-weight:700;white-space:nowrap;min-width:34px;text-align:right}}
.rp.hi{{color:var(--green)}}.rp.mi{{color:var(--amber)}}.rp.lo{{color:var(--red)}}
footer{{text-align:center;margin-top:36px;color:var(--muted);font-size:.78rem}}
.clickable{{cursor:pointer;transition:transform .12s,box-shadow .12s}}
.clickable:hover{{transform:translateY(-2px);box-shadow:0 4px 14px rgba(0,0,0,.13)}}
.overlay{{position:fixed;inset:0;background:rgba(0,0,0,.52);z-index:200;display:flex;align-items:flex-start;justify-content:center;padding:48px 16px 32px;overflow-y:auto}}
.overlay.hidden{{display:none}}
.modal{{background:#fff;border-radius:14px;width:100%;max-width:700px;box-shadow:0 12px 48px rgba(0,0,0,.22);animation:mIn .18s ease}}
@keyframes mIn{{from{{opacity:0;transform:translateY(-16px)}}to{{opacity:1;transform:translateY(0)}}}}
.mhd{{display:flex;align-items:center;justify-content:space-between;padding:18px 24px 16px;border-bottom:2px solid var(--border)}}
.mhd h2{{font-size:1rem;font-weight:700;color:var(--red);display:flex;align-items:center;gap:8px}}
.mhd .mbadge{{background:#fde8e8;color:var(--red);border-radius:20px;font-size:.72rem;font-weight:700;padding:2px 9px}}
.mclose{{background:none;border:none;font-size:1.5rem;cursor:pointer;color:var(--muted);line-height:1;padding:0 4px}}
.mclose:hover{{color:var(--text)}}
.mbd{{padding:20px 24px;max-height:65vh;overflow-y:auto}}
.msec{{margin-bottom:22px}}
.msec:last-child{{margin-bottom:0}}
.msec-hd{{font-size:.82rem;font-weight:700;color:var(--blue);padding-bottom:7px;margin-bottom:8px;border-bottom:1px solid var(--border);display:flex;align-items:baseline;gap:6px}}
.msec-hd span{{font-weight:400;color:var(--muted);font-size:.75rem}}
.nvt{{width:100%;border-collapse:collapse;font-size:.83rem}}
.nvt th{{background:var(--blue);color:#fff;padding:8px 10px;text-align:left;font-size:.74rem;font-weight:600;text-transform:uppercase;letter-spacing:.3px}}
.nvt td{{padding:8px 10px;border-bottom:1px solid var(--border);vertical-align:middle}}
.nvt tbody tr:last-child td{{border-bottom:none}}
.nvt tbody tr:hover{{background:#fff5f5}}
.mgrp{{display:inline-block;background:#eef4ff;color:var(--blue);border-radius:4px;font-size:.72rem;padding:2px 6px;font-weight:600;white-space:nowrap}}
.mage{{color:var(--muted);font-size:.78rem}}
.nv-att{{display:flex;gap:3px;flex-wrap:wrap}}
.nv-empty{{color:var(--muted);font-size:.85rem;padding:8px 0;text-align:center}}
@media(max-width:600px){{header{{padding:18px}}main{{padding:16px 10px 40px}}.panels{{padding:14px}}.overlay{{padding:24px 8px 16px}}.mbd{{padding:14px 14px}}}}
</style>
</head>
<body>
<div class="hdr-strip" style="height:4px;background:linear-gradient(90deg,#f5c518,#0d9488)"></div>
<header>
  <div class="hdr-inner">
    <img src="logo.png" alt="No Name School Logo" class="hdr-logo">
    <div class="hdr-text">
      <h1>No Name <span>School</span></h1>
      <div class="hdr-motto">✦ Be Yourself ✦</div>
      <div class="hdr-divider"></div>
      <div class="hdr-meta">
        <span class="hdr-pill">Term 2 · 2026</span>
        <span class="hdr-pill">11 Classes</span>
        <span class="hdr-pill" id="total-meta">— Students</span>
        <span class="hdr-pill gold">Updated {today}</span>
      </div>
    </div>
  </div>
</header>
<div class="hdr-strip"></div>
<main>
  <div class="summary">
    <div class="card"><div class="n" id="sc-students">—</div><div class="l">Students</div></div>
    <div class="card"><div class="n" id="sc-classes">11</div><div class="l">Classes</div></div>
    <div class="card g"><div class="n" id="sc-rate">—</div><div class="l">Attendance</div></div>
    <div class="card"><div class="n" id="sc-perfect">—</div><div class="l">Full Attend.</div></div>
    <div class="card r clickable" onclick="showNeverCame(null)" title="Click to see list"><div class="n" id="sc-zero">—</div><div class="l">Never Came ↗</div></div>
  </div>
  <div class="tabs-wrap"><div class="tabs" id="tabs"></div></div>
  <div class="panels" id="panels"></div>
  <footer>Updated {today} · No Name School · Auto-updated Sat, Sun &amp; Mon at 7 AM Perth time</footer>
</main>
<div class="overlay hidden" id="overlay" onclick="if(event.target===this)closeModal()">
  <div class="modal">
    <div class="mhd">
      <h2 id="modal-title">Never Came <span class="mbadge" id="modal-count"></span></h2>
      <button class="mclose" onclick="closeModal()" title="Close">&#x2715;</button>
    </div>
    <div class="mbd" id="modal-bd"></div>
  </div>
</div>
<script>
const G="""

    part2 = G_json

    part3 = """;

function rate(att){const v=att.filter(x=>x==="P"||x==="A");return v.length?Math.round(att.filter(x=>x==="P").length/v.length*100):0}
function rc(r){return r>=75?"hi":r>=50?"mi":"lo"}
function badge(v){if(v==="P")return`<span class="bp">P</span>`;if(v==="A")return`<span class="ba">A</span>`;return`<span class="be">—</span>`}

function buildGroup(grp,idx){
  const students=grp.students;
  const totalP=students.reduce((s,st)=>s+st.att.filter(x=>x==="P").length,0);
  const totalV=students.reduce((s,st)=>s+st.att.filter(x=>x==="P"||x==="A").length,0);
  const grpRate=totalV?Math.round(totalP/totalV*100):0;
  const perfect=students.filter(s=>rate(s.att)===100).length;
  const zero=students.filter(s=>rate(s.att)===0).length;
  const dateCols=grp.dates.map(d=>`<th class="dc">${d}</th>`).join("");
  const rows=students.map(s=>{
    const r=rate(s.att);
    const c=rc(r);
    const attCells=s.att.map(v=>`<td class="at">${badge(v)}</td>`).join("");
    return`<tr>
      <td class="sl">${s.sl}</td>
      <td class="nm">${s.n}</td>
      <td class="gd">${s.g==="F"?"♀":s.g==="M"?"♂":"—"}</td>
      <td class="ag">${s.a}</td>
      ${attCells}
      <td class="at" style="min-width:90px"><div class="rb"><div class="bar"><div class="bf ${c}" style="width:${r}%"></div></div><span class="rp ${c}">${r}%</span></div></td>
    </tr>`;
  }).join("");
  return`<div class="panel${idx===0?" active":""}" id="panel-${grp.id}">
    <div class="gh">
      <div class="gt">${grp.tab} <span>${grp.sub}</span></div>
      <div class="gstats">
        <div class="gs rate"><div class="gn">${grpRate}%</div><div class="gl">Attendance</div></div>
        <div class="gs pf"><div class="gn">${perfect}</div><div class="gl">Full Attend.</div></div>
        <div class="gs ab clickable" onclick="showNeverCame('${grp.id}')" title="Click to see list"><div class="gn">${zero}</div><div class="gl">Never Came ↗</div></div>
      </div>
    </div>
    <div class="tw"><table>
      <thead><tr><th>#</th><th>Name</th><th>G</th><th>Age</th>${dateCols}<th class="rc">Rate</th></tr></thead>
      <tbody>${rows}</tbody>
    </table></div>
  </div>`;
}

const tabsEl=document.getElementById("tabs");
tabsEl.innerHTML=G.map((g,i)=>{
  const ageMatch=g.sub.match(/\\d+[–\\-]\\d+\\s*yrs?/);
  const ageLbl=ageMatch?ageMatch[0]:"";
  return`<button class="tbtn${i===0?" active":""}" onclick="switchTab('${g.id}',this)"><span>${g.tab}<span class="cnt">${g.students.length}</span></span>${ageLbl?`<span class="tsub">${ageLbl}</span>`:""}</button>`;
}).join("");

document.getElementById("panels").innerHTML=G.map((g,i)=>buildGroup(g,i)).join("");

const allS=G.flatMap(g=>g.students);
const totP=allS.reduce((s,st)=>s+st.att.filter(x=>x==="P").length,0);
const totV=allS.reduce((s,st)=>s+st.att.filter(x=>x==="P"||x==="A").length,0);
const ovRate=totV?Math.round(totP/totV*100):0;
const perfCount=allS.filter(s=>rate(s.att)===100).length;
const zeroCount=allS.filter(s=>rate(s.att)===0).length;
document.getElementById("sc-students").textContent=allS.length;
document.getElementById("sc-rate").textContent=ovRate+"%";
document.getElementById("sc-perfect").textContent=perfCount;
document.getElementById("sc-zero").textContent=zeroCount;
document.getElementById("total-meta").textContent=allS.length+" Students";

function switchTab(id,btn){
  document.querySelectorAll(".panel").forEach(p=>p.classList.remove("active"));
  document.querySelectorAll(".tbtn").forEach(b=>b.classList.remove("active"));
  document.getElementById("panel-"+id).classList.add("active");
  btn.classList.add("active");
  btn.scrollIntoView({behavior:"smooth",block:"nearest",inline:"center"});
}

function showNeverCame(groupId){
  const scope=groupId?G.filter(g=>g.id===groupId):G;
  const isAll=!groupId;
  const title=isAll?"Never Came — All Classes":(G.find(g=>g.id===groupId).tab+" — Never Came");
  document.getElementById("modal-title").childNodes[0].textContent=title+" ";
  const hasRecord=s=>s.att.some(x=>x==="P"||x==="A");
  const neverCame=s=>hasRecord(s)&&rate(s.att)===0;
  let html="";let total=0;
  for(const grp of scope){
    const zeros=grp.students.filter(neverCame);
    if(!zeros.length)continue;
    total+=zeros.length;
    if(isAll){html+=`<div class="msec"><div class="msec-hd">${grp.tab} <span>${grp.sub}</span></div>`;}
    html+=`<table class="nvt"><thead><tr><th>#</th><th>Name</th><th>G</th><th>Age</th>`;
    if(isAll)html+=`<th>Group</th>`;
    html+=`<th>Attendance</th></tr></thead><tbody>`;
    zeros.forEach((s,i)=>{
      const gender=s.g==="F"?"♀":s.g==="M"?"♂":"—";
      const attBadges=s.att.map(v=>badge(v)).join(" ");
      html+=`<tr><td style="color:var(--muted);font-size:.75rem">${i+1}</td><td style="font-weight:600">${s.n}</td><td class="mage">${gender}</td><td class="mage">${s.a}</td>`;
      if(isAll)html+=`<td><span class="mgrp">${grp.tab}</span></td>`;
      html+=`<td><div class="nv-att">${attBadges}</div></td></tr>`;
    });
    html+=`</tbody></table>`;
    if(isAll)html+=`</div>`;
  }
  if(!total){html=`<p class="nv-empty">All students have attended at least once.</p>`;}
  document.getElementById("modal-count").textContent=total+" student"+(total!==1?"s":"");
  document.getElementById("modal-bd").innerHTML=html;
  document.getElementById("overlay").classList.remove("hidden");
  document.body.style.overflow="hidden";
}

function closeModal(){
  document.getElementById("overlay").classList.add("hidden");
  document.body.style.overflow="";
}

document.addEventListener("keydown",e=>{if(e.key==="Escape")closeModal()});
</script>
</body>
</html>"""

    html = part1 + part2 + part3
    OUT.write_text(html, encoding="utf-8")
    print(f"\nReport saved: {OUT}")

if __name__ == "__main__":
    main()
