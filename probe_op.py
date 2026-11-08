#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
oddsportal 历史盘口结构解析
目标：找到「赛事 → 已结束比赛 → 亚洲让分/总分 历史赔率」的取数路径
"""
import json
import re
import sys

from curl_cffi import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
BASE = "https://www.oddsportal.com"


def get(url, timeout=25):
    h = {"User-Agent": UA,
         "Accept": "text/html,application/xhtml+xml,application/json,*/*",
         "Accept-Language": "en-US,en;q=0.9"}
    try:
        r = requests.get(url, headers=h, timeout=timeout, impersonate="chrome124")
        return r.status_code, r.text
    except Exception as e:
        return None, "ERR %s: %s" % (type(e).__name__, e)


def nextdata(body):
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', body, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:
        return None


def dig(obj, path="", depth=0, out=None, maxd=6):
    """把嵌套 JSON 的路径打印出来（限制深度与数量）"""
    if out is None:
        out = []
    if depth > maxd or len(out) > 120:
        return out
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = "%s.%s" % (path, k) if path else k
            if isinstance(v, (dict, list)):
                out.append("%s  <%s len=%d>" % (p, type(v).__name__, len(v)))
                dig(v, p, depth + 1, out, maxd)
            else:
                out.append("%s = %s" % (p, str(v)[:70]))
    elif isinstance(obj, list) and obj:
        dig(obj[0], path + "[0]", depth + 1, out, maxd)
    return out


def step1_list():
    """赛事列表页"""
    for u in (BASE + "/esports/counter-strike/",
              BASE + "/esports/counter-strike/matches/"):
        st, body = get(u)
        print("\n" + "=" * 76)
        print("[list] %s  http=%s  size=%d" % (u, st, len(body or "")))
        if not body or st != 200:
            continue
        # Next.js 数据
        nd = nextdata(body)
        if nd:
            print("  __NEXT_DATA__ 存在, top keys:", list(nd.keys()))
            props = (nd.get("props") or {}).get("pageProps") or {}
            print("  pageProps keys:", list(props.keys())[:25])
            lines = dig(props, "pageProps", 0, [], 4)
            for L in lines[:60]:
                print("   ", L)
        else:
            print("  无 __NEXT_DATA__")
        # 赛事链接
        ls = re.findall(r'href="(/esports/counter-strike/[^"#?]{3,60})"', body)
        uniq = [x for x in dict.fromkeys(ls)]
        print("  赛事/子页链接 %d 条, 前 25:" % len(uniq))
        for x in uniq[:25]:
            print("    ", x)
        # 其他数据痕迹
        for pat in ("oddb", "window.__", "tournament", "ajax"):
            n = body.count(pat)
            if n:
                print("   痕迹 %-14s x%d" % (pat, n))
        return body
    return None


def step2_event(slug):
    """赛事结果页"""
    for suffix in ("/results/", "/"):
        u = BASE + "/esports/counter-strike/%s%s" % (slug, suffix)
        st, body = get(u)
        print("\n" + "=" * 76)
        print("[event] %s  http=%s  size=%d" % (u, st, len(body or "")))
        if not body or st != 200 or len(body) < 20000:
            continue
        nd = nextdata(body)
        if nd:
            props = (nd.get("props") or {}).get("pageProps") or {}
            print("  pageProps keys:", list(props.keys())[:25])
            # 找 rows / matches
            for key in ("rows", "matches", "data", "tournament", "participants"):
                if key in props:
                    v = props[key]
                    print("   %s: %s len=%s" % (key, type(v).__name__,
                                                len(v) if hasattr(v, "__len__") else "-"))
            lines = dig(props, "pageProps", 0, [], 5)
            for L in lines[:80]:
                print("   ", L)
        # 比赛链接
        ls = re.findall(r'href="(/esports/counter-strike/%s/([a-z0-9\-]{6,80}))"' % re.escape(slug), body)
        uniq = list(dict.fromkeys(ls))
        print("  比赛链接 %d 条, 前 10:" % len(uniq))
        for a, b in uniq[:10]:
            print("    ", a)
        if uniq:
            return slug, uniq[0][0]
        return slug, None
    return slug, None


def step3_match(path):
    """单场比赛页：看 1X2 / AH / OU 表"""
    for suffix in ("", "/"):
        u = BASE + path + suffix
        st, body = get(u)
        print("\n" + "=" * 76)
        print("[match] %s  http=%s  size=%d" % (u, st, len(body or "")))
        if not body or st != 200 or len(body) < 20000:
            continue
        nd = nextdata(body)
        if nd:
            props = (nd.get("props") or {}).get("pageProps") or {}
            print("  pageProps keys:", list(props.keys())[:30])
            lines = dig(props, "pageProps", 0, [], 5)
            for L in lines[:100]:
                print("   ", L)
        # 盘口 tab
        for kw in ("Asian Handicap", "Handicap", "Over/Under", "Maps", "1X2",
                   "Home/Away", "Correct Score"):
            n = body.count(kw)
            if n:
                print("   tab %-16s x%d" % (kw, n))
        # 找 oddb / hash 路由
        for kw in ("#/1X2", "#/AH", "#/OU", "submenu", "odds-data"):
            n = body.count(kw)
            if n:
                print("   痕迹 %-12s x%d" % (kw, n))
        return body
    return None


def main():
    print("curl_cffi ready")
    body = step1_list()
    if not body:
        print("列表页失败，退出")
        return

    # 手动挑关键赛事 slug（从之前 HLTV 数据集）
    wanted = ["iem-beijing", "esl-pro-league", "pgl", "blast", "esports-world-cup",
              "fissure", "iem", "esl"]
    ls = re.findall(r'href="(/esports/counter-strike/([^"#?/]{3,60})/?)"', body)
    slugs = list(dict.fromkeys(s for _, s in ls))
    print("\n候选 slug:", slugs[:30])

    pick = None
    for w in wanted:
        for s in slugs:
            if w in s:
                pick = s
                break
        if pick:
            break
    if not pick and slugs:
        pick = slugs[0]
    print("\n>>> 选用 slug:", pick)
    if not pick:
        return

    slug, mpath = step2_event(pick)
    if mpath:
        step3_match(mpath)
    print("\n" + "=" * 76)
    print("done")


if __name__ == "__main__":
    main()
