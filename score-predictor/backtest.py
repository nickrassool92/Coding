"""Backtest for the Full Time model: replays the season in kick-off order, predicting each game
only from matches played before it (plus last season), and scores the predictions.

Usage: python3 -I backtest.py <matches.json> <last_season_league.json> [prior_games] [home] [xg_weight]
matches.json: [{"home", "away", "utc", "round", "hg", "ag", "hxg", "axg"}] for this season's finished games.
last_season_league.json: FotMob league data for last season (holds its xG table).
Missing players are not modelled here, because past team news is not available.
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import predict as P  # noqa: E402


def run(matches, last, prior_games, home, xg_weight):
    last_rows = {r["name"]: {"xg": r["xg"] / r["played"], "xga": r["xgConceded"] / r["played"]} for r in last}
    bottom = sorted(last, key=lambda r: r["pts"])[:3]
    promoted = {"xg": sum(r["xg"] / r["played"] for r in bottom) / 3, "xga": sum(r["xgConceded"] / r["played"] for r in bottom) / 3}
    league_avg = sum(v["xg"] for v in last_rows.values()) / len(last_rows)
    teams = sorted({m["home"] for m in matches} | {m["away"] for m in matches})

    rows = []
    for m in sorted(matches, key=lambda x: x["utc"]):
        before = [x for x in matches if x["utc"] < m["utc"]]
        rating = {}
        for t in teams:
            g = [x for x in before if t in (x["home"], x["away"])]
            n = len(g)
            xf = sum(x["hxg"] if x["home"] == t else x["axg"] for x in g)
            xa = sum(x["axg"] if x["home"] == t else x["hxg"] for x in g)
            gf = sum(x["hg"] if x["home"] == t else x["ag"] for x in g)
            ga = sum(x["ag"] if x["home"] == t else x["hg"] for x in g)
            prior = last_rows.get(t, promoted)
            pf = 0.8 * prior["xg"] + 0.2 * league_avg
            pa = 0.8 * prior["xga"] + 0.2 * league_avg
            f_now = xg_weight * xf + (1 - xg_weight) * gf
            a_now = xg_weight * xa + (1 - xg_weight) * ga
            rating[t] = {"for": (f_now + pf * prior_games) / (n + prior_games),
                         "against": (a_now + pa * prior_games) / (n + prior_games)}
        avg = sum(r["for"] for r in rating.values()) / len(rating)
        h, a = m["home"], m["away"]
        lh = avg * (rating[h]["for"] / avg) * (rating[a]["against"] / avg) * home
        la = avg * (rating[a]["for"] / avg) * (rating[h]["against"] / avg) * P.AWAY
        mat = P.score_matrix(lh, la)
        size = len(mat)
        ph = sum(mat[i][j] for i in range(size) for j in range(size) if i > j)
        pd = sum(mat[i][i] for i in range(size))
        pa = 1 - ph - pd
        outcome = max((ph, "H"), (pd, "D"), (pa, "A"))[1]
        cells = sorted(((mat[i][j], i, j) for i in range(size) for j in range(size)), reverse=True)
        pick = next(c for c in cells if (c[1] > c[2] and outcome == "H") or (c[1] == c[2] and outcome == "D") or (c[1] < c[2] and outcome == "A"))
        actual = "H" if m["hg"] > m["ag"] else "A" if m["hg"] < m["ag"] else "D"
        probs = {"H": ph, "D": pd, "A": pa}
        rows.append({"match": f"{h} v {a}", "round": m["round"], "pred": [pick[1], pick[2]], "result": [m["hg"], m["ag"]],
                     "probs": [round(ph, 3), round(pd, 3), round(pa, 3)], "xg_pred": [round(lh, 2), round(la, 2)],
                     "xg_actual": [m["hxg"], m["axg"]], "right": outcome == actual,
                     "exact": [pick[1], pick[2]] == [m["hg"], m["ag"]],
                     "brier": sum((probs[k] - (1 if k == actual else 0)) ** 2 for k in "HDA"),
                     "logloss": -math.log(max(1e-9, probs[actual])), "actual": actual})
    return rows


def summary(rows):
    n = len(rows)
    return {"games": n, "right": sum(r["right"] for r in rows), "exact": sum(r["exact"] for r in rows),
            "brier": round(sum(r["brier"] for r in rows) / n, 4), "logloss": round(sum(r["logloss"] for r in rows) / n, 4)}


def baseline(rows, probs):
    n = len(rows)
    brier = sum(sum((probs[k] - (1 if k == r["actual"] else 0)) ** 2 for k in "HDA") for r in rows) / n
    pick = max(probs, key=probs.get)
    return {"right": sum(r["actual"] == pick for r in rows), "brier": round(brier, 4),
            "logloss": round(sum(-math.log(probs[r["actual"]]) for r in rows) / n, 4)}


if __name__ == "__main__":
    matches = json.load(open(sys.argv[1]))
    last = json.load(open(sys.argv[2]))["table"][0]["data"]["table"]["xg"]
    pg = float(sys.argv[3]) if len(sys.argv) > 3 else P.PRIOR_GAMES
    hm = float(sys.argv[4]) if len(sys.argv) > 4 else P.HOME
    xw = float(sys.argv[5]) if len(sys.argv) > 5 else P.XG_WEIGHT
    rows = run(matches, last, pg, hm, xw)
    print(json.dumps({"model": summary(rows),
                      "always_home": baseline(rows, {"H": 0.46, "D": 0.25, "A": 0.29}),
                      "coin_flip": baseline(rows, {"H": 1 / 3, "D": 1 / 3, "A": 1 / 3}),
                      "rows": rows}))
