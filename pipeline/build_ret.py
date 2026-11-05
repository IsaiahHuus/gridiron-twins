"""Build the kick / punt returner season table for Gridiron Twins.

Usage (run with -I so nothing in the raw folder is imported):
    python -I pipeline/build_ret.py <raw_dir> <out_js>

Regular season play-by-play only. A return = a kickoff or punt he fielded
and ran back (touchbacks and fair catches are not returns; fair catches are
counted separately). Fumbles count only on his own returns.
Output sets window.GT_RET = {...}.
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
MIN_KR, MIN_PR = 10, 8  # returns per full season to count as a real returner
COLS = ["id", "season", "team", "teams", "slot", "slots", "g",
        "kr", "kryds", "krtd", "kr40", "krlong", "krfum", "krfuml", "kfc",
        "pr", "pryds", "prtd", "pr20", "prlong", "prfum", "prfuml", "pfc"]


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
    with gzip.open(path, "rt", encoding="utf-8", newline="") as fh:
        rd = csv.reader(fh)
        ix = {n: i for i, n in enumerate(next(rd))}
        keys = ["season_type", "week", "game_id", "posteam", "play_type", "kickoff_returner_player_id",
                "punt_returner_player_id", "return_team", "return_yards", "return_touchdown", "touchback",
                "punt_fair_catch", "kickoff_fair_catch", "fumble", "fumble_lost", "fumbled_1_player_id"]
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
            if g(row, "posteam"):
                team_games[g(row, "posteam")].add(game)
            if pt not in ("kickoff", "punt"):
                continue
            pre = "kr" if pt == "kickoff" else "pr"
            rid = g(row, "kickoff_returner_player_id" if pt == "kickoff" else "punt_returner_player_id")
            if not rid:
                continue
            a = acc[rid]
            games[rid].add(game)
            tm = g(row, "return_team")
            if tm:
                teams[rid][tm] += 1
            if flag(g(row, "punt_fair_catch" if pt == "punt" else "kickoff_fair_catch")):
                a["pfc" if pt == "punt" else "kfc"] += 1
                continue
            if flag(g(row, "touchback")):
                continue
            y = num(g(row, "return_yards")) or 0
            a[pre] += 1
            a[pre + "yds"] += y
            a[pre + "td"] += flag(g(row, "return_touchdown"))
            if y >= (40 if pt == "kickoff" else 20):
                a["kr40" if pt == "kickoff" else "pr20"] += 1
            if y > a[pre + "long"]:
                a[pre + "long"] = y
            if flag(g(row, "fumble")) and g(row, "fumbled_1_player_id") == rid:
                a[pre + "fum"] += 1
                if flag(g(row, "fumble_lost")):
                    a[pre + "fuml"] += 1
    tg = sorted(len(v) for v in team_games.values())
    return acc, games, teams, {"teamGames": tg[len(tg) // 2] if tg else 0, "weeks": weeks}


def main():
    raw, out_js = sys.argv[1], sys.argv[2]
    players = load_players(os.path.join(raw, "players.csv"))
    seasons, table, ids = {}, [], set()
    for season in range(FIRST_SEASON, LAST_SEASON + 1):
        path = os.path.join(raw, "pbp", f"play_by_play_{season}.csv.gz")
        if not os.path.exists(path):
            continue
        t0 = time.time()
        acc, games, teams, info = process(path)
        info["fullGames"] = 16 if season <= 2020 else 17
        seasons[season] = info
        scale = min(1.0, info["teamGames"] / info["fullGames"])
        nkr, npr = max(4, round(MIN_KR * scale)), max(3, round(MIN_PR * scale))
        n = Counter()
        for pid, a in acc.items():
            kr, pr = a["kr"], a["pr"]
            if kr < nkr and pr < npr:
                continue
            slot = "KR/PR" if min(kr, pr) >= 0.3 * (kr + pr) else ("KR" if kr >= pr else "PR")
            order = [t for t, _ in teams[pid].most_common()]
            vals = {"id": pid, "season": season, "team": order[0] if order else "", "teams": "/".join(order),
                    "slot": slot, "slots": players.get(pid, {}).get("pos", ""), "g": len(games[pid])}
            for c in COLS:
                if c not in vals:
                    v = a.get(c, 0)
                    vals[c] = int(v) if float(v).is_integer() else round(v, 1)
            table.append([vals[c] for c in COLS])
            ids.add(pid)
            n[slot] += 1
        print(f"  {season}: KR {n['KR']}, PR {n['PR']}, both {n['KR/PR']}, {time.time() - t0:.1f}s", flush=True)
    people = {}
    for pid in ids:
        p = players.get(pid, {})
        people[pid] = {"n": p.get("name") or pid, "a": p.get("alias", ""), "c": p.get("college", ""),
                       "d": p.get("draft", ""), "b": p.get("born", ""), "p": p.get("pos", "")}
    data = {"built": time.strftime("%Y-%m-%d"), "source": "nflverse play-by-play (nflfastR), regular season",
            "seasons": seasons, "players": people, "cols": COLS, "rows": table}
    with open(out_js, "w", encoding="utf-8") as fh:
        fh.write("window.GT_RET=")
        json.dump(data, fh, separators=(",", ":"))
        fh.write(";\n")
    print(f"wrote {out_js}: {len(table)} returner seasons, {len(people)} players, {os.path.getsize(out_js) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
