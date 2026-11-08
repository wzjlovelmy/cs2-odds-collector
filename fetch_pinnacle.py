#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pinnacle CS2 盘口采集器（GitHub Actions 版，纯标准库，无需 pip）

为什么在 GitHub Actions 跑：本地到 guest.api.arcadia.pinnacle.com 连接被拒，
需要海外出口。Actions 的 runner 在 Azure，可直连。

三种模式：
  python fetch_pinnacle.py                  # 正常采集：刷新 latest，仅记录变化的盘口
  python fetch_pinnacle.py --probe          # 探测：打印结构诊断 + 落原始 JSON（首次务必先跑）
  python fetch_pinnacle.py --replay DIR     # 离线：从 --probe 落下的原始 JSON 重建 CSV

产出（--out 目录，默认 out/）：
  pinnacle_latest.csv    当前所有盘口，全量覆盖（git diff 很小）
  pinnacle_changes.csv   仅价格/盘口变动时才追加一行，用于开盘→收盘的 CLV 分析
  crawl_log.txt          每次运行的诊断摘要（追加）

长表字段：
  fetched_at, matchup_id, start_time, league, units, home, away,
  period, market_label, market_type, designation, side, points, price_us, price_dec, is_live
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ---------------------------------------------------------------- 常量

HOST = os.environ.get("PINNACLE_HOST", "https://guest.api.arcadia.pinnacle.com")
API_KEY = os.environ.get("PINNACLE_KEY", "CmX2KcMrXuFmNg6YFbmTxE0y9CIrOi0R")
SPORT_ID = int(os.environ.get("PINNACLE_SPORT", "29"))  # 29 = Counter-Strike 2

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

HEADERS = {
    "X-API-Key": API_KEY,
    "User-Agent": UA,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "identity",
    "Origin": "https://www.pinnacle.com",
    "Referer": "https://www.pinnacle.com/",
    "Cache-Control": "no-cache",
}

FIELDS = [
    "fetched_at", "matchup_id", "start_time", "league", "units", "home", "away",
    "period", "market_label", "market_type", "market_key", "is_alt",
    "designation", "side", "points", "price_us", "price_dec", "is_live",
]

# ---------------------------------------------------------------- HTTP


def get_json(path: str, retries: int = 3, timeout: int = 25):
    """返回 (obj, status)。4xx 除 403/429 外不重试。"""
    url = HOST + path
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read().decode("utf-8", "replace")
                return json.loads(raw), r.status
        except urllib.error.HTTPError as e:
            last = e.code
            body = ""
            try:
                body = e.read().decode("utf-8", "replace")[:200]
            except Exception:
                pass
            if e.code in (403, 429, 500, 502, 503, 504):
                time.sleep(2.0 * (i + 1))
                continue
            return {"_error": body}, e.code
        except Exception as e:
            last = str(e)
            time.sleep(1.5 * (i + 1))
    return {"_error": str(last)}, (last if isinstance(last, int) else -1)


# ---------------------------------------------------------------- 解析工具


def to_decimal(p):
    """美式赔率 → 欧式小数赔率；已经是小数则原样返回。"""
    if p is None:
        return None
    try:
        v = float(p)
    except (TypeError, ValueError):
        return None
    if v == 0:
        return None
    if abs(v) >= 100:                       # 美式：-135 / +120
        dec = 1.0 + (100.0 / abs(v) if v < 0 else v / 100.0)
        return round(dec, 4)
    if v > 1.0:                             # 已是欧式 1.74
        return round(v, 4)
    return None                             # 明显不是赔率（多半是 points 混进来了）


def period_label(period, units):
    """Pinnacle 的 period：0=整个系列赛，1/2/3=第 N 张图。"""
    if period in (0, None):
        return "series"
    return "map%d" % period


def as_list(obj):
    """markets / matchups 响应可能是裸 list，也可能包一层。"""
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        for k in ("markets", "matchups", "data", "items"):
            if isinstance(obj.get(k), list):
                return obj[k]
    return []


def pick_teams(mu):
    """返回 (home, away)。participants 顺序不可靠，按 alignment 取。"""
    parts = mu.get("participants") or []
    home = away = None
    for p in parts:
        align = (p.get("alignment") or "").lower()
        name = p.get("name") or p.get("shortName") or ""
        if align == "home":
            home = name
        elif align == "away":
            away = name
        elif home is None:
            home = name
        elif away is None:
            away = name
    if home is None or away is None:
        names = [p.get("name", "") for p in parts]
        if len(names) >= 2:
            home, away = names[0], names[1]
    return home or "", away or ""


