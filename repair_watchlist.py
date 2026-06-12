#!/usr/bin/env python3
"""
repair_watchlist.py
───────────────────
针对 watchlist.json 中分析不完整的股票进行单股修复：
  1. 自动检测哪些股票缺少 intro / business / highlights / financials
  2. 对每只问题股票单独重新调用 DeepSeek（batch=1，避免连坐）
  3. 验证输出格式，最多重试 3 次
  4. 将修复结果合并回 watchlist.json 并 git push

用法:
  python repair_watchlist.py              # 自动检测并修复所有问题股票
  python repair_watchlist.py NVDA.US ORCL.US QCOM.US   # 手动指定
"""

import sys, os, json, time, re

os.environ.setdefault("PYTHONIOENCODING", "utf-8")

# ── 把 generate_watchlist.py 所在目录加入 path ──────────────────────────────
WATCHLIST_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, WATCHLIST_DIR)

from generate_watchlist import (
    SYSTEM_PROMPT, BATCH_PROMPT, MODEL, API_BASE,
    get_realtime_context, get_futu_context,
    extract_json_array, to_yf_code,
)
from openai import OpenAI

WATCHLIST_JSON = os.path.join(WATCHLIST_DIR, "watchlist.json")

# ── 验证一个报告 schema 对象是否完整 ────────────────────────────────────────
REPORT_KEYS = ("tagline", "intro", "B", "C", "health_conc", "c4_prose", "risks")

def _strip_md(v):
    """**bold** → <b>bold</b>，递归处理。"""
    if isinstance(v, str):  return re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', v)
    if isinstance(v, list): return [_strip_md(x) for x in v]
    if isinstance(v, dict): return {k: _strip_md(x) for k, x in v.items()}
    return v

def _is_valid(ana: dict) -> tuple[bool, list]:
    issues = []
    if not ana.get("tagline"):              issues.append("missing tagline")
    if not ana.get("intro"):                issues.append("missing intro")
    if len(ana.get("B") or []) < 3:         issues.append("B<3")
    if len(ana.get("C") or []) < 2:         issues.append("C<2")
    if not ana.get("health_conc"):          issues.append("missing health_conc")
    if not ana.get("c4_prose"):             issues.append("missing c4_prose")
    if len(ana.get("risks") or []) < 3:     issues.append("risks<3")
    return (len(issues) == 0), issues


def _futu_code(display_code: str) -> str:
    """NVDA.US → US.NVDA   9992.HK → HK.09992"""
    sym, mkt = display_code.rsplit(".", 1)
    if mkt == "HK":
        sym = sym.zfill(5)
    return f"{mkt}.{sym}"


def analyze_single(client: OpenAI, s: dict, max_attempts: int = 3) -> dict:
    """调用 DeepSeek 对单只股票生成分析，带校验重试，返回 analysis dict。"""
    prompt = BATCH_PROMPT.format(n=1, stock_data=_build_context(s))

    for attempt in range(max_attempts):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                max_tokens=6000,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": prompt},
                ]
            )
            results = extract_json_array(resp.choices[0].message.content)
            if not results:
                print(f"  ⚠  attempt {attempt+1}: empty result")
                time.sleep(6)
                continue
            ana = results[0]
            ok, issues = _is_valid(ana)
            if ok:
                return ana
            print(f"  ⚠  attempt {attempt+1}: incomplete — {issues}")
            time.sleep(8)
        except Exception as e:
            print(f"  ⚠  attempt {attempt+1} error: {e}")
            time.sleep(2 ** attempt * 6)

    print(f"  ❌  给 {s['display_code']} 生成分析失败（{max_attempts} 次尝试）")
    return {}


def _build_context(s: dict) -> str:
    lines = [
        f"1. 代码={s['display_code']} | 名称={s['name']} | 市场={s['market']}",
        f"   现价={s['price']:.2f} {s['currency']} | 市值={s['market_cap']:.1f}B | IV={s['iv_pct']:.1f}%(futu)",
        f"   综合评分={s['display_score']:.1f}",
    ]
    if s.get("futu_context"):
        lines.append(s["futu_context"])
    if s.get("yf_context"):
        lines.append(s["yf_context"])
    return "\n".join(lines)


def main():
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("❌  DEEPSEEK_API_KEY not set"); sys.exit(1)
    client = OpenAI(api_key=api_key, base_url=API_BASE)

    # ── 读取 watchlist.json ───────────────────────────────────────────────────
    with open(WATCHLIST_JSON, encoding="utf-8") as f:
        data = json.load(f)
    stocks = data["stocks"]

    # ── 确定需要修复的股票 ────────────────────────────────────────────────────
    if len(sys.argv) > 1:
        targets = set(sys.argv[1:])
    else:
        targets = set()
        for s in stocks:
            rep = s.get("report") or {}
            ok, issues = _is_valid(rep)
            if not ok:
                targets.add(s["code"])
                print(f"  检测到问题: {s['code']} — {issues}")

    if not targets:
        print("✅  所有股票分析完整，无需修复"); return

    print(f"\n需要修复: {sorted(targets)}")
    print("─" * 55)

    # ── 逐只修复 ─────────────────────────────────────────────────────────────
    fixed = 0
    for stock_entry in stocks:
        code = stock_entry["code"]
        if code not in targets:
            continue

        print(f"\n🔧  [{code}] {stock_entry['name']} — 重新拉取上下文...")
        futu_c = _futu_code(code)
        yf_c   = to_yf_code(futu_c)

        s = {
            "display_code":  code,
            "futu_code":     futu_c,
            "yf_code":       yf_c,
            "name":          stock_entry["name"],
            "market":        stock_entry["market"],
            "price":         stock_entry["price"],
            "market_cap":    stock_entry["marketCap"],
            "currency":      stock_entry["currency"],
            "iv_pct":        stock_entry["iv30"],
            "display_score": (stock_entry.get("score") or 0) * 10,   # 近似反推；无评分为 0
        }

        s["futu_context"] = get_futu_context(futu_c, code)
        s["yf_context"]   = get_realtime_context(yf_c, code)

        print(f"  → 调用 DeepSeek 分析 {code}...")
        ana = analyze_single(client, s)
        if not ana:
            print(f"  ❌  跳过 {code}"); continue

        # 写回 stocks 列表（新报告 schema；保留旧 analysis 字段不动，前端优先读 report）
        stock_entry["report"]      = _strip_md({k: ana.get(k) for k in REPORT_KEYS})
        stock_entry["bullets"]     = ana.get("bullets", stock_entry.get("bullets", []))
        stock_entry["name_en"]     = ana.get("name_en") or stock_entry.get("name_en", "")
        stock_entry["industry"]    = ana.get("sector")  or stock_entry.get("industry", "")
        stock_entry["data_quality"] = ana.get("data_quality", {})
        fixed += 1
        print(f"  ✅  {code} 修复完成")

    if fixed == 0:
        print("\n没有成功修复任何股票"); return

    # ── 写回 watchlist.json ───────────────────────────────────────────────────
    with open(WATCHLIST_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n✅  {fixed} 只股票已修复 → {WATCHLIST_JSON}")
    print("\n下一步：git add watchlist.json && git commit && git push")


if __name__ == "__main__":
    main()
