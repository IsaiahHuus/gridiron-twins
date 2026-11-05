"""Build the head coach season table for Gridiron Twins.

Usage (run with -I so nothing in the raw folder is imported):
    python -I pipeline/build_hc.py <raw_dir> <out_js>

The coach for each team-game is the pbp home_coach / away_coach, so interim
coaches get credit only for their own games. Regular season builds the
record, points and team stats; playoff games are counted separately.

Per coach-season:
  results   W-L-T, points for/against, one-score games (<= 8), comeback wins
            (won after trailing by 10+)
  team      offense and defense EPA per play from scrimmage, giveaways and
            takeaways, penalties
  style     neutral pass rate (1st/2nd down, Q1-Q3, score within 10),
            4th-and-short go rate (4th & <= 2 outside own 20, not in the last
            5 minutes), 2-point tries vs extra points, plays per game,
            coach challenges (from the play text) and how many were overturned
Output sets window.GT_HC = {...}.
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
FIRST_SEASON, LAST_SEASON = 2000, 2026
TEAM_FIX = {"OAK": "LV", "SD": "LAC", "STL": "LA", "LAR": "LA", "JAC": "JAX", "ARZ": "ARI", "BLT": "BAL", "CLV": "CLE",
            "HST": "HOU", "SL": "LA"}
# Coach challenges read like "Philadelphia challenged the pass completion ruling..."; booth reviews say
# "Play Challenged by Review Assistant" and are skipped.
CHAL_RE = re.compile(r"(?:^|[.)]\s+)([A-Z][A-Za-z.\s']{2,30}?) challenged\b")
TEAM_NAMES = {"ARI": ["Arizona"], "ATL": ["Atlanta"], "BAL": ["Baltimore"], "BUF": ["Buffalo"], "CAR": ["Carolina"],
              "CHI": ["Chicago"], "CIN": ["Cincinnati"], "CLE": ["Cleveland"], "DAL": ["Dallas"], "DEN": ["Denver"],
              "DET": ["Detroit"], "GB": ["Green Bay"], "HOU": ["Houston"], "IND": ["Indianapolis"], "JAX": ["Jacksonville"],
              "KC": ["Kansas City"], "LV": ["Oakland", "Las Vegas"], "LAC": ["San Diego", "Chargers", "Los Angeles"],
              "LA": ["St. Louis", "Rams", "Los Angeles"], "MIA": ["Miami"], "MIN": ["Minnesota"], "NE": ["New England"],
              "NO": ["New Orleans"], "NYG": ["Giants"], "NYJ": ["Jets"], "PHI": ["Philadelphia"], "PIT": ["Pittsburgh"],
              "SF": ["San Francisco"], "SEA": ["Seattle"], "TB": ["Tampa Bay"], "TEN": ["Tennessee"], "WAS": ["Washington"]}


def challenger(phrase, teams):
    """Which of the two teams on the field matches the challenge phrase (most specific name wins)."""
    best, blen = None, 0
    for t in teams:
        for nm in TEAM_NAMES.get(t, []):
            if nm.lower() in phrase.lower() and len(nm) > blen:
                best, blen = t, len(nm)
    return best
COLS = ["id", "season", "team", "teams", "g", "gs", "w", "l", "t", "pf", "pa", "cg", "cw", "cl", "cbw",
        "op", "oepa", "dp", "depa", "np", "npass", "f4n", "f4go", "f4cv", "two", "xpa", "give", "take", "pen",
        "chal", "chalw", "pg", "pw", "pl"]
SUM = [c for c in COLS if c not in ("id", "season", "team", "teams")]


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
    return TEAM_FIX.get(code, code)


def process(path):
    tg = defaultdict(lambda: defaultdict(float))  # (game, team) -> stats
    meta = {}  # game -> (season_type, home, away, home_coach, away_coach, hs, as)
    minmargin = defaultdict(float)
    weeks = 0
    with gzip.open(path, "rt", encoding="utf-8", newline="") as fh:
        rd = csv.reader(fh)
        ix = {n: i for i, n in enumerate(next(rd))}
        keys = ["season_type", "week", "game_id", "home_team", "away_team", "home_coach", "away_coach", "home_score",
                "away_score", "posteam", "defteam", "play_type", "two_point_attempt", "qb_dropback", "qb_kneel",
                "qb_spike", "down", "ydstogo", "yardline_100", "qtr", "game_seconds_remaining", "score_differential",
                "epa", "interception", "fumble_lost", "penalty", "penalty_team", "fourth_down_converted", "desc",
                "replay_or_challenge_result"]
        I = {k: ix.get(k, -1) for k in keys}

        def g(row, k):
            i = I[k]
            v = row[i] if 0 <= i < len(row) else ""
            return "" if v == "NA" else v

        for row in rd:
            st = g(row, "season_type")
            game = g(row, "game_id")
            if game not in meta:
                meta[game] = (st, g(row, "home_team"), g(row, "away_team"), g(row, "home_coach"), g(row, "away_coach"),
                              num(g(row, "home_score")), num(g(row, "away_score")))
            if st != "REG":
                continue
            weeks = max(weeks, int(num(g(row, "week")) or 0))
            pos, dfn, pt = g(row, "posteam"), g(row, "defteam"), g(row, "play_type")
            sd = num(g(row, "score_differential"))
            if pos and sd is not None:
                minmargin[(game, pos)] = min(minmargin[(game, pos)], sd)
                if dfn:
                    minmargin[(game, dfn)] = min(minmargin[(game, dfn)], -sd)
            if flag(g(row, "penalty")) and g(row, "penalty_team"):
                tg[(game, g(row, "penalty_team"))]["pen"] += 1
            desc = g(row, "desc")
            if "challenged" in desc and "Review Assistant" not in desc:
                m = CHAL_RE.search(desc)
                ct = challenger(m.group(1), [t for t in (pos, dfn) if t]) if m else None
                if ct:
                    tg[(game, ct)]["chal"] += 1
                    if g(row, "replay_or_challenge_result").lower() == "reversed":
                        tg[(game, ct)]["chalw"] += 1
            if not pos:
                continue
            if pt == "extra_point":
                tg[(game, pos)]["xpa"] += 1
                continue
            if flag(g(row, "two_point_attempt")):
                tg[(game, pos)]["two"] += 1
                continue
            down = int(num(g(row, "down")) or 0)
            if down == 4 and pt in ("pass", "run", "punt", "field_goal"):
                yt, yl, gsr = num(g(row, "ydstogo")), num(g(row, "yardline_100")), num(g(row, "game_seconds_remaining"))
                if yt is not None and yt <= 2 and yl is not None and yl <= 80 and (gsr or 0) > 300:
                    s = tg[(game, pos)]
                    s["f4n"] += 1
                    if pt in ("pass", "run") and not flag(g(row, "qb_kneel")):
                        s["f4go"] += 1
                        s["f4cv"] += flag(g(row, "fourth_down_converted"))
            if pt not in ("pass", "run") or flag(g(row, "qb_kneel")) or flag(g(row, "qb_spike")):
                continue
            e = num(g(row, "epa"))
            so, sdf = tg[(game, pos)], tg[(game, dfn)]
            so["op"] += 1
            sdf["dp"] += 1
            if e is not None:
                so["oepa"] += e
                sdf["depa"] += e
            if flag(g(row, "interception")) or flag(g(row, "fumble_lost")):
                so["give"] += 1
                sdf["take"] += 1
            if down in (1, 2) and (num(g(row, "qtr")) or 5) <= 3 and sd is not None and abs(sd) <= 10:
                so["np"] += 1
                so["npass"] += flag(g(row, "qb_dropback"))
    return tg, meta, minmargin, weeks


def main():
    raw, out_js = sys.argv[1], sys.argv[2]
    seasons, table = {}, []
    for season in range(FIRST_SEASON, LAST_SEASON + 1):
        path = os.path.join(raw, "pbp", f"play_by_play_{season}.csv.gz")
        if not os.path.exists(path):
            continue
        t0 = time.time()
        tg, meta, minmargin, weeks = process(path)
        acc = defaultdict(lambda: defaultdict(float))
        teams = defaultdict(Counter)
        tgames = Counter()
        for game, (st, h, a, hc, ac, hs, as_) in meta.items():
            for tm, coach, mine, theirs in ((h, hc, hs, as_), (a, ac, as_, hs)):
                if not coach or mine is None or theirs is None:
                    continue
                c = acc[coach]
                if st != "REG":
                    c["pg"] += 1
                    c["pw" if mine > theirs else "pl"] += 1 if mine != theirs else 0
                    continue
                tgames[tm] += 1
                teams[coach][tm] += 1
                c["g"] += 1
                c["gs"] += 1
                res = "w" if mine > theirs else "l" if mine < theirs else "t"
                c[res] += 1
                c["pf"] += mine
                c["pa"] += theirs
                if abs(mine - theirs) <= 8:
                    c["cg"] += 1
                    if res == "w":
                        c["cw"] += 1
                    elif res == "l":
                        c["cl"] += 1
                if res == "w" and minmargin.get((game, tm), 0) <= -10:
                    c["cbw"] += 1
                for k, v in tg.get((game, tm), {}).items():
                    c[k] += v
        tgl = sorted(tgames.values())
        info = {"teamGames": tgl[len(tgl) // 2] if tgl else 0, "fullGames": 16 if season <= 2020 else 17, "weeks": weeks}
        seasons[season] = info
        need = max(2, round(4 * min(1.0, info["teamGames"] / info["fullGames"])))
        n = 0
        for coach, c in acc.items():
            if c["g"] < need:
                continue
            order = [t for t, _ in teams[coach].most_common()]
            vals = {"id": coach, "season": season, "team": order[0] if order else "", "teams": "/".join(order)}
            for k in SUM:
                v = c.get(k, 0)
                vals[k] = int(v) if float(v).is_integer() else round(v, 2)
            table.append([vals[c2] for c2 in COLS])
            n += 1
        print(f"  {season}: {n} head coaches, {time.time() - t0:.1f}s", flush=True)
    people = {r[0]: {"n": r[0], "a": "", "c": "", "d": "", "b": ""} for r in table}
    data = {"built": time.strftime("%Y-%m-%d"), "source": "nflverse play-by-play (nflfastR); coach = home_coach / away_coach",
            "seasons": seasons, "players": people, "cols": COLS, "rows": table}
    with open(out_js, "w", encoding="utf-8") as fh:
        fh.write("window.GT_HC=")
        json.dump(data, fh, separators=(",", ":"))
        fh.write(";\n")
    print(f"wrote {out_js}: {len(table)} coach seasons, {len(people)} coaches, {os.path.getsize(out_js) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
