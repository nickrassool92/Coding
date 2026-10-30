"""Win model for a race: features from each runner's form, a conditional logit fitted on past races,
then a second stage that blends the model with the betting market.

P(runner i wins) = exp(score_i) / sum over the field of exp(score_j)
Stage 1: score = w . features (form only).
Stage 2: score = a * stage-1 score + b * log(market probability), fitted on races stage 1 never saw.
Place chances come from simulating the full finishing order (see places()).
"""
import math
import random
from datetime import date

FEATURES = [
    "last_pos", "last_margin", "avg3_margin", "last_sp", "avg3_sp", "class_rise", "class_avg3_rise",
    "hcp_rel", "has_hcp", "weight_rel", "barrier_rel", "barrier_short", "days_log", "first_up", "first_up_rate",
    "dist_change", "dist_rate", "track_rate", "cond_rate", "career_win", "career_place", "starts_log",
    "age", "age_old", "female", "overseas", "no_form", "best_rating_rel",
]


def rate(rec, prior_rate, k=3.0):
    """Place rate (wins + seconds + thirds over starts) shrunk towards prior_rate by k starts."""
    starts, w, s, t = rec
    return (w + s + t + prior_rate * k) / (starts + k)


def cond_group(cond):
    c = (cond or "").lower()
    for name in ("heavy", "soft", "firm", "synthetic"):
        if c.startswith(name[:4]):
            return name
    return "good"


def features(race, runner, today, condition=None):
    """Feature dict for one runner. `today` is the race date (ISO string); `condition` the track rating."""
    field = [r for r in race["runners"]]
    n = max(2, len(field))
    starts = [s for s in runner.get("starts", []) if s["date"] < today]
    last = starts[0] if starts else None
    recent = starts[:3]
    d0 = date.fromisoformat(today)
    days = (d0 - date.fromisoformat(last["date"])).days if last else 365
    cap = lambda m: min(10.0, m if m is not None else 6.0)
    sp_score = lambda s: max(-3.0, min(2.0, math.log(s["field"] / s["sp"]))) if s.get("sp") else -1.0
    weights = [r["weight"] for r in field if r.get("weight")]
    hcps = [r["hcp"] for r in field if r.get("hcp")]
    career = runner.get("career") or [0, 0, 0, 0]
    car_place = rate(career, 0.3)
    group = cond_group(condition or race.get("track_condition"))
    cond_rec = runner.get({"good": "good", "soft": "soft", "heavy": "heavy", "firm": "firm"}.get(group, "good")) or [0, 0, 0, 0]
    ratings = [s["rating"] for s in starts[:6] if s.get("rating")]
    race_ratings = [max(s["rating"] for s in r.get("starts", [])[:6] if s.get("rating")) for r in field
                    if any(s.get("rating") for s in r.get("starts", [])[:6])]
    f = {
        "last_pos": (last["pos"] - 1) / max(1, last["field"] - 1) if last else 0.5,
        "last_margin": cap(last["margin"]) if last else 5.0,
        "avg3_margin": sum(cap(s["margin"]) for s in recent) / len(recent) if recent else 5.0,
        "last_sp": sp_score(last) if last else -1.0,
        "avg3_sp": sum(sp_score(s) for s in recent) / len(recent) if recent else -1.0,
        "class_rise": race["class"] - last["class"] if last else 0.0,
        "class_avg3_rise": race["class"] - sum(s["class"] for s in recent) / len(recent) if recent else 0.0,
        "hcp_rel": (runner["hcp"] - sum(hcps) / len(hcps)) / 5 if runner.get("hcp") and hcps else 0.0,
        "has_hcp": 1.0 if runner.get("hcp") else 0.0,
        "weight_rel": (runner["weight"] - sum(weights) / len(weights)) if runner.get("weight") and weights else 0.0,
        "barrier_rel": ((runner["barrier"] or 1) - 1) / (n - 1) if runner.get("barrier") else 0.5,
        "barrier_short": (((runner["barrier"] or 1) - 1) / (n - 1)) * (1600 / race["distance"]) if runner.get("barrier") and race.get("distance") else 0.5,
        "days_log": math.log1p(days),
        "first_up": 1.0 if days > 70 else 0.0,
        "first_up_rate": (rate(runner.get("first_up") or [0, 0, 0, 0], car_place) - car_place) if days > 70 else 0.0,
        "dist_change": math.log(race["distance"] / last["distance"]) if last and race.get("distance") else 0.0,
        "dist_rate": rate(runner.get("dist") or [0, 0, 0, 0], car_place) - car_place,
        "track_rate": rate(runner.get("track") or [0, 0, 0, 0], car_place) - car_place,
        "cond_rate": rate(cond_rec, car_place) - car_place,
        "career_win": (career[1] + 0.12 * 3) / (career[0] + 3),
        "career_place": car_place,
        "starts_log": math.log1p(career[0]),
        "age": (runner.get("age") or 4) - 4,
        "age_old": max(0, (runner.get("age") or 4) - 6),
        "female": 1.0 if (runner.get("sex") or "") in ("mare", "filly") else 0.0,
        "overseas": 1.0 if runner.get("country") not in ("AUS", "NZ", None) else 0.0,
        "no_form": 0.0 if starts else 1.0,
        "best_rating_rel": ((max(ratings) - sum(race_ratings) / len(race_ratings)) / 5) if ratings and race_ratings else 0.0,
    }
    return [f[k] for k in FEATURES]


