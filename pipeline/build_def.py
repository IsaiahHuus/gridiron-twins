"""Build defensive season tables for Gridiron Twins (DL now; LB and DB use the same code).

Usage (run with -I so nothing in the raw folder is imported):
    python -I pipeline/build_def.py <raw_dir> <app_dir> DL [LB] [DB]

Writes <app_dir>/dl-data.js (window.GT_DL), lb-data.js (GT_LB), db-data.js (GT_DB).

Where a player lined up each season comes from snap counts (2013+), weekly
depth charts (2001-2012) and, for 2000 or when neither lists him, the player
file. Stats are his own pbp credits: tackles (solo + assisted), sacks (half
sacks count 0.5), QB hits (recorded from 2006), tackles for loss and run
stops (counted from play results), forced fumbles, recoveries, passes
defended, interceptions and penalties.
"""
import csv
import gzip
import json
import os
import sys
import time
from collections import Counter, defaultdict

csv.field_size_limit(10**8)
FIRST_SEASON, LAST_SEASON = 2000, 2026
TEAM_FIX = {"OAK": "LV", "SD": "LAC", "STL": "LA", "LAR": "LA", "JAC": "JAX", "ARZ": "ARI", "BLT": "BAL", "CLV": "CLE",
            "HST": "HOU", "SL": "LA"}
# depth chart / snap labels -> (group, display spot)
SLOT_MAP = {}
for k in ("DE", "LDE", "RDE", "LE", "RE", "EDGE", "LEO"):
    SLOT_MAP[k] = ("DL", "DE")
for k in ("DT", "LDT", "RDT", "DL", "LDL", "RDL", "DI", "UT", "3T"):
    SLOT_MAP[k] = ("DL", "DT")
for k in ("NT", "NG"):
    SLOT_MAP[k] = ("DL", "NT")
for k in ("OLB", "LOLB", "ROLB", "LLB", "RLB"):
    SLOT_MAP[k] = ("LB", "OLB")
for k in ("ILB", "MLB", "LILB", "RILB", "LB", "WLB", "SLB", "MIKE", "WILL", "SAM", "MILB"):
    SLOT_MAP[k] = ("LB", "LB")
for k in ("CB", "LCB", "RCB", "NB", "NCB", "DB", "SCB"):
    SLOT_MAP[k] = ("DB", "CB")
for k in ("S", "FS", "SS", "RS", "LS"):
    SLOT_MAP[k] = ("DB", "S")
OUT = {"DL": ("GT_DL", "dl-data.js"), "LB": ("GT_LB", "lb-data.js"), "DB": ("GT_DB", "db-data.js")}
MIN = {"DL": (6, 10), "LB": (6, 15), "DB": (6, 12)}  # games, tackles+hits+passes defended per full season
COLS = ["id", "season", "team", "teams", "slot", "slots", "g", "gs", "snaps", "tsnaps",
        "tk", "solo", "sk", "hit", "hitn", "tfl", "stuff", "rtk", "rtky", "ff", "fr", "pd", "int", "pen"]
STAT_KEYS = ["tk", "solo", "sk", "hit", "tfl", "stuff", "rtk", "rtky", "ff", "fr", "pd", "int", "pen"]


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


def slot_of(label):
    return SLOT_MAP.get((label or "").strip().upper())