def side_of(designation, home, away):
    """把 home/away 翻成人看的队名，over/under 保持原样。"""
    d = (designation or "").lower()
    if d == "home":
        return home
    if d == "away":
        return away
    if d in ("over", "under"):
        return d
    if d == "draw":
        return "draw"
    return designation or ""


def flatten(mu, markets, fetched_at, is_live, include_alt=False):
    """一个 matchup + 其 markets → CSV 行列表。"""
    home, away = pick_teams(mu)
    league = ""
    lg = mu.get("league") or {}
    if isinstance(lg, dict):
        league = lg.get("name") or ""
    units = mu.get("units") or ""
    start = mu.get("startTime") or ""
    mid = mu.get("id")

    rows = []
    for m in markets:
        if not isinstance(m, dict):
            continue
        mtype = (m.get("type") or "").lower()
        period = m.get("period", 0)
        is_alt = bool(m.get("isAlternate"))
        if is_alt and not include_alt:
            continue
        if (m.get("status") or "open").lower() != "open":
            continue
        prices = m.get("prices") or []
        if not prices:
            continue
        mside = (m.get("side") or "").lower()
        for pr in prices:
            if not isinstance(pr, dict):
                continue
            des = pr.get("designation") or ""
            pts = pr.get("points")
            price = pr.get("price")
            dec = to_decimal(price)
            if dec is None:
                continue
            # team_total 的 market 级 side 指明是哪一队的大小分
            if mside in ("home", "away"):
                team = home if mside == "home" else away
                side_txt = "%s_%s" % (team, des)
            else:
                side_txt = side_of(des, home, away)
            rows.append({
                "fetched_at": fetched_at,
                "matchup_id": mid,
                "start_time": start,
                "league": league,
                "units": units,
                "home": home,
                "away": away,
                "period": period,
                "market_label": period_label(period, units),
                "market_type": mtype,
                "market_key": m.get("key") or "",
                "is_alt": int(is_alt),
                "designation": des,
                "side": side_txt,
                "points": "" if pts is None else pts,
                "price_us": "" if price is None else price,
                "price_dec": dec,
                "is_live": int(bool(is_live or mu.get("isLive"))),
            })
    return rows


# ---------------------------------------------------------------- 采集


def select_matchups(matchups, days_ahead=3, include_live=True):
    """只要主盘口（排除 special 子盘口），并且时间窗合理。"""
    now = datetime.now(timezone.utc)
    lo = now - timedelta(hours=6)
    hi = now + timedelta(days=days_ahead)
    out = []
    for mu in matchups:
        if not isinstance(mu, dict):
            continue
        if (mu.get("type") or "").lower() != "matchup":
            continue
        if mu.get("parent") is not None or mu.get("parentId") is not None:
            continue
        if len(mu.get("participants") or []) < 2:
            continue
        st = mu.get("startTime")
        if st:
            try:
                t = datetime.fromisoformat(st.replace("Z", "+00:00"))
            except ValueError:
                t = None
            if t is not None:
                if t < lo:
                    continue
                if t > hi:
                    continue
        out.append(mu)
    out.sort(key=lambda m: m.get("startTime") or "")
    return out


def crawl(days_ahead=3, max_matches=80, dump_raw=None, include_alt=False, verbose=True):
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    mus, status = get_json("/0.1/sports/%d/matchups" % SPORT_ID)
    if verbose:
        print("[matchups] status=%s type=%s n=%d"
              % (status, type(mus).__name__, len(as_list(mus))))
    if status != 200:
        return [], {"status": status, "error": str(mus)[:300], "matchups": 0}

    all_mu = as_list(mus)
    sel = select_matchups(all_mu, days_ahead=days_ahead)[:max_matches]
    if verbose:
        print("[matchups] 原始 %d 条，时间窗内主盘口 %d 场（上限 %d）"
              % (len(all_mu), len(sel), max_matches))
        for mu in sel[:3]:
            print("   · %s vs %s  %s  units=%s"
                  % (pick_teams(mu)[0], pick_teams(mu)[1],
                     mu.get("league", {}).get("name") if isinstance(mu.get("league"), dict) else "",
                     mu.get("units")))

    rows = []
    errs = []
    probe_samples = []
    for i, mu in enumerate(sel):
        mid = mu.get("id")
        mks, st = get_json("/0.1/matchups/%s/markets/related/straight" % mid)
        if st != 200:
            errs.append((mid, st))
            continue
        mlist = as_list(mks)
        rows.extend(flatten(mu, mlist, fetched_at, mu.get("isLive"), include_alt))
        if dump_raw is not None and len(probe_samples) < 2:
            probe_samples.append({"matchup": mu, "markets": mks})
        time.sleep(0.2)

    if dump_raw is not None:
        dump_raw.mkdir(parents=True, exist_ok=True)
        payload = {
            "fetched_at": fetched_at,
            "sport_id": SPORT_ID,
            "matchups_sample": all_mu[:15],   # 只存样本，避免几十 MB
            "markets_samples": probe_samples,
        }
        p = dump_raw / ("probe_%s.json" % fetched_at.replace(":", ""))
        p.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        print("[dump] %s  (%.1f KB)" % (p, p.stat().st_size / 1024))

    meta = {
        "status": 200,
        "fetched_at": fetched_at,
        "matchups": len(sel),
        "rows": len(rows),
        "errors": errs[:10],
        "n_errors": len(errs),
    }
    return rows, meta


