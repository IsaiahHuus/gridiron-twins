import json, collections
t = open("app/lb-data.js", encoding="utf-8").read(); d = json.loads(t[len("window.GT_LB="):].rstrip().rstrip(";"))
C = {c: i for i, c in enumerate(d["cols"])}; P = d["players"]
def find(n, s):
    for r in d["rows"]:
        if r[C["season"]] == s and P[r[C["id"]]]["n"] == n: return {c: r[i] for c, i in C.items()}
for n, s, exp in [("Ray Lewis", 2003, "161 tk (team), 6 INT, 1.5 sk"), ("Luke Kuechly", 2013, "156 tk, 4 INT"), ("T.J. Watt", 2021, "22.5 sk"),
                  ("Von Miller", 2012, "18.5 sk"), ("DeMarcus Ware", 2008, "20 sk"), ("Bobby Wagner", 2016, "167 tk"), ("Khalil Mack", 2016, "11 sk"),
                  ("Lavonte David", 2013, "145 tk, 7 sk, 5 INT"), ("Micah Parsons", 2023, "14 sk"), ("Fred Warner", 2024, "")]:
    r = find(n, s)
    if not r: print("MISSING", n, s); continue
    rate = r['sk'] / max(1, r['sk'] + r['tk'])
    print(f"{n} {s} [{r['team']} {r['slot']}/{r['slots']}] g={r['g']} gs={r['gs']} tk={r['tk']} solo={r['solo']} sk={r['sk']} hit={r['hit']} tfl={r['tfl']} int={r['int']} pd={r['pd']} ff={r['ff']} sk-share={rate:.3f} (official {exp})")
rates = [r[C["sk"]] / max(1, r[C["sk"]] + r[C["tk"]]) for r in d["rows"] if r[C["g"]] >= 10]
rates.sort(); print("sack-share quantiles", [round(rates[int(len(rates) * q)], 3) for q in (0.5, 0.75, 0.85, 0.9, 0.95)])
print(collections.Counter(r[C["slot"]] for r in d["rows"]))
