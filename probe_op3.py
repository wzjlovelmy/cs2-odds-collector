#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""oddsportal RSC payload + archive 端点解析"""
import json
import re

from curl_cffi import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
BASE = "https://www.oddsportal.com"


def get(url, ref=None):
    h = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}
    if ref:
        h["Referer"] = ref
        h["X-Requested-With"] = "XMLHttpRequest"
    try:
        r = requests.get(url, timeout=30, impersonate="chrome124", headers=h)
        return r.status_code, r.text
    except Exception as e:
        return None, "ERR %s" % e


def main():
    u = BASE + "/esports/counter-strike/counter-strike-iem-beijing/results/"
    st, body = get(u)
    print("[results] http=%s size=%d" % (st, len(body or "")))
    if st != 200:
        return

    # A. archive 端点上下文
    print("\n=== A. archive 端点上下文 ===")
    for m in list(re.finditer(r"ajax-sport-country-tournament-archive_", body))[:3]:
        print(repr(body[max(0, m.start() - 300):m.start() + 300]))
        print()

    # B. RSC payload 拼接
    pushes = re.findall(r'self\.__next_f\.push\(\[1,\s*"((?:[^"\\]|\\.)*)"\]\)', body)
    print("=== B. RSC push 条数 = %d ===" % len(pushes))
    joined = ""
    for p in pushes:
        try:
            joined += json.loads('"' + p + '"')
        except Exception:
            joined += p
    print("RSC 拼接长度 =", len(joined))

    for kw in ("iem-beijing", "score", "odds", "bookmaker", "handicap",
               "tournament", "matchId", "startTime", "participants"):
        print("   %-14s x%d" % (kw, joined.count(kw)))

    # C. 找 match id 模式
    print("\n=== C. id/比分 模式 ===")
    for pat in (r'"id":"([A-Za-z0-9]{10,24})"',
                r'"score":\[?\s*"?(\d+)"?\s*,\s*"?(\d+)"?',
                r'"home":\{"name":"([^"]{2,25})"',
                r'"slug":"([a-z0-9\-]{10,60})"'):
        hits = list(dict.fromkeys(re.findall(pat, joined)))[:8]
        print("   %-40s -> %s" % (pat[:38], hits))

    # D. 在 RSC 里找一场比赛的数据块
    print("\n=== D. 比赛数据块样本 ===")
    idx = joined.find("iem-beijing")
    if idx < 0:
        idx = joined.find("score")
    if idx >= 0:
        print(joined[max(0, idx - 400):idx + 900])
    else:
        print("未命中，dump 开头 600:")
        print(joined[:600])

    # E. 尝试 archive 端点
    print("\n=== E. archive 端点尝试 ===")
    tid = re.search(r"tournament-archive_/(\d+)/(\d+)", joined)
    print("   tid 提取:", tid.groups() if tid else None)
    cands = []
    if tid:
        cands.append("%s/ajax-sport-country-tournament-archive_/%s/%s/1/"
                     % (BASE, tid.group(1), tid.group(2)))
    for c in cands:
        st2, b2 = get(c, ref=u)
        print("   %s -> http=%s size=%d" % (c, st2, len(b2 or "")))
        if st2 == 200 and b2:
            print("    head:", b2[:400].replace("\n", " "))


if __name__ == "__main__":
    main()
