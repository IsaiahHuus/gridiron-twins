"""Build the QB season table for Gridiron Twins from nflverse play-by-play.

Usage (run from anywhere, with -I so nothing in the raw folder is imported):
    python -I pipeline/build_qb.py <raw_dir> <out_js>

<raw_dir> holds play_by_play_YYYY.csv.gz files (nflverse "pbp" release)
and players.csv (nflverse "players" release). The output is a small JS file
that sets window.GT_DATA = {...} so the page works without fetch().

Only regular-season plays are used. Two-point tries and kneels are skipped.
Everything is kept as raw counts per QB-season; the page derives the rates,
the era adjustment and the twin scores so they can be changed in the UI.
"""
import csv
import gzip
import json
import os
import re
import sys
import time
from collections import defaultdict

csv.field_size_limit(10**8)

FIRST_SEASON = 2000
LAST_SEASON = 2026

# Columns stored per QB-season (order matters: the page reads them by name).
COLS = [
    "id", "season", "team", "teams",
    "g", "gs", "w", "l", "t",
    "db", "att", "cmp", "yds", "td", "int",
    "sk", "sky", "scr", "scry",
    "drun", "druny", "rtd",
    "fum", "fuml",
    "epa", "epan", "succ", "repa",
    "cpoe", "cpoen", "ay", "ayn", "deep",
    "yac", "yacy", "fd", "sg", "hit",
]


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


class Acc:
    __slots__ = [c for c in COLS if c not in ("id", "season", "team", "teams", "g", "gs", "w", "l", "t")] + [
        "games", "team_db", "pname"]

    def __init__(self):
        for c in self.__slots__:
            setattr(self, c, 0)
        self.games = set()
        self.team_db = defaultdict(int)
        self.pname = ""