# ---------- conditional logit ----------

def softmax(scores):
    m = max(scores)
    e = [math.exp(s - m) for s in scores]
    t = sum(e)
    return [x / t for x in e]


def solve(A, b):
    """Solve A x = b by Gaussian elimination with partial pivoting (A is small and positive definite)."""
    n = len(b)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(M[r][c]))
        M[c], M[piv] = M[piv], M[c]
        for r in range(c + 1, n):
            f = M[r][c] / M[c][c]
            for k in range(c, n + 1):
                M[r][k] -= f * M[c][k]
    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        x[r] = (M[r][n] - sum(M[r][k] * x[k] for k in range(r + 1, n))) / M[r][r]
    return x


def newton(Z, n, l2, iters=25):
    """Maximise the conditional log-likelihood of winners minus l2/2 * |w|^2 by Newton's method.
    Z: list of (rows of features, winner index)."""
    w = [0.0] * n
    for _ in range(iters):
        g = [-l2 * v for v in w]
        H = [[l2 if i == j else 0.0 for j in range(n)] for i in range(n)]
        for X, wi in Z:
            p = softmax([sum(a * b for a, b in zip(w, x)) for x in X])
            mean = [sum(p[i] * X[i][j] for i in range(len(X))) for j in range(n)]
            for j in range(n):
                g[j] += X[wi][j] - mean[j]
            for i, x in enumerate(X):
                pi = p[i]
                for j in range(n):
                    pj = pi * x[j]
                    Hj = H[j]
                    for k in range(j, n):
                        Hj[k] += pj * x[k]
            for j in range(n):
                for k in range(j, n):
                    H[j][k] -= mean[j] * mean[k]
        for j in range(n):
            for k in range(j):
                H[j][k] = H[k][j]
        step = solve(H, g)
        w = [a + b for a, b in zip(w, step)]
        if max(abs(v) for v in step) < 1e-6:
            break
    return w


def fit(races, n_feat, l2=2.0):
    """races: list of (X, winner_index). Features are standardised first; returns (weights, means, sds)."""
    rows = [x for X, _ in races for x in X]
    means = [sum(r[j] for r in rows) / len(rows) for j in range(n_feat)]
    sds = [max(1e-6, math.sqrt(sum((r[j] - means[j]) ** 2 for r in rows) / len(rows))) for j in range(n_feat)]
    Z = [([[(x[j] - means[j]) / sds[j] for j in range(n_feat)] for x in X], wi) for X, wi in races]
    return newton(Z, n_feat, l2), means, sds


def score(w, means, sds, x):
    return sum(w[j] * (x[j] - means[j]) / sds[j] for j in range(len(w)))


def fit_blend(races):
    """races: list of (model_scores, market_logp, winner_index). Fits a and b in score = a*model + b*log p_market."""
    return newton([([[x, y] for x, y in zip(sc, m)], wi) for sc, m, wi in races], 2, 1e-6)


def market_logp(odds):
    """Log win probabilities from decimal odds, with the bookmaker's margin taken out."""
    inv = [1 / o if o and o > 1 else 0.0 for o in odds]
    t = sum(inv) or 1.0
    return [math.log(max(1e-4, v / t)) for v in inv]


# ---------- places ----------

def places(p_win, n_places=3, sims=20000, discount=0.85, seed=7):
    """Chance of finishing in the first n_places for each runner, by simulating the finishing order.
    After the winner, the rest are drawn from win chances raised to `discount` (below 1 flattens them),
    which fixes the well-known overrating of favourites for places by the plain Harville method."""
    rng = random.Random(seed)
    n = len(p_win)
    later = [p ** discount for p in p_win]
    counts = [[0] * n for _ in range(n_places)]
    for _ in range(sims):
        left = list(range(n))
        weights = list(p_win)
        for k in range(min(n_places, n)):
            tot = sum(weights[i] for i in left)
            r = rng.random() * tot
            for i in left:
                r -= weights[i]
                if r <= 0:
                    break
            counts[k][i] += 1
            left.remove(i)
            weights = later
    return [[c / sims for c in row] for row in counts]
