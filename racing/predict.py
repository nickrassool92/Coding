"""Cup Day predictions: win and place chances for every race, value against the odds, and a long shot.

Usage: python3 -I predict.py <model.json> <out.json> [previous.json] [odds.json] [cache_dir]
model.json comes from train.py. odds.json (optional) maps race number to {runner number: decimal odds},
gathered on race morning; each race's prices are blended with the model only when most of the field is priced.
Races that have started keep their previous predictions, so nothing changes after the jump.
"""
import json
import math
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model as M  # noqa: E402
import ra  # noqa: E402

KEY = "2026Nov03,VIC,Flemington"
RACE_DATE = "2026-11-03"
UTC_OFFSET = 11            # Melbourne is on daylight time (AEDT) in November
LONGSHOT_MIN = 15.0        # a long shot is $15 or longer
LONGSHOT_PLACE = 0.12      # with a real chance to place, since it is backed each way
# Past races show outsiders are over-bet (the market works best sharpened towards favourites), so the
# long shot is the best-value outsider and is labelled honestly: genuine value only if value >= 1.
MIN_PRICED = 0.8           # share of the field that must be priced before odds are blended in


def start_utc(time_str):
    t = datetime.strptime(f"{RACE_DATE} {time_str}", "%Y-%m-%d %I:%M%p")
    return (t - timedelta(hours=UTC_OFFSET)).replace(tzinfo=timezone.utc)


def nice_name(name):
    """ROYAL PRESS (NZ) -> Royal Press (NZ); apostrophes don't start a new capital."""
    base, _, country = name.partition(" (")
    words = " ".join(w[:1].upper() + w[1:].lower() for w in base.split())
    return words + (f" ({country}" if country else "")


