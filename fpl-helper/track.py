"""Gaffer track record: logs each gameweek's projections before the deadline and checks them afterwards.

Usage: python3 -I track.py <out.json> <ledger.json> <out_ledger.json> <out_calibration.json>
out.json is model.py's fresh output; ledger.json the previous track/projections document (may be missing).
1. While the next gameweek's deadline is still ahead, its projections are (re)logged, so the ledger
   ends up holding the last projections made before the deadline.
2. Once FPL marks a logged gameweek finished, every logged player's actual points are fetched
   and compared with the projection, by position.
3. Calibration: for each position, actual points over projected points across all checked weeks,
   shrunk towards 1.0. It is applied (model.py's fourth argument) once MIN_GWS weeks are checked,
   kept within 0.85 to 1.15. Projections are logged with any applied correction taken back out.
"""
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
FPL = "https://fantasy.premierleague.com/api/"
MIN_GWS = 3
PRIOR_POINTS = 400   # shrinkage: as if this many projected points had matched exactly
POS = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}


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


def load(path, default):
    try:
        with open(path) as f:
            d = json.load(f)
        return d.get("data", d)
    except (OSError, ValueError):
        return default


def main(out_path, ledger_path, out_ledger, out_cal):
    out = load(out_path, {})
    ledger = load(ledger_path, {"gws": {}})
    gws = ledger.setdefault("gws", {})
    now = datetime.now(timezone.utc)
    pr = out.get("projections") or {}
    deadline = out.get("deadline")
    if pr.get("gw") and deadline and now < datetime.fromisoformat(deadline.replace("Z", "+00:00")):
        key = str(pr["gw"])
        if not (gws.get(key) or {}).get("checked"):
            # Logged without any correction already applied, so the learned ratios never compound.
            cal_used = pr.get("calibration") or {}
            raw = {pid: round(xp / float(cal_used.get(str(pr["type"][pid]), 1.0)), 2) for pid, xp in pr["xp"].items()}
            gws[key] = {"made": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "deadline": deadline, "xp": raw, "type": pr["type"]}

    events = {str(e["id"]): e for e in get(FPL + "bootstrap-static/")["events"]}
    for key, g in gws.items():
        ev = events.get(key)
        if g.get("checked") or not ev or not ev.get("finished") or not ev.get("data_checked"):
            continue
        live = {str(e["id"]): e["stats"] for e in get(FPL + f"event/{key}/live/")["elements"]}
        by = {}
        abs_err = n = 0
        for pid, xp in g["xp"].items():
            st = live.get(pid)
            if st is None:
                continue
            t = str(g["type"].get(pid))
            row = by.setdefault(t, {"players": 0, "projected": 0.0, "actual": 0})
            row["players"] += 1
            row["projected"] += xp
            row["actual"] += st["total_points"]
            abs_err += abs(st["total_points"] - xp)
            n += 1
        for row in by.values():
            row["projected"] = round(row["projected"], 1)
        g["checked"] = {"by_position": by, "players": n, "mae": round(abs_err / n, 2) if n else None}
        time.sleep(0.3)

    checked = {k: g for k, g in gws.items() if g.get("checked")}
    cal = {"updatedAt": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "weeks_checked": len(checked), "min_weeks": MIN_GWS,
           "positions": {}, "applied": {}, "weeks": []}
    for t in ("1", "2", "3", "4"):
        proj = sum(g["checked"]["by_position"].get(t, {}).get("projected", 0) for g in checked.values())
        act = sum(g["checked"]["by_position"].get(t, {}).get("actual", 0) for g in checked.values())
        if not proj:
            continue
        shrunk = (act + PRIOR_POINTS) / (proj + PRIOR_POINTS)
        cal["positions"][POS[int(t)]] = {"projected": round(proj, 1), "actual": act, "ratio": round(act / proj, 3),
                                         "suggested": round(min(1.15, max(0.85, shrunk)), 3)}
        if len(checked) >= MIN_GWS:
            cal["applied"][t] = round(min(1.15, max(0.85, shrunk)), 3)
    cal["weeks"] = [{"gw": int(k), "players": g["checked"]["players"], "mae": g["checked"]["mae"],
                     "projected": round(sum(r["projected"] for r in g["checked"]["by_position"].values()), 1),
                     "actual": sum(r["actual"] for r in g["checked"]["by_position"].values())}
                    for k, g in sorted(checked.items(), key=lambda kv: int(kv[0]))]
    with open(out_ledger, "w") as f:
        json.dump(ledger, f)
    with open(out_cal, "w") as f:
        json.dump(cal, f)
    print(json.dumps({k: cal[k] for k in ("weeks_checked", "positions", "applied")}), file=sys.stderr)


if __name__ == "__main__":
    main(*sys.argv[1:5])
