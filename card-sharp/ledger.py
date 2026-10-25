"""Card Sharp track record: records every pick at kick-off and checks whether the player was carded.

Usage: python3 -I ledger.py <pack.json> <ledger.json> <out_ledger.json> <out_summary.json>
pack.json is packs/current; ledger.json the previous ledger/picks document (may be missing).
1. Every fixture in the pack that has kicked off has its five picks copied into the ledger once,
   exactly as they stood at kick-off (lineup checks finish 45 minutes before).
2. Picks from games that finished are graded from FotMob's match events: carded (yellow or red),
   not carded, or void when the player did not get on the pitch (bookmakers void those bets).
3. The summary compares predicted chances with what happened. Once 250 picks are graded it also
   sets `applied_multiplier`, a correction to the card rate that the daily refresh applies.
"""
import json
import math
import sys
import time
import unicodedata
import urllib.request
from datetime import datetime, timedelta, timezone

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
FOTMOB = "https://www.fotmob.com/api/data/"
MIN_PICKS = 250     # graded picks needed before the correction is applied
PRIOR_PICKS = 150   # the correction is shrunk towards 1.0 as if this many picks had matched the model exactly
BINS = [(0, 0.2), (0.2, 0.25), (0.25, 0.3), (0.3, 1.01)]


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


def norm(s):
    s = unicodedata.normalize("NFKD", (s or "").lower())
    return " ".join("".join(c for c in s if not unicodedata.combining(c)).replace("-", " ").replace(".", " ").split())


def same_player(pick_name, full_name):
    """A pick's name (usually the FPL short name, e.g. "Van Hecke" or "N.Jackson") against FotMob's full name."""
    p, f = norm(pick_name).split(), norm(full_name).split()
    if not p or not f:
        return False
    if " ".join(p) == " ".join(f):
        return True
    last = p[-1]
    if last not in f:
        return False
    # every other part of the pick name must appear too, or be an initial of a part
    return all(t in f or (len(t) == 1 and any(x.startswith(t) for x in f)) for t in p[:-1])


def load(path, default):
    try:
        with open(path) as f:
            d = json.load(f)
        return d.get("data", d) if isinstance(d, dict) else d
    except (OSError, ValueError):
        return default


def find_match(matches, kickoff, home, away):
    best = None
    for m in matches:
        t = m["status"].get("utcTime")
        if not t or abs((utc(t) - utc(kickoff)).total_seconds()) > 2 * 3600:
            continue
        score = sum(norm(x) in norm(m[s]["name"]) or norm(m[s]["name"]) in norm(x) for x, s in ((home, "home"), (away, "away")))
        if score and (best is None or score > best[0]):
            best = (score, m)
    return best[1] if best else None


def grade(entry, details):
    events = (details.get("matchFacts") or {}).get("events", {}).get("events", [])
    cards = [e for e in events if e.get("type") == "Card"]
    hit = next((e for e in cards if same_player(entry["player"], e.get("fullName") or e.get("nameStr") or (e.get("player") or {}).get("name", ""))), None)
    if hit:
        return "carded", hit.get("card")
    played = False
    for side in ("homeTeam", "awayTeam"):
        t = (details.get("lineup") or {}).get(side) or {}
        for p in t.get("starters") or []:
            played |= same_player(entry["player"], p.get("name", ""))
        for p in t.get("subs") or []:
            came_on = any(s.get("type") == "subIn" for s in (p.get("performance") or {}).get("substitutionEvents") or [])
            played |= came_on and same_player(entry["player"], p.get("name", ""))
    return ("not_carded" if played else "void"), None


def multiplier(graded):
    """The k that makes sum(1 - exp(-k * rate)) equal the cards actually shown, shrunk towards 1."""
    rates = [-math.log(1 - min(0.95, e["probability"])) for e in graded]
    hits = sum(e["result"] == "carded" for e in graded)
    lo, hi = 0.2, 5.0
    for _ in range(60):
        k = (lo + hi) / 2
        if sum(1 - math.exp(-k * r) for r in rates) < hits:
            lo = k
        else:
            hi = k
    raw = (lo + hi) / 2
    return raw, (len(graded) * raw + PRIOR_PICKS) / (len(graded) + PRIOR_PICKS)


