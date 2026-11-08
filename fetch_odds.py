#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CS2 盘口采集器（Bovada + Kambi/PAF），纯标准库，GitHub Actions 运行。

覆盖范围（2026-11 实测）：
  Bovada  ：系列赛 Moneyline / Point Spread(地图让分) / Total(总地图数) + Alternative 分档
  Kambi PAF：系列赛 Moneyline（场次更多，覆盖 PGL Major / BLAST Rivals）
  单图回合级盘口（Map1 总分 21.5 / 回合让分）在这些源上不存在，需 bet365/1xBet 级别权限。

输出
  out/cs2_odds_latest.csv   当前全量盘口（覆盖写）
  out/cs2_odds_changes.csv  仅当赔率或盘口变动时追加
  out/odds_log.txt          每次运行摘要
"""

from __future__ import annotations

import csv
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

FIELDS = [
    "fetched_at", "source", "event_id", "start_time", "league",
    "home", "away", "scope", "market", "line", "outcome", "team",
    "price_us", "price_dec", "is_alt",
]

BOVADA = ("https://www.bovada.lv/services/sports/event/coupon/events/A/description/esports"
          "?marketFilterId=all&preMatchOnly=false&lang=en")
KAMBI = ("https://eu-offering-api.kambicdn.com/offering/v2018/paf/listView/esports.json"
         "?lang=en_GB&market=FI&client_id=2&channel_id=1&ncid=1")


def http_json(url, extra=None, retries=3, timeout=30):
    h = {"User-Agent": UA, "Accept": "application/json, text/plain, */*",
         "Accept-Encoding": "identity", "Accept-Language": "en-US,en;q=0.9"}
    if extra:
        h.update(extra)
    for i in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=h),
                                        timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", "replace")), r.status
        except urllib.error.HTTPError as e:
            if e.code in (403, 429, 500, 502, 503, 504):
                time.sleep(2 * (i + 1))
                continue
            return None, e.code
        except Exception:
            time.sleep(1.5 * (i + 1))
    return None, -1


def dec_from_american(am):
    try:
        v = float(am)
    except (TypeError, ValueError):
        return None
    if v == 0:
        return None
    return round(1 + (100.0 / abs(v) if v < 0 else v / 100.0), 4)


def norm_iso(ts):
    """Bovada 给毫秒时间戳，Kambi 给 ISO 串。"""
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return str(ts or "")


# ---------------------------------------------------------------- Bovada


def fetch_bovada(fetched_at):
    j, st = http_json(BOVADA, {"Referer": "https://www.bovada.lv/",
                               "Origin": "https://www.bovada.lv"})
    if not isinstance(j, list):
        return [], {"source": "bovada", "status": st, "rows": 0}

    rows = []
    n_ev = 0
    for g in j:
        if not any("counter" in (p.get("description") or "").lower()
                   for p in (g.get("path") or [])):
            continue
        league = " / ".join((p.get("description") or "") for p in (g.get("path") or []))
        for ev in (g.get("events") or []):
            n_ev += 1
            comps = ev.get("competitors") or []
            home = next((c.get("name") for c in comps if c.get("home")), None)
            away = next((c.get("name") for c in comps if not c.get("home")), None)
            if not home or not away:
                names = [c.get("name") for c in comps]
                home, away = (names + [""])[0], (names + ["", ""])[1]
            start = norm_iso(ev.get("startTime"))
            for dg in (ev.get("displayGroups") or []):
                dgn = (dg.get("description") or "")
                is_alt = 1 if dgn.lower() not in ("game lines",) else 0
                for mk in (dg.get("markets") or []):
                    mname = (mk.get("description") or "").lower()
                    if "moneyline" in mname:
                        mtype = "moneyline"
                    elif "spread" in mname or "handicap" in mname:
                        mtype = "spread"
                    elif "total" in mname:
                        mtype = "total"
                    else:
                        mtype = mname
                    period = ((mk.get("period") or {}).get("description") or "").lower()
                    scope = "series" if period in ("game", "match", "") else period
                    for o in (mk.get("outcomes") or []):
                        pr = o.get("price") or {}
                        dec = pr.get("decimal")
                        try:
                            dec = round(float(dec), 4) if dec not in (None, "") else None
                        except ValueError:
                            dec = None
                        if dec is None:
                            dec = dec_from_american(pr.get("american"))
                        if dec is None:
                            continue
                        desc = o.get("description") or ""
                        low = desc.lower()
                        if low.startswith("over"):
                            team = "over"
                        elif low.startswith("under"):
                            team = "under"
                        elif home and home.split()[0].lower() in low:
                            team = "home"
                        elif away and away.split()[0].lower() in low:
                            team = "away"
                        else:
                            team = desc
                        rows.append({
                            "fetched_at": fetched_at, "source": "bovada",
                            "event_id": ev.get("id"), "start_time": start,
                            "league": league, "home": home, "away": away,
                            "scope": scope, "market": mtype,
                            "line": pr.get("handicap") if pr.get("handicap") is not None else "",
                            "outcome": desc, "team": team,
                            "price_us": pr.get("american", ""), "price_dec": dec,
                            "is_alt": is_alt,
                        })
    return rows, {"source": "bovada", "status": st, "events": n_ev, "rows": len(rows)}


# ---------------------------------------------------------------- Kambi


def fetch_kambi(fetched_at):
    j, st = http_json(KAMBI, {"Referer": "https://www.paf.com/",
                              "Origin": "https://www.paf.com"})
    if not isinstance(j, dict):
        return [], {"source": "kambi", "status": st, "rows": 0}

    rows = []
    n_ev = 0
    for e in (j.get("events") or []):
        ev = e.get("event") or {}
        path = [p.get("termKey") or "" for p in (ev.get("path") or [])]
        if not any("cs2" in t or "counter" in t for t in path):
            continue
        n_ev += 1
        for bo in (e.get("betOffers") or []):
            tname = ((bo.get("betOfferType") or {}).get("englishName") or "").lower()
            mtype = "moneyline" if "match" == tname else tname
            for o in (bo.get("outcomes") or []):
                odds = o.get("odds")
                if not odds:
                    continue
                # Kambi 的 odds 是 ×1000 整数（1800 = 1.80），line 同理
                dec = round(odds / 1000.0, 4)
                if dec <= 1.0:
                    continue
                ln = o.get("line")
                ln = round(ln / 1000.0, 2) if ln not in (None, 0) else ""
                part = (o.get("participant") or "").lower()
                if part in ("home", "away"):
                    team = part
                else:
                    team = o.get("label") or ""
                rows.append({
                    "fetched_at": fetched_at, "source": "kambi_paf",
                    "event_id": ev.get("id"), "start_time": norm_iso(ev.get("start")),
                    "league": ev.get("group") or "",
                    "home": ev.get("homeName") or "", "away": ev.get("awayName") or "",
                    "scope": "series", "market": mtype,
                    "line": ln,
                    "outcome": o.get("label") or "", "team": team,
                    "price_us": "", "price_dec": dec, "is_alt": 0,
                })
    return rows, {"source": "kambi", "status": st, "events": n_ev, "rows": len(rows)}


# ---------------------------------------------------------------- 落盘


def key_of(r):
    return (r["source"], str(r["event_id"]), r["scope"], r["market"],
            str(r["line"]), str(r["outcome"]))


def read_csv(p):
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(p, rows, append=False):
    p.parent.mkdir(parents=True, exist_ok=True)
    header = not (append and p.exists() and p.stat().st_size > 0)
    with p.open("a" if append else "w", encoding="utf-8",
                newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        if header:
            w.writeheader()
        w.writerows(rows)


def main():
    out = Path("out")
    out.mkdir(parents=True, exist_ok=True)
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    rows, metas = [], []
    for fn in (fetch_bovada, fetch_kambi):
        try:
            r, m = fn(fetched_at)
        except Exception as e:
            r, m = [], {"source": fn.__name__, "error": str(e)[:200]}
        rows.extend(r)
        metas.append(m)
        print("[%s] %s" % (fn.__name__, json.dumps(m, ensure_ascii=False)))

    if not rows:
        print("[warn] 无数据")
        with (out / "odds_log.txt").open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": fetched_at, "rows": 0, "metas": metas},
                               ensure_ascii=False) + "\n")
        return 2

    latest = out / "cs2_odds_latest.csv"
    prev = {key_of(r): r.get("price_dec") for r in read_csv(latest)}
    write_csv(latest, rows)
    changed = [r for r in rows if prev.get(key_of(r)) != str(r["price_dec"])]
    if changed:
        write_csv(out / "cs2_odds_changes.csv", changed, append=True)

    with (out / "odds_log.txt").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": fetched_at, "rows": len(rows),
                            "changed": len(changed), "metas": metas},
                           ensure_ascii=False) + "\n")

    print("[done] rows=%d changed=%d" % (len(rows), len(changed)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
