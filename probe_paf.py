#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PAF(Kambi) CS2 盘口结构探测。
确认三件事：
  1) 有多少 CS2 场次、覆盖哪些赛事
  2) betOfferType 名称全集（是否有 Map Winner / Handicap / Total Rounds）
  3) 单个 event 的完整字段结构（odds 标度、line 标度）
"""

from __future__ import annotations

import json
import urllib.request

BASE_URL = ("https://eu-offering-api.kambicdn.com/offering/v2018/paf/listView/esports.json"
            "?lang=en_GB&market={mkt}&client_id=2&channel_id=1&ncid=1")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

H = {"User-Agent": UA, "Accept": "application/json", "Accept-Encoding": "identity",
     "Origin": "https://www.paf.com", "Referer": "https://www.paf.com/"}


def get(url):
    r = urllib.request.Request(url, headers=H)
    with urllib.request.urlopen(r, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def path_terms(ev):
    return [p.get("termKey") for p in (ev.get("path") or [])]


def main():
    for mkt in ("GB", "FI"):
        try:
            j = get(BASE_URL.format(mkt=mkt))
        except Exception as e:
            print("market=%s 失败: %s" % (mkt, e))
            continue
        evs = j.get("events") or []
        print("=" * 74)
        print("market=%s  events=%d" % (mkt, len(evs)))
        if not evs:
            continue

        # 用 path 判断 CS2
        cs2 = [e for e in evs
               if any("cs2" in (t or "") or "counter" in (t or "") for t in path_terms(e.get("event", {})))]
        print("CS2 场次 =", len(cs2))

        groups = {}
        for e in cs2:
            g = e.get("event", {}).get("groupName") or e.get("event", {}).get("group") or "-"
            groups[g] = groups.get(g, 0) + 1
        print("赛事分布:", sorted(groups.items(), key=lambda x: -x[1])[:12])

        types = {}
        for e in cs2:
            for bo in (e.get("betOffers") or []):
                n = (bo.get("betOfferType") or {}).get("englishName") or \
                    (bo.get("betOfferType") or {}).get("name") or "?"
                types[n] = types.get(n, 0) + 1
        print("betOfferType 全集(%d 种):" % len(types))
        for k, v in sorted(types.items(), key=lambda x: -x[1]):
            print("   %-42s %d" % (k, v))

        if cs2:
            e0 = cs2[0]
            ev = e0.get("event", {})
            print("-" * 74)
            print("样本: id=%s  %s" % (ev.get("id"), ev.get("name")))
            print("event 字段:", sorted(ev.keys()))
            for bo in (e0.get("betOffers") or []):
                t = (bo.get("betOfferType") or {}).get("englishName")
                print("  [%s] id=%s state=%s" % (t, bo.get("id"), bo.get("status")))
                for o in (bo.get("outcomes") or []):
                    print("      label=%-22s odds=%-6s line=%-7s part=%s"
                          % (o.get("label"), o.get("odds"), o.get("line"),
                             o.get("participant")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
