import json
t = open("app/hc-data.js", encoding="utf-8").read(); d = json.loads(t[len("window.GT_HC="):].rstrip().rstrip(";"))
C = {c: i for i, c in enumerate(d["cols"])}
def find(n, s):
    for r in d["rows"]:
        if r[C["season"]] == s and r[C["id"]] == n: return {c: r[i] for c, i in C.items()}
for n, s, exp in [("Bill Belichick", 2007, "16-0, playoffs 2-1"), ("Andy Reid", 2023, "11-6, SB win 4-0"), ("Sean McVay", 2021, "12-5, SB 4-0"),
                  ("Dan Campbell", 2023, "12-5, aggressive"), ("Brandon Staley", 2021, "9-8, very aggressive"), ("Jim Caldwell", 2009, "14-2")]:
    r = find(n, s)
    if not r: print("MISSING", n, s); continue
    print(f"{n} {s} [{r['team']}] {r['w']}-{r['l']}-{r['t']} PF {r['pf']} PA {r['pa']} close {r['cw']}-{r['cl']}/{r['cg']} comebacks {r['cbw']} | off epa {r['oepa']/r['op']:+.3f} def {r['depa']/r['dp']:+.3f} | pass% {r['npass']/max(1,r['np']):.2f} 4th go {r['f4go']}/{r['f4n']} conv {r['f4cv']} | 2pt {r['two']} xp {r['xpa']} | chal {r['chalw']}/{r['chal']} pen {r['pen']} | playoffs {r['pw']}-{r['pl']}  (official {exp})")
import collections
print("coaches per season sample:", collections.Counter(r[C["season"]] for r in d["rows"]).most_common(3))
