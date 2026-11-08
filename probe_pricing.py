#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""oddspapi 定价/额度 + historical-odds 规格"""
import json
import re

from curl_cffi import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
S = requests.Session(impersonate="chrome124")
S.headers.update({"User-Agent": UA, "Accept": "text/html,application/json,*/*"})


def g(url, timeout=25):
    try:
        r = S.get(url, timeout=timeout)
        return r.status_code, r.text
    except Exception as e:
        return None, "ERR %s" % str(e)[:70]


def flat(html):
    t = re.sub(r"<script[\s\S]*?</script>", " ", html)
    t = re.sub(r"<style[\s\S]*?</style>", " ", t)
    t = re.sub(r"<[^>]+>", " ", t)
    t = t.replace("&quot;", '"').replace("&amp;", "&").replace("&#x27;", "'")
    return re.sub(r"\s+", " ", t)


print("=== pricing ===")
st, b = g("https://oddspapi.io/pricing")
print("http=%s size=%d" % (st, len(b or "")))
if st == 200:
    t = flat(b)
    for kw in ("Free", "requests", "month", "day", "Pinnacle", "historical",
               "bookmakers", "sports", "€", "$", "€", "per request"):
        idxs = [m.start() for m in re.finditer(kw, t, re.I)][:2]
        for i in idxs:
            print("  [%s] ...%s..." % (kw, t[max(0, i - 100):i + 160]))

print("\n=== docs: historical-odds 段落 ===")
st2, d = g("https://oddspapi.io/docs")
if st2 == 200:
    t = flat(d)
    for kw in ("historical-odds", "Historical odds", "odds-by-tournaments"):
        i = t.find(kw)
        if i >= 0:
            print("\n  [%s]\n  %s" % (kw, t[i:i + 700]))

    print("\n  --- odds 响应字段 ---")
    for kw in ("marketId", "marketType", "handicap", "period", "outcomeId",
               "outcomeName", "odds", "price", "bookmaker", "priceType",
               "startTime", "participant1Name"):
        i = t.find(kw)
        print("    %-18s x%-4d %s" % (kw, t.count(kw),
                                      ("..." + t[max(0, i - 50):i + 90] + "...") if i > 0 else ""))

    print("\n  --- period / handicap 说明 ---")
    for kw in ("period=", "period", "handicap=-1.5", "handicap"):
        for m in list(re.finditer(kw, t))[:2]:
            print("    [%s] %s" % (kw, t[max(0, m.start() - 80):m.start() + 160]))
