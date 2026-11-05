import csv, gzip, sys
rd = csv.reader(gzip.open(sys.argv[1], "rt", encoding="utf-8"))
h = next(rd); ix = {n: i for i, n in enumerate(h)}
tot = 0; fb = 0; odd = []
for r in rd:
    if r[ix["season_type"]] != "REG" or r[ix["passer_id"]] != sys.argv[2]: continue
    if r[ix["play_type"]] != "pass" or r[ix["complete_pass"]] not in ("1", "1.0"): continue
    if r[ix["two_point_attempt"]] in ("1", "1.0"): continue
    py = r[ix["passing_yards"]]
    if py in ("", "NA"):
        fb += float(r[ix["yards_gained"]] or 0); odd.append(r[ix["desc"]][:140])
    else:
        tot += float(py)
print("passing_yards sum", tot, "fallback", fb)
for o in odd[:5]: print(" ", o)
