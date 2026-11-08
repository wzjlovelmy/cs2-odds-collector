#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第二批：Kambi 多品牌 + bo3.gg 赔率端点 + Stake。
Kambi 是欧洲最大 B2B 博彩平台，它的 CS2 盘口含 Map 1 Winner / Map Handicap /
Map Total Rounds，正好是要的三种盘。
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

BASE = {
    "User-Agent": UA,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "identity",
}

BRANDS = ["unibet", "betsson", "nordicbet", "coolbet", "leovegas",
          "paf", "sportingbet", "mrgreen", "888sport", "unibetuk",
          "betssonit", "norgesspill"]

KEYS = ("counter-strike", "counter strike", "cs2", "csgo", "cs:go")


def req(url, extra=None, data=None, timeout=22):
    h = dict(BASE)
    if extra:
        h.update(extra)
    r = urllib.request.Request(url, headers=h, data=data)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, resp.read(), resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        try:
            return e.code, e.read()[:3000], ""
        except Exception:
            return e.code, b"", ""
    except Exception as e:
        return -1, str(e).encode(), ""


def show(tag, status, body, ctype=""):
    txt = body.decode("utf-8", "replace")
    low = txt.lower()
    hits = [k for k in KEYS if k in low]
    print("[%s] %-30s HTTP=%s bytes=%d" % ("OK  " if status == 200 else "ERR ", tag, status, len(body)))
    if hits:
        i = min(low.find(k) for k in hits if low.find(k) >= 0)
        print("       CS2命中 %s | ...%s..." % (hits, txt[max(0, i - 60):i + 90].replace("\n", " ")))
    print("       head: %s" % txt[:150].replace("\n", " "))


def kambi():
    print("\n########## Kambi 品牌探测 ##########")
    for b in BRANDS:
        url = ("https://eu-offering-api.kambicdn.com/offering/v2018/%s/listView/esports.json"
               "?lang=en_GB&market=GB&client_id=2&channel_id=1&ncid=1" % b)
        st, body, ct = req(url, {"Origin": "https://www.%s.com" % b,
                                 "Referer": "https://www.%s.com/" % b})
        show("kambi/" + b, st, body, ct)
        if st == 200 and b"counter" in body.lower():
            try:
                j = json.loads(body)
                events = j.get("events") or []
                print("       events=%d  首条=%s" % (len(events), events[0].get("event", {}).get("name") if events else "-"))
            except Exception as e:
                print("       parse err", e)
            return b
    return None


def bo3():
    print("\n########## bo3.gg 赔率端点 ##########")
    st, body, _ = req("https://api.bo3.gg/api/v1/matches?page%5Bsize%5D=3&sort=-start_date",
                      {"Accept": "application/vnd.api+json"})
    show("bo3 matches(latest)", st, body)
    if st != 200:
        return
    try:
        j = json.loads(body)
        rs = j.get("results") or []
        if not rs:
            return
        mid = rs[0].get("id")
        print("       样本 match id=%s slug=%s" % (mid, rs[0].get("slug")))
        print("       match 字段:", sorted(rs[0].keys()))
    except Exception as e:
        print("       parse err", e)
        return

    for path in ("https://api.bo3.gg/api/v1/matches/%s" % mid,
                 "https://api.bo3.gg/api/v1/matches/%s?include=odds" % mid,
                 "https://api.bo3.gg/api/v1/odds?filter%5Bmatch_id%5D=%s" % mid,
                 "https://api.bo3.gg/api/v1/matches/%s/odds" % mid):
        st, body, _ = req(path, {"Accept": "application/vnd.api+json"})
        txt = body.decode("utf-8", "replace")
        has = "odds" in txt.lower() or "bet" in txt.lower()
        print("  [%s] %-58s HTTP=%s bytes=%d odds字段=%s"
              % ("OK " if st == 200 else "ERR", path.split("bo3.gg")[1][:58], st, len(body), has))
        if st == 200 and has:
            print("       ...%s..." % txt[:260].replace("\n", " "))


def stake():
    print("\n########## Stake GraphQL ##########")
    payload = json.dumps({"query": "{ __typename }"}).encode()
    st, body, _ = req("https://stake.com/_api/graphql",
                      {"Content-Type": "application/json",
                       "Origin": "https://stake.com",
                       "Referer": "https://stake.com/"},
                      data=payload)
    show("stake graphql", st, body)


def main():
    print("=" * 78)
    hit = kambi()
    bo3()
    stake()
    print("\n>>> Kambi 可用品牌:", hit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
