"""Gaffer fetcher: downloads everything model.py needs into a data folder.

Usage: python3 -I fetch.py <entry_id> <data_dir>
Writes bootstrap.json, fixtures.json, entry.json, history.json, transfers.json, picks.json,
summaries.json (every player's matches this season) and fotmob.json (predicted or confirmed
lineups for the next gameweek, and each club's non-league fixtures this season and ahead).
"""
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
FPL = "https://fantasy.premierleague.com/api/"
FOTMOB = "https://www.fotmob.com/api/data/"
# FotMob club names that differ from FPL's.
ALIASES = {"AFC Bournemouth": "Bournemouth", "Brighton & Hove Albion": "Brighton", "Leeds United": "Leeds",
           "Manchester City": "Man City", "Manchester United": "Man Utd", "Newcastle United": "Newcastle",
           "Nottingham Forest": "Nott'm Forest", "Tottenham Hotspur": "Spurs"}


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


def save(d, name, obj):
    with open(os.path.join(d, name), "w") as f:
        json.dump(obj, f)


def main(entry_id, d):
    os.makedirs(d, exist_ok=True)
    boot = get(FPL + "bootstrap-static/")
    fixtures = get(FPL + "fixtures/")
    entry = get(FPL + f"entry/{entry_id}/")
    save(d, "bootstrap.json", boot)
    save(d, "fixtures.json", fixtures)
    save(d, "entry.json", entry)
    save(d, "history.json", get(FPL + f"entry/{entry_id}/history/"))
    save(d, "transfers.json", get(FPL + f"entry/{entry_id}/transfers/"))
    picks = get(FPL + f"entry/{entry_id}/event/{entry['current_event']}/picks/")
    save(d, "picks.json", picks)

    # Match-by-match history for every player who has played, so the model can see each
    # player's recent starts and rebuild every club's starting XIs to measure rotation.
    squad = {p["element"] for p in picks["picks"]}
    pool = [p for p in boot["elements"] if p["id"] in squad or p["minutes"] > 0]
    summaries = {}
    for p in pool:
        try:
            hist = get(FPL + f"element-summary/{p['id']}/")["history"]
        except Exception:
            continue
        summaries[p["id"]] = [{"fixture": h["fixture"], "round": h["round"], "minutes": h["minutes"],
                               "starts": h["starts"], "kickoff": h["kickoff_time"]} for h in hist]
        time.sleep(0.1)
    save(d, "summaries.json", summaries)

    # FotMob: map clubs, read the next gameweek's lineups, and list each club's other fixtures.
    fpl_team = {t["name"]: t["id"] for t in boot["teams"]}
    league = get(FOTMOB + "leagues?id=47")
    matches = league["fixtures"]["allMatches"]
    fm_to_fpl = {}
    for m in matches:
        for side in ("home", "away"):
            name = m[side]["name"]
            tid = fpl_team.get(ALIASES.get(name, name))
            if tid:
                fm_to_fpl[m[side]["id"]] = tid
    next_ev = next(ev for ev in boot["events"] if ev["is_next"])
    next_fx = [f for f in fixtures if f["event"] == next_ev["id"]]
    lineups = {}
    for f in next_fx:
        m = next((m for m in matches if m["status"].get("utcTime", "")[:16] == (f["kickoff_time"] or "")[:16]
                  and fm_to_fpl.get(m["home"]["id"]) == f["team_h"]), None)
        if not m:
            continue
        try:
            lu = get(FOTMOB + f"matchDetails?matchId={m['id']}")["content"]["lineup"]
        except Exception:
            continue
        for side, tid in (("homeTeam", f["team_h"]), ("awayTeam", f["team_a"])):
            t = lu.get(side) or {}
            starters = [p.get("name", "") for p in t.get("starters") or []]
            if starters:
                lineups[tid] = {"type": lu.get("lineupType") or "predicted", "starters": starters,
                                "unavailable": [p.get("name", "") for p in t.get("unavailable") or []]}
        time.sleep(0.2)

    now = datetime.now(timezone.utc)
    others = {}
    for fm_id, tid in fm_to_fpl.items():
        try:
            fx = get(FOTMOB + f"teams?id={fm_id}")["fixtures"]["allFixtures"]["fixtures"]
        except Exception:
            continue
        rows = []
        for x in fx:
            comp = (x.get("tournament") or {}).get("name", "")
            when = (x.get("status") or {}).get("utcTime")
            if not when or comp == "Premier League":
                continue
            t = datetime.fromisoformat(when.replace("Z", "+00:00"))
            if now - timedelta(days=150) <= t <= now + timedelta(days=45):
                rows.append({"comp": comp, "utc": when})
        others[tid] = rows
        time.sleep(0.2)
    save(d, "fotmob.json", {"lineups": lineups, "other_fixtures": others})


if __name__ == "__main__":
    main(int(sys.argv[1]), sys.argv[2])
