import json
t = open("app/ret-data.js", encoding="utf-8").read(); d = json.loads(t[len("window.GT_RET="):].rstrip().rstrip(";"))
C = {c: i for i, c in enumerate(d["cols"])}; P = d["players"]
def find(n, s):
    for r in d["rows"]:
        if r[C["season"]] == s and P[r[C["id"]]]["n"] == n: return {c: r[i] for c, i in C.items()}
for n, s, exp in [("Devin Hester", 2007, "KR 43-1,094-2, PR 42-651-4"), ("Devin Hester", 2006, "PR 47-600-3, KR 20-528-2"), ("Josh Cribbs", 2009, "KR 3 TD, PR 1 TD"),
                  ("Cordarrelle Patterson", 2013, "KR 43-1,393-2"), ("Dante Hall", 2003, "KR 2 TD, PR 2 TD"), ("Darren Sproles", 2011, ""), ("KaVontae Turpin", 2024, "")]:
    r = find(n, s)
    if not r: print("MISSING", n, s); continue
    print(f"{n} {s} [{r['team']} {r['slot']} pos {r['slots']}] g={r['g']} KR {r['kr']}-{r['kryds']}-{r['krtd']} long {r['krlong']} 40+ {r['kr40']} | PR {r['pr']}-{r['pryds']}-{r['prtd']} long {r['prlong']} FC {r['pfc']} | fum {r['krfum']+r['prfum']} lost {r['krfuml']+r['prfuml']}  (official {exp})")
