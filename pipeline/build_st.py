"""Build the kicker / punter season table for Gridiron Twins.

Usage (run with -I so nothing in the raw folder is imported):
    python -I pipeline/build_st.py <raw_dir> <out_js>

Regular season play-by-play only. Per player-season:
  kicking   field goals by distance, makes vs the model's make probability
            (fg_prob), extra points, kickoffs (touchbacks, distance, returns)
  punting   gross and net yards, inside the 20, touchbacks, fair catches,
            returns allowed, blocks, long
  misc      his own coverage tackles, passes and runs on fakes
A season is a kicker's or a punter's by which he did more of.
Output sets window.GT_KP = {...}.
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
MIN_KICKS = 15  # FG + XP attempts (kickers) or punts (punters) per full season
COLS = ["id", "season", "team", "teams", "slot", "slots", "g",
        "fga", "fgm", "fgx", "fgxn", "fgxm", "fga1", "fgm1", "fga3", "fgm3", "fga4", "fgm4", "fga5", "fgm5",
        "fglong", "fgblk", "xpa", "xpm", "ko", "kotb", "kodist", "kon", "koret", "korn",
        "punts", "pgross", "pn", "pret", "ptb", "pi20", "pfc", "pblk", "plong",
        "stk", "paa", "pay", "patd", "rua", "ruy", "rutd"]
SUM_KEYS = [c for c in COLS if c not in ("id", "season", "team", "teams", "slot", "slots", "g", "fglong", "plong")]


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


def process(path):
    acc = defaultdict(lambda: defaultdict(float))
    games = defaultdict(set)
    teams = defaultdict(Counter)
    team_games = defaultdict(set)
    weeks = 0
    tackles = defaultdict(int)
    passing = defaultdict(lambda: [0, 0.0, 0])
    rushing = defaultdict(lambda: [0, 0.0, 0])
    with gzip.open(path, "rt", encoding="utf-8", newline="") as fh:
        rd = csv.reader(fh)
        ix = {n: i for i, n in enumerate(next(rd))}
        keys = ["season_type", "week", "game_id", "posteam", "play_type", "two_point_attempt", "kicker_player_id",
                "punter_player_id", "kick_distance", "field_goal_result", "extra_point_result", "fg_prob",
                "touchback", "return_yards", "punt_inside_twenty", "punt_fair_catch", "punt_blocked",
                "passer_player_id", "rusher_player_id", "passing_yards", "rushing_yards", "pass_touchdown",
                "rush_touchdown", "complete_pass", "incomplete_pass", "interception", "qb_scramble",
                "solo_tackle_1_player_id", "solo_tackle_2_player_id", "assist_tackle_1_player_id",
                "assist_tackle_2_player_id", "tackle_with_assist_1_player_id", "tackle_with_assist_2_player_id"]
        I = {k: ix.get(k, -1) for k in keys}

        def g(row, k):
            i = I[k]
            v = row[i] if 0 <= i < len(row) else ""
            return "" if v == "NA" else v

        for row in rd:
            if g(row, "season_type") != "REG":
                continue
            game = g(row, "game_id")
            weeks = max(weeks, int(num(g(row, "week")) or 0))
            pt = g(row, "play_type")
            pos = g(row, "posteam")
            if pos:
                team_games[pos].add(game)
            if pt in ("kickoff", "punt"):
                for k in ("solo_tackle_1_player_id", "solo_tackle_2_player_id", "assist_tackle_1_player_id",
                          "assist_tackle_2_player_id", "tackle_with_assist_1_player_id", "tackle_with_assist_2_player_id"):
                    p = g(row, k)
                    if p:
                        tackles[p] += 1
            if pt == "field_goal":
                k = g(row, "kicker_player_id")
                if not k:
                    continue
                a = acc[k]
                games[k].add(game)
                if pos:
                    teams[k][pos] += 1
                d = num(g(row, "kick_distance")) or 0
                made = g(row, "field_goal_result") == "made"
                a["fga"] += 1
                a["fgm"] += made
                b = "1" if d < 30 else "3" if d < 40 else "4" if d < 50 else "5"
                a["fga" + b] += 1
                a["fgm" + b] += made
                if made and d > a["fglong"]:
                    a["fglong"] = d
                if g(row, "field_goal_result") == "blocked":
                    a["fgblk"] += 1
                p = num(g(row, "fg_prob"))
                if p is not None:
                    a["fgx"] += p
                    a["fgxn"] += 1
                    a["fgxm"] += made
            elif pt == "extra_point":
                k = g(row, "kicker_player_id")
                if not k:
                    continue
                games[k].add(game)
                if pos:
                    teams[k][pos] += 1
                acc[k]["xpa"] += 1
                acc[k]["xpm"] += g(row, "extra_point_result") == "good"
            elif pt == "kickoff":
                k = g(row, "kicker_player_id")
                if not k:
                    continue
                a = acc[k]
                games[k].add(game)
                a["ko"] += 1
                if flag(g(row, "touchback")):
                    a["kotb"] += 1
                d = num(g(row, "kick_distance"))
                if d is not None:
                    a["kodist"] += d
                    a["kon"] += 1
                r = num(g(row, "return_yards"))
                if r is not None and not flag(g(row, "touchback")):
                    a["koret"] += r
                    a["korn"] += 1
            elif pt == "punt":
                p = g(row, "punter_player_id")
                if not p:
                    continue
                a = acc[p]
                games[p].add(game)
                if pos:
                    teams[p][pos] += 1
                a["punts"] += 1
                d = num(g(row, "kick_distance"))
                if d is not None:
                    a["pgross"] += d
                    a["pn"] += 1
                    if d > a["plong"]:
                        a["plong"] = d
                a["pret"] += num(g(row, "return_yards")) or 0
                a["ptb"] += flag(g(row, "touchback"))
                a["pi20"] += flag(g(row, "punt_inside_twenty"))
                a["pfc"] += flag(g(row, "punt_fair_catch"))
                a["pblk"] += flag(g(row, "punt_blocked"))
            elif pt == "pass" and not flag(g(row, "two_point_attempt")):
                p = g(row, "passer_player_id")
                if p and (flag(g(row, "complete_pass")) or flag(g(row, "incomplete_pass")) or flag(g(row, "interception"))):
                    v = passing[p]
                    v[0] += 1
                    v[1] += num(g(row, "passing_yards")) or 0
                    v[2] += flag(g(row, "pass_touchdown"))
            elif pt == "run" and not flag(g(row, "two_point_attempt")):
                p = g(row, "rusher_player_id")
                if p:
                    v = rushing[p]
                    v[0] += 1
                    v[1] += num(g(row, "rushing_yards")) or 0
                    v[2] += flag(g(row, "rush_touchdown"))
    tg = sorted(len(v) for v in team_games.values())
    return acc, games, teams, tackles, passing, rushing, {"teamGames": tg[len(tg) // 2] if tg else 0, "weeks": weeks}


def main():
    raw, out_js = sys.argv[1], sys.argv[2]
    players = load_players(os.path.join(raw, "players.csv"))
    seasons, table, ids = {}, [], set()
    for season in range(FIRST_SEASON, LAST_SEASON + 1):
        path = os.path.join(raw, "pbp", f"play_by_play_{season}.csv.gz")
        if not os.path.exists(path):
            continue
        t0 = time.time()
        acc, games, teams, tackles, passing, rushing, info = process(path)
        info["fullGames"] = 16 if season <= 2020 else 17
        seasons[season] = info
        need = max(6, round(MIN_KICKS * min(1.0, info["teamGames"] / info["fullGames"])))
        n = Counter()
        for pid, a in acc.items():
            kicks, punts = a["fga"] + a["xpa"], a["punts"]
            slot = "P" if punts > kicks else "K"
            if (punts if slot == "P" else kicks) < need:
                continue
            pos = players.get(pid, {}).get("pos", "")
            if pos and pos not in ("K", "P", "PK"):
                continue
            order = [t for t, _ in teams[pid].most_common()]
            vals = {"id": pid, "season": season, "team": order[0] if order else "", "teams": "/".join(order),
                    "slot": slot, "slots": slot, "g": len(games[pid]), "stk": tackles.get(pid, 0),
                    "fglong": int(a["fglong"]), "plong": int(a["plong"])}
            pa, ru = passing.get(pid, [0, 0, 0]), rushing.get(pid, [0, 0, 0])
            vals.update({"paa": pa[0], "pay": int(pa[1]), "patd": pa[2], "rua": ru[0], "ruy": int(ru[1]), "rutd": ru[2]})
            for k in SUM_KEYS:
                if k not in vals:
                    v = a.get(k, 0)
                    vals[k] = round(v, 2) if isinstance(v, float) and v != int(v) else int(v)
            table.append([vals[c] for c in COLS])
            ids.add(pid)
            n[slot] += 1
        print(f"  {season}: {n['K']} kickers, {n['P']} punters, {time.time() - t0:.1f}s", flush=True)
    people = {}
    for pid in ids:
        p = players.get(pid, {})
        people[pid] = {"n": p.get("name") or pid, "a": p.get("alias", ""), "c": p.get("college", ""),
                       "d": p.get("draft", ""), "b": p.get("born", "")}
    data = {"built": time.strftime("%Y-%m-%d"), "source": "nflverse play-by-play (nflfastR), regular season",
            "seasons": seasons, "players": people, "cols": COLS, "rows": table}
    with open(out_js, "w", encoding="utf-8") as fh:
        fh.write("window.GT_KP=")
        json.dump(data, fh, separators=(",", ":"))
        fh.write(";\n")
    print(f"wrote {out_js}: {len(table)} K/P seasons, {len(people)} players, {os.path.getsize(out_js) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
