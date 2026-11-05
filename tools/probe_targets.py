import csv, gzip, sys, os
csv.field_size_limit(10**8)
for y in range(2000, 2027):
    p = f"raw/pbp/play_by_play_{y}.csv.gz"
    rd = csv.reader(gzip.open(p, "rt", encoding="utf-8")); h = next(rd); ix = {n: i for i, n in enumerate(h)}
    inc = inc_r = comp = 0
    for r in rd:
        if r[ix["season_type"]] != "REG" or r[ix["play_type"]] != "pass": continue
        if r[ix["incomplete_pass"]] in ("1", "1.0"):
            inc += 1
            if r[ix["receiver_player_id"]] not in ("", "NA"): inc_r += 1
    print(y, f"incompletions {inc}, with receiver {inc_r} ({100*inc_r/max(inc,1):.0f}%)", flush=True)
