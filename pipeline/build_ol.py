"""Build the offensive line season table for Gridiron Twins.

Usage (run with -I so nothing in the raw folder is imported):
    python -I pipeline/build_ol.py <raw_dir> <out_js>

Inputs under <raw_dir>: pbp/ (play-by-play), players.csv, depth_charts/
(weekly csv 2001-2024, daily csv.gz 2025+) and snap_counts/ (csv.gz, 2013+).

Who started where:
  2001-2012  weekly depth chart starters (depth_team 1) at LT/LG/C/RG/RT
  2013+      snap counts: a start = 50%+ of the offensive snaps; the spot
             comes from that week's depth chart (or his most common spot)
Per start we credit: designed runs through his gap, the team's dropbacks,
sacks and QB hits, and the game result. Penalties are his own, all season.
Individual sacks/pressures allowed are not in the free data.
"""
import csv
import gzip
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict

csv.field_size_limit(10**8)
FIRST_SEASON, LAST_SEASON = 2001, 2026
MIN_STARTS = 4  # per full season
OL_POS = {"T", "G", "C", "OT", "OG", "OL", "LT", "RT", "LG", "RG"}
SLOT_FIX = {"LOT": "LT", "ROT": "RT", "LOG": "LG", "ROG": "RG", "OLT": "LT", "ORT": "RT", "OLG": "LG", "ORG": "RG"}
SLOTS = {"LT", "LG", "C", "RG", "RT"}
TEAM_FIX = {"OAK": "LV", "SD": "LAC", "STL": "LA", "LAR": "LA", "JAC": "JAX", "ARZ": "ARI", "BLT": "BAL", "CLV": "CLE",
            "HST": "HOU", "SL": "LA"}
GAPS = {"LT": [("left", "end"), ("left", "tackle")], "LG": [("left", "guard")], "C": [("middle", "")],
        "RG": [("right", "guard")], "RT": [("right", "tackle"), ("right", "end")],
        "G": [("left", "guard"), ("right", "guard")],
        "T": [("left", "end"), ("left", "tackle"), ("right", "tackle"), ("right", "end")]}
COLS = ["id", "season", "team", "teams", "slot", "slots", "g", "gs", "w", "l", "t", "snaps", "tsnaps",
        "pen", "hold", "fs", "pyds", "gcar", "gyds", "gepa", "gsucc", "gstuff", "gexp", "tcar", "tdb", "tsk", "thit"]


def num(v):
    if v is None or v == "" or v == "NA":
        return None
    try:
        return float(v)
    except ValueError:
        return None


def flag(v):
    n = num(v)
    return n is not None and n == 1


def team(code):
    code = (code or "").strip()
    return TEAM_FIX.get(code, code)


def norm_slot(s):
    s = (s or "").strip().upper()
    s = SLOT_FIX.get(s, s)
    return s if s in SLOTS or s in ("G", "T") else ""