def summarise(picks, now):
    graded = [e for e in picks if e.get("result") in ("carded", "not_carded")]
    out = {"updatedAt": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "picks": len(picks), "graded": len(graded),
           "void": sum(e.get("result") == "void" for e in picks), "pending": sum(not e.get("result") for e in picks),
           "min_picks": MIN_PICKS, "applied_multiplier": 1.0}
    if not graded:
        return out
    hits = sum(e["result"] == "carded" for e in graded)
    expected = sum(e["probability"] for e in graded)
    out.update(carded=hits, expected=round(expected, 1),
               brier=round(sum((e["probability"] - (e["result"] == "carded")) ** 2 for e in graded) / len(graded), 4),
               bins=[{"from": a, "to": min(b, 1.0), "picks": len(g), "carded": sum(e["result"] == "carded" for e in g),
                      "predicted": round(sum(e["probability"] for e in g) / len(g), 3) if g else None}
                     for a, b in BINS for g in [[e for e in graded if a <= e["probability"] < b]]],
               by_confidence={c: {"picks": len(g), "carded": sum(e["result"] == "carded" for e in g)}
                              for c in ("high", "medium", "low") for g in [[e for e in graded if e.get("confidence") == c]] if g},
               by_gw=[{"gw": gw, "picks": len(g), "carded": sum(e["result"] == "carded" for e in g),
                       "expected": round(sum(e["probability"] for e in g), 1)}
                      for gw in sorted({e["gw"] for e in graded}) for g in [[e for e in graded if e["gw"] == gw]]])
    raw, shrunk = multiplier(graded)
    out["raw_multiplier"] = round(raw, 3)
    out["suggested_multiplier"] = round(shrunk, 3)
    if len(graded) >= MIN_PICKS:
        out["applied_multiplier"] = round(shrunk, 3)
    return out


def main(pack_path, ledger_path, out_ledger, out_summary):
    pack = load(pack_path, {})
    ledger = load(ledger_path, {"picks": []})
    picks = ledger.get("picks", [])
    have = {(e["fixture"], e["player"]) for e in picks}
    now = datetime.now(timezone.utc)

    for f in pack.get("fixtures", []):
        if not f.get("kickoffUtc") or utc(f["kickoffUtc"]) > now:
            continue
        for rank, p in enumerate((f.get("analysis") or {}).get("picks") or [], 1):
            if (f["id"], p["player"]) in have:
                continue
            picks.append({"fixture": f["id"], "gw": f.get("gw"), "kickoffUtc": f["kickoffUtc"], "home": f["home"], "away": f["away"],
                          "referee": f.get("referee"), "lineupsConfirmed": bool(f.get("lineupsConfirmed")), "rank": rank,
                          "player": p["player"], "team": p.get("team"), "probability": float(p["probability"]),
                          "confidence": p.get("confidence"), "result": None, "card": None})
            have.add((f["id"], p["player"]))

    todo = [e for e in picks if not e.get("result") and utc(e["kickoffUtc"]) < now - timedelta(hours=2, minutes=30)]
    if todo:
        matches = get(FOTMOB + "leagues?id=47")["fixtures"]["allMatches"]
        cache = {}
        for e in todo:
            m = find_match(matches, e["kickoffUtc"], e["home"], e["away"])
            if not m or not m["status"].get("finished"):
                continue
            if m["id"] not in cache:
                try:
                    cache[m["id"]] = get(FOTMOB + f"matchDetails?matchId={m['id']}")["content"]
                except Exception as ex:
                    print(f"match {m['id']} failed: {ex}", file=sys.stderr)
                    continue
                time.sleep(0.3)
            e["result"], e["card"] = grade(e, cache[m["id"]])

    with open(out_ledger, "w") as f:
        json.dump({"picks": picks, "updatedAt": now.strftime("%Y-%m-%dT%H:%M:%SZ")}, f, ensure_ascii=False)
    summary = summarise(picks, now)
    with open(out_summary, "w") as f:
        json.dump(summary, f, ensure_ascii=False)
    print(json.dumps({k: v for k, v in summary.items() if k not in ("bins", "by_gw", "by_confidence")}), file=sys.stderr)


if __name__ == "__main__":
    main(*sys.argv[1:5])
