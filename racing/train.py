"""Fit and test the Cup Day model on past metro meetings.

Usage: python3 -I train.py <meetings.txt> <cache_dir> <out_model.json>
meetings.txt lists meeting keys ("2026Oct17,VIC,Caulfield"), one per line. For each meeting the form
guide (as published before the races) is paired with the results. Meetings are split by date: the
earliest 70% fit the form model, the rest test it. The blend with the market (starting prices) is
fitted on the test meetings by two-fold cross-fitting, so its score is never measured on its own fit.
"""
import json
import math
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model as M  # noqa: E402
import ra  # noqa: E402


def key_date(key):
    return datetime.strptime(key.split(",")[0], "%Y%b%d").date().isoformat()


def build(keys, cache):
    """One row per race: features, winner index, starting prices and finishing positions."""
    rows = []
    for key in keys:
        try:
            form = ra.parse_form(ra.fetch("Form", key, cache))
            res = {r["race"]: r for r in ra.parse_results(ra.fetch("Results", key, cache))}
        except Exception as e:
            print("skip", key, e, file=sys.stderr)
            continue
        day = key_date(key)
        for race in form:
            out = res.get(race["race"])
            if not out:
                continue
            by_no = {r["no"]: r for r in out["runners"] if r.get("no")}
            runners = [r for r in race["runners"] if r["no"] in by_no and by_no[r["no"]]["finish"] and by_no[r["no"]]["sp"]]
            if len(runners) < 5 or not any(by_no[r["no"]]["finish"] == 1 for r in runners):
                continue
            race_now = dict(race, runners=runners, track_condition=out.get("track_condition"))
            X = [M.features(race_now, r, day, out.get("track_condition")) for r in runners]
            fin = [by_no[r["no"]]["finish"] for r in runners]
            rows.append({"key": key, "date": day, "race": race["race"], "name": race["name"], "X": X,
                         "winner": fin.index(1), "finish": fin, "sp": [by_no[r["no"]]["sp"] for r in runners]})
    return rows


def logloss(probs_by_race, rows):
    return sum(-math.log(max(1e-9, p[r["winner"]])) for p, r in zip(probs_by_race, rows)) / len(rows)


def top_pick(probs_by_race, rows):
    return sum(max(range(len(p)), key=p.__getitem__) == r["winner"] for p, r in zip(probs_by_race, rows))


