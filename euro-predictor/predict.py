"""Euro Nights: predicts the score of every Champions League, Europa League and Conference League game.

Usage: python3 -I predict.py <out.json> [previous.json] [cache_dir]
Downloads each club's season from FotMob (domestic league and European games, qualifiers included)
and fits one rating model across all of them:
  log(expected goals) = base + home + league strength + club attack - (opponent league strength + opponent defence)
Domestic games rank clubs within a league; European games are what compare one league with another.
Clubs' deviations from their league are shrunk towards zero, and older games fade with a half-life.
Goals only: most leagues outside the big five have no expected goals data.

When ODDS_API_KEY is set the model is blended with Australian bookmakers' odds, as in Full Time.
Predictions for games that have kicked off are copied from previous.json unchanged.
The score engine (score_matrix, outcome, fit_to_probs) is the same as Full Time's.
"""
import difflib
import json
import math
import os
import sys
import time
import unicodedata
import urllib.request
from datetime import datetime, timedelta, timezone

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
FOTMOB = "https://www.fotmob.com/api/data/"
COMPS = {42: ("UCL", "Champions League", "soccer_uefa_champs_league"),
         73: ("UEL", "Europa League", "soccer_uefa_europa_league"),
         10216: ("UECL", "Conference League", "soccer_uefa_europa_conference_league")}
EURO_WORDS = ("Champions League", "Europa League", "Conference League")
MAX_GOALS = 8
# Fitted by backtest.py on this season's European games (see the backtest in the app).
PARAMS = {
    "half_life": 800,      # days for a game's weight to halve (fading faster made predictions worse)
    "ridge_team": 16.0,    # pull of each club towards its league's level (bigger = stronger pull)
    "ridge_league": 0.5,   # pull of each league towards the overall average
    "draw_boost": 0.0,     # extra weight on every drawn score (none needed: draws were not underrated)
    "rho": 0.0,
    "window_days": 450,    # games older than this are left out
}
# The odds weight is not backtested (past odds need a paid plan). Markets know squads and
# rotation that a goals-only model cannot, so they get a little more weight than in Full Time.
MARKET_WEIGHT = 0.7
ODDS_URL = "https://api.the-odds-api.com/v4/sports/{sport}/odds/?regions=au&markets=h2h&oddsFormat=decimal&apiKey="


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
    return datetime.fromisoformat(s.replace(".000Z", "Z").replace("Z", "+00:00"))


def iso(d):
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------- score engine (same as Full Time) ----------

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


def fit_to_probs(lh, la, target, p):
    """Expected goals close to the model's that reproduce the target home and away win chances."""
    total = lh + la
    best = None
    for t in [total * (0.8 + 0.02 * k) for k in range(21)]:
        for k in range(1, 100):
            share = k / 100
            h, a = t * share, t * (1 - share)
            ph, pd, pa, _, _ = outcome(score_matrix(h, a, p))
            err = (ph - target[0]) ** 2 + (pa - target[2]) ** 2 + 0.1 * ((t - total) / total) ** 2
            if best is None or err < best[0]:
                best = (err, h, a)
    return best[1], best[2]


# ---------- data ----------

def is_euro(name):
    return any(w in (name or "") for w in EURO_WORDS)


def fetch_team(tid, cache_dir=None):
    path = os.path.join(cache_dir, f"team-{tid}.json") if cache_dir else None
    if path and os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    d = get(FOTMOB + f"teams?id={tid}")
    slim = {"id": tid, "name": d["details"]["name"], "country": d["details"].get("country"),
            "league": d["details"].get("primaryLeagueId"), "league_name": d["details"].get("primaryLeagueName"),
            "fixtures": [{"id": f["id"], "home": f["home"]["id"], "away": f["away"]["id"],
                          "home_name": f["home"]["name"], "away_name": f["away"]["name"],
                          "hg": f["home"].get("score"), "ag": f["away"].get("score"),
                          "utc": f["status"].get("utcTime"), "finished": bool(f["status"].get("finished")),
                          "tournament": f["tournament"]["name"], "tid": f["tournament"].get("leagueId")}
                         for f in d.get("fixtures", {}).get("allFixtures", {}).get("fixtures", [])]}
    if path:
        with open(path, "w") as f:
            json.dump(slim, f)
    time.sleep(0.2)
    return slim


