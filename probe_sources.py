#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多源 CS2 赔率可用性探测。
Pinnacle 已下架 esports（sport id 1~68 全是传统体育），需要换源。

对每个候选源输出：HTTP 状态 / 响应字节 / 是否出现 Counter-Strike / 前 200 字符。
只做探测，不解析。
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

BASE_HEADERS = {
    "User-Agent": UA,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "identity",
}

# (名字, url, 额外 headers)
SOURCES = [
    ("sofascore-esports-schedule",
     "https://api.sofascore.com/api/v1/sport/esports/scheduled-events/2026-11-09",
     {"Referer": "https://www.sofascore.com/"}),

    ("sofascore-cs2-schedule",
     "https://api.sofascore.com/api/v1/unique-tournament/20313/season/0/events/last/0",
     {"Referer": "https://www.sofascore.com/"}),

    ("kambi-unibet-esports",
     "https://eu-offering-api.kambicdn.com/offering/v2018/ubus/listView/esports.json"
     "?lang=en_US&market=US&client_id=2&channel_id=1&ncid=1",
     {}),

    ("kambi-betcafe-esports",
     "https://eu-offering-api.kambicdn.com/offering/v2018/betcafe/listView/esports.json"
     "?lang=en_US&market=NL&client_id=2&channel_id=1&ncid=1",
     {}),

    ("kambi-ub-esports-full",
     "https://eu-offering-api.kambicdn.com/offering/v2018/ub/esports.json"
     "?lang=en_GB&market=GB&client_id=2&channel_id=1&ncid=1&useCombined=true",
     {}),

    ("bo3gg-matches",
     "https://api.bo3.gg/api/v1/matches?page%5Bsize%5D=5&sort=start_date",
     {"Accept": "application/vnd.api+json"}),

    ("1xbet-linefeed",
     "https://1xbet.com/LineFeed/Get1x2_VZip?sports=1&count=5&lng=en&mode=4&country=1",
     {"Referer": "https://1xbet.com/"}),

    ("the-odds-api-sports",
     "https://api.the-odds-api.com/v4/sports",
     {}),

    ("pinnacle-web-esports",
     "https://www.pinnacle.com/en/esports/counter-strike-2/matchups/",
     {"Accept": "text/html"}),

    ("betway-esports",
     "https://sports.betway.com/api/en-CA/sports/esports",
     {"Referer": "https://sports.betway.com/"}),

    ("abios-public",
     "https://api.abiosgaming.com/v2/series?limit=5",
     {}),

    ("ggscore-csgo",
     "https://ggscore.com/en/csgo/matches",
     {"Accept": "text/html"}),
]

KEYS = ("counter-strike", "counter strike", "cs2", "csgo", "cs:go")


def probe(name, url, extra):
    h = dict(BASE_HEADERS)
    h.update(extra)
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            body = r.read()
            status = r.status
            ctype = r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        body = b""
        try:
            body = e.read()[:4000]
        except Exception:
            pass
        status = e.code
        ctype = ""
    except Exception as e:
        print("[FAIL] %-26s %s" % (name, str(e)[:90]))
        return
    txt = body.decode("utf-8", "replace")
    low = txt.lower()
    hits = [k for k in KEYS if k in low]
    print("[%s] %-26s HTTP=%s bytes=%d ctype=%s"
          % ("OK  " if status == 200 else "ERR ", name, status, len(body), ctype[:30]))
    if hits:
        print("       CS2 关键词命中: %s" % hits)
        # 找第一个出现位置附近的内容，便于确认是真赛事
        i = min(low.find(k) for k in hits if low.find(k) >= 0)
        print("       片段: ...%s..." % txt[max(0, i - 80):i + 100].replace("\n", " "))
    print("       开头: %s" % txt[:180].replace("\n", " "))


def main():
    print("=" * 78)
    for name, url, extra in SOURCES:
        probe(name, url, extra)
        print("-" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