def read_pbp(path):
    games, tw_game = {}, {}
    gap = defaultdict(lambda: defaultdict(lambda: [0, 0.0, 0.0, 0.0, 0, 0]))
    teamc = defaultdict(lambda: [0, 0, 0, 0])  # tcar, tdb, tsk, thit
    pens = defaultdict(lambda: [0, 0, 0, 0.0])  # pen, hold, fs, yards
    weeks = 0
    with gzip.open(path, "rt", encoding="utf-8", newline="") as fh:
        rd = csv.reader(fh)
        ix = {n: i for i, n in enumerate(next(rd))}
        keys = ["season_type", "week", "game_id", "home_team", "away_team", "home_score", "away_score", "posteam",
                "play_type", "two_point_attempt", "qb_scramble", "qb_kneel", "qb_dropback", "sack", "qb_hit",
                "run_location", "run_gap", "rushing_yards", "yards_gained", "epa", "success",
                "penalty_player_id", "penalty_type", "penalty_yards"]
        I = {k: ix.get(k, -1) for k in keys}

        def g(row, k):
            i = I[k]
            return row[i] if 0 <= i < len(row) else ""

        for row in rd:
            if g(row, "season_type") != "REG":
                continue
            game = g(row, "game_id")
            wk = int(num(g(row, "week")) or 0)
            weeks = max(weeks, wk)
            if game not in games:
                h, a = g(row, "home_team"), g(row, "away_team")
                games[game] = (wk, h, a, num(g(row, "home_score")), num(g(row, "away_score")))
                tw_game[(h, wk)] = game
                tw_game[(a, wk)] = game
            pid = g(row, "penalty_player_id")
            if pid and pid != "NA":
                p = pens[pid]
                p[0] += 1
                pt = g(row, "penalty_type")
                if pt == "Offensive Holding":
                    p[1] += 1
                elif pt == "False Start":
                    p[2] += 1
                p[3] += num(g(row, "penalty_yards")) or 0
            pos = g(row, "posteam")
            pt = g(row, "play_type")
            if not pos or pt not in ("run", "pass") or flag(g(row, "two_point_attempt")):
                continue
            tc = teamc[(game, pos)]
            if flag(g(row, "qb_dropback")):
                tc[1] += 1
                if flag(g(row, "sack")):
                    tc[2] += 1
                if flag(g(row, "qb_hit")):
                    tc[3] += 1
                continue
            if pt == "run" and not flag(g(row, "qb_scramble")) and not flag(g(row, "qb_kneel")):
                tc[0] += 1
                loc = g(row, "run_location")
                gp = g(row, "run_gap")
                gp = "" if gp == "NA" else gp
                if loc in ("left", "right", "middle"):
                    s = gap[(game, pos)][(loc, "" if loc == "middle" else gp)]
                    y = num(g(row, "rushing_yards"))
                    if y is None:
                        y = num(g(row, "yards_gained")) or 0
                    s[0] += 1
                    s[1] += y
                    s[2] += num(g(row, "epa")) or 0
                    s[3] += num(g(row, "success")) or 0
                    if y <= 0:
                        s[4] += 1
                    if y >= 10:
                        s[5] += 1
    return games, tw_game, gap, teamc, pens, weeks


def depth_old(path):
    """Weekly depth charts 2001-2024 -> {(team, week): [(gsis, slot, depth)]} and season slot counts."""
    by_week = defaultdict(list)
    slot_cnt = defaultdict(Counter)
    with open(path, encoding="utf-8", newline="") as fh:
        for d in csv.DictReader(fh):
            if d.get("game_type") != "REG" or d.get("formation") != "Offense":
                continue
            slot = norm_slot(d.get("depth_position"))
            gid = (d.get("gsis_id") or "").strip()
            if not slot or not gid or gid == "NA":
                continue
            if (d.get("position") or "").strip().upper() not in OL_POS and slot not in SLOTS:
                continue
            wk = int(num(d.get("week")) or 0)
            depth = int(num(d.get("depth_team")) or 9)
            by_week[(team(d.get("club_code")), wk)].append((gid, slot, depth))
            if depth == 1:
                slot_cnt[gid][slot] += 1
            else:
                slot_cnt[gid][slot] += 0.1
    return by_week, slot_cnt


def depth_new(path):
    """Daily depth charts 2025+ -> season slot counts per player."""
    slot_cnt = defaultdict(Counter)
    with gzip.open(path, "rt", encoding="utf-8", newline="") as fh:
        for d in csv.DictReader(fh):
            slot = norm_slot(d.get("pos_abb"))
            gid = (d.get("gsis_id") or "").strip()
            if slot in SLOTS and gid and gid != "NA":
                slot_cnt[gid][slot] += 1 if d.get("pos_rank") == "1" else 0.1
    return slot_cnt