def gather(cache_dir=None, league_cache=None):
    """European fixtures, club details and a de-duplicated list of finished games for the model:
    this season's domestic league and European games for every club in the three competitions, plus
    last season's European games, which link far more leagues to each other than this season's do."""
    fixtures, clubs, last_season = [], {}, []
    for cid, (code, cname, _) in COMPS.items():
        lg = get(FOTMOB + f"leagues?id={cid}")
        seasons = lg.get("allAvailableSeasons") or []
        if len(seasons) > 1:
            try:
                old = get(FOTMOB + f"leagues?id={cid}&season={seasons[1].replace('/', '%2F')}")
                last_season += [m for m in old["fixtures"]["allMatches"] if m["status"].get("finished") and m["status"].get("scoreStr")]
            except Exception as e:
                print(f"{code} last season failed: {e}", file=sys.stderr)
        for m in lg["fixtures"]["allMatches"]:
            st = m["status"]
            fixtures.append({"id": str(m["id"]), "comp": code, "round": m.get("round"),
                             "home_id": int(m["home"]["id"]), "away_id": int(m["away"]["id"]),
                             "home": m["home"]["name"], "away": m["away"]["name"],
                             "kickoff": (st.get("utcTime") or "").replace(".000Z", "Z"),
                             "started": bool(st.get("started")), "finished": bool(st.get("finished")),
                             "cancelled": bool(st.get("cancelled")), "score": st.get("scoreStr")})
            clubs[int(m["home"]["id"])] = m["home"]["name"]
            clubs[int(m["away"]["id"])] = m["away"]["name"]
    teams = {}
    for tid in clubs:
        try:
            teams[tid] = fetch_team(tid, cache_dir)
        except Exception as e:
            print(f"team {tid} failed: {e}", file=sys.stderr)
    # Leagues of European opponents outside the three competitions (mostly qualifiers).
    league_of = {int(k): v for k, v in (league_cache or {}).items()}
    for t in teams.values():
        league_of[t["id"]] = t["league"]
    opponents = [o for t in teams.values() for f in t["fixtures"] if f["finished"] and is_euro(f["tournament"]) for o in (f["home"], f["away"])]
    opponents += [int(m[side]["id"]) for m in last_season for side in ("home", "away")]
    for o in opponents:
        if o not in league_of:
            try:
                league_of[o] = fetch_team(o, cache_dir)["league"]
            except Exception:
                league_of[o] = None
    games = {}
    for t in teams.values():
        for f in t["fixtures"]:
            if not f["finished"] or f["hg"] is None or f["ag"] is None or not f["utc"]:
                continue
            if f["tid"] == t["league"]:
                lh = la = t["league"]  # domestic league game: both sides in this league
            elif is_euro(f["tournament"]):
                lh, la = league_of.get(f["home"]), league_of.get(f["away"])
            else:
                continue  # cups, super cups and friendlies are left out
            if lh is None or la is None:
                continue
            games[str(f["id"])] = {"id": str(f["id"]), "home": f["home"], "away": f["away"], "lh": lh, "la": la,
                                   "home_name": f["home_name"], "away_name": f["away_name"],
                              "hg": f["hg"], "ag": f["ag"], "utc": f["utc"].replace(".000Z", "Z"),
                              "euro": is_euro(f["tournament"]), "tournament": f["tournament"]}
    for m in last_season:
        h, a = int(m["home"]["id"]), int(m["away"]["id"])
        lh, la = league_of.get(h), league_of.get(a)
        if lh is None or la is None:
            continue
        hg, ag = (int(x) for x in m["status"]["scoreStr"].split(" - "))
        games[str(m["id"])] = {"id": str(m["id"]), "home": h, "away": a, "lh": lh, "la": la, "hg": hg, "ag": ag,
                               "home_name": m["home"]["name"], "away_name": m["away"]["name"],
                               "utc": m["status"]["utcTime"].replace(".000Z", "Z"), "euro": True, "tournament": "last season"}
    for g in games.values():
        g["_ts"] = utc(g["utc"]).timestamp()
    return fixtures, teams, league_of, sorted(games.values(), key=lambda g: g["utc"])


# ---------- model ----------

