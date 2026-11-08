#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""oddsportal results 页 HTML 结构切片（只输出摘要 + 小样本）"""
import json
import re

from curl_cffi import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
BASE = "https://www.oddsportal.com"


def get(url):
    try:
        r = requests.get(url, timeout=30, impersonate="chrome124",
                         headers={"User-Agent": UA,
                                  "Accept-Language": "en-US,en;q=0.9"})
        return r.status_code, r.text
    except Exception as e:
        return None, "ERR %s" % e


def ctx(body, needle, n=4, w=180):
    out = []
    for m in list(re.finditer(re.escape(needle), body))[:n]:
        s = max(0, m.start() - w // 2)
        out.append(body[s:s + w].replace("\n", " "))
    return out


def main():
    u = BASE + "/esports/counter-strike/counter-strike-iem-beijing/results/"
    st, body = get(u)
    print("[results] http=%s size=%d" % (st, len(body or "")))
    if st != 200:
        return

    # 1. window.__ 全局变量
    print("\n--- window.__ 上下文 ---")
    for m in list(re.finditer(r"window\.__[A-Za-z_]+", body))[:8]:
        print("  at %d: %s" % (m.start(), body[m.start():m.start() + 90]))

    # 2. 所有 href 去重
    hrefs = re.findall(r'href="([^"]{3,120})"', body)
    uniq = list(dict.fromkeys(hrefs))
    print("\n--- href 共 %d 条（去重后 %d），前 30 ---" % (len(hrefs), len(uniq)))
    for h in uniq[:30]:
        print("   ", h)

    # 3. 表格结构
    print("\n--- 表格/行 class 痕迹 ---")
    for pat in ("table-main", "eventRow", "event-row", "results", "data-odd",
                "oddsCell", ">" + "13" + "<", "<tr", "tbody"):
        print("   %-14s x%d" % (pat, body.count(pat)))

    # 4. 抓 <tr 片段
    print("\n--- <tr 原始片段（前 3 条，各 500 字符）---")
    for i, m in enumerate(list(re.finditer(r"<tr[\s>]", body))[:3]):
        print("  [%d] %s" % (i, body[m.start():m.start() + 500].replace("\n", " ")))
        print()

    # 5. 盘口 tab
    print("--- 盘口关键词 ---")
    for kw in ("Asian Handicap", "Handicap", "Over/Under", "1X2", "Maps",
               "home-away", "AH", "OU"):
        print("   %-16s x%d" % (kw, body.count(kw)))

    # 6. 找可能的 ajax / feed 端点
    print("\n--- ajax / feed 端点线索 ---")
    for pat in (r'"/ajax[^"]{0,80}"', r'"/feed[^"]{0,80}"', r'ajax-[a-z\-_]+',
                r'/api/[a-zA-Z0-9/_\-]{3,60}'):
        hits = list(dict.fromkeys(re.findall(pat, body)))[:8]
        if hits:
            print("   %s ->" % pat, hits)

    # 7. 数据脚本块名
    print("\n--- script 标签概览 ---")
    for m in list(re.finditer(r"<script([^>]*)>", body))[:25]:
        a = m.group(1).strip()
        if a:
            print("   <script %s>" % a[:110])


if __name__ == "__main__":
    main()
