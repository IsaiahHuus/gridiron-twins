import csv, gzip, collections
csv.field_size_limit(10**8)
rd = csv.reader(gzip.open("raw/pbp/play_by_play_2001.csv.gz", "rt", encoding="utf-8")); h = next(rd)
want = [c for c in h if any(k in c for k in ("tackle", "sack", "qb_hit", "pass_defense", "forced_fumble", "fumble_recovery_1", "interception_player", "safety_player"))]
print("cols:", [c for c in want if c.endswith("_id") or c.endswith("_team")])
for y in (2000, 2003, 2006, 2012, 2024):
    rd = csv.reader(gzip.open(f"raw/pbp/play_by_play_{y}.csv.gz", "rt", encoding="utf-8")); h = next(rd); ix = {n: i for i, n in enumerate(h)}
    c = collections.Counter()
    for r in rd:
        if r[ix["season_type"]] != "REG": continue
        for k in ("sack_player_id", "half_sack_1_player_id", "qb_hit_1_player_id", "tackle_for_loss_1_player_id", "pass_defense_1_player_id", "forced_fumble_player_1_player_id", "solo_tackle_1_player_id", "assist_tackle_1_player_id", "tackle_with_assist_1_player_id"):
            if r[ix[k]] not in ("", "NA"): c[k] += 1
        if r[ix["sack"]] in ("1", "1.0"):
            c["sack_plays"] += 1
            if r[ix["qb_hit_1_player_id"]] not in ("", "NA"): c["sack_with_hit_id"] += 1
    print(y, dict(c))
pos = {}
for d in csv.DictReader(open("raw/players.csv", encoding="utf-8")):
    if d["display_name"] in ("T.J. Watt", "J.J. Watt", "Aaron Donald", "Myles Garrett", "Von Miller", "DeMarcus Ware", "Julius Peppers", "Michael Strahan", "Khalil Mack", "Nick Bosa", "Vince Wilfork", "Chris Jones", "Micah Parsons", "Dwight Freeney", "Terrell Suggs"):
        pos[d["display_name"]] = d["position"] + "/" + d["position_group"]
print(pos)
pc = collections.Counter(d["position"] for d in csv.DictReader(open("raw/players.csv", encoding="utf-8")))
print({k: v for k, v in pc.items() if k in ("DE", "DT", "NT", "DL", "OLB", "ILB", "LB", "MLB", "EDGE", "CB", "S", "FS", "SS", "DB")})
