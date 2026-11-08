#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""oddspapi 规格与免费额度"""
import json
import re

from curl_cffi import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
S = requests.Session(impersonate="chrome124")
S.headers.update({"User-Agent": UA, "Accept": "application/json,text/html,*/*"})


def g(url, timeout=25):
    try:
        r = S.get(url, timeout=timeout)
        return r.status_code, r.text
    except Exception as e:
        return None, "ERR %s" % str(e)[:60]


def main():
    # 1) OpenAPI 可能性
    print("=== 1. OpenAPI 探测 ===")
    for u in ("https://oddspapi.io/openapi.json",
              "https://oddspapi.io/api/openapi.json",
              "https://oddspapi.io/docs/openapi.json",
              "https://api.oddspapi.io/openapi.json",
              "https://oddspapi.io/api/v1/docs",
              "https://oddspapi.io/api-docs"):
        st, b = g(u)
        print("  http=%-5s size=%-8d %s" % (st, len(b or ""), u))
        if st == 200 and b and b.strip().startswith("{"):
            try:
                j = json.loads(b)
                print("     keys:", list(j.keys())[:12])
                paths = j.get("paths") or {}
                print("     paths:", list(paths.keys())[:20])
                if paths:
                    k = list(paths.keys())[0]
                    print("     sample:", json.dumps(paths[k], ensure_ascii=False)[:400])
            except Exception as ex:
                print("     解析失败", ex)

    # 2) docs 页面正文提取
    print("\n=== 2. docs 正文 ===")
    st, b = g("https://oddspapi.io/docs")
    print("  http=%s size=%d" % (st, len(b or "")))
    if st == 200:
        txt = re.sub(r"<[^>]+>", " ", b)
        txt = re.sub(r"\s+", " ", txt)
        # 端点
        eps = list(dict.fromkeys(re.findall(r"/(?:api/)?v1/[a-zA-Z0-9/_\-{}$]{2,50}", b)))
        print("  端点:", eps[:25])
        # 关键词上下文
        for kw in ("free", "100 requests", "per month", "per day", "rate limit",
                   "historical", "apiKey", "apikey", "X-API"):
            for m in list(re.finditer(kw, txt, re.I))[:2]:
                seg = txt[max(0, m.start() - 130):m.start() + 190]
                print("  [%s] ...%s..." % (kw, seg))
                break

    # 3) 试探不带 key 的关键端点
    print("\n=== 3. 端点可达性（无 key）===")
    for u in ("https://oddspapi.io/api/v1/tournaments?sportId=17",
              "https://oddspapi.io/api/v1/matches?sportId=17",
              "https://oddspapi.io/api/v1/fixtures?sportId=17",
              "https://oddspapi.io/api/v1/bookmakers"):
        st, b = g(u)
        print("  http=%-5s size=%-7d %s" % (st, len(b or ""), u[-52:]))
        if st == 200 and b and len(b) < 1200:
            print("      ", b[:400].replace("\n", " "))
        elif st == 200:
            print("       len 较大, head:", b[:200].replace("\n", " "))


if __name__ == "__main__":
    main()
