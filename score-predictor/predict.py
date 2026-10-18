"""Full Time: predicts the score of every Premier League game in the current and next gameweek.

Usage: python3 -I predict.py <out.json> [previous.json]
Downloads the FPL and FotMob data it needs. Match-by-match expected goals are cached in the output,
so each run only fetches games finished since the last one. Predictions for games that have already
kicked off are copied from previous.json unchanged, so the track record always compares pre-match picks.

The model core (team_ratings, expected_goals, score_matrix, outcome) is shared with backtest.py,
which fits PARAMS on whole seasons of past games.
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
MAX_GOALS = 8
# Fitted by backtest.py on the 2025/26 season and checked on 2026/27 (see the backtest in the app).
PARAMS = {
    "prior_games": 12,     # weight of last season's per-game rates, in games
    "half_life": 100000,   # days for a game's weight to halve (recent form counts more)
    "xg_weight": 0.75,     # this season: mix of expected goals and actual goals
    "home": 1.10,          # multiplier on the home side's expected goals
    "away": 0.92,          # multiplier on the away side's expected goals
    "rho": -0.06,          # Dixon-Coles correction for 0-0, 1-0, 0-1 and 1-1
    "draw_boost": 0.0,     # extra weight on every drawn score, then renormalised
}
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


def utc(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


# ---------- model core ----------

def prior_from_table(rows):
    """Last season's per-game xG for and against by FotMob club name, a starting point for promoted
    clubs (last season's bottom three) and the league average."""
    per = {r["name"]: {"xg": r["xg"] / r["played"], "xga": r["xgConceded"] / r["played"]} for r in rows}
    bottom = sorted(rows, key=lambda r: r["pts"])[:3]
    promoted = {"xg": sum(r["xg"] / r["played"] for r in bottom) / 3,
                "xga": sum(r["xgConceded"] / r["played"] for r in bottom) / 3}
    avg = sum(v["xg"] for v in per.values()) / len(per)
    return per, promoted, avg


def team_ratings(clubs, matches, prior, when, p):
    """Goals-for and goals-against rates per club from this season's matches before `when`, each
    weighted by age, shrunk towards last season (itself regressed a fifth of the way to average)."""
    per, promoted, league_avg = prior
    when_ts = utc(when).timestamp()
    out = {}
    for t in clubs:
        pr = per.get(t, promoted)
        pf = 0.8 * pr["xg"] + 0.2 * league_avg
        pa = 0.8 * pr["xga"] + 0.2 * league_avg
        wsum = f = a = 0.0
        for m in matches:
            if t not in (m["home"], m["away"]) or m.get("hxg") is None:
                continue
            ts = m.get("_ts") or utc(m["utc"]).timestamp()
            if ts >= when_ts:
                continue
            age = (when_ts - ts) / 86400
            w = 0.5 ** (age / p["half_life"])
            home = m["home"] == t
            xf, xa = (m["hxg"], m["axg"]) if home else (m["axg"], m["hxg"])
            gf, ga = (m["hg"], m["ag"]) if home else (m["ag"], m["hg"])
            f += w * (p["xg_weight"] * xf + (1 - p["xg_weight"]) * gf)
            a += w * (p["xg_weight"] * xa + (1 - p["xg_weight"]) * ga)
            wsum += w
        out[t] = {"for": (f + pf * p["prior_games"]) / (wsum + p["prior_games"]),
                  "against": (a + pa * p["prior_games"]) / (wsum + p["prior_games"])}
    return out


def expected_goals(rating, home, away, p, home_factor=1.0, away_factor=1.0):
    avg = sum(r["for"] for r in rating.values()) / len(rating)
    lh = avg * (rating[home]["for"] / avg) * (rating[away]["against"] / avg) * p["home"] * home_factor
    la = avg * (rating[away]["for"] / avg) * (rating[home]["against"] / avg) * p["away"] * away_factor
    return lh, la


def poisson(k, lam):
    return math.exp(-lam) * lam ** k / math.factorial(k)


def score_matrix(lh, la, p=PARAMS):
    rho = p["rho"]
    m = [[poisson(i, lh) * poisson(j, la) for j in range(MAX_GOALS + 1)] for i in range(MAX_GOALS + 1)]
    m[0][0] *= max(0.0, 1 - lh * la * rho)
    m[0][1] *= max(0.0, 1 + lh * rho)
    m[1][0] *= max(0.0, 1 + la * rho)
    m[1][1] *= max(0.0, 1 - rho)
    for i in range(MAX_GOALS + 1):
        m[i][i] *= 1 + p["draw_boost"]
    total = sum(sum(r) for r in m)
    return [[v / total for v in r] for r in m]


def outcome(m):
    """Win/draw/loss chances, and the most likely score within the most likely result."""
    n = len(m)
    ph = sum(m[i][j] for i in range(n) for j in range(n) if i > j)
    pd = sum(m[i][i] for i in range(n))
    pa = 1 - ph - pd
    res = max((ph, "H"), (pd, "D"), (pa, "A"))[1]
    cells = sorted(((m[i][j], i, j) for i in range(n) for j in range(n)), reverse=True)
    pick = next(c for c in cells if (c[1] > c[2] and res == "H") or (c[1] == c[2] and res == "D") or (c[1] < c[2] and res == "A"))
    return ph, pd, pa, [pick[1], pick[2]], cells


# ---------- data ----------

def league(season=None):
    return get(FOTMOB + "leagues?id=47" + (f"&season={season.replace('/', '%2F')}" if season else ""))


def match_xg(match_id):
    stats = get(FOTMOB + f"matchDetails?matchId={match_id}")["content"]["stats"]["Periods"]["All"]["stats"]
    for grp in stats:
        for s in grp.get("stats", []):
            if s.get("key") == "expected_goals" and isinstance(s.get("stats"), list) and len(s["stats"]) == 2:
                return float(s["stats"][0]), float(s["stats"][1])
    return None, None


def season_matches(lg, cache):
    """Finished league matches with both sides' xG, reusing cached ones and fetching only new games."""
    known = {m["id"]: m for m in cache}
    out = []
    for m in lg["fixtures"]["allMatches"]:
        st = m["status"]
        if not st.get("finished") or not st.get("scoreStr"):
            continue
        mid = str(m["id"])
        if mid in known and known[mid].get("hxg") is not None:
            out.append(known[mid])
            continue
        try:
            hx, ax = match_xg(mid)
        except Exception:
            hx = ax = None
        hg, ag = (int(x) for x in st["scoreStr"].split(" - "))
        out.append({"id": mid, "home": m["home"]["name"], "away": m["away"]["name"], "utc": st["utcTime"].replace(".000Z", "Z"),
                    "round": m.get("round"), "hg": hg, "ag": ag, "hxg": hx, "axg": ax})
        time.sleep(0.15)
    return out


def main(out_path, prev_path=None):
    prev_doc = {}
    if prev_path:
        try:
            with open(prev_path) as f:
                prev_doc = json.load(f)
        except Exception:
            prev_doc = {}
    p = PARAMS

    boot = get(FPL + "bootstrap-static/")
    fixtures = get(FPL + "fixtures/")
    lg = league()
    season = lg["table"][0]["data"]["selectedSeason"]
    seasons = lg["allAvailableSeasons"]
    last = league(seasons[1])["table"][0]["data"]["table"]["xg"] if len(seasons) > 1 else []
    matches = season_matches(lg, prev_doc.get("match_xg", []))
    prior = prior_from_table(last)

    teams = {t["id"]: t for t in boot["teams"]}
    fm_name = {}
    for row in lg["table"][0]["data"]["table"]["all"]:
        name = row["name"]
        fpl = next((t for t in boot["teams"] if t["name"] == ALIASES.get(name, name) or t["name"] == name), None)
        if fpl:
            fm_name[fpl["id"]] = name
    clubs = list(fm_name.values())

    # Missing attackers: each unavailable player takes away part of his share of the team's
    # expected goal involvement (a replacement makes up the rest).
    contrib, absent = {}, {}
    for pl in boot["elements"]:
        xgi = float(pl["expected_goals"] or 0) + 0.5 * float(pl["expected_assists"] or 0)
        contrib[pl["team"]] = contrib.get(pl["team"], 0) + xgi
    for pl in boot["elements"]:
        chance = pl["chance_of_playing_next_round"]
        missing = 1.0 if pl["status"] in ("i", "s", "n") and not chance else (1 - chance / 100 if chance is not None and pl["status"] != "u" else 0)
        xgi = float(pl["expected_goals"] or 0) + 0.5 * float(pl["expected_assists"] or 0)
        if missing > 0 and contrib.get(pl["team"]) and xgi / contrib[pl["team"]] >= 0.05:
            absent.setdefault(pl["team"], []).append((pl["web_name"], missing, xgi / contrib[pl["team"]], pl["news"]))

    def attack_factor(tid):
        loss = sum(m * share for _, m, share, _ in absent.get(tid, []))
        return max(0.75, 1 - 0.6 * loss)

    upcoming = [ev["id"] for ev in boot["events"] if not ev["finished"]][:2]
    prev = {g["id"]: g for g in prev_doc.get("games", [])}
    now = datetime.now(timezone.utc)
    now_s = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    rating_now = team_ratings(clubs, matches, prior, now_s, p)

    games = []
    for f in fixtures:
        if f["event"] not in upcoming:
            continue
        h, a = f["team_h"], f["team_a"]
        started = f["started"] or (f["kickoff_time"] and utc(f["kickoff_time"]) <= now)
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
        if h not in fm_name or a not in fm_name:
            games.append({**base, "pred": None})
            continue
        lh, la = expected_goals(rating_now, fm_name[h], fm_name[a], p, attack_factor(h), attack_factor(a))
        m = score_matrix(lh, la, p)
        ph, pd, pa, pick, cells = outcome(m)
        btts = sum(m[i][j] for i in range(1, MAX_GOALS + 1) for j in range(1, MAX_GOALS + 1))
        over = sum(m[i][j] for i in range(MAX_GOALS + 1) for j in range(MAX_GOALS + 1) if i + j >= 3)
        games.append({**base, "pred": {
            "xg": [round(lh, 2), round(la, 2)],
            "score": pick,
            "probs": {"home": round(ph, 3), "draw": round(pd, 3), "away": round(pa, 3)},
            "top_scores": [{"score": [i, j], "p": round(v, 3)} for v, i, j in cells[:4]],
            "btts": round(btts, 3), "over25": round(over, 3),
            "clean_sheet": [round(sum(m[i][0] for i in range(MAX_GOALS + 1)), 3), round(sum(m[0][j] for j in range(MAX_GOALS + 1)), 3)],
            "absences": {
                "home": [{"name": n, "news": nw} for n, mi, s, nw in absent.get(h, []) if mi >= 0.5],
                "away": [{"name": n, "news": nw} for n, mi, s, nw in absent.get(a, []) if mi >= 0.5]},
            "made": now_s}})

    # Track record: every finished game this season that had a pre-match prediction.
    history = {int(k): v for k, v in prev_doc.get("history", {}).items()}
    for g in games:
        if g["finished"] and g["result"] and g.get("pred"):
            hs, as_ = g["result"]
            ps = g["pred"]["score"]
            res = "H" if hs > as_ else "A" if hs < as_ else "D"
            pres = "H" if ps[0] > ps[1] else "A" if ps[0] < ps[1] else "D"
            history[g["id"]] = {"gw": g["gw"], "match": f"{g['home_short']} v {g['away_short']}", "result": g["result"],
                                "pred": ps, "right_result": res == pres, "exact": [hs, as_] == ps}

    avg = sum(r["for"] for r in rating_now.values()) / len(rating_now)
    short = {fm_name[t]: teams[t]["short_name"] for t in fm_name}
    out = {
        "backtest": prev_doc.get("backtest"),
        "season": season,
        "params": p,
        "updatedAt": now_s,
        "ratings": {short[c]: {"attack": round(r["for"] / avg, 2), "defence": round(r["against"] / avg, 2)} for c, r in rating_now.items()},
        "games": sorted(games, key=lambda g: (g["kickoff"] or "", g["id"])),
        "history": history,
        "match_xg": matches,
    }
    with open(out_path, "w") as f:
        json.dump(out, f, ensure_ascii=False)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
