#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""定位 oddsportal 单场赔率页 + 提取 AH/OU"""
import json
import re

from curl_cffi import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
BASE = "https://www.oddsportal.com"
LIST = BASE + "/esports/counter-strike/counter-strike-iem-beijing/results/"

S = requests.Session(impersonate="chrome124")
S.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})


def get(url, ref=None):
    h = {}
    if ref:
        h = {"Referer": ref, "X-Requested-With": "XMLHttpRequest"}
    try:
        r = S.get(url, timeout=30, headers=h)
        return r.status_code, r.text
    except Exception as e:
        return None, "ERR %s" % e


def rsc(body):
    out = ""
    for p in re.findall(r'self\.__next_f\.push\(\[1,\s*"((?:[^"\\]|\\.)*)"\]\)', body):
        try:
            out += json.loads('"' + p + '"')
        except Exception:
            out += p
    return out


def grab_obj(text, start):
    """从 start 处的 '{' 起做括号匹配"""
    depth, i, inq, esc = 0, start, False, False
    while i < len(text):
        c = text[i]
        if inq:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                inq = False
        else:
            if c == '"':
                inq = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
        i += 1
    return None


def main():
    # 先访问首页拿 cookie
    st0, _ = get(BASE + "/")
    print("[home] http=%s" % st0)

    st, body = get(LIST)
    R = rsc(body)
    print("[list] http=%s rsc=%d" % (st, len(R)))

    # --- A. 一个完整比赛行对象
    print("\n=== A. 比赛行完整字段 ===")
    m = re.search(r'\{"id":\d+,"is-double"', R)
    if not m:
        m = re.search(r'\{"id":\d+,', R)
    row = grab_obj(R, m.start()) if m else None
    if row:
        try:
            j = json.loads(row)
            print("  keys:", list(j.keys()))
            for k, v in j.items():
                print("    %-28s = %s" % (k, str(v)[:70]))
        except Exception as e:
            print("  解析失败", e, row[:500])

    # --- B. 试单场 URL 形式
    print("\n=== B. 单场 URL 尝试 ===")
    eid = None
    hslug, aslug = "the-mongolz", "navi"
    if row:
        try:
            j = json.loads(row)
            eid = j.get("id")
            hslug = (j.get("home-name") or "").lower().replace(" ", "-")
            aslug = (j.get("away-name") or "").lower().replace(" ", "-")
        except Exception:
            pass
    print("  eid=%s  %s vs %s" % (eid, hslug, aslug))

    cands = []
    if eid:
        cands += [
            BASE + "/esports/counter-strike/counter-strike-iem-beijing/%s-%s-%s/" % (hslug, aslug, eid),
            BASE + "/esports/counter-strike/counter-strike-iem-beijing/%s-%s/" % (hslug, aslug),
            BASE + "/event/%s/" % eid,
            BASE + "/esports/counter-strike/counter-strike-iem-beijing/results/%s/" % eid,
        ]
    for u in cands:
        st2, b2 = get(u, ref=LIST)
        ok = st2 == 200 and b2 and len(b2) > 30000
        print("  http=%s size=%-7d %s" % (st2, len(b2 or ""), u[-72:]))
        if ok:
            R2 = rsc(b2) if "self.__next_f" in b2 else b2
            hits = {kw: R2.count(kw) for kw in
                    ("asian_handicap", "Asian Handicap", "over_under",
                     "Over/Under", "bookmaker", "oddsData", "\"odds\":")}
            print("       ", hits)
            # 找 odds 数组内容
            mo = re.search(r'"odds":\s*\[\s*\{', R2)
            if mo:
                ob = grab_obj(R2, mo.start() + len('"odds":'))
                print("        odds 样本:", (ob or "")[:400])
            # 找 bookmaker 列表
            mb = re.search(r'"bookmakers?":\s*\[\s*\{', R2)
            if mb:
                ob = grab_obj(R2, mb.start() + len(mb.group(0)) - 1)
                print("        bookmakers 样本:", (ob or "")[:300])
            break

    # --- C. archive 端点带 cookie 重试
    print("\n=== C. archive 端点（带 cookie）===")
    m2 = re.search(r"(/ajax-sport-country-tournament-archive_[^\"\\\\]+/\d+/\d+)", R)
    if m2:
        u = BASE + m2.group(1).replace("\\", "")
        st3, b3 = get(u, ref=LIST)
        print("  http=%s size=%d" % (st3, len(b3 or "")))
        if b3:
            print("  head:", b3[:300].replace("\n", " "))


if __name__ == "__main__":
    main()
