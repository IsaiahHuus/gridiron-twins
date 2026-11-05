import json
t = open("app/dl-data.js", encoding="utf-8").read(); d = json.loads(t[len("window.GT_DL="):].rstrip().rstrip(";"))
C = {c: i for i, c in enumerate(d["cols"])}; P = d["players"]
def find(n, s):
    for r in d["rows"]:
        if r[C["season"]] == s and P[r[C["id"]]]["n"] == n: return {c: r[i] for c, i in C.items()}
for n, s, exp in [("Michael Strahan", 2001, "22.5 sk"), ("J.J. Watt", 2012, "20.5 sk, 81 tk, 16 PD"), ("Jared Allen", 2011, "22 sk"),
                  ("Aaron Donald", 2018, "20.5 sk"), ("Myles Garrett", 2023, "14 sk"), ("Vince Wilfork", 2012, "NT"),
                  ("Julius Peppers", 2008, "14.5 sk"), ("Dwight Freeney", 2004, "16 sk"), ("Nick Bosa", 2023, "10.5 sk")]:
    r = find(n, s)
    if not r: print("MISSING", n, s); continue
    print(f"{n} {s} [{r['team']} {r['slot']} {r['slots']}] g={r['g']} gs={r['gs']} snaps={r['snaps']} sk={r['sk']} hit={r['hit']} tk={r['tk']} solo={r['solo']} tfl={r['tfl']} stuff={r['stuff']} ff={r['ff']} pd={r['pd']} pen={r['pen']}  (official {exp})")
import collections
print(collections.Counter(r[C["slot"]] for r in d["rows"]))