def read_pbp(path):
    games, tw_game = {}, {}
    acc = defaultdict(lambda: defaultdict(float))
    pgames = defaultdict(set)
    pteam = defaultdict(Counter)
    weeks = 0
    with gzip.open(path, "rt", encoding="utf-8", newline="") as fh:
        rd = csv.reader(fh)
        ix = {n: i for i, n in enumerate(next(rd))}
        T = ["solo_tackle_1_player_id", "solo_tackle_2_player_id", "tackle_with_assist_1_player_id",
             "tackle_with_assist_2_player_id", "assist_tackle_1_player_id", "assist_tackle_2_player_id",
             "assist_tackle_3_player_id", "assist_tackle_4_player_id"]
        keys = ["season_type", "week", "game_id", "home_team", "away_team", "defteam", "play_type", "two_point_attempt",
                "qb_scramble", "qb_kneel", "sack", "yards_gained", "sack_player_id", "half_sack_1_player_id",
                "half_sack_2_player_id", "qb_hit_1_player_id", "qb_hit_2_player_id",
                "forced_fumble_player_1_player_id", "forced_fumble_player_2_player_id",
                "fumble_recovery_1_player_id", "fumble_recovery_1_team", "pass_defense_1_player_id",
                "pass_defense_2_player_id", "interception_player_id", "penalty_player_id", "penalty_team"] + T
        I = {k: ix.get(k, -1) for k in keys}

        def g(row, k):
            i = I[k]
            v = row[i] if 0 <= i < len(row) else ""
            return "" if v == "NA" else v

        for row in rd:
            if g(row, "season_type") != "REG":
                continue
            game = g(row, "game_id")
            wk = int(num(g(row, "week")) or 0)
            weeks = max(weeks, wk)
            if game not in games:
                h, a = g(row, "home_team"), g(row, "away_team")
                games[game] = wk
                tw_game[(h, wk)] = game
                tw_game[(a, wk)] = game
            dt = g(row, "defteam")

            def credit(pid, key, amt=1.0):
                if not pid:
                    return
                acc[pid][key] += amt
                pgames[pid].add(game)
                if dt:
                    pteam[pid][dt] += 1

            pt = g(row, "play_type")
            pid = g(row, "penalty_player_id")
            if pid and g(row, "penalty_team") == dt and pt in ("run", "pass", "no_play"):
                credit(pid, "pen")
            # only plays from scrimmage count; kick and punt coverage tackles are left out
            if flag(g(row, "two_point_attempt")) or pt not in ("run", "pass"):
                continue
            tacklers = []
            for k in T:
                p = g(row, k)
                if p and p not in tacklers:
                    tacklers.append(p)
            for i, p in enumerate(tacklers):
                credit(p, "tk")
            for k in ("solo_tackle_1_player_id", "solo_tackle_2_player_id"):
                credit(g(row, k), "solo")
            credit(g(row, "sack_player_id"), "sk")
            credit(g(row, "half_sack_1_player_id"), "sk", 0.5)
            credit(g(row, "half_sack_2_player_id"), "sk", 0.5)
            credit(g(row, "qb_hit_1_player_id"), "hit")
            credit(g(row, "qb_hit_2_player_id"), "hit")
            credit(g(row, "forced_fumble_player_1_player_id"), "ff")
            credit(g(row, "forced_fumble_player_2_player_id"), "ff")
            if g(row, "fumble_recovery_1_team") == dt:
                credit(g(row, "fumble_recovery_1_player_id"), "fr")
            credit(g(row, "pass_defense_1_player_id"), "pd")
            credit(g(row, "pass_defense_2_player_id"), "pd")
            credit(g(row, "interception_player_id"), "int")
            y = num(g(row, "yards_gained"))
            if y is None:
                continue
            if y < 0 and not flag(g(row, "sack")):
                for p in tacklers:
                    credit(p, "tfl")
            if pt == "run" and not flag(g(row, "qb_scramble")) and not flag(g(row, "qb_kneel")):
                for p in tacklers:
                    credit(p, "rtk")
                    credit(p, "rtky", y)
                    if y <= 0:
                        credit(p, "stuff")
    return games, tw_game, acc, pgames, pteam, weeks


def depth_old(path):
    """Weekly depth charts 2001-2024 (Defense rows) -> starts per (team, week) and spot counts per player."""
    starts = defaultdict(list)
    spot = defaultdict(Counter)
    with open(path, encoding="utf-8", newline="") as fh:
        for d in csv.DictReader(fh):
            if d.get("game_type") != "REG" or d.get("formation") != "Defense":
                continue
            s = slot_of(d.get("depth_position")) or slot_of(d.get("position"))
            gid = (d.get("gsis_id") or "").strip()
            if not s or not gid or gid == "NA":
                continue
            wk = int(num(d.get("week")) or 0)
            depth = int(num(d.get("depth_team")) or 9)
            spot[gid][s] += 1 if depth == 1 else 0.2
            if depth == 1:
                starts[(team(d.get("club_code")), wk)].append(gid)
    return starts, spot