def process_season(path, season):
    t0 = time.time()
    qbs = defaultdict(Acc)          # dropback player id -> Acc
    runs = defaultdict(lambda: [0, 0.0, 0, 0.0, set()])  # rusher id -> n, yds, td, epa, games
    fumbles = defaultdict(lambda: [0, 0])                # player id -> fum, lost
    game_load = defaultdict(lambda: defaultdict(int))    # (game, team) -> {player: plays}
    games = {}                                           # game -> (home, away, hs, as)
    team_games = defaultdict(set)

    with gzip.open(path, "rt", encoding="utf-8", newline="") as fh:
        rd = csv.reader(fh)
        header = next(rd)
        ix = {name: i for i, name in enumerate(header)}

        def col(name):
            return ix.get(name, -1)

        max_week = 0
        I = {k: col(k) for k in [
            "season_type", "week", "play_type", "two_point_attempt", "game_id", "posteam",
            "home_team", "away_team", "home_score", "away_score",
            "qb_dropback", "qb_scramble", "qb_spike", "qb_kneel", "sack",
            "passer_id", "passer_player_id", "passer", "passer_player_name",
            "rusher_id", "rusher_player_id",
            "complete_pass", "incomplete_pass", "interception",
            "pass_touchdown", "rush_touchdown",
            "passing_yards", "rushing_yards", "yards_gained",
            "air_yards", "yards_after_catch", "cpoe", "epa", "qb_epa", "success",
            "first_down_pass", "shotgun", "qb_hit",
            "fumble", "fumble_lost", "fumbled_1_player_id",
        ]}

        def g(row, k):
            i = I[k]
            return row[i] if i >= 0 and i < len(row) else ""

        for row in rd:
            if g(row, "season_type") != "REG":
                continue
            wk = num(g(row, "week"))
            if wk is not None and wk > max_week:
                max_week = int(wk)
            pt = g(row, "play_type")
            if pt not in ("pass", "run", "qb_spike", "qb_kneel"):
                continue
            if flag(g(row, "two_point_attempt")):
                continue
            game = g(row, "game_id")
            pos = g(row, "posteam")
            if not pos:
                continue
            team_games[pos].add(game)
            if game not in games:
                games[game] = (g(row, "home_team"), g(row, "away_team"),
                               num(g(row, "home_score")), num(g(row, "away_score")))

            if flag(g(row, "fumble")):
                fid = g(row, "fumbled_1_player_id")
                if fid:
                    fumbles[fid][0] += 1
                    if flag(g(row, "fumble_lost")):
                        fumbles[fid][1] += 1

            if pt == "qb_kneel":
                continue

            scramble = flag(g(row, "qb_scramble"))
            if flag(g(row, "qb_dropback")):
                qid = g(row, "passer_id") or g(row, "passer_player_id")
                if not qid and scramble:
                    qid = g(row, "rusher_player_id") or g(row, "rusher_id")
                if not qid:
                    continue
                s = qbs[qid]
                if not s.pname:
                    s.pname = g(row, "passer") or g(row, "passer_player_name")
                s.games.add(game)
                if pt == "qb_spike":
                    s.att += 1   # spikes are official attempts, not real dropbacks
                    continue
                s.db += 1
                s.team_db[pos] += 1
                game_load[(game, pos)][qid] += 1
                e = num(g(row, "qb_epa"))
                if e is None:
                    e = num(g(row, "epa"))
                if e is not None:
                    s.epa += e
                    s.epan += 1
                sc = num(g(row, "success"))
                if sc is not None:
                    s.succ += sc
                if flag(g(row, "shotgun")):
                    s.sg += 1
                if flag(g(row, "qb_hit")):
                    s.hit += 1
                if flag(g(row, "sack")):
                    s.sk += 1
                    s.sky += -(num(g(row, "yards_gained")) or 0)
                elif scramble:
                    s.scr += 1
                    s.scry += num(g(row, "rushing_yards")) or 0
                    if flag(g(row, "rush_touchdown")):
                        s.rtd += 1
                else:
                    comp = flag(g(row, "complete_pass"))
                    inc = flag(g(row, "incomplete_pass"))
                    itc = flag(g(row, "interception"))
                    if not (comp or inc or itc):
                        continue
                    s.att += 1
                    if comp:
                        s.cmp += 1
                        py = num(g(row, "passing_yards"))
                        if py is None:
                            py = num(g(row, "yards_gained")) or 0
                        s.yds += py
                        yac = num(g(row, "yards_after_catch"))
                        if yac is not None:
                            s.yac += yac
                            s.yacy += py
                    if flag(g(row, "pass_touchdown")):
                        s.td += 1
                    if itc:
                        s.int += 1
                    if flag(g(row, "first_down_pass")):
                        s.fd += 1
                    ay = num(g(row, "air_yards"))
                    if ay is not None:
                        s.ay += ay
                        s.ayn += 1
                        if ay >= 20:
                            s.deep += 1
                    cp = num(g(row, "cpoe"))
                    if cp is not None:
                        s.cpoe += cp
                        s.cpoen += 1
            elif pt == "run" and not scramble:
                rid = g(row, "rusher_player_id") or g(row, "rusher_id")
                if not rid:
                    continue
                r = runs[rid]
                r[0] += 1
                r[1] += num(g(row, "rushing_yards")) or 0
                if flag(g(row, "rush_touchdown")):
                    r[2] += 1
                e = num(g(row, "epa"))
                if e is not None:
                    r[3] += e
                r[4].add(game)

    # Primary QB per team-game = most dropbacks. Gives starts and W-L-T.
    starts = defaultdict(lambda: [0, 0, 0, 0])  # gs, w, l, t
    for (game, pos), load in game_load.items():
        load = {k: v for k, v in load.items() if v > 0 and k in qbs}
        if not load:
            continue
        top = max(load.items(), key=lambda kv: kv[1])[0]
        home, away, hs, as_ = games.get(game, ("", "", None, None))
        rec = starts[top]
        rec[0] += 1
        if hs is None or as_ is None:
            continue
        mine, theirs = (hs, as_) if pos == home else (as_, hs)
        if mine > theirs:
            rec[1] += 1
        elif mine < theirs:
            rec[2] += 1
        else:
            rec[3] += 1

    rows = []
    for qid, s in qbs.items():
        r = runs.get(qid)
        if r:
            s.drun, s.druny, s.rtd = r[0], r[1], s.rtd + r[2]
            s.repa = r[3]
            s.games |= r[4]
        fm = fumbles.get(qid)
        if fm:
            s.fum, s.fuml = fm
        team_order = sorted(s.team_db.items(), key=lambda kv: -kv[1])
        team = team_order[0][0] if team_order else ""
        teams = "/".join(t for t, _ in team_order)
        st = starts.get(qid, [0, 0, 0, 0])
        rows.append((qid, s, team, teams, st))

    tg = sorted(len(v) for v in team_games.values())
    info = {
        "teamGames": tg[len(tg) // 2] if tg else 0,
        "fullGames": 16 if season <= 2020 else 17,
        "weeks": max_week,
    }
    print(f"  {season}: {len(rows)} passers, median team games {info['teamGames']}, "
          f"{time.time() - t0:.1f}s", flush=True)
    return rows, info


def load_players(path):
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8", newline="") as fh:
        for d in csv.DictReader(fh):
            gid = d.get("gsis_id") or ""
            if not gid:
                continue
            draft = ""
            if d.get("draft_year") and d.get("draft_round") and d.get("draft_round") != "NA":
                try:
                    draft = f"{d['draft_year']} R{int(float(d['draft_round']))} #{int(float(d['draft_pick']))}"
                except (ValueError, KeyError):
                    draft = ""
            elif d.get("draft_year") in ("", "NA", None):
                draft = "Undrafted"
            legal = f"{d.get('first_name') or ''} {d.get('last_name') or ''}".strip()
            out[gid] = {
                "alias": legal if legal and legal != (d.get("display_name") or "") else "",
                "name": d.get("display_name") or "",
                "pos": d.get("position") or "",
                "college": (d.get("college_name") or "").replace("NA", ""),
                "draft": draft,
                "born": (d.get("birth_date") or "").replace("NA", ""),
            }
    return out


def main():
    raw_dir, out_js = sys.argv[1], sys.argv[2]
    players = load_players(os.path.join(raw_dir, "players.csv"))
    print(f"players.csv: {len(players)} people")
    seasons = {}
    table = []
    names = {}
    for season in range(FIRST_SEASON, LAST_SEASON + 1):
        path = os.path.join(raw_dir, "pbp", f"play_by_play_{season}.csv.gz")
        if not os.path.exists(path):
            print(f"  {season}: no file, skipped")
            continue
        rows, info = process_season(path, season)
        seasons[season] = info
        for qid, s, team, teams, st in rows:
            pos = players.get(qid, {}).get("pos", "")
            # Keep real QBs; drop trick plays by other positions.
            if not ((pos == "QB" and s.db >= 10) or s.db >= 100):
                continue
            names.setdefault(qid, s.pname)
            g = len(s.games)
            vals = {
                "id": qid, "season": season, "team": team, "teams": teams,
                "g": g, "gs": st[0], "w": st[1], "l": st[2], "t": st[3],
            }
            for c in COLS:
                if c not in vals:
                    v = getattr(s, c)
                    vals[c] = round(v, 3) if isinstance(v, float) else v
            table.append([vals[c] for c in COLS])

    people = {}
    for qid, short in names.items():
        p = players.get(qid, {})
        people[qid] = {
            "n": p.get("name") or re.sub(r"\.", ". ", short or qid),
            "a": p.get("alias", ""),
            "c": p.get("college", ""),
            "d": p.get("draft", ""),
            "b": p.get("born", ""),
        }

    data = {
        "built": time.strftime("%Y-%m-%d"),
        "source": "nflverse play-by-play (nflfastR), regular season",
        "seasons": seasons,
        "players": people,
        "cols": COLS,
        "rows": table,
    }
    os.makedirs(os.path.dirname(os.path.abspath(out_js)), exist_ok=True)
    with open(out_js, "w", encoding="utf-8") as fh:
        fh.write("window.GT_DATA=")
        json.dump(data, fh, separators=(",", ":"))
        fh.write(";\n")
    print(f"wrote {out_js}: {len(table)} QB-seasons, {len(people)} QBs, "
          f"{os.path.getsize(out_js) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
