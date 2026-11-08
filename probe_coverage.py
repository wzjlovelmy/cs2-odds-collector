#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""oddspapi historical-data / coverage 覆盖范围"""
import re

from curl_cffi import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
S = requests.Session(impersonate="chrome124")
S.headers.update({"User-Agent": UA, "Accept": "text/html,*/*"})


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


for path in ("/historical-data", "/coverage"):
    st, b = g("https://oddspapi.io" + path)
    print("\n=== %s http=%s size=%d ===" % (path, st, len(b or "")))
    if st != 200:
        continue
    t = flat(b)
    print("  正文长度", len(t))
    print("  片段:", t[:1400])

# docs 里 historical odds 的完整参数
st, d = g("https://oddspapi.io/docs")
if st == 200:
    t = flat(d)
    print("\n=== docs: 'historical odds' 前后 ===")
    for m in list(re.finditer(r"[Hh]istorical [Oo]dds", t))[:4]:
        print("\n ...%s..." % t[max(0, m.start() - 250):m.start() + 600])

    print("\n=== docs: 端点参数区（GET odds）===")
    i = t.find("GET odds")
    if i < 0:
        i = t.find("Get odds")
    if i >= 0:
        print(t[i:i + 900])
