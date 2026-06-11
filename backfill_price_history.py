#!/usr/bin/env python3
"""一次性工具：给现有 watchlist.json 回填 initialPrice / initialPriceDate /
priceHistory（2 年日线收盘），不重新生成 AI 分析。"""

import json, os, sys, time

os.environ.setdefault("PYTHONIOENCODING", "utf-8")

WATCHLIST_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, WATCHLIST_DIR)

# generate_watchlist 在 import 时已做 Windows GBK 控制台 UTF-8 包装，这里不再重复包装
from generate_watchlist import get_price_history, to_yf_code
from repair_watchlist import _futu_code

WATCHLIST_JSON = os.path.join(WATCHLIST_DIR, "watchlist.json")

with open(WATCHLIST_JSON, encoding="utf-8") as f:
    data = json.load(f)

ok = fail = 0
for s in data["stocks"]:
    code = s["code"]
    yf_c = to_yf_code(_futu_code(code))
    ph = get_price_history(yf_c)
    if not ph:
        print(f"  ❌  {code:<10} 历史数据获取失败")
        fail += 1
        continue
    s["initialPrice"]     = ph["initialPrice"]
    s["initialPriceDate"] = ph["initialPriceDate"]
    s["priceHistory"]     = {"dates": ph["dates"], "closes": ph["closes"]}
    print(f"  ✅  {code:<10} {len(ph['closes']):>4} 个交易日  "
          f"期初价={ph['initialPrice']:<10} ({ph['initialPriceDate']})")
    ok += 1
    time.sleep(0.4)

with open(WATCHLIST_JSON, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"\n✅  回填完成：{ok} 成功 / {fail} 失败 → {WATCHLIST_JSON}")
