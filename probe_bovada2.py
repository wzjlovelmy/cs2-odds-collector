#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bovada 深挖：能否拿到单图（Map 1）级别的回合让分 / 回合总分。
两条路：
  1) coupon 端点换 marketFilterId=all / 去掉 preMatchOnly
  2) event 详情端点 /services/sports/event/v2/events/A/{id}
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

H = {"User-Agent": UA, "Accept": "application/json", "Accept-Encoding": "identity",
     "Referer": "https://www.bovada.lv/", "Origin": "https://www.bovada.lv"}

COUPON = ("https://www.bovada.lv/services/sports/event/coupon/events/A/description/esports"
          "?marketFilterId=%s&preMatchOnly=%s&lang=en")


def get(url, quiet=False):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=30) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception as e:
        return -1, str(e).encode()


def cs2_events(j):
    out = []
    for g in j if isinstance(j, list) else []:
        if not any("counter" in (p.get("description") or "").lower()
                   for p in (g.get("path") or [])):
            continue
        out.extend(g.get("events") or [])
    return out


def summarize(ev, tag):
    dgs = ev.get("displayGroups") or []
    descs = []
    for dg in dgs:
        for mk in (dg.get("markets") or []):
            descs.append("%s|%s" % (dg.get("description"), mk.get("description")))
    print("   %-8s id=%-10s %-34s markets=%-3s %s"
          % (tag, ev.get("id"), (ev.get("description") or "")[:34],
             ev.get("numMarkets"), sorted(set(descs))[:8]))


def main():
    print("=" * 78)
    print("### 1) coupon 端点参数变化")
    for fid in ("def", "all"):
        for pre in ("true", "false"):
            st, body = get(COUPON % (fid, pre))
            if st != 200:
                print("  filter=%-4s pre=%-5s HTTP=%s" % (fid, pre, st))
                continue
            try:
                j = json.loads(body.decode("utf-8", "replace"))
            except Exception:
                print("  filter=%-4s pre=%-5s 非 JSON len=%d" % (fid, pre, len(body)))
                continue
            evs = cs2_events(j)
            nm = sum(len(e.get("displayGroups") or []) for e in evs)
            mk = sum(len(dg.get("markets") or []) for e in evs for dg in (e.get("displayGroups") or []))
            print("  filter=%-4s pre=%-5s HTTP=200 bytes=%-7d CS2场次=%-3d 组=%-3d 盘口=%d"
                  % (fid, pre, len(body), len(evs), nm, mk))
            if not evs:
                continue
            for e in evs[:2]:
                summarize(e, "f=%s" % fid)
            if fid == "all":
                # 打印所有 displayGroup 名称
                names = {}
                for e in evs:
                    for dg in (e.get("displayGroups") or []):
                        names[dg.get("description")] = names.get(dg.get("description"), 0) + 1
                print("     displayGroup 全集:", sorted(names.items(), key=lambda x: -x[1]))
            break

    print("\n### 2) event 详情端点")
    st, body = get(COUPON % ("def", "true"))
    evs = cs2_events(json.loads(body.decode("utf-8", "replace"))) if st == 200 else []
    if not evs:
        print("  无 CS2 事件")
        return 0
    eid = evs[0].get("id")
    cands = [
        "https://www.bovada.lv/services/sports/event/v2/events/A/%s" % eid,
        "https://www.bovada.lv/services/sports/event/coupon/events/A/%s" % eid,
        "https://www.bovada.lv/services/sports/event/v2/events/A/%s?lang=en" % eid,
        "https://www.bovada.lv/services/sports/event/v2/events/A/%s?marketFilterId=all&lang=en" % eid,
        "https://www.bovada.lv/services/sports/event/coupon/events/A/%s?marketFilterId=all&lang=en" % eid,
    ]
    for u in cands:
        st, body = get(u)
        txt = body.decode("utf-8", "replace")
        print("  [%s] HTTP=%-4s bytes=%-7d %s"
              % ("OK " if st == 200 else "ERR", st, len(body), u.split("events/A/")[-1][:40]))
        if st == 200 and len(body) > 200:
            try:
                j = json.loads(txt)
            except Exception:
                continue
            objs = j if isinstance(j, list) else [j]
            for o in objs[:1]:
                if isinstance(o, dict) and "displayGroups" in o:
                    dgs = o.get("displayGroups") or []
                    print("      displayGroups=%d" % len(dgs))
                    for dg in dgs[:12]:
                        ms = [m.get("description") for m in (dg.get("markets") or [])]
                        print("        [%s] %s" % (dg.get("description"), ms[:6]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