# ---------------------------------------------------------------- 落盘


def key_of(r):
    return (str(r["matchup_id"]), str(r["period"]), r["market_type"],
            r["designation"], str(r["points"]))


def read_csv(path):
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, append=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    write_header = True
    if append and path.exists() and path.stat().st_size > 0:
        write_header = False
    with path.open(mode, encoding="utf-8-sig" if not append else "utf-8",
                   newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        if write_header:
            w.writeheader()
        for r in rows:
            w.writerow(r)


def save(rows, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    latest_p = out_dir / "pinnacle_latest.csv"
    changes_p = out_dir / "pinnacle_changes.csv"

    prev = {key_of(r): r.get("price_dec") for r in read_csv(latest_p)}
    write_csv(latest_p, rows)                       # 全量覆盖

    changed = [r for r in rows if prev.get(key_of(r)) != str(r["price_dec"])]
    if changed:
        write_csv(changes_p, changed, append=True)  # 仅变动
    return len(changed), len(prev)


def log_line(out_dir, meta):
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "crawl_log.txt").open("a", encoding="utf-8") as f:
        f.write(json.dumps(meta, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------- probe


def list_sports():
    """列出全部 sport id。Pinnacle 的 id 与直觉不符（29 是足球），必须实测。"""
    obj, status = get_json("/0.1/sports")
    print("HTTP:", status)
    lst = as_list(obj)
    print("n =", len(lst))
    if lst:
        print("keys:", sorted(lst[0].keys()))
    kw = ("counter", "csgo", "cs2", "esport", "dota", "league of",
          "valorant", "overwatch", "call of", "strike")
    print("\n--- 关键词命中 ---")
    for s in lst:
        name = ((s.get("name") or "") + " " + (s.get("slug") or "")).lower()
        if any(k in name for k in kw):
            print("  id=%-6s %s" % (s.get("id"), s.get("name")))
    print("\n--- 全量 ---")
    items = sorted(lst, key=lambda x: (x.get("id") or 0))
    for i in range(0, len(items), 3):
        print("   ".join("id=%-5s %-28s" % (s.get("id"), s.get("name"))
                         for s in items[i:i + 3]))
    return 0


def scan_sports():
    """/0.1/sports 不含 esports，逐个试探候选 sport id。"""
    # 先看是否有 all=true 这类开关能带出隐藏项目
    for path in ("/0.1/sports?all=true", "/0.1/sports/all", "/0.1/sports?brandId=0"):
        obj, st = get_json(path)
        n = len(as_list(obj))
        print("%-28s HTTP=%-4s n=%s" % (path, st, n))
        if st == 200 and n > 60:
            names = [(s.get("id"), s.get("name")) for s in as_list(obj)]
            hit = [x for x in names
                   if any(k in (x[1] or "").lower()
                          for k in ("esport", "counter", "strike", "dota", "valorant", "league of"))]
            print("   关键词命中:", hit if hit else "无")
            print("   最大 id:", max(i for i, _ in names))

    print("\n--- 候选 sport id 探测 ---")
    cands = [235, 236, 242, 266, 274, 277, 279, 154, 155, 237, 238,
             239, 240, 241, 243, 244, 245, 246, 248]
    for sid in cands:
        obj, st = get_json("/0.1/sports/%d/matchups" % sid, retries=1)
        lst = as_list(obj)
        if st != 200 or not lst:
            print("  id=%-4s HTTP=%-4s n=%d" % (sid, st, len(lst)))
            continue
        # 只挑 type=matchup 的，看球队名判断是不是 CS2
        ms = [m for m in lst if isinstance(m, dict) and m.get("type") == "matchup"]
        sample = []
        for m in ms[:2]:
            parts = [p.get("name", "") for p in (m.get("participants") or [])]
            lg = (m.get("league") or {}).get("name", "")
            sample.append("%s | %s" % (" vs ".join(parts), lg))
        print("  id=%-4s HTTP=%-4s n=%-5d matchup=%-4d  %s"
              % (sid, st, len(lst), len(ms), " ;; ".join(sample)[:150]))
        # 对每个疑似 esports 的 id 再看 period/type 组合
        if ms:
            mid = ms[0].get("id")
            mks, s2 = get_json("/0.1/matchups/%s/markets/related/straight" % mid, retries=1)
            ml = as_list(mks)
            combos = {}
            for m in ml:
                k = "%s/p%s" % (m.get("type"), m.get("period"))
                combos[k] = combos.get(k, 0) + 1
            print("        markets=%d %s" % (len(ml), combos))
    return 0


def probe():
    """打印结构诊断，帮助确认字段名是否与预期一致。"""
    mus, status = get_json("/0.1/sports/%d/matchups" % SPORT_ID)
    print("=" * 70)
    print("HOST      :", HOST)
    print("SPORT_ID  :", SPORT_ID)
    print("HTTP      :", status)
    if status != 200:
        print("原始响应  :", str(mus)[:800])
        return 1

    lst = as_list(mus)
    print("matchups  : %d 条" % len(lst))
    if lst:
        print("顶层键    :", sorted(lst[0].keys()) if isinstance(lst[0], dict) else "-")
        types = {}
        for mu in lst:
            if isinstance(mu, dict):
                types[mu.get("type")] = types.get(mu.get("type"), 0) + 1
        print("type 分布 :", types)
        leagues = {}
        for mu in lst:
            lg = (mu.get("league") or {}).get("name") if isinstance(mu, dict) else None
            leagues[lg] = leagues.get(lg, 0) + 1
        print("联赛 top8 :", sorted(leagues.items(), key=lambda x: -x[1])[:8])

    sel = select_matchups(lst, days_ahead=7)[:5]
    print("抽检 %d 场：" % len(sel))
    for mu in sel:
        mid = mu.get("id")
        mks, st = get_json("/0.1/matchups/%s/markets/related/straight" % mid)
        mlist = as_list(mks)
        print("-" * 70)
        print("   id=%s status=%s | %s vs %s | start=%s | units=%s | markets=%d"
              % (mid, st, pick_teams(mu)[0], pick_teams(mu)[1],
                 mu.get("startTime"), mu.get("units"), len(mlist)))
        if mlist and isinstance(mlist[0], dict):
            print("   market 键 :", sorted(mlist[0].keys()))
            combo = {}
            for m in mlist:
                k = "%s/p%s" % (m.get("type"), m.get("period"))
                combo[k] = combo.get(k, 0) + 1
            print("   type/period:", combo)
            print("   首条样例  :", json.dumps(mlist[0], ensure_ascii=False)[:400])
        rows = flatten(mu, mlist, "probe", mu.get("isLive"))
        for r in rows[:6]:
            print("     -> p%-2s %-8s %-6s %-7s pts=%-6s dec=%s"
                  % (r["period"], r["market_type"], r["designation"],
                     str(r["side"])[:7], r["points"], r["price_dec"]))
    print("=" * 70)
    return 0


# ---------------------------------------------------------------- main


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out", help="输出目录（默认 out）")
    ap.add_argument("--probe", action="store_true", help="只做结构探测，不写 CSV")
    ap.add_argument("--list-sports", action="store_true", help="列出所有 sport id")
    ap.add_argument("--scan-sports", action="store_true", help="试探候选 esports sport id")
    ap.add_argument("--dump-raw", default="", help="额外保存原始 JSON 到此目录")
    ap.add_argument("--days-ahead", type=int, default=3)
    ap.add_argument("--max-matches", type=int, default=120)
    ap.add_argument("--include-alt", action="store_true", help="同时保存替代盘口")
    ap.add_argument("--sport", type=int, default=0, help="覆盖 SPORT_ID")
    args = ap.parse_args()

    global SPORT_ID
    if args.sport:
        SPORT_ID = args.sport

    if args.list_sports:
        return list_sports()
    if args.scan_sports:
        return scan_sports()
    if args.probe:
        return probe()

    out_dir = Path(args.out)
    dump = Path(args.dump_raw) if args.dump_raw else None
    rows, meta = crawl(args.days_ahead, args.max_matches, dump, args.include_alt)

    if not rows:
        print("[warn] 没有取到任何盘口")
        print(json.dumps(meta, ensure_ascii=False)[:500])
        log_line(out_dir, meta)
        return 2

    n_chg, n_prev = save(rows, out_dir)
    meta["changed"] = n_chg
    meta["prev_rows"] = n_prev
    log_line(out_dir, meta)

    print("[done] 盘口行=%d  变动=%d  抓取比赛=%d  失败=%d"
          % (len(rows), n_chg, meta["matchups"], meta["n_errors"]))
    print("[done] fetched_at=%s" % meta["fetched_at"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
