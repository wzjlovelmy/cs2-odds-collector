#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第二轮历史让分盘源：sofascore / bo3.gg / oddspapi / betexplorer / oddsportal XHR"""
import json
import re

from curl_cffi import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
S = requests.Session(impersonate="chrome124")
S.headers.update({"User-Agent": UA, "Accept": "application/json,text/html,*/*",
                  "Accept-Language": "en-US,en;q=0.9"})


def g(url, ref=None, timeout=20):
    h = {"Referer": ref} if ref else {}
    try:
        r = S.get(url, timeout=timeout, headers=h)
        return r.status_code, r.text
    except Exception as e:
        return None, "ERR %s: %s" % (type(e).__name__, str(e)[:60])


def line(tag, url, st, body, note=""):
    print("  %-9s http=%-5s size=%-7d %s %s"
          % (tag, st, len(body or ""), url[-58:], note))


# --------------------------------------------------- sofascore
def sofascore():
    print("\n=== sofascore ===")
    # 1) 赛事列表
    c = ["https://api.sofascore.com/api/v1/sport/esports/scheduled-events/2026-11-05",
         "https://www.sofascore.com/api/v1/sport/esports/scheduled-events/2026-11-05"]
    for u in c:
        st, b = g(u)
        line("sofasc", u, st, b)
        if st == 200 and b.startswith("{"):
            j = json.loads(b)
            evs = j.get("events") or []
            print("     events=%d" % len(evs))
            cs = [e for e in evs
                  if "counter" in json.dumps(e.get("tournament") or {}).lower()
                  or "cs" in ((e.get("tournament") or {}).get("slug") or "")]
            print("     CS 场次=%d" % len(cs))
            if cs:
                print("     keys:", list(cs[0].keys())[:20])
                eid = cs[0]["id"]
                # 2) event odds
                for ou in ("https://api.sofascore.com/api/v1/event/%s/odds/1/all" % eid,
                           "https://api.sofascore.com/api/v1/event/%s/odds/1/featured" % eid):
                    st2, b2 = g(ou, ref=u)
                    line("sofasc", ou, st2, b2)
                    if st2 == 200 and b2 and b2.startswith("{"):
                        print("      odds 结构:", b2[:600])
                        return
            return


# --------------------------------------------------- bo3.gg
def bo3():
    print("\n=== bo3.gg ===")
    st, b = g("https://api.bo3.gg/api/v1/matches?page[limit]=3&sort=-start_date&filter[status]=finished")
    line("bo3", "matches finished", st, b)
    if st != 200 or not b.startswith("{"):
        st, b = g("https://api.bo3.gg/api/v1/matches?page[limit]=3")
        line("bo3", "matches", st, b)
    if st != 200:
        return
    j = json.loads(b)
    d = j.get("results") or j.get("data") or []
    if not d:
        return
    m = d[0]
    print("   match id=%s slug=%s bo=%s" % (m.get("id"), m.get("slug"), m.get("bo_type")))
    print("   含 bet 的字段:", {k: v for k, v in m.items()
                              if "bet" in k.lower() or "odd" in k.lower()})
    mid = m.get("id")
    slug = m.get("slug")
    cands = [
        "https://api.bo3.gg/api/v1/matches/%s" % mid,
        "https://api.bo3.gg/api/v1/matches/%s/odds" % mid,
        "https://api.bo3.gg/api/v1/matches/%s/bets" % mid,
        "https://api.bo3.gg/api/v1/matches/%s/bet_updates" % mid,
        "https://api.bo3.gg/api/v1/bets?filter[match_id]=%s" % mid,
        "https://api.bo3.gg/api/v1/odds?filter[match_id]=%s" % mid,
        "https://bo3.gg/matches/%s" % slug,
    ]
    for u in cands:
        st2, b2 = g(u)
        line("bo3", u, st2, b2)
        if st2 == 200 and b2 and len(b2) > 200 and "odd" in b2.lower():
            print("      → 命中 odds 字样, 片段:", b2[:400])
        if st2 == 200 and b2 and u.endswith(str(mid)):
            try:
                jj = json.loads(b2)
                inner = jj.get("data", jj)
                if isinstance(inner, dict):
                    print("      详情 keys:", list(inner.keys())[:20])
            except Exception:
                pass


# --------------------------------------------------- oddspapi
def oddspapi():
    print("\n=== oddspapi.io ===")
    for u in ("https://oddspapi.io/api/v1/",
              "https://oddspapi.io/api/v1/sports",
              "https://oddspapi.io/api/v1/odds?apiKey=test&sport=counter-strike",
              "https://oddspapi.io/docs",
              "https://oddspapi.io/api/v1/historical?apiKey=test"):
        st, b = g(u)
        line("oddspapi", u, st, b)
        if st == 200 and b and len(b) < 4000:
            print("      ", b[:300].replace("\n", " "))


# --------------------------------------------------- betexplorer
def betex():
    print("\n=== betexplorer ===")
    for u in ("https://www.betexplorer.com/esports/",
              "https://www.betexplorer.com/",
              "https://www.betexplorer.com/esports/counter-strike/",
              "https://www.betexplorer.com/cs2/",
              "https://www.betexplorer.com/counter-strike/matches/"):
        st, b = g(u)
        line("betexp", u, st, b)
        if st == 200 and b:
            for kw in ("counter", "cs2", "handicap", "asian"):
                if kw in b.lower():
                    print("        hit %s" % kw)


# --------------------------------------------------- oddsportal XHR
def oddsportal_xhr():
    print("\n=== oddsportal XHR 端点 ===")
    get_home = g("https://www.oddsportal.com/")
    print("  home http=%s" % get_home[0])
    eid = 11643979
    enc = "zaJFTWlo"
    cands = [
        "https://www.oddsportal.com/ajax-event-odds_/%s/1/0/" % eid,
        "https://www.oddsportal.com/ajax-event-odds/%s/1/" % eid,
        "https://www.oddsportal.com/api/event/%s/odds" % eid,
        "https://www.oddsportal.com/event/%s/odds/" % eid,
        "https://www.oddsportal.com/match-odds/%s/" % enc,
        "https://www.oddsportal.com/ajax-event-details_/%s/" % eid,
        "https://www.oddsportal.com/ajax-event-odds/%s/%s/" % (eid, enc),
    ]
    ref = "https://www.oddsportal.com/event/%s/" % eid
    for u in cands:
        st, b = g(u, ref=ref)
        line("oddxhr", u, st, b)
        if st == 200 and b and len(b) > 100:
            print("      head:", b[:260].replace("\n", " "))


def main():
    for fn in (sofascore, bo3, oddspapi, betex, oddsportal_xhr):
        try:
            fn()
        except Exception as e:
            print("[%s] 异常 %s: %s" % (fn.__name__, type(e).__name__, e))
    print("\n=== done ===")


if __name__ == "__main__":
    main()
