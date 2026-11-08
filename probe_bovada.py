#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bovada CS2 盘口结构解析。
Bovada esports 聚合端点公开无鉴权，含 Counter-Strike 的 Moneyline / Handicap / Total。
确认：赛事覆盖、market description 全集、是否区分 Map 1 级别盘口。
"""

from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone

URL = ("https://www.bovada.lv/services/sports/event/coupon/events/A/description/esports"
       "?marketFilterId=def&preMatchOnly=true&lang=en")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

H = {"User-Agent": UA, "Accept": "application/json", "Accept-Encoding": "identity",
     "Referer": "https://www.bovada.lv/", "Origin": "https://www.bovada.lv"}


def load():
    r = urllib.request.Request(URL, headers=H)
    with urllib.request.urlopen(r, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def is_cs2(grp):
    return any("counter" in (p.get("description") or "").lower()
               for p in (grp.get("path") or []))


def main():
    j = load()
    print("顶层 group 数 =", len(j))

    all_leagues = []
    for g in j:
        p = g.get("path") or []
        league = " / ".join(x.get("description", "") for x in p)
        all_leagues.append((league, len(g.get("events") or [])))
    print("\n全部电竞联赛(%d):" % len(all_leagues))
    for lg, n in sorted(all_leagues, key=lambda x: -x[1])[:20]:
        print("   %-52s %d" % (lg, n))

    cs2 = [g for g in j if is_cs2(g)]
    print("\nCS2 group 数 =", len(cs2))
    n_ev = sum(len(g.get("events") or []) for g in cs2)
    print("CS2 比赛数 =", n_ev)

    # market description 全集
    mdesc = {}
    dgdesc = {}
    for g in cs2:
        for ev in (g.get("events") or []):
            for dg in (ev.get("displayGroups") or []):
                dgdesc[dg.get("description") or "?"] = dgdesc.get(dg.get("description") or "?", 0) + 1
                for mk in (dg.get("markets") or []):
                    d = mk.get("description") or "?"
                    mdesc[d] = mdesc.get(d, 0) + 1
    print("\ndisplayGroup 全集:", sorted(dgdesc.items(), key=lambda x: -x[1]))
    print("\nmarket description 全集(%d 种):" % len(mdesc))
    for k, v in sorted(mdesc.items(), key=lambda x: -x[1])[:25]:
        print("   %-46s %d" % (k, v))

    # 详细样本
    if not cs2:
        return
    ev = (cs2[0].get("events") or [None])[0]
    if not ev:
        return
    ts = ev.get("startTime")
    st = datetime.fromtimestamp(ts / 1000, timezone.utc).isoformat() if isinstance(ts, (int, float)) else ts
    print("\n" + "-" * 74)
    print("样本: id=%s  %s  start=%s" % (ev.get("id"), ev.get("description"), st))
    print("event 字段:", sorted(ev.keys()))
    comps = ev.get("competitors") or []
    print("competitors:", [(c.get("name"), c.get("home")) for c in comps])
    for dg in (ev.get("displayGroups") or []):
        print("  == displayGroup: %s ==" % dg.get("description"))
        for mk in (dg.get("markets") or []):
            print("     [%s] period=%s" % (mk.get("description"), (mk.get("period") or {}).get("description")))
            for o in (mk.get("outcomes") or [])[:4]:
                pr = o.get("price") or {}
                print("        %-26s dec=%-7s am=%-7s hcp=%-8s"
                      % (o.get("description"), pr.get("decimal"), pr.get("american"), pr.get("handicap")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
