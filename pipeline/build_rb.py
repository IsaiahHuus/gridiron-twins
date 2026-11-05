"""Build the RB season table for Gridiron Twins from nflverse play-by-play.

Usage (run with -I so nothing in the raw folder is imported):
    python -I pipeline/build_rb.py <raw_dir> <out_js>

Same inputs as build_qb.py. Regular season only; two-point tries, kneels
and QB scrambles are skipped. Output sets window.GT_RB = {...} with raw
counts per RB season; the page derives rates, era grades and twin scores.
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
RB_POS = {"RB", "FB", "HB"}
MIN_TOUCHES = 50  # per full season
DESC_RE = re.compile(r"(?:incomplete(?: [a-z]+){0,2} to|intended for) (?:\d+-)?([A-Z][A-Za-z'\-]{0,4}\.\s?[A-Z][A-Za-z'\-]+)")

COLS = [
    "id", "season", "team", "teams", "g",
    "car", "ryds", "rtd", "repa", "rsucc", "rfd", "r10", "r20", "stuff",
    "tgt", "rec", "recy", "rectd", "recepa", "recfd", "ay", "ayn", "yac", "ycn",
    "fum", "fuml", "tcar", "ttgt",
]
NUM = [c for c in COLS if c not in ("id", "season", "team", "teams", "g", "tcar", "ttgt", "fum", "fuml")]


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


def process_season(path, season):
    t0 = time.time()
    acc = defaultdict(Acc)
    fumbles = defaultdict(lambda: [0, 0])
    team_car = defaultdict(int)
    team_tgt = defaultdict(int)
    team_games = defaultdict(set)
    max_week = 0
    with gzip.open(path, "rt", encoding="utf-8", newline="") as fh:
        rd = csv.reader(fh)
        header = next(rd)
        ix = {n: i for i, n in enumerate(header)}
        keys = ["season_type", "week", "play_type", "two_point_attempt", "game_id", "posteam",
                "qb_scramble", "qb_kneel", "qb_spike", "sack",
                "rusher_player_id", "rusher_player_name", "receiver_player_id", "receiver_player_name",
                "complete_pass", "incomplete_pass", "interception", "pass_touchdown", "rush_touchdown",
                "rushing_yards", "receiving_yards", "yards_gained", "air_yards", "yards_after_catch",
                "epa", "success", "first_down_rush", "first_down_pass",
                "fumble", "fumble_lost", "fumbled_1_player_id", "desc", "receiver"]
        I = {k: ix.get(k, -1) for k in keys}
        name_ids = defaultdict(lambda: defaultdict(int))
        pending = []

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
            if pt not in ("pass", "run"):
                continue
            if flag(g(row, "two_point_attempt")):
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
            e = num(g(row, "epa"))
            if pt == "run":
                if flag(g(row, "qb_scramble")) or flag(g(row, "qb_kneel")):
                    continue
                team_car[(game, pos)] += 1
                rid = g(row, "rusher_player_id")
                if not rid:
                    continue
                s = acc[rid]
                s.pname = s.pname or g(row, "rusher_player_name")
                y = num(g(row, "rushing_yards"))
                if y is None:
                    y = num(g(row, "yards_gained")) or 0
                s.car += 1
                s.ryds += y
                if flag(g(row, "rush_touchdown")):
                    s.rtd += 1
                if e is not None:
                    s.repa += e
                sc = num(g(row, "success"))
                if sc is not None:
                    s.rsucc += sc
                if flag(g(row, "first_down_rush")):
                    s.rfd += 1
                if y >= 10:
                    s.r10 += 1
                if y >= 20:
                    s.r20 += 1
                if y <= 0:
                    s.stuff += 1
            else:
                if flag(g(row, "sack")) or flag(g(row, "qb_spike")):
                    continue
                comp = flag(g(row, "complete_pass"))
                if not (comp or flag(g(row, "incomplete_pass")) or flag(g(row, "interception"))):
                    continue
                team_tgt[(game, pos)] += 1
                rid = g(row, "receiver_player_id")
                if not rid:
                    # 2003-2008 data leaves the target off incompletions; read it from the play text
                    if not comp:
                        nm = g(row, "receiver")
                        if not nm or nm == "NA":
                            m = DESC_RE.search(g(row, "desc"))
                            nm = m.group(1).replace(" ", "") if m else ""
                        if nm:
                            pending.append((game, pos, nm, e, num(g(row, "air_yards"))))
                    continue
                s = acc[rid]
                s.pname = s.pname or g(row, "receiver_player_name")
                if comp:
                    name_ids[(pos, g(row, "receiver_player_name"))][rid] += 1
                s.tgt += 1
                if e is not None:
                    s.recepa += e
                ay = num(g(row, "air_yards"))
                if ay is not None:
                    s.ay += ay
                    s.ayn += 1
                if comp:
                    s.rec += 1
                    ry = num(g(row, "receiving_yards"))
                    if ry is None:
                        ry = num(g(row, "yards_gained")) or 0
                    s.recy += ry
                    if flag(g(row, "pass_touchdown")):
                        s.rectd += 1
                    if flag(g(row, "first_down_pass")):
                        s.recfd += 1
                    yac = num(g(row, "yards_after_catch"))
                    if yac is not None:
                        s.yac += yac
                        s.ycn += 1
            s.games.add(game)
            s.tg.add((game, pos))
            s.team_t[pos] += 1

    for game, pos, name, e, ay in pending:
        ids = name_ids.get((pos, name))
        if not ids:
            continue
        s = acc[max(ids, key=ids.get)]
        s.tgt += 1
        if e is not None:
            s.recepa += e
        if ay is not None:
            s.ay += ay
            s.ayn += 1
        s.games.add(game)
        s.tg.add((game, pos))
        s.team_t[pos] += 1

    rows = []
    for pid, s in acc.items():
        order = sorted(s.team_t.items(), key=lambda kv: -kv[1])
        fm = fumbles.get(pid, [0, 0])
        rows.append((pid, s, order[0][0] if order else "", "/".join(t for t, _ in order), fm,
                     sum(team_car[k] for k in s.tg), sum(team_tgt[k] for k in s.tg)))
    tg = sorted(len(v) for v in team_games.values())
    info = {"teamGames": tg[len(tg) // 2] if tg else 0, "fullGames": 16 if season <= 2020 else 17, "weeks": max_week}
    print(f"  {season}: {len(rows)} ball carriers/targets, {time.time() - t0:.1f}s", flush=True)
    return rows, info


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
    raw_dir, out_js = sys.argv[1], sys.argv[2]
    players = load_players(os.path.join(raw_dir, "players.csv"))
    seasons, table, names = {}, [], {}
    for season in range(FIRST_SEASON, LAST_SEASON + 1):
        path = os.path.join(raw_dir, "pbp", f"play_by_play_{season}.csv.gz")
        if not os.path.exists(path):
            continue
        rows, info = process_season(path, season)
        seasons[season] = info
        # Real contributors only: 50+ touches (carries + catches), scaled for a season in progress
        scale = min(1.0, info["teamGames"] / info["fullGames"]) if info["fullGames"] else 1.0
        min_touches = max(20, round(MIN_TOUCHES * scale))
        for pid, s, team, teams, fm, tcar, ttgt in rows:
            if players.get(pid, {}).get("pos", "") not in RB_POS or s.car + s.rec < min_touches:
                continue
            names.setdefault(pid, s.pname)
            vals = {"id": pid, "season": season, "team": team, "teams": teams, "g": len(s.games),
                    "fum": fm[0], "fuml": fm[1], "tcar": tcar, "ttgt": ttgt}
            for c in NUM:
                v = getattr(s, c)
                vals[c] = round(v, 2) if isinstance(v, float) else v
            table.append([vals[c] for c in COLS])
    people = {}
    for pid, short in names.items():
        p = players.get(pid, {})
        people[pid] = {"n": p.get("name") or re.sub(r"\.", ". ", short or pid), "a": p.get("alias", ""),
                       "c": p.get("college", ""), "d": p.get("draft", ""), "b": p.get("born", "")}
    data = {"built": time.strftime("%Y-%m-%d"), "source": "nflverse play-by-play (nflfastR), regular season",
            "seasons": seasons, "players": people, "cols": COLS, "rows": table}
    with open(out_js, "w", encoding="utf-8") as fh:
        fh.write("window.GT_RB=")
        json.dump(data, fh, separators=(",", ":"))
        fh.write(";\n")
    print(f"wrote {out_js}: {len(table)} RB seasons, {len(people)} RBs, {os.path.getsize(out_js) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