def fit(games, when, p, iters=30):
    """Weighted Poisson fit of base, home, league strengths and club attack/defence, using only
    games before `when`. Block Newton steps: each block's parameters are updated together."""
    when_ts = when.timestamp()
    rows = []
    for g in games:
        age = (when_ts - g["_ts"]) / 86400
        if age <= 0 or age > p["window_days"]:
            continue
        w = 0.5 ** (age / p["half_life"])
        rows.append((g["home"], g["away"], g["lh"], g["la"], g["hg"], g["ag"], w))
    th = {"base": math.log(1.3), "home": 0.2, "S": {}, "a": {}, "d": {}}
    for h, a, lh, la, *_ in rows:
        for t in (h, a):
            th["a"].setdefault(t, 0.0)
            th["d"].setdefault(t, 0.0)
        th["S"].setdefault(lh, 0.0)
        th["S"].setdefault(la, 0.0)

    def sides():
        # each row gives two "scoring" observations: (scorer, conceder, scorer league, conceder league, goals, home?, w)
        for h, a, lh, la, hg, ag, w in rows:
            yield h, a, lh, la, hg, 1, w
            yield a, h, la, lh, ag, 0, w

    def eta(s, c, ls, lc, home):
        return th["base"] + th["home"] * home + th["S"][ls] + th["a"][s] - th["S"][lc] - th["d"][c]

    for _ in range(iters):
        for block in ("glob", "a", "d", "S"):
            g1, g2 = {}, {}
            for s, c, ls, lc, goals, home, w in sides():
                lam = math.exp(eta(s, c, ls, lc, home))
                r, hss = w * (goals - lam), w * lam
                if block == "glob":
                    for k, x in (("base", 1), ("home", home)):
                        g1[k] = g1.get(k, 0) + r * x
                        g2[k] = g2.get(k, 0) + hss * x
                elif block == "a":
                    g1[s] = g1.get(s, 0) + r
                    g2[s] = g2.get(s, 0) + hss
                elif block == "d":
                    g1[c] = g1.get(c, 0) - r
                    g2[c] = g2.get(c, 0) + hss
                elif ls != lc:  # league strength only moves on cross-league games
                    g1[ls] = g1.get(ls, 0) + r
                    g2[ls] = g2.get(ls, 0) + hss
                    g1[lc] = g1.get(lc, 0) - r
                    g2[lc] = g2.get(lc, 0) + hss
            if block == "glob":
                for k in g1:
                    th[k] += g1[k] / g2[k] if g2[k] else 0
            else:
                tgt = th[block]
                ridge = p["ridge_league"] if block == "S" else p["ridge_team"]
                for k in tgt:
                    gr = g1.get(k, 0) - ridge * tgt[k]
                    tgt[k] += 0.8 * gr / (g2.get(k, 0) + ridge)
        # keep the league scale centred so base stays meaningful
        if th["S"]:
            mean = sum(th["S"].values()) / len(th["S"])
            for k in th["S"]:
                th["S"][k] -= mean
    return th


def expected(th, home, away, lh, la, neutral=False):
    def part(t, key):
        return th[key].get(t, 0.0)
    eh = th["base"] + (0 if neutral else th["home"]) + th["S"].get(lh, 0) + part(home, "a") - th["S"].get(la, 0) - part(away, "d")
    ea = th["base"] + th["S"].get(la, 0) + part(away, "a") - th["S"].get(lh, 0) - part(home, "d")
    return math.exp(eh), math.exp(ea)


# ---------- odds ----------

def plain(name):
    n = unicodedata.normalize("NFKD", name.lower())
    n = "".join(c for c in n if not unicodedata.combining(c))
    for w in ("fc ", " fc", "afc ", "sc ", " sc", "fk ", " fk", "sk ", " sk", "cf ", " cf", "ac ", "as ", "nk ", "hnk ",
              "gnk ", "ssc ", "rc ", "rcd ", "sv ", "if ", " if", "bk ", " bk", "aik ", "1. ", "club ", " club", "kv ", "krc "):
        n = n.replace(w, " ")
    return " ".join(n.replace("-", " ").replace(".", " ").split())


