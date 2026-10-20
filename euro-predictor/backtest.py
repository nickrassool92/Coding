"""Backtest and fitting for Euro Nights.

Replays this season's European games (qualifiers and league phase) in date order, predicting each
from the games played before that day, and scores the predictions. Bookmaker odds are not part of
it (past odds need a paid plan), so this tests the stats model on its own.

Usage:
  python3 -I backtest.py score <cache_dir>        (uses predict.PARAMS)
  python3 -I backtest.py fit <cache_dir>          (grid search; prints the best settings)
"""
import itertools
import json
import math
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import predict as P  # noqa: E402

START = "2026-08-01"


def test_games(games):
    return [g for g in games if g["euro"] and g["tournament"] != "last season" and g["utc"] >= START]


def lambdas(games, tests, p):
    """Expected goals for every test game from a fit on the games before its day."""
    out, fits = {}, {}
    for g in tests:
        day = g["utc"][:10]
        if day not in fits:
            fits[day] = P.fit(games, datetime.fromisoformat(day + "T00:00:00+00:00"), p)
        out[g["id"]] = P.expected(fits[day], g["home"], g["away"], g["lh"], g["la"])
    return out


def score(tests, lams, p):
    rows = []
    for g in tests:
        lh, la = lams[g["id"]]
        ph, pd, pa, pick, _ = P.outcome(P.score_matrix(lh, la, p))
        actual = "H" if g["hg"] > g["ag"] else "A" if g["hg"] < g["ag"] else "D"
        pr = {"H": ph, "D": pd, "A": pa}
        guess = "H" if pick[0] > pick[1] else "A" if pick[0] < pick[1] else "D"
        rows.append({"date": g["utc"][:10], "tournament": g["tournament"], "match": f"{g['home_name']} v {g['away_name']}", "pred": pick, "result": [g["hg"], g["ag"]],
                     "right": guess == actual, "exact": pick == [g["hg"], g["ag"]], "actual": actual,
                     "probs": [round(ph, 3), round(pd, 3), round(pa, 3)],
                     "brier": sum((pr[k] - (k == actual)) ** 2 for k in "HDA"), "logloss": -math.log(max(1e-9, pr[actual]))})
    n = len(rows)
    return {"games": n, "right": sum(r["right"] for r in rows), "exact": sum(r["exact"] for r in rows),
            "brier": round(sum(r["brier"] for r in rows) / n, 4), "logloss": round(sum(r["logloss"] for r in rows) / n, 4),
            "draw_prob": round(sum(r["probs"][1] for r in rows) / n, 3), "draw_rate": round(sum(r["actual"] == "D" for r in rows) / n, 3)}, rows


def baselines(rows):
    n = len(rows)
    rates = {k: sum(r["actual"] == k for r in rows) / n for k in "HDA"}
    out = {}
    for name, pr in (("home_draw_away_rates", rates), ("coin_flip", {"H": 1 / 3, "D": 1 / 3, "A": 1 / 3})):
        pick = max(pr, key=pr.get)
        out[name] = {"right": sum(r["actual"] == pick for r in rows),
                     "brier": round(sum(sum((pr[k] - (k == r["actual"])) ** 2 for k in "HDA") for r in rows) / n, 4),
                     "logloss": round(sum(-math.log(pr[r["actual"]]) for r in rows) / n, 4)}
    return out


def app_summary(s, rows, base, p):
    """The backtest as the app shows it: overall, by stage, baselines and every game."""
    def part(name, rs):
        return {"name": name, "games": len(rs), "right": sum(r["right"] for r in rs), "exact": sum(r["exact"] for r in rs),
                "brier": round(sum(r["brier"] for r in rs) / len(rs), 4)}
    stages = [("Qualifiers", lambda t: "Qualification" in t)] + [
        (name + " league phase", lambda t, n=name: t == n) for name in ("Champions League", "Europa League", "Conference League")]
    return {"summary": {k: s[k] for k in ("games", "right", "exact", "brier", "logloss")}, "baselines": base, "params": p,
            "stages": [part(n, [r for r in rows if f(r["tournament"])]) for n, f in stages if any(f(r["tournament"]) for r in rows)],
            "games": [{k: r[k] for k in ("date", "match", "tournament", "pred", "result", "right", "exact")} for r in rows]}


if __name__ == "__main__":
    mode, cache = sys.argv[1], sys.argv[2]
    _, _, _, games = P.gather(cache)
    tests = test_games(games)
    print(f"{len(tests)} test games, {len(games)} games in all", file=sys.stderr)
    if mode == "fit":
        best = None
        for hl, rt, rl in itertools.product((60, 120, 240), (2.0, 4.0, 8.0, 16.0), (0.5, 2.0, 8.0)):
            p = dict(P.PARAMS, half_life=hl, ridge_team=rt, ridge_league=rl)
            lams = lambdas(games, tests, p)
            for db in (0.0, 0.1, 0.2, 0.3):
                q = dict(p, draw_boost=db)
                s, _ = score(tests, lams, q)
                print("grid", hl, rt, rl, db, s["logloss"], s["right"], file=sys.stderr, flush=True)
                if best is None or s["logloss"] < best[0]["logloss"]:
                    best = (s, q)
        p = best[1]
    else:
        p = P.PARAMS
    s, rows = score(tests, lambdas(games, tests, p), p)
    s_old, _ = score(tests, lambdas(games, tests, P.PARAMS), P.PARAMS)
    print(json.dumps({"params": p, "model": s, "current_params": s_old, "baselines": baselines(rows),
                      "app": app_summary(s, rows, baselines(rows), p),
                      "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "rows": rows}))
