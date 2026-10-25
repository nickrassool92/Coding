"""Gaffer model: projects FPL points for the next five gameweeks and plans transfers.

Usage: python3 -I model.py <entry_id> <data_dir> <out.json>
<data_dir> must hold bootstrap.json, fixtures.json, entry.json, history.json,
transfers.json and picks.json (the latest gameweek's picks) from the public FPL API.
fetch.py also adds summaries.json (recent matches) and fotmob.json (lineups and other
fixtures); without them the model falls back to season-long start rates.
"""
import json
import math
import os
import sys
import unicodedata
from datetime import datetime, timezone

HORIZON = 5
WEIGHTS = [1.0, 0.9, 0.8, 0.7, 0.6]
POS = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}
GOAL_PTS = {1: 10, 2: 6, 3: 5, 4: 4}
CS_PTS = {1: 4, 2: 4, 3: 1, 4: 0}
POS_MEAN = {1: 3.2, 2: 3.3, 3: 3.8, 4: 4.0}
FDR_ATT = {1: 1.25, 2: 1.15, 3: 1.0, 4: 0.8, 5: 0.68}
FDR_DEF = {1: 1.35, 2: 1.2, 3: 1.0, 4: 0.7, 5: 0.5}
SQUAD_LIMIT = {1: 2, 2: 5, 3: 5, 4: 3}
HIT = 4
SAVED_FT = 1.0  # rough value, in points, of keeping a transfer in hand for another gameweek (counted for up to two)


def load(d, name, default=None):
    path = f"{d}/{name}"
    if default is not None and not os.path.exists(path):
        return default
    with open(path) as f:
        return json.load(f)


def norm(s):
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c)).replace("-", " ").replace(".", " ")


