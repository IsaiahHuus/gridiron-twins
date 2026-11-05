import json
t = open("app/kp-data.js", encoding="utf-8").read(); d = json.loads(t[len("window.GT_KP="):].rstrip().rstrip(";"))
C = {c: i for i, c in enumerate(d["cols"])}; P = d["players"]
def find(n, s):
    for r in d["rows"]:
        if r[C["season"]] == s and P[r[C["id"]]]["n"] == n: return {c: r[i] for c, i in C.items()}
for n, s, exp in [("Justin Tucker", 2016, "38/39 FG, 27/27 XP"), ("Adam Vinatieri", 2014, "30/31 FG"), ("Matt Prater", 2013, "25/26, long 64"),
                  ("Sebastian Janikowski", 2011, "31/35, long 63"), ("Shane Lechler", 2009, "96 punts? 51.1 avg"), ("Johnny Hekker", 2016, "47.8 avg, 51 in20"),
                  ("Michael Dickson", 2018, "48.2 avg"), ("Pat McAfee", 2014, "")]:
    r = find(n, s)
    if not r: print("MISSING", n, s); continue
    if r["slot"] == "K":
        print(f"{n} {s} [{r['team']} K] g={r['g']} FG {r['fgm']}/{r['fga']} 50+ {r['fgm5']}/{r['fga5']} long {r['fglong']} XP {r['xpm']}/{r['xpa']} KO {r['ko']} TB {r['kotb']} FGOE {(r['fgxm']-r['fgx'])/max(1,r['fgxn'])*100:+.1f}% tk {r['stk']}  (official {exp})")
    else:
        net = (r['pgross'] - r['pret'] - 20 * r['ptb']) / r['punts']
        print(f"{n} {s} [{r['team']} P] g={r['g']} punts {r['punts']} avg {r['pgross']/r['pn']:.1f} net {net:.1f} in20 {r['pi20']} tb {r['ptb']} fc {r['pfc']} long {r['plong']} fake {r['pay']}/{r['patd']} rush {r['ruy']}  (official {exp})")
