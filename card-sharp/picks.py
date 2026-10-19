"""Card Sharp picks without Claude: the top five "to be carded" picks for every upcoming game.

Usage: python3 -I picks.py <out.json> [previous.json]
Downloads FPL (card counts, minutes, availability, fixtures) and FotMob (referees, predicted or
confirmed lineups) and scores every likely starter with the same model the Claude refresh uses:
  rate = (yellows + prior * 5) / (minutes / 90 + 5)
  chance = 1 - exp(-rate * 85/90 * referee factor * derby factor)
Games that have kicked off keep their previous picks, so the page never changes a pick after kick-off.
It has no news, social media or tipster input: that only comes from the Claude refresh.
"""
import json
import math
import sys
import time
import unicodedata
import urllib.request
from datetime import datetime, timedelta, timezone

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
FPL = "https://fantasy.premierleague.com/api/"
FOTMOB = "https://www.fotmob.com/api/data/"
# FotMob club names that differ from FPL's.
ALIASES = {"AFC Bournemouth": "Bournemouth", "Brighton & Hove Albion": "Brighton", "Leeds United": "Leeds",
           "Manchester City": "Man City", "Manchester United": "Man Utd", "Newcastle United": "Newcastle",
           "Nottingham Forest": "Nott'm Forest", "Tottenham Hotspur": "Spurs"}
PRIOR = {2: 0.20, 3: 0.22, 4: 0.14}
POSITION = {2: "defence", 3: "midfield", 4: "attack"}
LEAGUE_REF_RATE = 3.9
DERBIES = [{"ARS", "TOT"}, {"ARS", "CHE"}, {"CHE", "TOT"}, {"LIV", "EVE"}, {"LIV", "MUN"}, {"MCI", "MUN"},
           {"NEW", "SUN"}, {"AVL", "WOL"}, {"CRY", "BHA"}, {"LEE", "MUN"}, {"WHU", "TOT"}, {"WHU", "CHE"},
           {"WHU", "MIL"}, {"FUL", "CHE"}, {"BRE", "FUL"}, {"NFO", "LEI"}, {"COV", "AVL"}, {"MCI", "LIV"}]
SOURCES = [{"name": "Fantasy Premier League (cards, minutes, availability)", "url": "https://fantasy.premierleague.com"},
           {"name": "FotMob (referees and lineups)", "url": "https://www.fotmob.com/leagues/47/overview/premier-league"}]


def get(url, tries=3):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception:
            if attempt == tries - 1:
                raise
            time.sleep(3 * (attempt + 1))


def norm(s):
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c)).replace("-", " ").replace(".", " ")


