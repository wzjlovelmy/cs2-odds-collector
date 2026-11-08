#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""betexplorer CS2 路径定位 + oddspapi 端点表"""
import json
import re

from curl_cffi import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
S = requests.Session(impersonate="chrome124")
S.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})


def g(url, ref=None, timeout=25):
    h = {"Referer": ref} if ref else {}
    try:
        r = S.get(url, timeout=timeout, headers=h)
        return r.status_code, r.text
    except Exception as e:
        return None, "ERR %s" % str(e)[:60]


def betexplorer():
    print("\n=== betexplorer 路径定位 ===")
    st, body = g("https://www.betexplorer.com/")
    print("home http=%s size=%d" % (st, len(body or "")))
    if st != 200:
        return

    # 所有 href 里含 counter / cyber / esport
    hrefs = list(dict.fromkeys(re.findall(r'href="([^"]{4,90})"', body)))
    hits = [h for h in hrefs if re.search(r"counter|cyber|esport|csgo|cs2", h, re.I)]
    print("含 CS 线索的链接 %d 条:" % len(hits))
    for h in hits[:20]:
        print("   ", h)

    # "counter" 出现的上下文
    print("\n'counter' 上下文:")
    for m in list(re.finditer(r"counter", body, re.I))[:6]:
        print("   ...%s..." % body[max(0, m.start() - 90):m.start() + 90].replace("\n", " "))

    # 探测候选路径
    cands = ["/esports/", "/cyber/", "/counter-strike/", "/csgo/", "/cs2/",
             "/esports/counter-strike/", "/sports/counter-strike/",
             "/counter-strike/", "/esports/csgo/"]
    print("\n候选路径:")
    for c in cands:
        st2, b2 = g("https://www.betexplorer.com" + c)
        print("   http=%-5s size=%-7d %s" % (st2, len(b2 or ""), c))
        if st2 == 200 and b2 and len(b2) > 20000:
            ls = list(dict.fromkeys(re.findall(r'href="(/[a-z0-9\-/]{4,70})"', b2)))
            cs = [x for x in ls if re.search(r"counter|csgo|cs2|cyber", x, re.I)]
            print("      子链接命中:", cs[:10])
            return


def oddspapi():
    print("\n=== oddspapi 端点 ===")
    st, b = g("https://oddspapi.io/api/v1/sports")
    if st == 200:
        try:
            j = json.loads(b)
            print("  sports:", [(x.get("sportId"), x.get("slug")) for x in j][:14])
            es = [x for x in j if "count" in (x.get("slug") or "").lower()
                  or "esport" in (x.get("slug") or "").lower()]
            print("  电竞项:", es)
        except Exception as e:
            print("  解析失败", e)

    st2, docs = g("https://oddspapi.io/docs")
    print("  docs http=%s size=%d" % (st2, len(docs or "")))
    if st2 == 200:
        eps = list(dict.fromkeys(re.findall(r"/api/v1/[a-zA-Z0-9/_\-{}]{2,50}", docs)))
        print("  文档中的端点:")
        for e in eps[:30]:
            print("     ", e)
        for kw in ("historical", "free", "requests", "limit", "apiKey", "esport"):
            n = docs.lower().count(kw)
            if n:
                print("    kw %-12s x%d" % (kw, n))
        # historical 上下文
        i = docs.lower().find("historical")
        if i > 0:
            print("    historical 上下文:", docs[max(0, i - 200):i + 300].replace("\n", " ")[:500])


def main():
    for fn in (betexplorer, oddspapi):
        try:
            fn()
        except Exception as e:
            print("[%s] 异常 %s" % (fn.__name__, e))
    print("\n=== done ===")


if __name__ == "__main__":
    main()
