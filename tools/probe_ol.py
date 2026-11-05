import csv, gzip, collections
csv.field_size_limit(10**8)
for y in (2001, 2006, 2012, 2024):
    c = collections.Counter(); clubs = set(); weeks = collections.Counter()
    for d in csv.DictReader(open(f"raw/depth_charts/depth_charts_{y}.csv", encoding="utf-8")):
        if d["formation"] == "Offense" and d["position"] in ("T", "G", "C", "OT", "OG", "OL", "LT", "RT", "LG", "RG"):
            c[(d["depth_position"], d["depth_team"])] += 1
        clubs.add(d["club_code"]); weeks[d["game_type"]] += 1
    print(y, sorted(c.items())[:14], "clubs:", sorted(clubs)[:40], dict(weeks))
c = collections.Counter(); dts = set()
for d in csv.DictReader(gzip.open("raw/depth_charts/depth_charts_2026.csv.gz", "rt", encoding="utf-8")):
    if d["pos_abb"] in ("LT", "LG", "C", "RG", "RT"): c[(d["pos_abb"], d["pos_rank"])] += 1
    dts.add(d["dt"][:10])
print("2026 new fmt", sorted(c.items()), "dates", len(dts), min(dts), max(dts))
rd = csv.reader(gzip.open("raw/pbp/play_by_play_2010.csv.gz", "rt", encoding="utf-8")); h = next(rd); ix = {n: i for i, n in enumerate(h)}
pt = collections.Counter(); gap = collections.Counter()
for r in rd:
    if r[ix["penalty_type"]] not in ("", "NA"): pt[r[ix["penalty_type"]]] += 1
    if r[ix["play_type"]] == "run": gap[(r[ix["run_location"]], r[ix["run_gap"]])] += 1
print("penalties", pt.most_common(25)); print("gaps", gap.most_common(12))