def similar(a, b):
    a, b = plain(a), plain(b)
    if a == b or (a and b and (a in b or b in a)):
        return 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def market_odds(fixtures):
    """No-margin win/draw/loss chances averaged over Australian bookmakers, keyed by FotMob match id.
    Odds API names differ from FotMob's, so games are matched on kick-off time plus name similarity."""
    key = os.environ.get("ODDS_API_KEY")
    if not key:
        return {}, "no key"
    out, notes = {}, []
    for cid, (code, _, sport) in COMPS.items():
        try:
            events = get(ODDS_URL.format(sport=sport) + key)
        except Exception as e:
            notes.append(f"{code} odds failed")
            continue
        pool = [f for f in fixtures if f["comp"] == code and not f["started"] and f["kickoff"]]
        for ev in events:
            ct = utc(ev["commence_time"])
            best = None
            for f in pool:
                if abs((utc(f["kickoff"]) - ct).total_seconds()) > 3 * 3600:
                    continue
                s = similar(ev["home_team"], f["home"]) + similar(ev["away_team"], f["away"])
                if best is None or s > best[0]:
                    best = (s, f)
            if not best or best[0] < 1.2:
                continue
            h, a = ev["home_team"], ev["away_team"]
            probs, sportsbet = [], None
            for bk in ev.get("bookmakers", []):
                mk = next((m for m in bk.get("markets", []) if m["key"] == "h2h"), None)
                if not mk:
                    continue
                price = {o["name"]: o["price"] for o in mk["outcomes"]}
                if h not in price or a not in price or "Draw" not in price:
                    continue
                inv = [1 / price[h], 1 / price["Draw"], 1 / price[a]]
                probs.append([x / sum(inv) for x in inv])
                if bk["key"] == "sportsbet":
                    sportsbet = {"home": price[h], "draw": price["Draw"], "away": price[a]}
            if probs:
                avg = [sum(p[i] for p in probs) / len(probs) for i in range(3)]
                out[best[1]["id"]] = {"home": avg[0], "draw": avg[1], "away": avg[2], "books": len(probs), "sportsbet": sportsbet}
    return out, f"{len(out)} games priced" + (f" ({', '.join(notes)})" if notes else "")


# ---------- main ----------

def league_label(t):
    """League name with the country code, since several countries have a "Premier League"."""
    return f"{t.get('league_name')} ({t.get('country')})" if t.get("country") else t.get("league_name")


def predict_game(th, f, teams, league_of, market, p):
    lh, la = league_of.get(f["home_id"]), league_of.get(f["away_id"])
    eh, ea = expected(th, f["home_id"], f["away_id"], lh, la, neutral=f.get("neutral", False))
    mh, md, ma, _, _ = outcome(score_matrix(eh, ea, p))
    mk = market.get(f["id"])
    if mk:
        target = [MARKET_WEIGHT * mk[k] + (1 - MARKET_WEIGHT) * v for k, v in (("home", mh), ("draw", md), ("away", ma))]
        eh, ea = fit_to_probs(eh, ea, target, p)
    m = score_matrix(eh, ea, p)
    ph, pd, pa, pick, cells = outcome(m)
    btts = sum(m[i][j] for i in range(1, MAX_GOALS + 1) for j in range(1, MAX_GOALS + 1))
    over = sum(m[i][j] for i in range(MAX_GOALS + 1) for j in range(MAX_GOALS + 1) if i + j >= 3)
    return {"xg": [round(eh, 2), round(ea, 2)], "score": pick,
            "probs": {"home": round(ph, 3), "draw": round(pd, 3), "away": round(pa, 3)},
            "top_scores": [{"score": [i, j], "p": round(v, 3)} for v, i, j in cells[:4]],
            "btts": round(btts, 3), "over25": round(over, 3),
            "clean_sheet": [round(sum(m[i][0] for i in range(MAX_GOALS + 1)), 3), round(sum(m[0][j] for j in range(MAX_GOALS + 1)), 3)],
            "model": {"home": round(mh, 3), "draw": round(md, 3), "away": round(ma, 3)},
            "market": ({"home": round(mk["home"], 3), "draw": round(mk["draw"], 3), "away": round(mk["away"], 3),
                        "books": mk["books"], "sportsbet": mk["sportsbet"]} if mk else None)}