def snaps(path, pfr_to_gsis):
    out = []
    with gzip.open(path, "rt", encoding="utf-8", newline="") as fh:
        for d in csv.DictReader(fh):
            if d.get("game_type") != "REG":
                continue
            s = slot_of(d.get("position"))
            gid = pfr_to_gsis.get(d.get("pfr_player_id") or "")
            snp, pct = num(d.get("defense_snaps")) or 0, num(d.get("defense_pct")) or 0
            if not s or not gid or snp <= 0:
                continue
            out.append((d["game_id"], team(d.get("team")), gid, s, snp, snp / pct if pct > 0 else 0, pct >= 0.5))
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
    raw, app_dir, groups = sys.argv[1], sys.argv[2], sys.argv[3:] or ["DL"]
    players, pfr_to_gsis = load_players(os.path.join(raw, "players.csv"))
    seasons = {}
    tables = {k: [] for k in groups}
    ids = {k: set() for k in groups}
    for season in range(FIRST_SEASON, LAST_SEASON + 1):
        t0 = time.time()
        pbp = os.path.join(raw, "pbp", f"play_by_play_{season}.csv.gz")
        if not os.path.exists(pbp):
            continue
        games, tw_game, acc, pgames, pteam, weeks = read_pbp(pbp)
        old = os.path.join(raw, "depth_charts", f"depth_charts_{season}.csv")
        dstarts, dspot = depth_old(old) if os.path.exists(old) else ({}, {})
        sc = os.path.join(raw, "snap_counts", f"snap_counts_{season}.csv.gz")
        srows = snaps(sc, pfr_to_gsis) if season >= 2013 and os.path.exists(sc) else []
        pl = defaultdict(lambda: {"gs": set(), "g": set(), "snaps": 0.0, "tsnaps": 0.0, "spot": Counter(), "team": Counter()})
        if srows:
            for game, tm, gid, s, snp, ts, started in srows:
                p = pl[gid]
                p["g"].add(game)
                p["snaps"] += snp
                p["tsnaps"] += ts
                p["spot"][s] += 1
                p["team"][tm] += 1
                if started:
                    p["gs"].add(game)
        else:
            for (tm, wk), lst in dstarts.items():
                game = tw_game.get((tm, wk))
                if not game:
                    continue
                for gid in lst:
                    pl[gid]["gs"].add(game)
                    pl[gid]["g"].add(game)
                    pl[gid]["team"][tm] += 1
            for gid, cnt in dspot.items():
                pl[gid]["spot"].update(cnt)
        tg = Counter()
        for game in games:
            a, h = game.split("_")[2], game.split("_")[3]
            tg[a] += 1
            tg[h] += 1
        tgl = sorted(tg.values())
        info = {"teamGames": tgl[len(tgl) // 2] if tgl else 0, "fullGames": 16 if season <= 2020 else 17, "weeks": weeks}
        seasons[season] = info
        scale = min(1.0, info["teamGames"] / info["fullGames"])
        has_starts = season >= 2001
        counts = Counter()
        for gid in set(acc) | set(pl):
            p = pl.get(gid)
            spot = p["spot"] if p else Counter()
            if spot:
                grp, disp = spot.most_common(1)[0][0]
            else:
                fb = slot_of(players.get(gid, {}).get("pos", ""))
                if not fb:
                    continue
                grp, disp = fb
            if grp not in tables:
                continue
            st = acc.get(gid, {})
            gset = set(pgames.get(gid, set())) | (p["g"] if p else set())
            g = len(gset)
            mg, mplays = MIN[grp]
            plays = st.get("tk", 0) + st.get("hit", 0) + st.get("pd", 0)
            if g < max(3, round(mg * scale)) or plays < max(4, round(mplays * scale)):
                continue
            tcount = (p["team"] if p and p["team"] else Counter()) + pteam.get(gid, Counter())
            tot = sum(tcount.values()) or 1
            # a team counts only if it is 15%+ of his season (drops stray credits on odd turnover plays)
            order = [t for t, c in tcount.most_common() if c / tot >= 0.15] or [t for t, _ in tcount.most_common(1)]
            spots = [s[1] for s, _ in spot.most_common()] if spot else [disp]
            vals = {"id": gid, "season": season, "team": order[0] if order else "", "teams": "/".join(order),
                    "slot": disp, "slots": "/".join(dict.fromkeys(spots)), "g": g,
                    "gs": len(p["gs"]) if (p and has_starts) else 0, "snaps": round(p["snaps"], 1) if p else 0,
                    "tsnaps": round(p["tsnaps"], 1) if p else 0, "hitn": g if season >= 2006 else 0}
            for k in STAT_KEYS:
                v = st.get(k, 0)
                vals[k] = round(v, 1) if isinstance(v, float) and v != int(v) else int(v)
            if season < 2006:
                vals["hit"] = 0
            tables[grp].append([vals[c] for c in COLS])
            ids[grp].add(gid)
            counts[grp] += 1
        print(f"  {season}: " + ", ".join(f"{k} {counts[k]}" for k in groups) +
              f" ({'snaps' if srows else 'depth' if dstarts else 'pbp only'}), {time.time() - t0:.1f}s", flush=True)
    for grp in groups:
        var, fname = OUT[grp]
        people = {}
        for gid in ids[grp]:
            p = players.get(gid, {})
            people[gid] = {"n": p.get("name") or gid, "a": p.get("alias", ""), "c": p.get("college", ""),
                           "d": p.get("draft", ""), "b": p.get("born", "")}
        data = {"built": time.strftime("%Y-%m-%d"),
                "source": "nflverse play-by-play, depth charts and snap counts, regular season",
                "seasons": seasons, "players": people, "cols": COLS, "rows": tables[grp]}
        dest = os.path.join(app_dir, fname)
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(f"window.{var}=")
            json.dump(data, fh, separators=(",", ":"))
            fh.write(";\n")
        print(f"wrote {dest}: {len(tables[grp])} {grp} seasons, {len(people)} players, {os.path.getsize(dest) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