def plural(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


def notes(race, r):
    """A few plain-English facts about a runner's chances."""
    out = []
    starts = r.get("starts") or []
    n = len(race["runners"])
    if not starts:
        out.append("No race form yet")
    else:
        last = starts[0]
        days = (datetime.fromisoformat(RACE_DATE) - datetime.fromisoformat(last["date"])).days
        if last["pos"] == 1:
            out.append(f"Won last start ({last['venue'].title().rstrip('.')} {last['distance']}m)")
        elif last["pos"] <= 3:
            out.append(f"Placed last start ({last['pos']} of {last['field']}, {last['margin'] or 0:.1f}L)")
        if days > 70:
            fu = r.get("first_up") or [0, 0, 0, 0]
            out.append(f"First-up after {days} days" + (f" ({plural(fu[1], 'win')} from {fu[0]} first-up)" if fu[0] else ""))
        if race["class"] - last["class"] >= 1:
            out.append("Up in class")
        elif last["class"] - race["class"] >= 1:
            out.append("Down in class")
    dist = r.get("dist") or [0, 0, 0, 0]
    if dist[0] >= 2 and dist[1] / dist[0] >= 0.4:
        out.append(f"Strong at the distance ({plural(dist[1], 'win')} from {dist[0]})")
    elif dist[0] == 0 and starts:
        out.append("First time at the distance")
    trk = r.get("track") or [0, 0, 0, 0]
    if trk[0] >= 2 and trk[1] >= 1:
        out.append(f"Has won at Flemington ({plural(trk[1], 'win')} from {trk[0]})")
    if r.get("barrier") and n >= 10 and r["barrier"] >= n - 2 and race["distance"] <= 1600:
        out.append(f"Wide barrier ({r['barrier']}) over {race['distance']}m")
    if r.get("barrier") and r["barrier"] <= 3 and race["distance"] <= 1400:
        out.append(f"Good inside draw ({r['barrier']})")
    if r.get("gear_change"):
        out.append("Gear change")
    return out[:4]


def main(model_path, out_path, prev_path=None, odds_path=None, cache=None):
    mdl = json.load(open(model_path))
    mdl = mdl.get("data", mdl) if "w" not in mdl else mdl  # a saved database document may wrap the fields
    prev = {}
    if prev_path and os.path.exists(prev_path):
        prev = json.load(open(prev_path))
        prev = prev.get("data", prev)
    odds = {}
    if odds_path and os.path.exists(odds_path):
        o = json.load(open(odds_path))
        odds = {int(k): {int(n): float(v) for n, v in d.items() if v} for k, d in (o.get("data", o).get("races") or {}).items()}
    now = datetime.now(timezone.utc)
    form = ra.parse_form(ra.fetch("Form", KEY, cache, max_age=600))
    try:
        scr = ra.parse_scratchings(ra.fetch("Scratchings", KEY, cache, max_age=600))
    except Exception:
        scr = {"track_rating": None, "weather": None, "scratched": {}}
    rating = scr["track_rating"] or "Good 4"
    rating_note = "" if scr["track_rating"] else " (expected; official rating not out yet)"
    prev_races = {r["race"]: r for r in prev.get("races", [])}
    a, b = mdl["blend"]

    races = []
    for race in form:
        jump = start_utc(race["time"]) if race.get("time") else None
        if jump and jump <= now and race["race"] in prev_races:
            races.append({**prev_races[race["race"]], "status": "closed"})
            continue
        gone = set(scr["scratched"].get(race["race"], []))
        field = [r for r in race["runners"] if r["no"] not in gone]
        if len(field) < 2:
            continue
        race_now = dict(race, runners=field, track_condition=rating.replace(" ", ""))
        X = [M.features(race_now, r, RACE_DATE, rating.replace(" ", "")) for r in field]
        s = [M.score(mdl["w"], mdl["means"], mdl["sds"], x) for x in X]
        p_model = M.softmax([mdl.get("temp", 1.0) * v for v in s])  # model alone, calibrated
        priced = odds.get(race["race"], {})
        have = [r["no"] for r in field if priced.get(r["no"], 0) > 1]
        blended = len(have) >= MIN_PRICED * len(field)
        if blended:
            mk = [priced.get(r["no"]) or 1 / max(1e-3, p) for r, p in zip(field, p_model)]
            p = M.softmax([a * v + bb for v, bb in zip(s, [b * x for x in M.market_logp(mk)])])
        else:
            mk = [priced.get(r["no"]) for r in field]
            p = p_model
        n_places = 3 if len(field) >= 8 else 2
        pos = M.places(p, n_places=max(n_places, 4 if race["race"] == 7 else n_places), sims=20000)
        runners = []
        for i, r in enumerate(field):
            place = sum(pos[k][i] for k in range(n_places))
            row = {"no": r["no"], "name": nice_name(r["name"]), "barrier": r.get("barrier"), "weight": r.get("weight"),
                   "jockey": r.get("jockey"), "trainer": r.get("trainer"), "last10": r.get("last10"), "age": r.get("age"),
                   "sex": r.get("sex"), "score": round(s[i], 4), "win": round(p[i], 4), "place": round(place, 4),
                   "model_win": round(p_model[i], 4), "fair_win": round(1 / max(1e-4, p[i]), 2),
                   "fair_place": round(1 / max(1e-4, place), 2), "odds": mk[i] if priced.get(r["no"]) else None,
                   "notes": notes(race_now, r)}
            if race["race"] == 7:
                row["top4"] = round(sum(pos[k][i] for k in range(4)), 4)
            if row["odds"]:
                row["value"] = round(p[i] * row["odds"], 3)
            runners.append(row)
        runners.sort(key=lambda x: -x["win"])
        longshot = None
        if priced:
            cands = [x for x in runners if x["odds"] and x["odds"] >= LONGSHOT_MIN and x["place"] >= LONGSHOT_PLACE]
            if cands:
                c = max(cands, key=lambda x: (x["win"] * x["odds"], x["place"]))
                longshot = {"no": c["no"], "name": c["name"], "odds": c["odds"], "win": c["win"], "place": c["place"],
                            "edge": round(c["win"] * c["odds"] - 1, 3)}
        races.append({"race": race["race"], "time": race["time"], "start_utc": jump.strftime("%Y-%m-%dT%H:%M:%SZ") if jump else None,
                      "name": race["name"], "distance": race["distance"], "prize": race["prize"], "class": race["class"],
                      "conditions": race.get("summary") or race["conditions"][:200], "places_paid": n_places, "field_size": len(field),
                      "scratched": sorted(gone), "odds_blended": blended, "priced": len(have),
                      "runners": runners, "longshot": longshot, "status": "open"})

    open_ls = [dict(r["longshot"], race=r["race"]) for r in races if r.get("longshot") and r["status"] == "open"]
    out = {"meeting": {"key": KEY, "date": RACE_DATE, "venue": "Flemington", "track_rating": rating + rating_note, "weather": scr["weather"],
                       "updatedAt": now.strftime("%Y-%m-%dT%H:%M:%SZ")},
           "blend": [a, b], "model_report": mdl.get("report"), "races": sorted(races, key=lambda r: r["race"]),
           "longshot_of_day": max(open_ls, key=lambda x: (x["edge"], x["place"])) if open_ls else None,
           "odds_note": f"{sum(1 for r in races if r.get('odds_blended'))} of {len(races)} races priced" if odds else "no odds yet"}
    with open(out_path, "w") as f:
        json.dump(out, f, ensure_ascii=False)
    print(f"{len(races)} races, track {rating}, {out['odds_note']}", file=sys.stderr)


if __name__ == "__main__":
    args = sys.argv[1:] + [None] * 5
    main(args[0], args[1], args[2], args[3], args[4])
