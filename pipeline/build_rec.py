"""Build the WR and TE season tables for Gridiron Twins from nflverse play-by-play.

Usage (run with -I so nothing in the raw folder is imported):
    python -I pipeline/build_rec.py <raw_dir> <app_dir>

Writes <app_dir>/wr-data.js (window.GT_WR) and <app_dir>/te-data.js (window.GT_TE).
Regular season only; two-point tries, sacks and spikes are skipped. Only real
contributors are kept: a WR season needs 40+ targets and a TE season 30+
(both scaled down for a season still in progress).
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
FIRST_SEASON, LAST_SEASON = 2000, 2026
GROUPS = {"WR": ({"WR"}, 40, "GT_WR", "wr-data.js"), "TE": ({"TE"}, 30, "GT_TE", "te-data.js")}

COLS = [
    "id", "season", "team", "teams", "g",
    "tgt", "rec", "recy", "rectd", "recepa", "rsucc", "recfd",
    "ay", "ayn", "deep", "deepc", "yac", "ycn", "rz", "mid", "locn",
    "car", "ryds", "rtd", "fum", "fuml", "ttgt", "tay",
]
NUM = ["tgt", "rec", "recy", "rectd", "recepa", "rsucc", "recfd", "ay", "ayn", "deep", "deepc", "yac", "ycn", "rz", "mid", "locn"]


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
    def __init__(self):
        for c in NUM:
            setattr(self, c, 0)
        self.games = set()
        self.tg = set()
        self.team_t = defaultdict(int)
        self.pname = ""


# 2003-2008 play-by-play leaves receiver_player_id empty on incompletions and
# interceptions; the play text still names the target ("... incomplete deep
# right to R.Moss", "... intended for R.Wayne INTERCEPTED ...").
DESC_RE = re.compile(r"(?:incomplete(?: [a-z]+){0,2} to|intended for) (?:\d+-)?([A-Z][A-Za-z'\-]{0,4}\.\s?[A-Z][A-Za-z'\-]+)")


def add_target(s, game, pos, comp, e, sc, ay, yl, loc, ry=0.0, td=False, fd=False, yac=None):
    s.tgt += 1
    if e is not None:
        s.recepa += e
    if sc is not None:
        s.rsucc += sc
    if ay is not None:
        s.ay += ay
        s.ayn += 1
        if ay >= 20:
            s.deep += 1
            if comp:
                s.deepc += 1
    if yl is not None and yl <= 20:
        s.rz += 1
    if loc in ("left", "middle", "right"):
        s.locn += 1
        if loc == "middle":
            s.mid += 1
    if comp:
        s.rec += 1
        s.recy += ry
        if td:
            s.rectd += 1
        if fd:
            s.recfd += 1
        if yac is not None:
            s.yac += yac
            s.ycn += 1
    s.games.add(game)
    s.tg.add((game, pos))
    s.team_t[pos] += 1


def process_season(path):
    acc = defaultdict(Acc)
    name_ids = defaultdict(lambda: defaultdict(int))
    pending = []
    rush = defaultdict(lambda: [0, 0.0, 0, set()])
    fumbles = defaultdict(lambda: [0, 0])
    team_tgt, team_ay, team_games = defaultdict(int), defaultdict(float), defaultdict(set)
    max_week = 0
    with gzip.open(path, "rt", encoding="utf-8", newline="") as fh:
        rd = csv.reader(fh)
        ix = {n: i for i, n in enumerate(next(rd))}
        keys = ["season_type", "week", "play_type", "two_point_attempt", "game_id", "posteam", "yardline_100",
                "qb_scramble", "qb_kneel", "qb_spike", "sack", "rusher_player_id",
                "receiver_player_id", "receiver_player_name", "complete_pass", "incomplete_pass", "interception",
                "pass_touchdown", "rush_touchdown", "rushing_yards", "receiving_yards", "yards_gained",
                "air_yards", "yards_after_catch", "pass_location", "epa", "success", "first_down_pass",
                "fumble", "fumble_lost", "fumbled_1_player_id", "desc", "receiver"]
        I = {k: ix.get(k, -1) for k in keys}

        def g(row, k):
            i = I[k]
            return row[i] if 0 <= i < len(row) else ""

        for row in rd:
            if g(row, "season_type") != "REG":
                continue
            wk = num(g(row, "week"))
            if wk is not None and wk > max_week:
                max_week = int(wk)
            pt = g(row, "play_type")
            if pt not in ("pass", "run") or flag(g(row, "two_point_attempt")):
                continue
            game, pos = g(row, "game_id"), g(row, "posteam")
            if not pos:
                continue
            team_games[pos].add(game)
            if flag(g(row, "fumble")):
                fid = g(row, "fumbled_1_player_id")
                if fid:
                    fumbles[fid][0] += 1
                    if flag(g(row, "fumble_lost")):
                        fumbles[fid][1] += 1
            if pt == "run":
                if flag(g(row, "qb_scramble")) or flag(g(row, "qb_kneel")):
                    continue
                rid = g(row, "rusher_player_id")
                if rid:
                    r = rush[rid]
                    r[0] += 1
                    r[1] += num(g(row, "rushing_yards")) or 0
                    if flag(g(row, "rush_touchdown")):
                        r[2] += 1
                    r[3].add(game)
                continue
            if flag(g(row, "sack")) or flag(g(row, "qb_spike")):
                continue
            comp = flag(g(row, "complete_pass"))
            if not (comp or flag(g(row, "incomplete_pass")) or flag(g(row, "interception"))):
                continue
            ay = num(g(row, "air_yards"))
            team_tgt[(game, pos)] += 1
            if ay is not None:
                team_ay[(game, pos)] += ay
            e, sc = num(g(row, "epa")), num(g(row, "success"))
            yl, loc = num(g(row, "yardline_100")), g(row, "pass_location")
            rid = g(row, "receiver_player_id")
            if not rid:
                if not comp:
                    nm = g(row, "receiver")
                    if not nm or nm == "NA":
                        m = DESC_RE.search(g(row, "desc"))
                        nm = m.group(1).replace(" ", "") if m else ""
                    if nm:
                        pending.append((game, pos, nm, e, sc, ay, yl, loc))
                continue
            s = acc[rid]
            s.pname = s.pname or g(row, "receiver_player_name")
            if comp:
                name_ids[(pos, g(row, "receiver_player_name"))][rid] += 1
                ry = num(g(row, "receiving_yards"))
                if ry is None:
                    ry = num(g(row, "yards_gained")) or 0
                add_target(s, game, pos, True, e, sc, ay, yl, loc, ry, flag(g(row, "pass_touchdown")),
                           flag(g(row, "first_down_pass")), num(g(row, "yards_after_catch")))
            else:
                add_target(s, game, pos, False, e, sc, ay, yl, loc)
    resolved = 0
    for game, pos, name, e, sc, ay, yl, loc in pending:
        ids = name_ids.get((pos, name))
        if ids:
            add_target(acc[max(ids, key=ids.get)], game, pos, False, e, sc, ay, yl, loc)
            resolved += 1
    tg = sorted(len(v) for v in team_games.values())
    return acc, rush, fumbles, team_tgt, team_ay, {"teamGames": tg[len(tg) // 2] if tg else 0, "weeks": max_week,
                                                    "_resolved": resolved, "_pending": len(pending)}


def load_players(path):
    out = {}
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
    return out


def main():
    raw_dir, app_dir = sys.argv[1], sys.argv[2]
    players = load_players(os.path.join(raw_dir, "players.csv"))
    out = {k: {"seasons": {}, "rows": [], "names": {}} for k in GROUPS}
    for season in range(FIRST_SEASON, LAST_SEASON + 1):
        path = os.path.join(raw_dir, "pbp", f"play_by_play_{season}.csv.gz")
        if not os.path.exists(path):
            continue
        t0 = time.time()
        acc, rush, fumbles, team_tgt, team_ay, info = process_season(path)
        info["fullGames"] = 16 if season <= 2020 else 17
        res, pend = info.pop("_resolved"), info.pop("_pending")
        if pend:
            print(f"  {season}: recovered {res} of {pend} unnamed targets from play text", flush=True)
        scale = min(1.0, info["teamGames"] / info["fullGames"])
        counts = {}
        for key, (posset, min_t, _, _) in GROUPS.items():
            out[key]["seasons"][season] = info
            need = max(12, round(min_t * scale))
            n = 0
            for pid, s in acc.items():
                if players.get(pid, {}).get("pos", "") not in posset or s.tgt < need:
                    continue
                order = sorted(s.team_t.items(), key=lambda kv: -kv[1])
                r = rush.get(pid, [0, 0.0, 0, set()])
                fm = fumbles.get(pid, [0, 0])
                vals = {"id": pid, "season": season, "team": order[0][0] if order else "",
                        "teams": "/".join(t for t, _ in order), "g": len(s.games | r[3]),
                        "car": r[0], "ryds": round(r[1], 1), "rtd": r[2], "fum": fm[0], "fuml": fm[1],
                        "ttgt": sum(team_tgt[k] for k in s.tg), "tay": round(sum(team_ay[k] for k in s.tg), 1)}
                for c in NUM:
                    v = getattr(s, c)
                    vals[c] = round(v, 2) if isinstance(v, float) else v
                out[key]["rows"].append([vals[c] for c in COLS])
                out[key]["names"].setdefault(pid, s.pname)
                n += 1
            counts[key] = n
        print(f"  {season}: WR {counts['WR']}, TE {counts['TE']}, {time.time() - t0:.1f}s", flush=True)
    for key, (_, _, var, fname) in GROUPS.items():
        people = {}
        for pid, short in out[key]["names"].items():
            p = players.get(pid, {})
            people[pid] = {"n": p.get("name") or re.sub(r"\.", ". ", short or pid), "a": p.get("alias", ""),
                           "c": p.get("college", ""), "d": p.get("draft", ""), "b": p.get("born", "")}
        data = {"built": time.strftime("%Y-%m-%d"), "source": "nflverse play-by-play (nflfastR), regular season",
                "seasons": out[key]["seasons"], "players": people, "cols": COLS, "rows": out[key]["rows"]}
        dest = os.path.join(app_dir, fname)
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(f"window.{var}=")
            json.dump(data, fh, separators=(",", ":"))
            fh.write(";\n")
        print(f"wrote {dest}: {len(out[key]['rows'])} {key} seasons, {len(people)} players, {os.path.getsize(dest) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
