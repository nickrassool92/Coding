"""Backtest and fitting for the Full Time model.

Replays a season in kick-off order, predicting each game only from matches played before it plus
the previous season's table, and scores the predictions. Settings are fitted on one season and then
checked on another the fit never saw.

Usage:
  python3 -I backtest.py fit <fit_matches.json> <fit_prior_league.json> <test_matches.json> <test_prior_league.json>
  python3 -I backtest.py score <matches.json> <prior_league.json>   (uses predict.PARAMS)
matches.json: [{"home", "away", "utc", "round", "hg", "ag", "hxg", "axg"}]; prior_league.json: FotMob
league data for the previous season. Missing players are not modelled, as past team news isn't available.
"""
import itertools
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import predict as P  # noqa: E402


def load_matches(path):
    ms = json.load(open(path))
    for m in ms:
        m["utc"] = m["utc"].replace(".000Z", "Z")
        m["_ts"] = P.utc(m["utc"]).timestamp()
    return sorted([m for m in ms if m.get("hxg") is not None], key=lambda m: m["utc"])


def load_prior(path):
    return P.prior_from_table(json.load(open(path))["table"][0]["data"]["table"]["xg"])


def lambdas(matches, prior, p):
    """Expected goals for every match from the ratings just before kick-off (no home factors yet)."""
    clubs = sorted({m["home"] for m in matches} | {m["away"] for m in matches})
    out = []
    for m in matches:
        r = P.team_ratings(clubs, matches, prior, m["utc"], p)
        base = dict(p, home=1.0, away=1.0)
        out.append(P.expected_goals(r, m["home"], m["away"], base))
    return out


def score(matches, lams, p):
    rows = []
    for m, (lh, la) in zip(matches, lams):
        mat = P.score_matrix(lh * p["home"], la * p["away"], p)
        ph, pd, pa, pick, _ = P.outcome(mat)
        actual = "H" if m["hg"] > m["ag"] else "A" if m["hg"] < m["ag"] else "D"
        pr = {"H": ph, "D": pd, "A": pa}
        guess = "H" if pick[0] > pick[1] else "A" if pick[0] < pick[1] else "D"
        rows.append({"match": f"{m['home']} v {m['away']}", "round": m.get("round"), "pred": pick, "result": [m["hg"], m["ag"]],
                     "right": guess == actual, "exact": pick == [m["hg"], m["ag"]], "actual": actual,
                     "probs": [round(ph, 3), round(pd, 3), round(pa, 3)], "xg_pred": [round(lh * p["home"], 2), round(la * p["away"], 2)],
                     "xg_actual": [m["hxg"], m["axg"]],
                     "brier": sum((pr[k] - (k == actual)) ** 2 for k in "HDA"), "logloss": -math.log(max(1e-9, pr[actual]))})
    n = len(rows)
    return {"games": n, "right": sum(r["right"] for r in rows), "exact": sum(r["exact"] for r in rows),
            "brier": round(sum(r["brier"] for r in rows) / n, 4), "logloss": round(sum(r["logloss"] for r in rows) / n, 4),
            "draw_prob": round(sum(r["probs"][1] for r in rows) / n, 3), "draw_rate": round(sum(r["actual"] == "D" for r in rows) / n, 3)}, rows


def baselines(rows):
    n = len(rows)
    out = {}
    for name, pr in (("always_home", {"H": 0.46, "D": 0.25, "A": 0.29}), ("coin_flip", {"H": 1 / 3, "D": 1 / 3, "A": 1 / 3})):
        pick = max(pr, key=pr.get)
        out[name] = {"right": sum(r["actual"] == pick for r in rows),
                     "brier": round(sum(sum((pr[k] - (k == r["actual"])) ** 2 for k in "HDA") for r in rows) / n, 4),
                     "logloss": round(sum(-math.log(pr[r["actual"]]) for r in rows) / n, 4)}
    return out


def fit(fit_m, fit_prior):
    """Stage 1 fits the rating settings, stage 2 the home, away and draw settings. Log loss is the target."""
    best = None
    for pg, hl, xw in itertools.product((6, 9, 12, 16, 24), (45, 90, 180, 365, 100000), (0.6, 0.75, 0.9)):
        p = dict(P.PARAMS, prior_games=pg, half_life=hl, xg_weight=xw)
        s, _ = score(fit_m, lambdas(fit_m, fit_prior, p), p)
        if best is None or s["logloss"] < best[0]["logloss"]:
            best = (s, p)
        print("stage1", pg, hl, xw, s["logloss"], file=sys.stderr)
    p1 = best[1]
    lams = lambdas(fit_m, fit_prior, p1)
    for hm, aw, rho, db in itertools.product((1.04, 1.08, 1.12, 1.16), (0.88, 0.92, 0.96, 1.0),
                                              (-0.15, -0.1, -0.06, 0.0), (0.0, 0.05, 0.1, 0.15, 0.2)):
        p = dict(p1, home=hm, away=aw, rho=rho, draw_boost=db)
        s, _ = score(fit_m, lams, p)
        if s["logloss"] < best[0]["logloss"]:
            best = (s, p)
    return best


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "fit":
        fit_m, fit_prior = load_matches(sys.argv[2]), load_prior(sys.argv[3])
        test_m, test_prior = load_matches(sys.argv[4]), load_prior(sys.argv[5])
        s_fit, p = fit(fit_m, fit_prior)
        s_old_fit, _ = score(fit_m, lambdas(fit_m, fit_prior, P.PARAMS), P.PARAMS)
        s_test, rows = score(test_m, lambdas(test_m, test_prior, p), p)
        s_old_test, _ = score(test_m, lambdas(test_m, test_prior, P.PARAMS), P.PARAMS)
        print(json.dumps({"params": p, "fit_season": {"new": s_fit, "old": s_old_fit, "baselines": baselines(score(fit_m, lambdas(fit_m, fit_prior, p), p)[1])},
                          "test_season": {"new": s_test, "old": s_old_test, "baselines": baselines(rows)}, "test_rows": rows}))
    else:
        m, prior = load_matches(sys.argv[2]), load_prior(sys.argv[3])
        s, rows = score(m, lambdas(m, prior, P.PARAMS), P.PARAMS)
        print(json.dumps({"model": s, "baselines": baselines(rows), "rows": rows}))