def snaps(path, pfr_to_gsis):
    """Snap counts -> list of (game_id, team, gsis, slot_hint, snaps, team_snaps, started)."""
    out = []
    with gzip.open(path, "rt", encoding="utf-8", newline="") as fh:
        for d in csv.DictReader(fh):
            if d.get("game_type") != "REG" or (d.get("position") or "") not in OL_POS:
                continue
            gid = pfr_to_gsis.get(d.get("pfr_player_id") or "")
            if not gid:
                continue
            s, pct = num(d.get("offense_snaps")) or 0, num(d.get("offense_pct")) or 0
            if s <= 0:
                continue
            out.append((d["game_id"], team(d.get("team")), gid, norm_slot(d.get("position")), s,
                        s / pct if pct > 0 else 0, pct >= 0.5))
    return out


def load_players(path):
    out, pfr = {}, {}
    with open(path, encoding="utf-8", newline="") as fh:
        for d in csv.DictReader(fh):
            gid = d.get("gsis_id") or ""
            if not gid:
                continue
            draft = ""
            try:
                if d.get("draft_round") not in ("", "NA", None):
                    draft = f"{d['draft_year']} R{int(float(d['draft_round']))} #{int(float(d['draft_pick']))}"
                elif d.get("draft_year") in ("", "NA", None):
                    draft = "Undrafted"
            except (ValueError, KeyError):
                draft = ""
            legal = f"{d.get('first_name') or ''} {d.get('last_name') or ''}".strip()
            name = d.get("display_name") or ""
            out[gid] = {"name": name, "alias": legal if legal != name else "", "pos": d.get("position") or "",
                        "college": (d.get("college_name") or "").replace("NA", ""), "draft": draft,
                        "born": (d.get("birth_date") or "").replace("NA", "")}
            if d.get("pfr_id") and d["pfr_id"] != "NA":
                pfr[d["pfr_id"]] = gid
    return out, pfr


