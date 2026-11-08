#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kambi 品牌第二轮：修正 Origin/Referer，扩大品牌池，并核对 paf 的 betoffer 原始响应。
目标：找到同时提供 Match / Map Winner / Handicap / Total Rounds 的品牌。
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

API = "https://eu-offering-api.kambicdn.com/offering/v2018"

# (brand, origin, market)
BRANDS = [
    ("paf", "https://www.paf.com", "FI"),
    ("coolbet", "https://www.coolbet.com", "EE"),
    ("betsson", "https://www.betsson.com", "SE"),
    ("nordicbet", "https://www.nordicbet.com", "SE"),
    ("leovegas", "https://www.leovegas.com", "SE"),
    ("mrgreen", "https://www.mrgreen.com", "SE"),
    ("betsafe", "https://www.betsafe.com", "SE"),
    ("bethard", "https://www.bethard.com", "SE"),
    ("atg", "https://www.atg.se", "SE"),
    ("svenskaspel", "https://www.svenskaspel.se", "SE"),
    ("norsk-tipping", "https://www.norsk-tipping.no", "NO"),
    ("danskespil", "https://www.danskespil.dk", "DK"),
    ("bet25", "https://www.bet25.dk", "DK"),
    ("veikkaus", "https://www.veikkaus.fi", "FI"),
    ("unibet", "https://www.unibet.co.uk", "GB"),
    ("888sport", "https://www.888sport.com", "GB"),
    ("redbet", "https://www.redbet.com", "SE"),
    ("videoslots", "https://www.videoslots.com", "SE"),
    ("tipico", "https://www.tipico.de", "DE"),
    ("winamax", "https://www.winamax.fr", "FR"),
]


def fetch(url, origin, timeout=20):
    h = {"User-Agent": UA, "Accept": "application/json, text/plain, */*",
         "Accept-Encoding": "identity", "Accept-Language": "en-US,en;q=0.9",
         "Origin": origin, "Referer": origin + "/"}
    r = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        try:
            return e.code, e.read()[:500]
        except Exception:
            return e.code, b""
    except Exception as e:
        return -1, str(e).encode()


def check_brand(brand, origin, mkt):
    url = ("%s/%s/listView/esports.json?lang=en_GB&market=%s"
           "&client_id=2&channel_id=1&ncid=1" % (API, brand, mkt))
    st, body = fetch(url, origin)
    txt = body.decode("utf-8", "replace")
    if st != 200:
        return brand, st, 0, 0, txt[:70].replace("\n", " ")
    try:
        j = json.loads(txt)
    except Exception:
        return brand, st, 0, 0, "非 JSON"
    evs = j.get("events") or []
    # 统计盘口类型种类数
    kinds = set()
    for e in evs:
        for bo in (e.get("betOffers") or []):
            kinds.add((bo.get("betOfferType") or {}).get("englishName"))
    return brand, st, len(evs), len(kinds), ",".join(sorted(k for k in kinds if k))[:80]


def paf_raw():
    """核对 paf 的 betoffer 端点到底返回什么。"""
    print("\n########## paf betoffer 原始响应 ##########")
    origin = "https://www.paf.com"
    # 先拿一个未开赛 event
    st, body = fetch("%s/paf/listView/esports.json?lang=en_GB&market=FI&client_id=2&channel_id=1&ncid=1" % API, origin)
    j = json.loads(body.decode("utf-8", "replace"))
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    eid = None
    for e in (j.get("events") or []):
        ev = e.get("event", {})
        if not any("cs2" in (t or "") for t in [p.get("termKey") for p in (ev.get("path") or [])]):
            continue
        try:
            t = datetime.fromisoformat(ev["start"].replace("Z", "+00:00"))
        except Exception:
            continue
        if t > now:
            eid = ev["id"]
            print("用 event id=%s  %s  start=%s" % (eid, ev.get("name"), ev.get("start")))
            break
    if not eid:
        print("没有未开赛事件")
        return
    for suffix in ("", "&includeParticipantsInOdds=false", "&useCombined=true"):
        url = ("%s/paf/betoffer/%s.json?lang=en_GB&market=FI&client_id=2&channel_id=1&ncid=1%s"
               % (API, eid, suffix))
        st, body = fetch(url, origin)
        txt = body.decode("utf-8", "replace")
        print("  suffix=%-34s HTTP=%s bytes=%d" % (repr(suffix), st, len(body)))
        print("     head: %s" % txt[:220].replace("\n", " "))


def main():
    print("=" * 78)
    print("%-16s %-6s %-6s %-5s %s" % ("brand", "HTTP", "events", "种类", "盘口类型"))
    print("-" * 78)
    good = []
    for b, o, m in BRANDS:
        try:
            name, st, n, k, kinds = check_brand(b, o, m)
        except Exception as e:
            print("%-16s ERROR %s" % (b, str(e)[:50]))
            continue
        flag = "  <<<" if st == 200 and n > 0 else ""
        print("%-16s %-6s %-6s %-5s %s%s" % (name, st, n, k, kinds, flag))
        if st == 200 and n > 0:
            good.append((name, o, m, k))
        time.sleep(0.4)
    print("\n可用品牌:", good)
    paf_raw()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
