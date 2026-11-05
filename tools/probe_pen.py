import csv, gzip
csv.field_size_limit(10**8)
for y in (2001, 2002, 2003, 2005, 2007, 2008, 2009, 2015, 2024):
    rd = csv.reader(gzip.open(f"raw/pbp/play_by_play_{y}.csv.gz", "rt", encoding="utf-8")); h = next(rd); ix = {n: i for i, n in enumerate(h)}
    tot = withid = withname = 0; ex = []
    for r in rd:
        if r[ix["season_type"]] != "REG": continue
        if r[ix["penalty_type"]] in ("Offensive Holding", "False Start"):
            tot += 1
            if r[ix["penalty_player_id"]] not in ("", "NA"): withid += 1
            elif r[ix["penalty_player_name"]] not in ("", "NA"): withname += 1
            elif len(ex) < 2: ex.append(r[ix["desc"]][:110])
    print(y, f"holding+false starts {tot}: with id {withid}, name only {withname}", ex)
