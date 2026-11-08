#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""oddsportal archive ajax + 单场赔率端点"""
import json
import re

from curl_cffi import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
BASE = "https://www.oddsportal.com"
REF = BASE + "/esports/counter-strike/counter-strike-iem-beijing/results/"


def get(url, ref=REF):
    h = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9",
         "Referer": ref, "X-Requested-With": "XMLHttpRequest",
         "Accept": "text/html,application/xhtml+xml,application/json,*/*"}
    try:
        r = requests.get(url, timeout=30, impersonate="chrome124", headers=h)
        return r.status_code, r.text
    except Exception as e:
        return None, "ERR %s" % e


def rsc(body):
    pushes = re.findall(r'self\.__next_f\.push\(\[1,\s*"((?:[^"\\]|\\.)*)"\]\)', body)
    out = ""
    for p in pushes:
        try:
            out += json.loads('"' + p + '"')
        except Exception:
            out += p
    return out


def main():
    st, body = get(REF)
    print("[results] http=%s size=%d" % (st, len(body or "")))
    R = rsc(body)
    print("RSC len", len(R))

    # --- A. 直接打 archive ajax 端点
    m = re.search(r"(/ajax-sport-country-tournament-archive_[^\"\\\\]+/\d+/\d+)", R)
    print("\n=== A. archive 端点 ===")
    if m:
        path = m.group(1).replace("\\", "")
        for q in ("", "?_=1794150281"):
            u = BASE + path + q
            st2, b2 = get(u)
            print("  %s\n    http=%s size=%d" % (u[-70:], st2, len(b2 or "")))
            if b2:
                for kw in ("<tr", "odd", "AH", "handicap", "13", "data-"):
                    print("      %-10s x%d" % (kw, b2.count(kw)))
                print("      head:", b2[:500].replace("\n", " "))
    else:
        print("  未找到端点")

    # --- B. RSC 中比赛行对象
    print("\n=== B. 比赛行（name 形如 'A - B'）===")
    rows = re.findall(r'\{[^{}]*?"name":"([^"]{3,60}?\s-\s[^"]{2,40})"[^{}]*?\}', R)
    print("  条数", len(rows), "前 12:", rows[:12])
    # 找完整一行的上下文
    mm = re.search(r'.{300}"name":"[^"]+ - [^"]+".{500}', R)
    if mm:
        print("\n  单行上下文:\n", mm.group(0)[:820])

    # --- C. RSC 里的比赛 URL
    print("\n=== C. 比赛 URL ===")
    urls = list(dict.fromkeys(re.findall(
        r"/esports/counter-strike/counter-strike-iem-beijing/[a-z0-9\-]{4,80}/", R)))
    print("  条数", len(urls))
    for u in urls[:12]:
        print("   ", u)

    # --- D. 试旧式单场赔率端点
    print("\n=== D. 赔率端点尝试 ===")
    cands = [
        BASE + "/esports/counter-strike/counter-strike-iem-beijing/results/",
    ]
    if urls:
        cands.append(BASE + urls[0])
    for u in cands:
        st3, b3 = get(u)
        print("  %s\n    http=%s size=%d" % (u[-80:], st3, len(b3 or "")))
        if b3 and len(b3) > 20000:
            R3 = rsc(b3) if "self.__next_f" in b3 else b3
            for kw in ("Asian Handicap", "Handicap", "Over/Under", "AH",
                       "OU", "oddsData", "bookmakersCount"):
                print("      %-16s x%d" % (kw, R3.count(kw)))
            # 抓 AH 相关片段
            i = R3.find("Asian Handicap")
            if i > 0:
                print("      AH 片段:", R3[max(0, i - 200):i + 400].replace("\\", ""))


if __name__ == "__main__":
    main()