def main(meetings_path, cache, out_path):
    keys = sorted({k.strip() for k in open(meetings_path) if k.strip()}, key=key_date)
    rows = build(keys, cache)
    rows.sort(key=lambda r: (r["date"], r["key"], r["race"]))
    dates = sorted({r["date"] for r in rows})
    cut = dates[int(len(dates) * 0.7)]
    tr, te = [r for r in rows if r["date"] < cut], [r for r in rows if r["date"] >= cut]
    print(f"{len(rows)} races, {sum(len(r['X']) for r in rows)} runners; fit {len(tr)} races, test {len(te)}", file=sys.stderr)

    nf = len(M.FEATURES)
    w, means, sds = M.fit([(r["X"], r["winner"]) for r in tr], nf)
    model_p = lambda r: M.softmax([M.score(w, means, sds, x) for x in r["X"]])
    market_p = lambda r: [math.exp(v) for v in M.market_logp(r["sp"])]
    n = len(te)
    uniform = sum(math.log(len(r["X"])) for r in te) / n
    s_model = [model_p(r) for r in te]
    s_mkt = [market_p(r) for r in te]

    # Blend: cross-fit a, b on halves of the test set.
    half = te[: n // 2], te[n // 2:]
    blended = []
    ab = []
    for fit_on, score_on in ((half[1], half[0]), (half[0], half[1])):
        a, b = M.fit_blend([([M.score(w, means, sds, x) for x in r["X"]], M.market_logp(r["sp"]), r["winner"]) for r in fit_on])
        ab.append((a, b))
        for r in score_on:
            blended.append(M.softmax([a * M.score(w, means, sds, x) + b * m for x, m in zip(r["X"], M.market_logp(r["sp"]))]))
    a_all, b_all = M.fit_blend([([M.score(w, means, sds, x) for x in r["X"]], M.market_logp(r["sp"]), r["winner"]) for r in te])

    # 5-fold cross-validation by date blocks over all races: out-of-fold model scores, then the blend
    # tested the same way. More stable than a single split when the sample is a few hundred races.
    folds = 5
    order = sorted(range(len(rows)), key=lambda i: (rows[i]["date"], rows[i]["key"], rows[i]["race"]))
    fold_of = {i: k * folds // len(order) for k, i in enumerate(order)}
    oof = [None] * len(rows)
    for f in range(folds):
        wf, mf, sf = M.fit([(rows[i]["X"], rows[i]["winner"]) for i in order if fold_of[i] != f], nf)
        for i in order:
            if fold_of[i] == f:
                oof[i] = [M.score(wf, mf, sf, x) for x in rows[i]["X"]]
    cv = {"model": 0.0, "market": 0.0, "blend": 0.0, "model_top": 0, "market_top": 0, "blend_top": 0}
    blends = []
    for f in range(folds):
        trn = [(oof[i], M.market_logp(rows[i]["sp"]), rows[i]["winner"]) for i in order if fold_of[i] != f]
        ab_f = M.fit_blend(trn)
        blends.append([round(v, 3) for v in ab_f])
        for i in order:
            if fold_of[i] != f:
                continue
            r, sc, mk = rows[i], oof[i], M.market_logp(rows[i]["sp"])
            for name, p in (("model", M.softmax(sc)), ("market", M.softmax(mk)),
                            ("blend", M.softmax([ab_f[0] * x + ab_f[1] * y for x, y in zip(sc, mk)]))):
                cv[name] -= math.log(max(1e-9, p[r["winner"]]))
                cv[name + "_top"] += max(range(len(p)), key=p.__getitem__) == r["winner"]
    for k in ("model", "market", "blend"):
        cv[k] = round(cv[k] / len(rows), 4)
    # Temperature for the model on its own (used when a race has no odds), fitted on out-of-fold scores.
    temp = M.newton([([[x] for x in oof[i]], rows[i]["winner"]) for i in order], 1, 1e-6)[0]
    ab_oof = M.fit_blend([(oof[i], M.market_logp(rows[i]["sp"]), rows[i]["winner"]) for i in order])
    a_all, b_all = ab_oof

    # Refit the form model on everything for use on Cup Day.
    w_all, means_all, sds_all = M.fit([(r["X"], r["winner"]) for r in rows], nf)
    report = {
        "races": len(rows), "fit_races": len(tr), "test_races": n, "cut_date": cut,
        "test": {"uniform_logloss": round(uniform, 4), "model_logloss": round(logloss(s_model, te), 4),
                 "market_logloss": round(logloss(s_mkt, te), 4), "blend_logloss": round(logloss(blended, te), 4),
                 "model_top_pick_wins": top_pick(s_model, te), "market_fav_wins": top_pick(s_mkt, te),
                 "blend_top_pick_wins": top_pick(blended, te)},
        "blend_cross_fit": ab, "blend": [a_all, b_all], "cv": cv, "cv_blends": blends,
        "weights": dict(zip(M.FEATURES, [round(x, 4) for x in w_all])),
    }
    with open(out_path, "w") as f:
        json.dump({"features": M.FEATURES, "w": w_all, "means": means_all, "sds": sds_all,
                   "blend": [a_all, b_all], "temp": temp, "report": report}, f, indent=1)
    print(json.dumps(report["test"]), file=sys.stderr)
    print("cv", json.dumps(cv), blends, [round(a_all, 3), round(b_all, 3)], "temp", round(temp, 3), file=sys.stderr)
    print(json.dumps(report["weights"]), file=sys.stderr)


if __name__ == "__main__":
    main(*sys.argv[1:4])
