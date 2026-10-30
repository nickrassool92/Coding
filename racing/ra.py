"""Racing Australia free fields: fetch and parse form guides, acceptances and results.

Pages are plain HTML from https://racingaustralia.horse/FreeFields/. A meeting key looks like
"2026Nov03,VIC,Flemington". Parsers return plain dicts so the model and the app never touch HTML.
"""
import html
import os
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
BASE = "https://racingaustralia.horse/FreeFields/"


def fetch(page, key, cache_dir=None, max_age=None):
    """page is "Form", "Acceptances", "Results" or "Scratchings". Cached copies are reused unless older than max_age seconds."""
    path = None
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
        path = os.path.join(cache_dir, f"{page}_{key}.html".replace(",", "_").replace(" ", "-"))
        if os.path.exists(path) and (max_age is None or time.time() - os.path.getmtime(path) < max_age):
            with open(path, encoding="utf-8") as f:
                return f.read()
    url = BASE + f"{page}.aspx?Key=" + urllib.parse.quote(key)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=90) as r:
                text = r.read().decode("utf-8", "ignore")
            break
        except Exception:
            if attempt == 2:
                raise
            time.sleep(5 * (attempt + 1))
    if path:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    return text


def clean(s):
    s = html.unescape(re.sub(r"<[^>]+>", " ", s))
    return re.sub(r"\s+", " ", s).strip()


def num(s, default=None):
    try:
        return float(s)
    except (TypeError, ValueError):
        return default


# ---------- race headers ----------

def parse_header(chunk):
    chunk = re.sub(r"<!--.*?-->", "", chunk, flags=re.S)
    th = re.search(r'class="race-title">\s*<tr>\s*<th>(.*?)</th>', chunk, re.S)
    title = clean(th.group(1)) if th else ""
    title = title.replace("Times displayed in local time of Race Meeting", "").strip()
    m = re.match(r"Race (\d+) - (\S+) (.*?) \((\d+) METRES\)", title)
    info = re.search(r'(?:class="race-info"|<tr>\s*<td>)(.*?)</t[dr]>', chunk[chunk.find("race-title"):], re.S | re.I)
    info_text = clean(info.group(1)) if info else ""
    prize = re.search(r"Of \$([\d,]+)", info_text)
    cond = re.search(r"Track Condition:\s*([A-Za-z]+)\s*(\d+)?", info_text)
    summary = re.split(r"prior to distribution", info_text)[-1]
    summary = re.split(r"Track Name:|This race carries", summary)[0].strip(" .")
    return {"race": int(m.group(1)) if m else None, "summary": summary, "time": m.group(2) if m else None,
            "name": m.group(3).strip() if m else title, "distance": int(m.group(4)) if m else None,
            "prize": int(prize.group(1).replace(",", "")) if prize else None, "conditions": info_text,
            "class": race_class(info_text + " " + (m.group(3) if m else "")),
            "track_condition": (cond.group(1) + (cond.group(2) or "")) if cond else None}


CLASS_LEVEL = [(r"\bGROUP 1\b|\bG1\b", 6), (r"\bGROUP 2\b|\bG2\b", 5), (r"\bGROUP 3\b|\bG3\b", 4),
               (r"\bLISTED\b|\bLR\b", 3)]


def race_class(text):
    """A rough class number: 6 Group 1 down to 3 Listed, then benchmark / rating races scaled from their number."""
    t = text.upper()
    for pat, lvl in CLASS_LEVEL:
        if re.search(pat, t):
            return lvl
    bm = re.search(r"(?:BENCHMARK|BM|RATING|RTG|CL)\s*(\d+)", t)
    if bm:
        v = int(bm.group(1))
        return round(min(2.8, max(0.0, (v - 50) / 20)), 2) if v > 10 else round(v / 3, 2)
    if "MAIDEN" in t or "MDN" in t:
        return 0.3
    return 1.5


# ---------- form guide ----------

def parse_start(pos_text, remain_html):
    """One past start from the horse-last-start table."""
    t = clean(remain_html)
    pos = re.match(r"(\d+)\s*of\s*(\d+)", clean(pos_text))
    if not pos or re.search(r"Jump Out|Trial|BARRIER TRIAL", t, re.I):
        return None
    m = re.match(r"(.+?) (\d{2}[A-Z][a-z]{2}\d{2}) (\d{3,4})m (\S+)", t)
    if not m:
        return None
    try:
        date = datetime.strptime(m.group(2), "%d%b%y").date().isoformat()
    except ValueError:
        return None
    cond = m.group(4)
    rest = t[m.end():]
    cls_text = rest.split("$")[0]
    prize = re.search(r"\$([\d,]+)", rest)
    wb = re.search(r"([\d.]+)kg Barrier (\d+)", rest)
    rtg = re.search(r"Rtg (\d+)", rest)
    margin = re.search(r"(\d+(?:\.\d+)?)L", rest[rest.find("1st"):] if "1st" in rest else rest)
    sps = re.findall(r"\$(\d+(?:\.\d+)?)(?=/|\s*$)", t)
    return {"pos": int(pos.group(1)), "field": int(pos.group(2)), "venue": m.group(1), "date": date,
            "distance": int(m.group(3)), "condition": cond, "class": race_class(cls_text), "class_text": cls_text.strip(),
            "prize": int(prize.group(1).replace(",", "")) if prize else None,
            "weight": num(wb.group(1)) if wb else None, "barrier": int(wb.group(2)) if wb else None,
            "rating": int(rtg.group(1)) if rtg else None, "margin": num(margin.group(1), 0.0) if margin else None,
            "sp": num(sps[-1]) if sps else None}


