"""Full Time: predicts the score of every Premier League game in the current and next gameweek.

Usage: python3 -I predict.py <out.json> [previous.json]
Downloads the FPL and FotMob data it needs. Predictions for games that have already kicked off
are copied from previous.json unchanged, so the track record always compares pre-match picks.
"""
import json
import math
import sys
import time
import urllib.request
from datetime import datetime, timezone

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
FPL = "https://fantasy.premierleague.com/api/"
FOTMOB = "https://www.fotmob.com/api/data/"
PRIOR_GAMES = 12     # weight of last season's per-game rates, in games (backtested: 12 beat 4 and 8)
XG_WEIGHT = 0.75     # this season: mix of expected goals and actual goals
HOME, AWAY = 1.10, 0.92
RHO = -0.06          # Dixon-Coles correction for 0-0, 1-0, 0-1 and 1-1
MAX_GOALS = 8
ALIASES = {"AFC Bournemouth": "Bournemouth", "Brighton & Hove Albion": "Brighton", "Leeds United": "Leeds",
           "Manchester City": "Man City", "Manchester United": "Man Utd", "Newcastle United": "Newcastle",
           "Nottingham Forest": "Nott'm Forest", "Tottenham Hotspur": "Spurs"}


def get(url, tries=3):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception:
            if attempt == tries - 1:
                raise
            time.sleep(5 * (attempt + 1))


def xg_table(season=None):
    url = FOTMOB + "leagues?id=47" + (f"&season={season.replace('/', '%2F')}" if season else "")
    data = get(url)
    t = data["table"][0]["data"]
    return t["selectedSeason"], t["table"]["xg"], data


def poisson(k, lam):
    return math.exp(-lam) * lam ** k / math.factorial(k)


def score_matrix(lh, la):
    m = [[poisson(i, lh) * poisson(j, la) for j in range(MAX_GOALS + 1)] for i in range(MAX_GOALS + 1)]
    m[0][0] *= 1 - lh * la * RHO
    m[0][1] *= 1 + lh * RHO
    m[1][0] *= 1 + la * RHO
    m[1][1] *= 1 - RHO
    total = sum(sum(r) for r in m)
    return [[v / total for v in r] for r in m]


