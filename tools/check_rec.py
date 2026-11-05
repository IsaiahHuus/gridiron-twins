import json, sys
def load(p, var):
    t = open(p, encoding="utf-8").read(); return json.loads(t[len(f"window.{var}="):].rstrip().rstrip(";"))
for path, var, checks in [("app/wr-data.js", "GT_WR", [("Calvin Johnson", 2012, "122-1964-5"), ("Cooper Kupp", 2021, "145-1947-16"), ("Randy Moss", 2007, "98-1493-23"), ("Marvin Harrison", 2002, "143-1722-11"), ("Justin Jefferson", 2022, "128-1809-8")]),
                          ("app/te-data.js", "GT_TE", [("Rob Gronkowski", 2011, "90-1327-17"), ("Travis Kelce", 2020, "105-1416-11"), ("Tony Gonzalez", 2004, "102-1258-7"), ("George Kittle", 2018, "88-1377-5")])]:
    d = load(path, var); C = {c: i for i, c in enumerate(d["cols"])}; P = d["players"]
    for n, s, exp in checks:
        r = next(({c: x[i] for c, i in C.items()} for x in d["rows"] if x[C["season"]] == s and P[x[C["id"]]]["n"] == n), None)
        if not r: print("MISSING", n, s); continue
        print(f"{n} {s} [{r['team']}] g={r['g']} tgt={r['tgt']} rec={r['rec']} yds={r['recy']:.0f} td={r['rectd']} aDOT={(r['ay']/r['ayn'] if r['ayn'] else 0):.1f} tshare={r['tgt']/r['ttgt']:.3f} mid={(r['mid']/r['locn'] if r['locn'] else 0):.2f} (official {exp})")
    for s in (2000, 2003, 2010, 2026):
        rows = [x for x in d["rows"] if x[C["season"]] == s]
        print(var, s, "rows", len(rows), "locn>0", sum(1 for x in rows if x[C["locn"]] > 0), "ayn>0", sum(1 for x in rows if x[C["ayn"]] > 0))
