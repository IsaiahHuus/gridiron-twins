import json
t = open("app/ol-data.js", encoding="utf-8").read(); d = json.loads(t[len("window.GT_OL="):].rstrip().rstrip(";"))
C = {c: i for i, c in enumerate(d["cols"])}; P = d["players"]
by = {}
for r in d["rows"]:
    by.setdefault(P[r[C["id"]]]["n"], []).append({c: r[i] for c, i in C.items()})
for n in ["Joe Thomas", "Jason Kelce", "Tyron Smith", "Zack Martin", "Walter Jones", "Orlando Pace", "Trent Williams", "Quenton Nelson", "Penei Sewell"]:
    rows = by.get(n)
    if not rows: print("MISSING", n); continue
    gs = sum(r["gs"] for r in rows); pen = sum(r["pen"] for r in rows)
    slots = {}
    for r in rows: slots[r["slot"]] = slots.get(r["slot"], 0) + r["gs"]
    print(f"{n}: {rows[0]['season']}-{rows[-1]['season']} {len(rows)} seasons, {gs} starts, spots {slots}, pens {pen}, holds {sum(r['hold'] for r in rows)}, fs {sum(r['fs'] for r in rows)}, gap runs {sum(r['gcar'] for r in rows)} ypc {sum(r['gyds'] for r in rows)/max(1,sum(r['gcar'] for r in rows)):.2f}")