def main():
    raw, out_js = sys.argv[1], sys.argv[2]
    players, pfr_to_gsis = load_players(os.path.join(raw, "players.csv"))
    seasons, table, ids = {}, [], set()
    for season in range(FIRST_SEASON, LAST_SEASON + 1):
        t0 = time.time()
        pbp = os.path.join(raw, "pbp", f"play_by_play_{season}.csv.gz")
        if not os.path.exists(pbp):
            continue
        games, tw_game, gap, teamc, pens, weeks = read_pbp(pbp)
        old = os.path.join(raw, "depth_charts", f"depth_charts_{season}.csv")
        new = os.path.join(raw, "depth_charts", f"depth_charts_{season}.csv.gz")
        by_week, slot_cnt = depth_old(old) if os.path.exists(old) else ({}, depth_new(new) if os.path.exists(new) else {})
        starts = []  # (gsis, game, team, slot, snaps, team_snaps)
        sc_path = os.path.join(raw, "snap_counts", f"snap_counts_{season}.csv.gz")
        snap_rows = snaps(sc_path, pfr_to_gsis) if season >= 2013 and os.path.exists(sc_path) else []
        source = "snaps" if snap_rows else "depth"
        if snap_rows:
            wk_slot = {}
            for (tm, wk), lst in by_week.items():
                for gid, slot, depth in lst:
                    if (tm, wk, gid) not in wk_slot or depth == 1:
                        wk_slot[(tm, wk, gid)] = slot
            for game, tm, gid, hint, s, ts, started in snap_rows:
                if not started or game not in games:
                    continue
                wk = games[game][0]
                slot = wk_slot.get((tm, wk, gid))
                if not slot and slot_cnt.get(gid):
                    slot = slot_cnt[gid].most_common(1)[0][0]
                starts.append((gid, game, tm, slot or hint or "G", s, ts))
        else:
            seen = set()
            for (tm, wk), lst in by_week.items():
                game = tw_game.get((tm, wk))
                if not game:
                    continue
                for gid, slot, depth in lst:
                    if depth != 1 or (gid, game) in seen:
                        continue
                    seen.add((gid, game))
                    starts.append((gid, game, tm, slot, 0, 0))
        acc = defaultdict(lambda: {"gs": 0, "w": 0, "l": 0, "t": 0, "snaps": 0.0, "tsnaps": 0.0, "gcar": 0, "gyds": 0.0,
                                   "gepa": 0.0, "gsucc": 0.0, "gstuff": 0, "gexp": 0, "tcar": 0, "tdb": 0, "tsk": 0,
                                   "thit": 0, "teams": Counter(), "slots": Counter()})
        for gid, game, tm, slot, s, ts in starts:
            a = acc[gid]
            a["gs"] += 1
            a["snaps"] += s
            a["tsnaps"] += ts
            a["teams"][tm] += 1
            a["slots"][slot] += 1
            wk, h, aw, hs, as_ = games[game]
            if hs is not None and as_ is not None:
                mine, theirs = (hs, as_) if tm == h else (as_, hs)
                a["w" if mine > theirs else "l" if mine < theirs else "t"] += 1
            gs_ = gap.get((game, tm), {})
            for key in GAPS.get(slot, []):
                v = gs_.get(key)
                if v:
                    a["gcar"] += v[0]
                    a["gyds"] += v[1]
                    a["gepa"] += v[2]
                    a["gsucc"] += v[3]
                    a["gstuff"] += v[4]
                    a["gexp"] += v[5]
            tc = teamc.get((game, tm), [0, 0, 0, 0])
            a["tcar"] += tc[0]
            a["tdb"] += tc[1]
            a["tsk"] += tc[2]
            a["thit"] += tc[3]
        tg = Counter()
        for game, (wk, h, aw, hs, as_) in games.items():
            tg[h] += 1
            tg[aw] += 1
        tgl = sorted(tg.values())
        info = {"teamGames": tgl[len(tgl) // 2] if tgl else 0, "fullGames": 16 if season <= 2020 else 17, "weeks": weeks}
        seasons[season] = info
        need = max(2, round(MIN_STARTS * min(1.0, info["teamGames"] / info["fullGames"])))
        n = 0
        for gid, a in acc.items():
            pos = players.get(gid, {}).get("pos", "")
            if a["gs"] < need or (pos and pos not in OL_POS):
                continue
            p = pens.get(gid, [0, 0, 0, 0.0])
            slot_order = [s for s, _ in a["slots"].most_common()]
            vals = {"id": gid, "season": season, "team": a["teams"].most_common(1)[0][0],
                    "teams": "/".join(t for t, _ in a["teams"].most_common()), "slot": slot_order[0],
                    "slots": "/".join(slot_order), "g": a["gs"], "pen": p[0], "hold": p[1], "fs": p[2], "pyds": p[3]}
            for k in ("gs", "w", "l", "t", "snaps", "tsnaps", "gcar", "gyds", "gepa", "gsucc", "gstuff", "gexp",
                      "tcar", "tdb", "tsk", "thit"):
                v = a[k]
                vals[k] = round(v, 2) if isinstance(v, float) else v
            table.append([vals[c] for c in COLS])
            ids.add(gid)
            n += 1
        print(f"  {season}: {n} linemen from {source}, {len(starts)} starts, {time.time() - t0:.1f}s", flush=True)
    people = {}
    for gid in ids:
        p = players.get(gid, {})
        people[gid] = {"n": p.get("name") or gid, "a": p.get("alias", ""), "c": p.get("college", ""),
                       "d": p.get("draft", ""), "b": p.get("born", "")}
    data = {"built": time.strftime("%Y-%m-%d"), "source": "nflverse play-by-play, depth charts and snap counts, regular season",
            "seasons": seasons, "players": people, "cols": COLS, "rows": table}
    with open(out_js, "w", encoding="utf-8") as fh:
        fh.write("window.GT_OL=")
        json.dump(data, fh, separators=(",", ":"))
        fh.write(";\n")
    print(f"wrote {out_js}: {len(table)} OL seasons, {len(people)} linemen, {os.path.getsize(out_js) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
