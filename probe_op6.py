#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""oddsportal /event/{id}/ 页赔率字段挖掘"""
import json
import re
from collections import Counter

from curl_cffi import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
BASE = "https://www.oddsportal.com"
S = requests.Session(impersonate="chrome124")
S.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})

EID = 11643979
ENCODE = "zaJFTWlo"


def get(url, ref=None):
    h = {"Referer": ref} if ref else {}
    try:
        r = S.get(url, timeout=30, headers=h)
        return r.status_code, r.text
    except Exception as e:
        return None, "ERR %s" % e


def rsc(body):
    out = ""
    for p in re.findall(r'self\.__next_f\.push\(\[1,\s*"((?:[^"\\]|\\.)*)"\]\)', body):
        try:
            out += json.loads('"' + p + '"')
        except Exception:
            out += p
    return out


def main():
    get(BASE + "/")
    u = "%s/event/%s/" % (BASE, EID)
    st, body = get(u, ref=BASE + "/esports/counter-strike/")
    print("[event] http=%s size=%d" % (st, len(body or "")))
    if st != 200:
        return
    R = rsc(body) if "self.__next_f" in body else body
    print("RSC len=%d (raw=%d)" % (len(R), len(body)))

    # A. 所有 JSON key 频次
    keys = Counter(re.findall(r'"([a-zA-Z][a-zA-Z0-9_\-]{2,28})":', R))
    print("\n=== A. 高频 key 前 60 ===")
    for k, v in keys.most_common(60):
        print("   %-28s %d" % (k, v))

    # B. 含 odd / price / hand 的 key
    print("\n=== B. 赔率相关 key ===")
    for k, v in keys.most_common():
        if any(t in k.lower() for t in ("odd", "price", "hand", "line",
                                        "market", "bookm", "bet")):
            print("   %-28s %d" % (k, v))

    # C. ajax / api 端点
    print("\n=== C. ajax / api 端点 ===")
    for pat in (r'ajax-[a-zA-Z0-9_\-]{4,40}', r'/api/[a-zA-Z0-9/_\-]{3,60}'):
        hits = list(dict.fromkeys(re.findall(pat, R)))[:15]
        print("   %s -> %s" % (pat[:24], hits))

    # D. bookmaker 对象样本
    print("\n=== D. bookmaker 对象样本 ===")
    m = re.search(r'\{[^{}]{0,40}"bookmaker[^"]*":', R)
    if m:
        s = max(0, m.start() - 100)
        print("  ", R[s:s + 500].replace("\\", ""))

    # E. 尝试 encodeEventId URL
    print("\n=== E. encodeEventId URL ===")
    for path in ("/esports/counter-strike/counter-strike-iem-beijing/the-mongolz-mouz-%s/" % ENCODE,
                 "/esports/counter-strike/counter-strike-iem-beijing/mouz-the-mongolz-%s/" % ENCODE):
        st2, b2 = get(BASE + path, ref=u)
        print("  http=%s size=%-7d %s" % (st2, len(b2 or ""), path[-46:]))
        if st2 == 200 and b2 and len(b2) > 30000:
            R2 = rsc(b2) if "self.__next_f" in b2 else b2
            k2 = Counter(re.findall(r'"([a-zA-Z][a-zA-Z0-9_\-]{2,28})":', R2))
            rel = [(k, v) for k, v in k2.most_common()
                   if any(t in k.lower() for t in ("odd", "price", "hand", "bookm"))]
            print("     赔率 key:", rel[:12])

    # F. 页面里 hash 路由 / tab
    print("\n=== F. tab / hash 路由 ===")
    for kw in ("#/1X2", "#/AH", "#/OU", "#/score", "submenu", "tab-",
               "over-under", "asian-handicap", "home-away"):
        n = body.count(kw)
        if n:
            print("   %-16s x%d" % (kw, n))


if __name__ == "__main__":
    main()
