#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第三轮：美国/其他公开接口。runner 是 Azure westus（美国 IP），美国站可访问性最好。
Bovada 的 coupon 接口历史上完全公开，且 CS2 有 Moneyline / Map Handicap / Total。
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

H0 = {"User-Agent": UA, "Accept": "application/json, text/plain, */*",
      "Accept-Language": "en-US,en;q=0.9", "Accept-Encoding": "identity"}

TARGETS = [
    ("bovada-cs2",
     "https://www.bovada.lv/services/sports/event/coupon/events/A/description/esports/counter-strike"
     "?marketFilterId=def&preMatchOnly=true&lang=en",
     {"Referer": "https://www.bovada.lv/"}),

    ("bovada-esports-all",
     "https://www.bovada.lv/services/sports/event/coupon/events/A/description/esports"
     "?marketFilterId=def&preMatchOnly=true&lang=en",
     {"Referer": "https://www.bovada.lv/"}),

    ("betonline-cs2",
     "https://www.betonline.ag/sportsbook/esports/counter-strike",
     {"Accept": "text/html"}),

    ("draftkings-esports",
     "https://sportsbook-nash.draftkings.com/api/sportscontent/dkusnj/v1/sports/3",
     {"Referer": "https://sportsbook.draftkings.com/"}),

    ("fanduel-esports",
     "https://sportsbook.fanduel.com/api/sports/esports",
     {"Referer": "https://sportsbook.fanduel.com/"}),

    ("betano-esports",
     "https://www.betano.com/api/sport/esports/",
     {"Referer": "https://www.betano.com/"}),

    ("1xbet-kz",
     "https://1xbet.kz/LineFeed/Get1x2_VZip?sports=1&count=5&lng=en&mode=4&country=1",
     {"Referer": "https://1xbet.kz/"}),

    ("1xbet-service",
     "https://1xbet.com/service/LineFeed/Get1x2_VZip?sports=1&count=5&lng=en&mode=4&country=1",
     {"Referer": "https://1xbet.com/"}),

    ("roobet-graphql",
     "https://roobet.com/_api/graphql",
     {"Referer": "https://roobet.com/"}),

    ("betway-ca",
     "https://sports.betway.com/api/en-CA/sports/esports/counter-strike",
     {"Referer": "https://sports.betway.com/"}),

    ("bovada-nfl-sanity",
     "https://www.bovada.lv/services/sports/event/coupon/events/A/description/football/nfl"
     "?marketFilterId=def&preMatchOnly=true&lang=en",
     {"Referer": "https://www.bovada.lv/"}),
]

KEYS = ("counter-strike", "counter strike", "cs2", "csgo", "cs:go", "map handicap")


def probe(name, url, extra):
    h = dict(H0)
    h.update(extra)
    r = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(r, timeout=25) as resp:
            body = resp.read()
            st = resp.status
    except urllib.error.HTTPError as e:
        st, body = e.code, b""
        try:
            body = e.read()[:2000]
        except Exception:
            pass
    except Exception as e:
        print("[FAIL] %-22s %s" % (name, str(e)[:80]))
        return
    txt = body.decode("utf-8", "replace")
    low = txt.lower()
    hits = [k for k in KEYS if k in low]
    print("[%s] %-22s HTTP=%s bytes=%d %s"
          % ("OK  " if st == 200 else "ERR ", name, st, len(body),
             ("CS2:" + ",".join(hits)) if hits else ""))
    if st == 200 and len(body) > 100:
        print("      head: %s" % txt[:200].replace("\n", " "))
    elif st != 200:
        print("      head: %s" % txt[:120].replace("\n", " "))


def bovada_structure():
    """如果 Bovada 通了，看 CS2 有哪些 market description。"""
    print("\n########## Bovada CS2 market 结构 ##########")
    url = ("https://www.bovada.lv/services/sports/event/coupon/events/A/description/esports/counter-strike"
           "?marketFilterId=def&preMatchOnly=true&lang=en")
    h = dict(H0)
    h["Referer"] = "https://www.bovada.lv/"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=25) as resp:
            j = json.loads(resp.read().decode("utf-8", "replace"))
    except Exception as e:
        print("  失败:", str(e)[:100])
        return
    if not isinstance(j, list) or not j:
        print("  空结果")
        return
    n_ev = 0
    mdesc = {}
    for grp in j:
        for ev in (grp.get("events") or []):
            n_ev += 1
            if n_ev > 40:
                break
            for dg in (ev.get("displayGroups") or []):
                for mk in (dg.get("markets") or []):
                    d = mk.get("description") or "?"
                    mdesc[d] = mdesc.get(d, 0) + 1
    print("  events =", n_ev)
    print("  market description 全集:")
    for k, v in sorted(mdesc.items(), key=lambda x: -x[1]):
        print("     %-40s %d" % (k, v))
    # 打一个样本的完整结构
    for grp in j:
        evs = grp.get("events") or []
        if not evs:
            continue
        ev = evs[0]
        print("-" * 70)
        print("  样本: id=%s  %s  start=%s" % (ev.get("id"), ev.get("description"), ev.get("startTime")))
        for dg in (ev.get("displayGroups") or []):
            for mk in (dg.get("markets") or [])[:10]:
                outs = [(o.get("description"), (o.get("price") or {}).get("decimal"),
                         (o.get("price") or {}).get("handicap")) for o in (mk.get("outcomes") or [])]
                print("    [%s] %s" % (mk.get("description"), outs[:4]))
        break


def main():
    print("=" * 78)
    for name, url, extra in TARGETS:
        probe(name, url, extra)
        print("-" * 78)
    bovada_structure()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
