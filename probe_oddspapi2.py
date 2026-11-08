#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""oddspapi 无 key 路径穷举 + 参数名提取"""
import json
import re

from curl_cffi import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
S = requests.Session(impersonate="chrome124")
S.headers.update({"User-Agent": UA, "Accept": "application/json,*/*"})


def g(url, timeout=25):
    try:
        r = S.get(url, timeout=timeout)
        return r.status_code, r.text
    except Exception as e:
        return None, "ERR %s" % str(e)[:70]


cands = [
    "https://oddspapi.io/api/v1/matches?tournamentId=2390",
    "https://oddspapi.io/api/v1/matches?sportId=17&tournamentId=2390",
    "https://api.oddspapi.io/v4/tournaments?sportId=17",
    "https://api.oddspapi.io/v4/matches?tournamentId=2390",
    "https://api.oddspapi.io/v4/odds?matchId=1",
    "https://api.oddspapi.io/v4/bookmakers",
    "https://api.oddspapi.io/v4/historical?matchId=1",
    "https://oddspapi.io/api/v1/sports",
    "https://oddspapi.io/api/v1/odds?matchId=1",
    "https://oddspapi.io/api/v1/historical?matchId=1",
    "https://oddspapi.io/api/v1/tournaments?sportId=17&apiKey=demo",
    "https://api.oddspapi.io/v4/tournaments?sportId=17&apiKey=demo",
]

print("=== 端点穷举（无 key）===")
for u in cands:
    st, b = g(u)
    note = ""
    if b and len(b) < 300:
        note = " | body=" + b.replace("\n", " ")[:150]
    print("http=%-5s size=%-7d %s%s" % (st, len(b or ""), u[-62:], note))

# docs 参数表
print("\n=== docs 参数提取 ===")
st, b = g("https://oddspapi.io/docs")
if st == 200:
    txt = re.sub(r"<[^>]+>", " ", b)
    txt = txt.replace("&quot;", '"').replace("&amp;", "&").replace("\\n", " ")
    txt = re.sub(r"\s+", " ", txt)
    for kw in ("GET /v4/odds", "GET /v4/matches", "GET /v4/historical",
               "GET /v4/tournaments", "GET /v4/bookmakers", "GET /v4/sports"):
        i = txt.find(kw)
        if i >= 0:
            print("\n  [%s] %s" % (kw, txt[i:i + 320]))
    print("\n  --- 参数关键词频次 ---")
    for kw in ("matchId", "tournamentId", "sportId", "bookmaker", "fromDate",
               "toDate", "marketId", "outcomeId", "marketType", "handicap",
               "period", "participantId", "startDate", "endDate", "apiKey"):
        print("    %-14s x%d" % (kw, txt.count(kw)))

# 全端点列表（从 JS 或正文）
print("\n=== 文档中出现的 v4 端点 ===")
if st == 200:
    eps = list(dict.fromkeys(re.findall(r"/v4/[a-zA-Z0-9/_\-]{2,40}", b)))
    print("  ", eps)