def main(out_path, prev_path=None):
    boot = get(FPL + "bootstrap-static/")
    fixtures = get(FPL + "fixtures/")
    season, cur, league = xg_table()
    seasons = league["allAvailableSeasons"]
    last_season = seasons[1] if len(seasons) > 1 else None
    _, last, _ = xg_table(last_season) if last_season else (None, [], None)

    teams = {t["id"]: t for t in boot["teams"]}
    by_name = {t["name"]: t["id"] for t in boot["teams"]}

    def fpl_id(name):
        return by_name.get(ALIASES.get(name, name)) or by_name.get(name)

    # Per-game rates this season (expected and actual) and last season.
    cur_rows, last_rows = {}, {}
    for r in cur:
        tid = fpl_id(r["name"])
        if tid:
            gf, ga = (int(x) for x in r["scoresStr"].split("-"))
            n = r["played"] or 0
            cur_rows[tid] = {"n": n, "xg": r["xg"], "xga": r["xgConceded"], "gf": gf, "ga": ga}
    for r in last:
        tid = fpl_id(r["name"])
        if tid:
            last_rows[tid] = {"xg": r["xg"] / r["played"], "xga": r["xgConceded"] / r["played"]}

    # Promoted clubs have no top-flight record: start them at the average of last season's bottom three.
    if last:
        bottom = sorted(last, key=lambda r: r["pts"])[:3]
        promoted_prior = {"xg": sum(r["xg"] / r["played"] for r in bottom) / 3,
                          "xga": sum(r["xgConceded"] / r["played"] for r in bottom) / 3}
    else:
        promoted_prior = {"xg": 1.1, "xga": 1.7}
    league_avg = sum(v["xg"] for v in last_rows.values()) / len(last_rows) if last_rows else 1.4

    rating = {}
    for tid in teams:
        c = cur_rows.get(tid, {"n": 0, "xg": 0, "xga": 0, "gf": 0, "ga": 0})
        prior = last_rows.get(tid, promoted_prior)
        # Regress last season a fifth of the way to average, since squads change over the summer.
        pf = 0.8 * prior["xg"] + 0.2 * league_avg
        pa = 0.8 * prior["xga"] + 0.2 * league_avg
        n = c["n"]
        f_now = (XG_WEIGHT * c["xg"] + (1 - XG_WEIGHT) * c["gf"]) if n else 0
        a_now = (XG_WEIGHT * c["xga"] + (1 - XG_WEIGHT) * c["ga"]) if n else 0
        rating[tid] = {"for": (f_now + pf * PRIOR_GAMES) / (n + PRIOR_GAMES),
                       "against": (a_now + pa * PRIOR_GAMES) / (n + PRIOR_GAMES)}
    avg = sum(r["for"] for r in rating.values()) / len(rating)

    # Missing attackers: each unavailable player takes away part of his share of the team's
    # expected goal involvement (a replacement makes up the rest).
    contrib, absent = {}, {}
    for p in boot["elements"]:
        xgi = float(p["expected_goals"] or 0) + 0.5 * float(p["expected_assists"] or 0)
        contrib[p["team"]] = contrib.get(p["team"], 0) + xgi
    for p in boot["elements"]:
        chance = p["chance_of_playing_next_round"]
        missing = 1.0 if p["status"] in ("i", "s", "n") and not chance else (1 - chance / 100 if chance is not None and p["status"] != "u" else 0)
        xgi = float(p["expected_goals"] or 0) + 0.5 * float(p["expected_assists"] or 0)
        if missing > 0 and contrib.get(p["team"]) and xgi / contrib[p["team"]] >= 0.05:
            absent.setdefault(p["team"], []).append((p["web_name"], missing, xgi / contrib[p["team"]], p["news"]))

    def attack_factor(tid):
        loss = sum(m * share for _, m, share, _ in absent.get(tid, []))
        return max(0.75, 1 - 0.6 * loss)

    events = boot["events"]
    upcoming = [ev["id"] for ev in events if not ev["finished"]][:2]
    prev = {}
    if prev_path:
        try:
            with open(prev_path) as f:
                prev = {g["id"]: g for g in json.load(f).get("games", [])}
        except Exception:
            prev = {}

    now = datetime.now(timezone.utc)
    games = []
    for f in fixtures:
        if f["event"] not in upcoming:
            continue
        h, a = f["team_h"], f["team_a"]
        started = f["started"] or (f["kickoff_time"] and datetime.fromisoformat(f["kickoff_time"].replace("Z", "+00:00")) <= now)
        base = {"id": f["id"], "gw": f["event"], "kickoff": f["kickoff_time"],
                "home": teams[h]["name"], "away": teams[a]["name"],
                "home_short": teams[h]["short_name"], "away_short": teams[a]["short_name"],
                "finished": bool(f["finished_provisional"]),
                "result": [f["team_h_score"], f["team_a_score"]] if f["team_h_score"] is not None else None}
        if started and f["id"] in prev and prev[f["id"]].get("pred"):
            games.append({**base, "pred": prev[f["id"]]["pred"]})
            continue
        if started:
            # Never predict a game after kick-off: without a pre-match prediction it stays blank.
            games.append({**base, "pred": None})
            continue
        lh = avg * (rating[h]["for"] / avg) * (rating[a]["against"] / avg) * HOME * attack_factor(h)
        la = avg * (rating[a]["for"] / avg) * (rating[h]["against"] / avg) * AWAY * attack_factor(a)
        m = score_matrix(lh, la)
        cells = [(m[i][j], i, j) for i in range(MAX_GOALS + 1) for j in range(MAX_GOALS + 1)]
        cells.sort(reverse=True)
        ph = sum(m[i][j] for i in range(MAX_GOALS + 1) for j in range(MAX_GOALS + 1) if i > j)
        pd = sum(m[i][i] for i in range(MAX_GOALS + 1))
        pa = 1 - ph - pd
        # Most likely score within the most likely result, so the score and the result agree.
        outcome = max((ph, "H"), (pd, "D"), (pa, "A"))[1]
        pick = next(c for c in cells if (c[1] > c[2] and outcome == "H") or (c[1] == c[2] and outcome == "D") or (c[1] < c[2] and outcome == "A"))
        btts = sum(m[i][j] for i in range(1, MAX_GOALS + 1) for j in range(1, MAX_GOALS + 1))
        over = sum(m[i][j] for i in range(MAX_GOALS + 1) for j in range(MAX_GOALS + 1) if i + j >= 3)
        games.append({**base, "pred": {
            "xg": [round(lh, 2), round(la, 2)],
            "score": [pick[1], pick[2]],
            "probs": {"home": round(ph, 3), "draw": round(pd, 3), "away": round(pa, 3)},
            "top_scores": [{"score": [i, j], "p": round(p, 3)} for p, i, j in cells[:4]],
            "btts": round(btts, 3), "over25": round(over, 3),
            "clean_sheet": [round(sum(m[i][0] for i in range(MAX_GOALS + 1)), 3), round(sum(m[0][j] for j in range(MAX_GOALS + 1)), 3)],
            "absences": {
                "home": [{"name": n, "news": nw} for n, mi, s, nw in absent.get(h, []) if mi >= 0.5],
                "away": [{"name": n, "news": nw} for n, mi, s, nw in absent.get(a, []) if mi >= 0.5]},
            "made": now.strftime("%Y-%m-%dT%H:%M:%SZ")}})

    # Track record: every finished game this season that had a pre-match prediction.
    history = {}
    if prev_path:
        try:
            with open(prev_path) as f:
                history = {int(k): v for k, v in json.load(f).get("history", {}).items()}
        except Exception:
            history = {}
    for g in games:
        if g["finished"] and g["result"] and g.get("pred"):
            hs, as_ = g["result"]
            ps = g["pred"]["score"]
            res = "H" if hs > as_ else "A" if hs < as_ else "D"
            pres = "H" if ps[0] > ps[1] else "A" if ps[0] < ps[1] else "D"
            history[g["id"]] = {"gw": g["gw"], "match": f"{g['home_short']} v {g['away_short']}", "result": g["result"],
                                "pred": ps, "right_result": res == pres, "exact": [hs, as_] == ps}

    backtest = None
    if prev_path:
        try:
            with open(prev_path) as f:
                backtest = json.load(f).get("backtest")
        except Exception:
            backtest = None

    out = {
        "backtest": backtest,
        "season": season,
        "updatedAt": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ratings": {teams[t]["short_name"]: {"attack": round(r["for"] / avg, 2), "defence": round(r["against"] / avg, 2)} for t, r in rating.items()},
        "games": sorted(games, key=lambda g: (g["kickoff"] or "", g["id"])),
        "history": history,
    }
    with open(out_path, "w") as f:
        json.dump(out, f, ensure_ascii=False)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
