"""Weekly retune of Euro Nights' settings, run after each round of European games.

Usage: python3 -I retrain.py <current.json> <cache_dir> <out_tuning.json>
current.json is the predictions/current document (for the settings in use).

This season's European games are replayed day by day as in backtest.py. Settings are searched on
all but the latest HOLDOUT games, then the best candidate is compared with the settings in use on
those latest games, which the search never saw. The candidate is adopted only if it is better
there by MARGIN in log loss and no worse on the search games.
"""
import itertools
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backtest as B  # noqa: E402
import predict as P  # noqa: E402

HOLDOUT = 60     # about one round across the three competitions
MARGIN = 0.005   # log loss improvement needed on the held-out games


def summary(rows):
    n = len(rows)
    return {"games": n, "right": sum(r["right"] for r in rows), "exact": sum(r["exact"] for r in rows),
            "logloss": round(sum(r["logloss"] for r in rows) / n, 4), "brier": round(sum(r["brier"] for r in rows) / n, 4)}


def main(current_path, cache_dir, out_path):
    cur = json.load(open(current_path))
    cur = cur.get("data", cur)
    in_use = {**P.PARAMS, **(cur.get("tuned_params") or {})}
    _, _, _, games = P.gather(cache_dir, cur.get("league_of"))
    tests = B.test_games(games)
    search, hold = tests[:-HOLDOUT], tests[-HOLDOUT:]

    def rows_for(p, which):
        return B.score(which, B.lambdas(games, which, p), p)[1]

    best = None
    hls = sorted({in_use["half_life"] // 2, in_use["half_life"], in_use["half_life"] * 2})
    rts = sorted({in_use["ridge_team"] / 2, in_use["ridge_team"], in_use["ridge_team"] * 2})
    rls = sorted({in_use["ridge_league"] / 2, in_use["ridge_league"], in_use["ridge_league"] * 2})
    for hl, rt, rl in itertools.product(hls, rts, rls):
        p = dict(in_use, half_life=hl, ridge_team=rt, ridge_league=rl)
        lams = B.lambdas(games, search, p)
        for db in sorted({0.0, 0.05, 0.1, in_use["draw_boost"]}):
            q = dict(p, draw_boost=db)
            s = summary(B.score(search, lams, q)[1])
            if best is None or s["logloss"] < best[0]["logloss"]:
                best = (s, q)
    cand = best[1]
    s_old, s_new = summary(rows_for(in_use, search)), best[0]
    h_old, h_new = summary(rows_for(in_use, hold)), summary(rows_for(cand, hold))
    adopt = cand != in_use and h_new["logloss"] <= h_old["logloss"] - MARGIN and s_new["logloss"] <= s_old["logloss"]
    chosen = cand if adopt else in_use
    s_all, rows = B.score(tests, B.lambdas(games, tests, chosen), chosen)
    out = {"date": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "games": len(tests), "adopted": adopt,
           "params_in_use": in_use, "candidate": cand, "chosen": chosen,
           "search": {"in_use": s_old, "candidate": s_new}, "holdout": {"in_use": h_old, "candidate": h_new},
           "backtest": B.app_summary(s_all, rows, B.baselines(rows), chosen)}
    with open(out_path, "w") as f:
        json.dump(out, f)
    print(json.dumps({k: out[k] for k in ("adopted", "search", "holdout")}), file=sys.stderr)


if __name__ == "__main__":
    main(*sys.argv[1:4])