def utc(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def main(entry_id, d, out_path, calibration_path=None):
    b = load(d, "bootstrap.json")
    fixtures = load(d, "fixtures.json")
    entry = load(d, "entry.json")
    history = load(d, "history.json")
    transfers = load(d, "transfers.json")
    picks = load(d, "picks.json")
    summaries = {int(k): v for k, v in load(d, "summaries.json", {}).items()}
    fotmob = load(d, "fotmob.json", {"lineups": {}, "other_fixtures": {}})
    lineups = {int(k): v for k, v in fotmob.get("lineups", {}).items()}
    other_fx = {int(k): [(r["comp"], utc(r["utc"])) for r in v] for k, v in fotmob.get("other_fixtures", {}).items()}

    E = {p["id"]: p for p in b["elements"]}
    teams = {t["id"]: t for t in b["teams"]}
    next_ev = next(ev for ev in b["events"] if ev["is_next"])
    gws = [g for g in range(next_ev["id"], next_ev["id"] + HORIZON) if g <= 38]

    played = {t: 0 for t in teams}
    for f in fixtures:
        if f["finished"] or f["finished_provisional"]:
            played[f["team_h"]] += 1
            played[f["team_a"]] += 1

    by_gw = {g: {t: [] for t in teams} for g in gws}
    for f in fixtures:
        if f["event"] in by_gw:
            by_gw[f["event"]][f["team_h"]].append((f["team_a"], True, f["team_h_difficulty"], f["kickoff_time"]))
            by_gw[f["event"]][f["team_a"]].append((f["team_h"], False, f["team_a_difficulty"], f["kickoff_time"]))

    def recent(p):
        """Weighted share of the last four matches started, and average minutes when starting."""
        cutoff = datetime.now(timezone.utc).timestamp() - 3 * 3600  # ignore games not yet played
        rows = [r for r in summaries.get(p["id"], []) if r["kickoff"] and utc(r["kickoff"]).timestamp() < cutoff][-4:][::-1]
        if not rows:
            return None, None
        w = [0.4, 0.3, 0.2, 0.1][:len(rows)]
        share = sum(wi * (1 if r["starts"] else 0) for wi, r in zip(w, rows)) / sum(w)
        mins = [r["minutes"] for r in rows if r["starts"]]
        return share, (sum(mins) / len(mins) if mins else None)

    def in_lineup(p):
        """True, False, or None when there is no lineup yet; plus whether it is confirmed."""
        lu = lineups.get(p["team"])
        if not lu:
            return None, False
        full = norm(p["first_name"] + " " + p["second_name"]).split()
        web = norm(p["web_name"]).strip()

        def match(name):
            toks = norm(name).split()
            return bool(toks) and (norm(name).strip() == web or (toks[-1] in full and (len(toks) == 1 or toks[0] in full)))
        confirmed = lu.get("type", "").lower() not in ("predicted", "")
        if any(match(n) for n in lu.get("unavailable", [])):
            return False, True
        return any(match(n) for n in lu["starters"]), confirmed

    def europe(team, kickoff):
        """A European match within three and a half days either side of a league game. Domestic cup
        games are left out: managers rotate in the cup game itself, not the league game around it."""
        if not kickoff:
            return None
        k = utc(kickoff)
        near = [(c, t) for c, t in other_fx.get(team, [])
                if any(x in c for x in ("Champions League", "Europa League", "Conference League"))
                and abs((t - k).total_seconds()) <= 3.5 * 86400]
        return min(near, key=lambda x: abs((x[1] - k).total_seconds())) if near else None

    rotation = {}  # player id -> reasons, for the app
    EURO = ("Champions League", "Europa League", "Conference League")

    def club_rotation():
        """How many changes each club makes to its starting XI between league games, normally and
        when a European game falls within three and a half days, rebuilt from every player's matches."""
        xi = {}
        for pid, rows in summaries.items():
            team = E[pid]["team"] if pid in E else None
            for r in rows:
                if r["starts"] and r.get("fixture"):
                    xi.setdefault((team, r["fixture"]), set()).add(pid)
        fx_by_id = {f["id"]: f for f in fixtures}
        stats = {}
        for t in teams:
            games = sorted([f for f in fixtures if f["finished_provisional"] and t in (f["team_h"], f["team_a"])],
                           key=lambda f: f["kickoff_time"])
            normal, euro = [], []
            for a, b2 in zip(games, games[1:]):
                xa, xb = xi.get((t, a["id"]), set()), xi.get((t, b2["id"]), set())
                if len(xa) < 10 or len(xb) < 10:
                    continue
                changes = 11 - len(xa & xb)
                k = utc(b2["kickoff_time"])
                near = any(any(x in c for x in EURO) and abs((when - k).total_seconds()) <= 3.5 * 86400
                           for c, when in other_fx.get(t, []))
                (euro if near else normal).append(changes)
            stats[t] = (normal, euro)
        all_n = [c for n, _ in stats.values() for c in n]
        all_e = [c for _, e in stats.values() for c in e]
        avg_n = sum(all_n) / len(all_n) if all_n else 1.5
        avg_e = sum(all_e) / len(all_e) if all_e else avg_n + 1.0
        out = {}
        for t, (n, e) in stats.items():
            # Shrink towards the league average: a handful of games is a small sample.
            cn = (sum(n) + avg_n * 3) / (len(n) + 3)
            ce = (sum(e) + avg_e * 3) / (len(e) + 3)
            out[t] = {"normal": round(cn, 1), "euro": round(ce, 1), "games": len(n), "euro_games": len(e)}
        return out

    club_rot = club_rotation()

    def availability(p, offset, kickoff=None):
        if p["status"] == "u":
            return 0.0
        season = min(1.0, p["starts"] / played[p["team"]]) if played[p["team"]] else 0.5
        share, _ = recent(p)
        start_rate = season if share is None else 0.5 * season + 0.5 * share
        if p["minutes"] < 90:
            start_rate = min(start_rate, 0.35)
        reasons = rotation.setdefault(p["id"], [])
        if offset == 0:
            if share is not None and season >= 0.6 and share <= 0.4:
                reasons.append("Dropped recently: started few of the last four games")
            listed, confirmed = in_lineup(p)
            if listed is True:
                start_rate = 1.0 if confirmed else max(start_rate, 0.9)
            elif listed is False:
                start_rate = min(start_rate, 0.15 if confirmed else 0.3)
                reasons.append("Not in the confirmed lineup" if confirmed else "Not in FotMob's predicted lineup")
        eu = europe(p["team"], kickoff) if p["element_type"] != 1 else None
        if eu:
            # Chance a starter keeps his place in a European week, relative to a normal week, from
            # this club's own record. Regular starters are dropped less often than fringe players.
            cr = club_rot[p["team"]]
            keep = max(0.5, (11 - cr["euro"]) / max(1.0, 11 - cr["normal"]))
            start_rate *= keep ** (0.5 if season >= 0.9 else 1.3)
            if offset <= 1 and (season < 0.9 or keep < 0.85):
                reasons.append(f"{eu[0]} on {eu[1].strftime('%a %d %b')}. {teams[p['team']]['short_name']} make about "
                               f"{cr['euro']:.1f} changes around European games, against {cr['normal']:.1f} normally")
        chance = p["chance_of_playing_next_round"]
        if p["status"] in ("i", "s", "n"):
            chance = 0 if chance is None else chance
            return start_rate * (chance / 100 if offset == 0 else min(1.0, 0.25 + 0.25 * offset))
        if chance is not None:
            return start_rate * (chance / 100 if offset == 0 else min(1.0, chance / 100 + 0.25 * offset))
        return start_rate

    def per_match(p):
        """Expected points for a 90-minute appearance in an average fixture: attacking part, defensive part."""
        t = p["element_type"]
        m90 = p["minutes"] / 90
        xg90 = float(p["expected_goals_per_90"] or 0)
        xa90 = float(p["expected_assists_per_90"] or 0)
        xgc90 = float(p["expected_goals_conceded_per_90"] or 1.3)
        att = xg90 * GOAL_PTS[t] + xa90 * 3
        cs = math.exp(-xgc90) * CS_PTS[t]
        conceded = -(xgc90 / 2) if t in (1, 2) else 0
        saves = (p["saves"] / m90 / 3) if t == 1 and m90 else 0
        bonus = p["bonus"] / m90 if m90 else 0
        dc = float(p.get("defensive_contribution_per_90") or 0)
        dc_pts = 2 * min(1.0, dc / (10 if t == 2 else 12) * 0.8) if t != 1 else 0
        under_att = att
        under_def = 2 + cs + conceded + saves + bonus + dc_pts
        # Shrink towards the actual points per game, then towards the position mean, so a hot
        # start over a handful of games does not count as much as a full season.
        ppg = float(p["points_per_game"] or 0)
        k = m90 / (m90 + 6)
        blend = 0.6 * (under_att + under_def) + 0.4 * ppg if m90 else POS_MEAN[t]
        total = k * blend + (1 - k) * POS_MEAN[t]
        share_att = under_att / (under_att + under_def) if (under_att + under_def) > 0 else 0.3
        return total * share_att, total * (1 - share_att)

    # Per-position corrections learned by track.py from how past projections compared with actual points.
    cal = {}
    if calibration_path:
        try:
            with open(calibration_path) as f:
                c = json.load(f)
            cal = {int(k): float(v) for k, v in (c.get("data", c).get("applied") or {}).items()}
        except (OSError, ValueError, AttributeError):
            cal = {}

    proj = {}
    for p in b["elements"]:
        att, dfn = per_match(p)
        k_pos = cal.get(p["element_type"], 1.0)
        att, dfn = att * k_pos, dfn * k_pos
        row = []
        for i, g in enumerate(gws):
            pts = 0.0
            fx = []
            # Season figures already reflect a player's usual minutes, so only adjust when recent
            # starts have been shorter than normal (for example, being eased back from injury).
            _, mins = recent(p)
            usual = p["minutes"] / p["starts"] if p["starts"] else None
            minutes_factor = min(1.0, max(0.65, mins / usual)) if mins and usual else 1.0
            for opp, home, diff, kickoff in by_gw[g][p["team"]]:
                h = 1.05 if home else 0.97
                pts += availability(p, i, kickoff) * minutes_factor * (att * FDR_ATT[diff] + dfn * FDR_DEF[diff]) * h
                fx.append({"opp": teams[opp]["short_name"], "home": home, "fdr": diff})
            row.append({"gw": g, "xp": round(pts, 2), "fixtures": fx})
        if row and p["ep_next"] not in (None, "") and by_gw[gws[0]][p["team"]]:
            # FPL's own figure leans on form, so scale it by this week's fixture before blending.
            diffs = [x[2] for x in by_gw[gws[0]][p["team"]]]
            fix = sum(0.5 * FDR_ATT[x] + 0.5 * FDR_DEF[x] for x in diffs)
            row[0]["xp"] = round(0.8 * row[0]["xp"] + 0.2 * float(p["ep_next"]) * fix, 2)
        proj[p["id"]] = row

    def horizon(pid):
        return sum(w * r["xp"] for w, r in zip(WEIGHTS, proj[pid]))

    # Selling prices: purchase price plus half of any rise, rounded down.
    bought = {}
    for t in sorted(transfers, key=lambda x: x["event"]):
        bought[t["element_in"]] = t["element_in_cost"]
    squad_ids = [pk["element"] for pk in picks["picks"]]

    def sell_price(pid):
        now = E[pid]["now_cost"]
        cost = bought.get(pid, now - E[pid]["cost_change_start"])
        return now if now <= cost else cost + (now - cost) // 2

    bank = entry["last_deadline_bank"]

    # Free transfers: one more each gameweek, carried over up to five; chips keep them.
    chips_used = {c["event"]: c["name"] for c in history.get("chips", [])}
    ft = None
    for h in history["current"]:
        g = h["event"]
        if ft is None:
            ft = 1
            continue
        if chips_used.get(g) in ("wildcard", "freehit"):
            continue  # transfers in a Wildcard or Free Hit week are free, and nothing is banked
        else:
            ft = min(5, max(0, ft - h["event_transfers"]) + 1)
    ft = ft or 1

    def best_xi(ids, gw_index=0):
        pts = {i: proj[i][gw_index]["xp"] for i in ids}
        gk = sorted([i for i in ids if E[i]["element_type"] == 1], key=lambda i: -pts[i])
        outfield = sorted([i for i in ids if E[i]["element_type"] != 1], key=lambda i: -pts[i])
        best = None
        for d in range(3, 6):
            for m in range(2, 6):
                f = 10 - d - m
                if not 1 <= f <= 3:
                    continue
                pick = (
                    sorted([i for i in outfield if E[i]["element_type"] == 2], key=lambda i: -pts[i])[:d]
                    + sorted([i for i in outfield if E[i]["element_type"] == 3], key=lambda i: -pts[i])[:m]
                    + sorted([i for i in outfield if E[i]["element_type"] == 4], key=lambda i: -pts[i])[:f]
                )
                if len(pick) != 10:
                    continue
                s = sum(pts[i] for i in pick)
                if best is None or s > best[0]:
                    best = (s, pick, f"{d}-{m}-{f}")
        xi = [gk[0]] + best[1]
        bench_out = sorted([i for i in outfield if i not in xi], key=lambda i: -pts[i])
        bench = [gk[1]] + bench_out
        cap = sorted(xi, key=lambda i: -pts[i])
        return {"xi": xi, "bench": bench, "formation": best[2], "captain": cap[0], "vice": cap[1],
                "xp": round(sum(pts[i] for i in xi) + pts[cap[0]], 1)}

    def club_counts(ids):
        c = {}
        for i in ids:
            c[E[i]["team"]] = c.get(E[i]["team"], 0) + 1
        return c

    def week_values(ids):
        """Points the best XI plus captain would score each gameweek, with a little credit for the bench."""
        vals = []
        for gi in range(len(gws)):
            xi = best_xi(ids, gi)
            vals.append(xi["xp"] + 0.1 * sum(proj[i][gi]["xp"] for i in xi["bench"]))
        return vals

    def squad_value(ids):
        return sum(w * v for w, v in zip(WEIGHTS, week_values(ids)))

    def timing(ids, out, inn):
        """Gain in each gameweek from swapping out for inn, and the best gameweek to make the move.

        Making a move in gameweek t earns the gains from t onwards. Waiting gives up the earlier
        gains but keeps a transfer in hand, worth about SAVED_FT points a week for up to two weeks."""
        before = week_values(ids)
        after = week_values([inn if i == out else i for i in ids])
        deltas = [round(a - b, 2) for a, b in zip(after, before)]
        score = [sum(w * d for w, d in zip(WEIGHTS[t:], deltas[t:])) + SAVED_FT * min(t, 2) for t in range(len(deltas))]
        return deltas, gws[max(range(len(score)), key=lambda t: (score[t], -t))]

    def best_single(ids, money):
        clubs = club_counts(ids)
        base = squad_value(ids)
        options = []
        for out in ids:
            o = E[out]
            budget = money + sell_price(out)
            pool = [p for p in b["elements"]
                    if p["id"] not in ids and p["element_type"] == o["element_type"] and p["now_cost"] <= budget
                    and p["status"] == "a" and p["minutes"] >= 180
                    and (p["team"] == o["team"] or clubs.get(p["team"], 0) < 3)]
            # Only the strongest few candidates per slot need the full squad evaluation.
            pool = sorted(pool, key=lambda p: -horizon(p["id"]))[:12]
            for p in pool:
                trial = [p["id"] if i == out else i for i in ids]
                gain = squad_value(trial) - base
                options.append((gain, out, p["id"], budget - p["now_cost"]))
        options.sort(key=lambda x: -x[0])
        return options

    def describe(pid):
        p = E[pid]
        return {"id": pid, "name": p["web_name"], "team": teams[p["team"]]["short_name"], "pos": POS[p["element_type"]],
                "price": p["now_cost"] / 10, "sell": sell_price(pid) / 10 if pid in squad_ids else None,
                "status": p["status"], "news": p["news"], "chance": p["chance_of_playing_next_round"],
                "form": float(p["form"] or 0), "total": p["total_points"], "ownership": float(p["selected_by_percent"] or 0),
                "xp": [r["xp"] for r in proj[pid]], "xp5": round(horizon(pid), 1), "fixtures": [r["fixtures"] for r in proj[pid]],
                "risk": sorted(set(rotation.get(pid, [])))}

    # Plans for 0 to 3 transfers this gameweek, built greedily from the best remaining move
    # that pays its way this week. Moves that only pay later are listed as upcoming instead.
    plans = []
    ids, money, moves = list(squad_ids), bank, []
    plans.append({"transfers": 0, "moves": [], "gain": 0.0, **best_xi(ids)})
    for n in range(1, 4):
        pick = None
        for opt in best_single(ids, money)[:40]:
            deltas, when = timing(ids, opt[1], opt[2])
            if when == gws[0]:
                pick = (opt, deltas)
                break
        if not pick:
            break
        (gain, out, inn, left), deltas = pick
        alts = [o for o in best_single(ids, money) if o[1] == out and o[2] != inn][:3]
        ids = [inn if i == out else i for i in ids]
        money = left
        moves.append({"out": describe(out), "in": describe(inn), "gain": round(gain, 1), "weekly": deltas,
                      "alternatives": [{"in": describe(o[2]), "gain": round(o[0], 1)} for o in alts]})
        total_gain = round(sum(m["gain"] for m in moves), 1)
        plans.append({"transfers": n, "moves": list(moves), "gain": total_gain, "bank": money / 10, **best_xi(ids)})
        squad_after = ids

    # Other transfer ideas: each player sold and each player bought appears once, leaving out
    # this week's top move, so later moves (and the week to make them) show up too.
    first = plans[1]["moves"][0] if len(plans) > 1 else None
    seen = {first["out"]["id"], first["in"]["id"]} if first else set()
    ideas = []
    for gain, out, inn, left in best_single(squad_ids, bank):
        if out in seen or inn in seen:
            continue
        seen.update((out, inn))
        deltas, when = timing(squad_ids, out, inn)
        ideas.append({"out": describe(out), "in": describe(inn), "gain": round(gain, 1), "bank_after": left / 10,
                      "weekly": deltas, "best_gw": when})
        if len(ideas) == 6:
            break

    # Chip guidance from the current squad's projections.
    chips_left = [c["name"] for c in b["chips"] if c["start_event"] <= next_ev["id"] <= c["stop_event"]
                  and not any(u["name"] == c["name"] and c["start_event"] <= u["event"] <= c["stop_event"]
                              for u in history.get("chips", []))]
    chip_view = {}
    for gi, g in enumerate(gws):
        xi = best_xi(squad_ids, gi)
        bench_xp = sum(proj[i][gi]["xp"] for i in xi["bench"])
        cap_xp = proj[xi["captain"]][gi]["xp"]
        chip_view[g] = {"bench_xp": round(bench_xp, 1), "captain": E[xi["captain"]]["web_name"], "captain_xp": round(cap_xp, 1)}

    # Has the gameweek before the next deadline finished? Recommendations wait until it has.
    cur = next((ev for ev in b["events"] if ev["is_current"]), None)
    cur_fx = [f for f in fixtures if cur and f["event"] == cur["id"]]
    current_complete = bool(cur) and all(f["finished"] for f in cur_fx)
    last_kickoff = max((f["kickoff_time"] for f in cur_fx if f["kickoff_time"]), default=None)

    out = {
        "club_rotation": {teams[t]["short_name"]: v for t, v in club_rot.items()},
        "entry": entry_id,
        "current_gw": cur["id"] if cur else None,
        "current_complete": current_complete,
        "current_last_kickoff": last_kickoff,
        "current_games_left": sum(1 for f in cur_fx if not f["finished_provisional"]),
        "team_name": entry["name"],
        "manager": entry["player_first_name"],
        "overall_rank": entry["summary_overall_rank"],
        "total_points": entry["summary_overall_points"],
        "last_gw": picks["entry_history"]["event"],
        "last_gw_points": picks["entry_history"]["points"],
        "next_gw": next_ev["id"],
        "deadline": next_ev["deadline_time"],
        "bank": bank / 10,
        "squad_value": entry["last_deadline_value"] / 10,
        "free_transfers_estimate": ft,
        "chips_left": chips_left,
        "chip_view": chip_view,
        "gws": gws,
        "squad": [describe(i) for i in squad_ids],
        "plans": [{**pl, "xi": [describe(i) for i in pl["xi"]], "bench": [describe(i) for i in pl["bench"]],
                   "captain": E[pl["captain"]]["web_name"], "vice": E[pl["vice"]]["web_name"]} for pl in plans],
        "ideas": ideas,
        # Next gameweek's projection for every player likely to matter, logged by track.py to check later.
        "projections": {"gw": gws[0] if gws else None, "calibration": {str(k): v for k, v in cal.items()},
                        "xp": {str(pid): row[0]["xp"] for pid, row in proj.items() if row and (row[0]["xp"] >= 1.0 or pid in squad_ids)},
                        "type": {str(p["id"]): p["element_type"] for p in b["elements"] if proj.get(p["id"]) and (proj[p["id"]][0]["xp"] >= 1.0 or p["id"] in squad_ids)}},
        "updatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    with open(out_path, "w") as f:
        json.dump(out, f, ensure_ascii=False)


if __name__ == "__main__":
    main(int(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None)