def utc(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def iso(d):
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


def matches_name(p, name):
    full = norm(p["first_name"] + " " + p["second_name"]).split()
    web = norm(p["web_name"]).strip()
    toks = norm(name).split()
    return bool(toks) and (norm(name).strip() == web or (toks[-1] in full and (len(toks) == 1 or toks[0] in full)))


def referee_of(details):
    ref = (details.get("matchFacts") or {}).get("infoBox", {}).get("Referee") or {}
    stats = {s.get("type"): s for s in ref.get("stats") or []}
    games = (stats.get("matches") or {}).get("value")
    yel = stats.get("yellowCards") or {}
    out = {"name": ref.get("text")}
    if games and yel.get("total") is not None:
        out.update(games=games, yellows=yel["total"], reds=(stats.get("redCards") or {}).get("value"))
    return out


def main(out_path, prev_path=None):
    prev = {}
    if prev_path:
        try:
            with open(prev_path) as f:
                prev = json.load(f)
        except (OSError, ValueError):
            prev = {}
    prev_fx = {f["id"]: f for f in prev.get("fixtures", [])}
    now = datetime.now(timezone.utc)

    boot = get(FPL + "bootstrap-static/")
    fixtures = get(FPL + "fixtures/")
    league = get(FOTMOB + "leagues?id=47")
    teams = {t["id"]: t for t in boot["teams"]}
    fm_matches = league["fixtures"]["allMatches"]
    fpl_id = {t["name"]: t["id"] for t in boot["teams"]}
    full_name = {}  # FPL team id -> FotMob's full club name, which the page shows
    for m in fm_matches:
        for side in ("home", "away"):
            tid = fpl_id.get(ALIASES.get(m[side]["name"], m[side]["name"]))
            if tid:
                full_name[tid] = m[side]["name"]
    name_of = lambda tid: full_name.get(tid, teams[tid]["name"])

    played = {tid: 0 for tid in teams}
    for f in fixtures:
        if f["finished"]:
            played[f["team_h"]] += 1
            played[f["team_a"]] += 1
    by_team = {}
    for p in boot["elements"]:
        by_team.setdefault(p["team"], []).append(p)

    # The current and next gameweek, dropping games that kicked off more than 3 hours ago.
    upcoming = [f for f in fixtures if f["event"] and f["kickoff_time"] and utc(f["kickoff_time"]) > now - timedelta(hours=3)]
    gws = sorted({f["event"] for f in upcoming})[:2]
    upcoming = sorted([f for f in upcoming if f["event"] in gws], key=lambda f: f["kickoff_time"])

    referees = dict(prev.get("referees", {}))
    out_fx = []
    for f in upcoming:
        h, a = teams[f["team_h"]], teams[f["team_a"]]
        fid = f"{h['short_name'].lower()}-{a['short_name'].lower()}"
        kick = utc(f["kickoff_time"])
        old = prev_fx.get(fid)
        if kick <= now and old:  # kicked off: keep the pre-match picks
            out_fx.append(old)
            continue
        fx = {"id": fid, "gw": f["event"], "home": name_of(h["id"]), "away": name_of(a["id"]), "kickoffUtc": iso(kick),
              "kickoffTbc": False, "referee": None, "lineupsConfirmed": False}
        m = next((m for m in fm_matches if m["status"].get("utcTime", "")[:16] == f["kickoff_time"][:16]
                  and fpl_id.get(ALIASES.get(m["home"]["name"], m["home"]["name"])) == h["id"]), None)
        details, lineup = {}, {}
        # FotMob only has referees and lineups in the last few days before a game.
        if m and kick - now < timedelta(days=4):
            try:
                details = get(FOTMOB + f"matchDetails?matchId={m['id']}")["content"]
                lineup = details.get("lineup") or {}
            except Exception:
                details = {}
            time.sleep(0.3)
        ref = referee_of(details) if details else {}
        if ref.get("name"):
            fx["referee"] = ref["name"]
            if ref.get("games"):
                referees[ref["name"]] = {"games": ref["games"], "yellows": ref["yellows"], "reds": ref.get("reds")}
        elif old and old.get("referee"):
            fx["referee"] = old["referee"]
        r = referees.get(fx["referee"] or "")
        ref_rate = r["yellows"] / r["games"] if r and r.get("games") else None
        ref_factor = (ref_rate / LEAGUE_REF_RATE) ** 0.7 if ref_rate else 1.0
        derby = 1.08 if {h["short_name"], a["short_name"]} in DERBIES else 1.0
        # lineupType is "predicted", "lastStarting11" (the previous game's XI) or "standard" once teams are named.
        ltype = (lineup.get("lineupType") or "").lower()
        fx["lineupsConfirmed"] = ltype == "standard" and kick - now < timedelta(hours=2)
        start_label = ("Confirmed starter" if fx["lineupsConfirmed"] else "Predicted to start" if ltype == "predicted"
                       else "Started last game")

        cands, absent = [], {}
        for side, tid in (("homeTeam", h["id"]), ("awayTeam", a["id"])):
            t = lineup.get(side) or {}
            starters = [p.get("name", "") for p in t.get("starters") or []]
            out = [p.get("name", "") for p in t.get("unavailable") or []]
            absent[tid] = [p["web_name"] for p in by_team[tid] if p["status"] in ("i", "s") and p["minutes"] > 0
                           or (p["status"] == "d" and (p["chance_of_playing_next_round"] or 0) < 50 and p["minutes"] > 0)]
            for p in by_team[tid]:
                if p["element_type"] == 1 or p["status"] in ("i", "s", "u", "n"):
                    continue
                if p["status"] == "d" and (p["chance_of_playing_next_round"] or 0) < 75:
                    continue
                if any(matches_name(p, n) for n in out):
                    continue
                if starters:
                    if not any(matches_name(p, n) for n in starters):
                        continue
                    start_note = start_label
                elif played[tid] and p["starts"] / played[tid] >= 0.6:
                    start_note = "Regular starter"
                else:
                    continue
                prior = PRIOR[p["element_type"]]
                rate = (p["yellow_cards"] + prior * 5) / (p["minutes"] / 90 + 5)
                prob = 1 - math.exp(-rate * 85 / 90 * ref_factor * derby)
                cands.append((prob, p, tid, start_note))
        cands.sort(key=lambda c: -c[0])
        picks = []
        for prob, p, tid, start_note in cands[:5]:
            y, s = p["yellow_cards"], p["starts"]
            ref_txt = f"with {fx['referee']} averaging {ref_rate:.1f} yellows a game" if ref_rate else "referee not known yet"
            per = y / s if s else 0
            picks.append({"player": p["web_name"], "team": name_of(tid), "probability": round(prob, 2),
                          "confidence": "high" if prob >= 0.35 else "medium" if prob >= 0.25 else "low",
                          "reasoning": f"{y} yellow{'' if y == 1 else 's'} in {s} start{'' if s == 1 else 's'} this season"
                                       f"{f', about {per:.2f} a game' if s else ''}. {start_note}, in {POSITION[p['element_type']]}, {ref_txt}."
                                       + (" Derby game." if derby > 1 else "")})
        hy, ay = (sum(p["yellow_cards"] for p in by_team[t]) / played[t] if played[t] else None for t in (h["id"], a["id"]))
        outlook = (f"{fx['referee']} is in charge" + (f" and averages {ref_rate:.1f} yellows a game." if ref_rate else ".")
                   if fx["referee"] else "Referee not announced yet.")
        if hy is not None and ay is not None:
            outlook += f" {fx['home']} pick up {hy:.1f} yellows a game, {fx['away']} {ay:.1f}."
        fx["analysis"] = {"outlook": outlook + " Picks are from the stats model only (no news or tipsters).",
                          "absent": "; ".join(f"{name_of(t)}: {', '.join(n)}" for t, n in absent.items() if n),
                          "picks": picks, "updatedAt": iso(now)}
        out_fx.append(fx)

    team_rows = {name_of(t): {"games": played[t], "ypg": round(sum(p["yellow_cards"] for p in by_team[t]) / played[t], 2) if played[t] else None}
                 for t in teams}
    players = sorted([{"name": p["web_name"], "team": name_of(p["team"]), "yellows": p["yellow_cards"], "apps": p["starts"],
                       "note": f"{p['red_cards']} red" if p["red_cards"] else ""}
                      for p in boot["elements"] if p["yellow_cards"] >= 2 or p["red_cards"]], key=lambda r: -r["yellows"])
    pack = {"season": prev.get("season", ""), "matchweek": min((fx["gw"] for fx in out_fx), default=None),
            "asOf": now.strftime("%Y-%m-%d"), "analysedAt": iso(now), "fixtures": out_fx, "referees": referees,
            "teams": team_rows, "players": players, "lastSeasonNote": prev.get("lastSeasonNote", ""),
            "notes": "Picks come from the stats model only: card rates from FPL, referees and lineups from FotMob. "
                     "Refreshed every hour, so confirmed lineups show up about an hour before kick-off.",
            "sources": SOURCES}
    with open(out_path, "w") as f:
        json.dump(pack, f, ensure_ascii=False, indent=1)
    print(f"{len(out_fx)} fixtures, gameweeks {gws}", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
