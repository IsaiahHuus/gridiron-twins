import json, sys
txt = open(sys.argv[1], encoding="utf-8").read()
d = json.loads(txt[len("window.GT_RB="):].rstrip().rstrip(";"))
C = {c: i for i, c in enumerate(d["cols"])}; P = d["players"]
def find(n, s):
    for r in d["rows"]:
        if r[C["season"]] == s and P[r[C["id"]]]["n"] == n: return {c: r[i] for c, i in C.items()}
for n, s, exp in [("LaDainian Tomlinson", 2006, "348-1815-28 rush, 56-508-3 rec"), ("Adrian Peterson", 2012, "348-2097-12, 40-217-1"),
                  ("Christian McCaffrey", 2019, "287-1387-15, 116-1005-4"), ("Derrick Henry", 2020, "378-2027-17"),
                  ("Marshall Faulk", 2000, "253-1359-18, 81-830-8"), ("Saquon Barkley", 2024, "345-2005-13")]:
    r = find(n, s)
    if not r: print("MISSING", n, s); continue
    print(f"{n} {s} [{r['team']}] g={r['g']} car={r['car']} ryds={r['ryds']:.0f} rtd={r['rtd']} | tgt={r['tgt']} rec={r['rec']} recy={r['recy']:.0f} rectd={r['rectd']} | 10+={r['r10']} stuff={r['stuff']} share={r['car']/r['tcar']:.2f} fuml={r['fuml']}  (official {exp})")
for s in (2000, 2010, 2020, 2026):
    rows = [r for r in d["rows"] if r[C["season"]] == s]
    q = [r for r in rows if r[C["car"]] + r[C["rec"]] >= 100]
    print(s, "rows", len(rows), "100+ touches", len(q))
