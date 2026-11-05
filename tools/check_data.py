import json, sys
txt = open(sys.argv[1], encoding="utf-8").read()
d = json.loads(txt[len("window.GT_DATA="):].rstrip().rstrip(";"))
C = {c: i for i, c in enumerate(d["cols"])}
P = d["players"]
def find(name, season):
    for r in d["rows"]:
        if r[C["season"]] == season and P[r[C["id"]]]["n"] == name:
            return {c: r[i] for c, i in C.items()}
checks = [("Peyton Manning", 2004, "4557 yds 49 TD 10 INT"), ("Tom Brady", 2007, "4806 yds 50 TD 8 INT 16-0"),
          ("Patrick Mahomes", 2018, "5097 yds 50 TD 12 INT 12-4"), ("Dak Prescott", 2016, "3667 yds 23 TD 4 INT 13-3"),
          ("Michael Vick", 2006, "1039 rush yds"), ("Lamar Jackson", 2019, "3127 yds 36 TD 6 INT 1206 rush 13-2"),
          ("Drew Brees", 2011, "5476 yds 46 TD 14 INT"), ("Joe Burrow", 2026, "partial")]
for n, s, exp in checks:
    r = find(n, s)
    if not r: print("MISSING", n, s); continue
    print(f"{n} {s} [{r['team']}] g={r['g']} gs={r['gs']} {r['w']}-{r['l']}-{r['t']} att={r['att']} cmp={r['cmp']} yds={r['yds']:.0f} td={r['td']} int={r['int']} sk={r['sk']} db={r['db']} scr={r['scr']} drun={r['drun']} rush={r['scry']+r['druny']:.0f} rtd={r['rtd']} epa/db={r['epa']/r['epan']:.3f} cpoe={(r['cpoe']/r['cpoen'] if r['cpoen'] else float('nan')):.1f}  | expected {exp}")
print(d["seasons"]["2026"])
for s in (2000, 2003, 2005, 2006, 2009, 2016, 2026):
    rows = [r for r in d["rows"] if r[C["season"]] == s and r[C["db"]] >= 150]
    n = len(rows)
    def share(col): return sum(1 for r in rows if r[C[col]] > 0) / max(n, 1)
    print(s, "qualified", n, "cpoen>0 %.2f ayn>0 %.2f yacy>0 %.2f sg>0 %.2f hit>0 %.2f fum>0 %.2f" % (share("cpoen"), share("ayn"), share("yacy"), share("sg"), share("hit"), share("fum")))
