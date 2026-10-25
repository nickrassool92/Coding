"""Weekly retune of Full Time's settings, run after each gameweek.

Usage: python3 -I retrain.py <current.json> <last_season.json> <out_tuning.json>
current.json is the predictions/current document (this season's games with xG are in match_xg).
last_season.json is {"matches": [...2025/26 games...], "prior_last": <2024/25 xG table rows>,
"prior_this": <2025/26 xG table rows>}, stored in the app's database as tools/last_season.

Settings are searched on last season plus this season except the latest HOLDOUT games, then the
best candidate is compared with the settings in use on those latest games, which the search never
saw. The candidate is adopted only if it is better there by MARGIN in log loss and no worse on the
search games, so one odd weekend can't drag the model around.
"""
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backtest as B  # noqa: E402
import predict as P  # noqa: E402

HOLDOUT = 30     # about three gameweeks
MARGIN = 0.005   # log loss improvement needed on the held-out games


def prep(ms):
    for m in ms:
        m["utc"] = m["utc"].replace(".000Z", "Z")
        m["_ts"] = P.utc(m["utc"]).timestamp()
    return sorted([m for m in ms if m.get("hxg") is not None], key=lambda m: m["utc"])


def scored(sets, p):
    """Rows for several (matches, prior, targets) sets, each predicted from its own season's games."""
    rows = []
    for matches, prior, targets in sets:
        lams = B.lambdas(matches, prior, p)
        keep = [i for i, m in enumerate(matches) if m["id"] in targets]
        _, r = B.score([matches[i] for i in keep], [lams[i] for i in keep], p)
        rows += r
    return rows


def summary(rows):
    n = len(rows)
    return {"games": n, "right": sum(r["right"] for r in rows), "exact": sum(r["exact"] for r in rows),
            "logloss": round(sum(r["logloss"] for r in rows) / n, 4), "brier": round(sum(r["brier"] for r in rows) / n, 4)}


def search(sets, base):
    """The same two-stage grid as backtest.fit, scored on all the search sets together."""
    import itertools
    best = None
    for pg, hl, xw in itertools.product((6, 9, 12, 16, 24), (45, 90, 180, 365, 100000), (0.6, 0.75, 0.9)):
        p = dict(base, prior_games=pg, half_life=hl, xg_weight=xw)
        s = summary(scored(sets, p))
        if best is None or s["logloss"] < best[0]["logloss"]:
            best = (s, p)
    p1 = best[1]
    lam_sets = [(m, pr, t, B.lambdas(m, pr, dict(p1, home=1.0, away=1.0))) for m, pr, t in sets]
    for hm, aw, rho, db in itertools.product((1.04, 1.08, 1.12, 1.16), (0.88, 0.92, 0.96, 1.0),
                                              (-0.15, -0.1, -0.06, 0.0), (0.0, 0.05, 0.1, 0.15, 0.2)):
        p = dict(p1, home=hm, away=aw, rho=rho, draw_boost=db)
        rows = []
        for matches, prior, targets, lams in lam_sets:
            keep = [i for i, m in enumerate(matches) if m["id"] in targets]
            rows += B.score([matches[i] for i in keep], [lams[i] for i in keep], p)[1]
        s = summary(rows)
        if s["logloss"] < best[0]["logloss"]:
            best = (s, p)
    return best[1]


def main(current_path, last_path, out_path):
    cur = json.load(open(current_path))
    cur = cur.get("data", cur)
    last = json.load(open(last_path))
    last = last.get("data", last)
    this = prep(cur["match_xg"])
    prev = prep(last["matches"])
    prior_last = P.prior_from_table(last["prior_last"])
    prior_this = P.prior_from_table(last["prior_this"])
    in_use = {**P.PARAMS, **(cur.get("tuned_params") or {})}

    hold = {m["id"] for m in this[-HOLDOUT:]}
    tune_this = {m["id"] for m in this[:-HOLDOUT]}
    search_sets = [(prev, prior_last, {m["id"] for m in prev}), (this, prior_this, tune_this)]
    hold_set = [(this, prior_this, hold)]

    cand = search(search_sets, in_use)
    s_old, s_new = summary(scored(search_sets, in_use)), summary(scored(search_sets, cand))
    h_old, h_new = summary(scored(hold_set, in_use)), summary(scored(hold_set, cand))
    adopt = cand != in_use and h_new["logloss"] <= h_old["logloss"] - MARGIN and s_new["logloss"] <= s_old["logloss"]
    chosen = cand if adopt else in_use
    season_rows = scored([(this, prior_this, {m["id"] for m in this})], chosen)
    out = {"date": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "games_this_season": len(this),
           "adopted": adopt, "params_in_use": in_use, "candidate": cand, "chosen": chosen,
           "search": {"in_use": s_old, "candidate": s_new}, "holdout": {"in_use": h_old, "candidate": h_new},
           "this_season_with_chosen": summary(season_rows)}
    with open(out_path, "w") as f:
        json.dump(out, f)
    print(json.dumps({k: out[k] for k in ("adopted", "search", "holdout", "this_season_with_chosen")}), file=sys.stderr)


if __name__ == "__main__":
    main(*sys.argv[1:4])
