import json, collections
t = open("app/db-data.js", encoding="utf-8").read(); d = json.loads(t[len("window.GT_DB="):].rstrip().rstrip(";"))
C = {c: i for i, c in enumerate(d["cols"])}; P = d["players"]
def find(n, s):
    for r in d["rows"]:
        if r[C["season"]] == s and P[r[C["id"]]]["n"] == n: return {c: r[i] for c, i in C.items()}
for n, s, exp in [("Ed Reed", 2004, "9 INT"), ("Champ Bailey", 2006, "10 INT"), ("Darrelle Revis", 2009, "6 INT, 31 PD"), ("Richard Sherman", 2013, "8 INT"),
                  ("Trevon Diggs", 2021, "11 INT"), ("Xavien Howard", 2020, "10 INT"), ("Troy Polamalu", 2010, "7 INT"), ("Charles Woodson", 2009, "9 INT"),
                  ("Charles Woodson", 2013, "S"), ("Sauce Gardner", 2022, "2 INT, 20 PD"), ("Jalen Ramsey", 2017, "4 INT")]:
    r = find(n, s)
    if not r: print("MISSING", n, s); continue
    print(f"{n} {s} [{r['team']} {r['slot']}/{r['slots']}] g={r['g']} gs={r['gs']} int={r['int']} pd={r['pd']} tk={r['tk']} solo={r['solo']} tfl={r['tfl']} sk={r['sk']} ff={r['ff']} pen={r['pen']} rtk={r['rtk']} (official {exp})")
print(collections.Counter(r[C["slot"]] for r in d["rows"]))