def main(out_path, prev_path=None, cache_dir=None):
    prev_doc = {}
    if prev_path:
        try:
            with open(prev_path) as f:
                prev_doc = json.load(f)
        except Exception:
            prev_doc = {}
    # Settings adopted by the weekly retune (retrain.py) override the fitted defaults.
    p = {**PARAMS, **(prev_doc.get("tuned_params") or {})}
    now = datetime.now(timezone.utc)
    fixtures, teams, league_of, games = gather(cache_dir, prev_doc.get("league_of"))
    th = fit(games, now, p)
    market, market_note = market_odds(fixtures)
    prev = {g["id"]: g for g in prev_doc.get("games", [])}

    # Show games from 3 days ago to 8 days ahead: this round's results and the next round.
    shown = [f for f in fixtures if f["kickoff"] and not f["cancelled"]
             and now - timedelta(days=3) <= utc(f["kickoff"]) <= now + timedelta(days=8)]
    out_games = []
    for f in sorted(shown, key=lambda f: (f["kickoff"], f["comp"], f["id"])):
        result = [int(x) for x in f["score"].split(" - ")] if f["finished"] and f["score"] else None
        base = {"id": f["id"], "comp": f["comp"], "round": f["round"], "kickoff": f["kickoff"],
                "home": f["home"], "away": f["away"], "finished": f["finished"], "result": result,
                "home_league": league_label(teams.get(f["home_id"], {})), "away_league": league_label(teams.get(f["away_id"], {}))}
        started = f["started"] or utc(f["kickoff"]) <= now
        if started:
            # Never predict after kick-off: keep the pre-match prediction, or leave it blank.
            out_games.append({**base, "pred": (prev.get(f["id"]) or {}).get("pred")})
            continue
        out_games.append({**base, "pred": {**predict_game(th, f, teams, league_of, market, p), "made": iso(now)}})

    history = dict(prev_doc.get("history", {}))
    for g in out_games:
        if g["finished"] and g["result"] and g.get("pred"):
            hs, as_ = g["result"]
            ps = g["pred"]["score"]
            res = "H" if hs > as_ else "A" if hs < as_ else "D"
            pres = "H" if ps[0] > ps[1] else "A" if ps[0] < ps[1] else "D"
            history[g["id"]] = {"comp": g["comp"], "date": g["kickoff"][:10], "match": f"{g['home']} v {g['away']}",
                                "result": g["result"], "pred": ps, "right_result": res == pres, "exact": [hs, as_] == ps}

    # Ratings: every club in the three competitions, as expected goals for and against an average European side.
    names = {f["home_id"]: f["home"] for f in fixtures} | {f["away_id"]: f["away"] for f in fixtures}
    comp_of = {}
    for f in fixtures:
        comp_of.setdefault(f["home_id"], f["comp"])
        comp_of.setdefault(f["away_id"], f["comp"])
    ratings = []
    for tid, name in names.items():
        lg = league_of.get(tid)
        att = math.exp(th["base"] + th["S"].get(lg, 0) + th["a"].get(tid, 0))
        dfn = math.exp(th["base"] - th["S"].get(lg, 0) - th["d"].get(tid, 0))
        ratings.append({"club": name, "comp": comp_of[tid], "league": league_label(teams.get(tid, {})),
                        "attack": round(att, 2), "defence": round(dfn, 2), "net": round(att - dfn, 2)})
    ratings.sort(key=lambda r: -r["net"])
    # Each league's strength with the number of its clubs seen in European games, which is what it rests on.
    cutoff = now.timestamp() - p["window_days"] * 86400
    seen = {}
    for g in games:
        if g["euro"] and g["_ts"] >= cutoff and g["lh"] != g["la"]:
            seen.setdefault(g["lh"], set()).add(g["home"])
            seen.setdefault(g["la"], set()).add(g["away"])
    leagues = {}
    for t in teams.values():
        if t["league"] in th["S"]:
            leagues[t["league"]] = {"league": league_label(t), "strength": round(th["S"][t["league"]], 3), "clubs": len(seen.get(t["league"], ()))}

    out = {"backtest": prev_doc.get("backtest"), "tuned_params": prev_doc.get("tuned_params"), "tuning": prev_doc.get("tuning", []),
           "params": p, "market_weight": MARKET_WEIGHT,
           "market_note": market_note, "updatedAt": iso(now), "games": out_games, "history": history,
           "ratings": ratings, "league_strength": sorted(leagues.values(), key=lambda r: -r["strength"]),
           "fitted_on": len([g for g in games if 0 < (now.timestamp() - g["_ts"]) / 86400 <= p["window_days"]]),
           "league_of": {str(k): v for k, v in league_of.items() if v is not None}}
    with open(out_path, "w") as f:
        json.dump(out, f, ensure_ascii=False)
    print(f"{len(out_games)} games shown, {out['fitted_on']} games fitted, {market_note}", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None, sys.argv[3] if len(sys.argv) > 3 else None)