def record(text, label):
    m = re.search(label + r":\s*(\d+):(\d+)-(\d+)-(\d+)", text)
    return [int(x) for x in m.groups()] if m else [0, 0, 0, 0]


def parse_form(page):
    """Races with their field and every runner's recent form."""
    races = []
    chunks = re.split(r'<a name="Race\d+"></a>', page)[1:]
    for chunk in chunks:
        hdr = parse_header(chunk)
        field = {}
        strip = chunk[chunk.find("race-strip-fields"):chunk.find("horse-form-table")]
        for row in re.findall(r"<tr class='(?:Odd|Even)Row'>(.*?)</tr>", strip, re.S):
            cells = dict()
            for cls, val in re.findall(r"<td[^>]*class=['\"]?([\w-]+)['\"]?[^>]*>(.*?)</td>", row, re.S):
                cells.setdefault(cls, clean(val))
            no = cells.get("no")
            if not no or not no.isdigit():
                continue
            field[int(no)] = {"no": int(no), "last10": cells.get("last", ""), "name": cells.get("horse", ""),
                              "trainer": cells.get("trainer", ""), "jockey": cells.get("jockey", ""),
                              "barrier": int(cells["barrier"]) if cells.get("barrier", "").isdigit() else None,
                              "weight": num(cells.get("weight", "").replace("kg", "")),
                              "hcp": int(cells["hcp"]) if cells.get("hcp", "").isdigit() else None}
        for block in chunk.split('class="horse-form-table"')[1:]:
            no = re.search(r'class="horse-number">(\d+)<', block)
            if not no or int(no.group(1)) not in field:
                continue
            h = field[int(no.group(1))]
            info = clean(block[:block.find("horse-last-start")] if "horse-last-start" in block else block[:6000])
            age = re.search(r"(\d+) year old (\w+) (\w+)", info)
            h["age"] = int(age.group(1)) if age else None
            h["sex"] = age.group(3) if age else None
            h["country"] = (re.search(r"\(([A-Z]{2,3})\)", h["name"]) or [None, "AUS"])[1]
            h["gear_change"] = "Gear Changes:" in info
            for key, label in (("career", "Record"), ("first_up", "1st Up"), ("second_up", "2nd Up"), ("track", "Track"),
                               ("dist", "Dist"), ("track_dist", "Track/Dist"), ("firm", "Firm"), ("good", "Good"),
                               ("soft", "Soft"), ("heavy", "Heavy")):
                h[key] = record(info, r"(?<![/\w])" + re.escape(label))
            starts = []
            table = block[block.find("horse-last-start"):] if "horse-last-start" in block else ""
            for pos_html, remain in re.findall(r"<td class='Pos'>(.*?)</td>\s*<td class='remain'>(.*?)</td>", table, re.S):
                s = parse_start(pos_html, remain)
                if s:
                    starts.append(s)
            h["starts"] = sorted(starts, key=lambda s: s["date"], reverse=True)
        hdr["runners"] = list(field.values())
        races.append(hdr)
    return races


# ---------- results ----------

def parse_results(page):
    page = re.sub(r"<!--.*?-->", "", page, flags=re.S)  # a commented-out cell would shift the columns
    races = []
    chunks = re.split(r'<a name="Race\d+"></a>', page)[1:] or re.split(r'(?=<table[^>]*class="race-title")', page)[1:]
    for chunk in chunks:
        hdr = parse_header(chunk)
        runners = []
        for row in re.findall(r"<tr class='(?:Odd|Even)Row'>(.*?)</tr>", chunk, re.S):
            tds = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
            vals = [clean(x) for x in tds]
            if len(vals) < 11:
                continue
            fin = re.search(r"Finish F?(\w+)'", row)
            finish = vals[1]
            sp = re.search(r"\$(\d+(?:\.\d+)?)", vals[-1])
            runners.append({"finish": int(finish) if finish.isdigit() else None, "status": finish,
                            "no": int(vals[2]) if vals[2].isdigit() else None, "name": vals[3],
                            "trainer": vals[4], "jockey": vals[5], "margin": num(vals[6].replace("L", "")),
                            "barrier": int(vals[7]) if vals[7].isdigit() else None,
                            "weight": num(vals[8].replace("kg", "")), "sp": num(sp.group(1)) if sp else None})
        if runners:
            hdr["runners"] = runners
            races.append(hdr)
    return races


# ---------- scratchings and track rating ----------

def parse_scratchings(page):
    """{"track_rating": "Good 4", "weather": ..., "scratched": {race: [runner numbers]}} including late scratchings."""
    txt = clean(page)
    good = r"((?:Firm|Good|Soft|Heavy|Synthetic)\s*\d*)"
    rating = re.search(r"Track Rating:\s*" + good, txt) or re.search(r"Track Condition:\s*" + good, txt)
    weather = re.search(r"Weather:\s*([A-Za-z ]+?)\s+(?:Total|Penetrometer|Dual)", txt)
    scratched = {}
    for section in re.findall(r"(?:Late )?Scratchings\s+(Race \d+:.*?)(?=Late Scratchings|Late Riders|Undeclared|$)", txt):
        for race, body in re.findall(r"Race (\d+):\s*(.*?)(?=Race \d+:|$)", section):
            for no in re.findall(r"(?:^|\s)(\d+)e?\s+[A-Z][A-Z'’ .-]+", body):
                scratched.setdefault(int(race), set()).add(int(no))
    return {"track_rating": rating.group(1).strip() if rating else None,
            "weather": weather.group(1).strip() if weather else None,
            "scratched": {r: sorted(v) for r, v in scratched.items()}}
