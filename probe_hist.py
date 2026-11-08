#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
历史让分盘口来源探测（在 GitHub Actions 美国出口运行）
目标：找到「已结束比赛 + 让分/总分盘口」的可回溯数据源
"""
import json
import re
import sys

try:
    from curl_cffi import requests
except ImportError:
    requests = None

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def get(url, headers=None, timeout=20, imp="chrome124"):
    h = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/json,*/*",
        "Accept-Language": "en-US,en;q=0.9",
    }
    if headers:
        h.update(headers)
    try:
        if requests:
            r = requests.get(url, headers=h, timeout=timeout, impersonate=imp,
                             allow_redirects=True)
        else:
            import urllib.request
            req = urllib.request.Request(url, headers=h)
            r = urllib.request.urlopen(req, timeout=timeout)
        return r.status_code, r.text, dict(r.headers)
    except Exception as e:
        return None, "ERR: %s: %s" % (type(e).__name__, e), {}


def show(tag, url, body, extra=""):
    """打印可达性与结构线索"""
    size = len(body) if body else 0
    print("\n" + "=" * 76)
    print("[%s] %s" % (tag, url))
    print("size=%d  %s" % (size, extra))
    if not body:
        return
    low = body.lower()
    for kw in ("cloudflare", "just a moment", "captcha", "access denied",
               "handicap", "asian", "spread", "total", "map handicap",
               "over/under", "odds", "counter-strike"):
        if kw in low:
            print("   hit: %s x%d" % (kw, low.count(kw)))


# ---------------------------------------------------------------- 1 betexplorer

def probe_betexplorer():
    cands = [
        "https://www.betexplorer.com/counter-strike/",
        "https://www.betexplorer.com/esports/counter-strike/",
        "https://www.betexplorer.com/counter-strike/china/",
    ]
    for u in cands:
        st, body, hd = get(u)
        show("betexplorer", u, body, "http=%s" % st)
        if st == 200 and len(body) > 5000:
            # 找赛事链接
            links = re.findall(r'href="(/counter-strike/[^"]{4,60})"', body)
            uniq = list(dict.fromkeys(links))[:15]
            print("   赛事/子页链接:", uniq)
            # 找内嵌赔率痕迹
            for pat in ("data-odd", "oddsCell", "table-main", "js-tournament"):
                if pat in body:
                    print("   痕迹:", pat)
            return body
    return None


# ---------------------------------------------------------------- 2 oddsportal

def probe_oddsportal():
    for u in ("https://www.oddsportal.com/esports/counter-strike/",
              "https://www.oddsportal.com/esports/"):
        st, body, hd = get(u)
        show("oddsportal", u, body, "http=%s" % st)
        if body and "oddb" in body.lower():
            print("   oddb 数据痕迹存在")


# ---------------------------------------------------------------- 3 fonbet

def probe_fonbet():
    """俄系站：让分层最全（含 map handicap / round handicap）"""
    urls = [
        "https://line51.bk6bba-resources.com/ma/line",
        "https://line-lb62.bk6bba-resources.com/ma/line",
        "https://line.bk6bba-resources.com/ma/line",
    ]
    for u in urls:
        st, body, hd = get(u, timeout=25)
        show("fonbet", u, body, "http=%s" % st)
        if st == 200 and body and body.strip().startswith(("{", "[")):
            try:
                j = json.loads(body)
            except Exception:
                continue
            print("   JSON keys:", list(j.keys())[:15])
            sp = j.get("sports") or []
            for s in sp:
                nm = (s.get("name") or "") + " " + str(s.get("alias") or "")
                if any(k in nm.lower() for k in ("cs", "counter", "esport",
                                                 "dota", "valorant", "кибер")):
                    print("   esport sport:", s.get("id"), nm[:60], s.get("kind"))
            return j
    return None


# ---------------------------------------------------------------- 4 bo3.gg

def probe_bo3():
    cands = [
        "https://api.bo3.gg/api/v1/matches?page[limit]=5&sort=start_date",
        "https://bo3.gg/api/v1/matches?page[limit]=5",
        "https://api.bo3.gg/api/v1/teams?page[limit]=2",
    ]
    for u in cands:
        st, body, hd = get(u, headers={"Accept": "application/json"})
        show("bo3.gg", u, body, "http=%s" % st)
        if st == 200 and body and body.strip().startswith(("{", "[")):
            try:
                j = json.loads(body)
            except Exception:
                continue
            if isinstance(j, dict):
                print("   keys:", list(j.keys())[:12])
                d = j.get("data") or j.get("results") or []
                if isinstance(d, list) and d:
                    print("   首条字段:", list(d[0].keys())[:25])
                    print("   odds 相关:",
                          {k: v for k, v in d[0].items()
                           if "odd" in k.lower() or "bet" in k.lower()})
            return j
    return None


# ---------------------------------------------------------------- 5 oddspapi

def probe_oddspapi():
    for u in ("https://api.oddspapi.io/v1/sports",
              "https://oddspapi.io/api/v1/sports"):
        st, body, hd = get(u, headers={"Accept": "application/json"})
        show("oddspapi", u, body, "http=%s" % st)


# ---------------------------------------------------------------- 6 the-odds-api

def probe_oddsapi():
    u = "https://api.the-odds-api.com/v4/sports/?apiKey=demo"
    st, body, hd = get(u)
    show("the-odds-api", u, body, "http=%s" % st)
    if st == 200 and body:
        try:
            j = json.loads(body)
            print("   sports n=%d" % len(j))
            for s in j:
                if any(k in (s.get("key") or "") for k in ("cs", "esport")):
                    print("   ", s)
        except Exception:
            pass


# ---------------------------------------------------------------- 7 misc

def probe_misc():
    urls = [
        ("egamersworld", "https://egamersworld.com/counter-strike/matches"),
        ("escorenews", "https://escorenews.com/en/csgo"),
        ("csgobettings", "https://csgobettings.com/"),
        ("hltv-betting", "https://www.hltv.org/betting/csgo"),
        ("golgg", "https://gol.gg/esports/home/"),
        ("abios", "https://api.abiosgaming.com/v2/series?limit=1"),
    ]
    for tag, u in urls:
        st, body, hd = get(u, timeout=15)
        show(tag, u, body, "http=%s" % st)


def main():
    print("curl_cffi =", "yes" if requests else "no (fallback urllib)")
    only = sys.argv[1] if len(sys.argv) > 1 else ""

    tasks = [
        ("betexplorer", probe_betexplorer),
        ("oddsportal", probe_oddsportal),
        ("fonbet", probe_fonbet),
        ("bo3", probe_bo3),
        ("oddspapi", probe_oddspapi),
        ("oddsapi", probe_oddsapi),
        ("misc", probe_misc),
    ]
    for name, fn in tasks:
        if only and only != name:
            continue
        try:
            fn()
        except Exception as e:
            print("\n[%s] 异常: %s: %s" % (name, type(e).__name__, e))
    print("\n" + "=" * 76)
    print("probe done")


if __name__ == "__main__":
    main()
