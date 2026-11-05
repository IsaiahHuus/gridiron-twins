import csv, gzip, collections
csv.field_size_limit(10**8)
rd = csv.reader(gzip.open("raw/pbp/play_by_play_2010.csv.gz", "rt", encoding="utf-8")); h = next(rd); ix = {n: i for i, n in enumerate(h)}
print([c for c in h if "return" in c or "fair_catch" in c or "muff" in c])
n = collections.Counter(); ex = []
for r in rd:
    pt = r[ix["play_type"]]
    if pt not in ("kickoff", "punt") or r[ix["season_type"]] != "REG": continue
    kr = r[ix["kickoff_returner_player_id"]]; pr = r[ix["punt_returner_player_id"]]
    n[(pt, "kr" if kr not in ("", "NA") else "-", "pr" if pr not in ("", "NA") else "-", "fc" if r[ix["punt_fair_catch"]] in ("1", "1.0") else "", "tb" if r[ix["touchback"]] in ("1", "1.0") else "")] += 1
    if pt == "kickoff" and kr not in ("", "NA") and len(ex) < 2: ex.append((r[ix["posteam"]], r[ix["defteam"]], r[ix["return_team"]] if "return_team" in ix else "?", r[ix["desc"]][:90]))
for k, v in n.most_common(12): print(k, v)
print(ex)
