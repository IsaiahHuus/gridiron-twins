import csv, gzip, sys
csv.field_size_limit(10**8)
rd = csv.reader(gzip.open("raw/pbp/play_by_play_2005.csv.gz", "rt", encoding="utf-8")); h = next(rd); ix = {n: i for i, n in enumerate(h)}
n = 0
for r in rd:
    if r[ix["play_type"]] == "pass" and r[ix["incomplete_pass"]] in ("1", "1.0") and r[ix["season_type"]] == "REG":
        print(repr(r[ix["desc"]][:160]), "| rcv:", repr(r[ix["receiver_player_id"]]), repr(r[ix["receiver_player_name"]]), repr(r[ix["receiver"]]) if "receiver" in ix else "")
        n += 1
        if n >= 6: break
