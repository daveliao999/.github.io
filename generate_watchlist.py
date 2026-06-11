#!/usr/bin/env python3
"""
FCN Watchlist Generator
Input:  FCN_Results.xlsx (sorted by score desc, take top N)
Output: watchlist.json  (website sole data source)

Flow:
  1. Read Excel → top N stocks
  2. yfinance   → 10-week sparklines + latest price change
  3. DeepSeek API → bullets + structured analysis (skill spec format)
  4. Merge all  → watchlist.json
"""

import json, os, sys, re, time, argparse
from datetime import datetime, timedelta

# Windows GBK console fix (only when running directly, not when imported)
if sys.platform == "win32" and hasattr(sys.stdout, 'buffer'):
    import io
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import yfinance as yf
from openai import OpenAI
import json_repair

# ── Config ────────────────────────────────────────────────────────────────────
EXCEL_PATH   = r"C:\Users\liy22223\Desktop\FCN筛选器v1\screener\FCN_Results.xlsx"
OUTPUT_PATH  = r"C:\Users\liy22223\Desktop\FCN筛选器v1\watchlist\watchlist.json"
TOP_N        = 30
MODEL        = "deepseek-v4-pro"
API_BASE     = "https://api.deepseek.com"
BATCH_SIZE   = 3
MAX_WORKERS  = 3

# ── Optional field helpers (return None if cell is blank/NaN) ────────────────
def _opt_float(v):
    try:    return float(v) if v is not None and str(v).strip() not in ('', 'nan') else None
    except: return None

def _opt_int(v):
    # Handle values like "6M", "12M" by stripping trailing non-numeric characters
    if isinstance(v, str):
        v = v.strip().rstrip('Mm月').strip()
    f = _opt_float(v)
    return int(f) if f is not None else None

def _opt_str(v):
    s = str(v).strip() if v is not None else ''
    return s if s not in ('', 'nan', 'None') else None

# ── Code helpers ──────────────────────────────────────────────────────────────
def to_display_code(futu: str) -> str:
    """US.IREN → IREN.US   HK.09992 → 9992.HK"""
    mkt, sym = futu.split(".", 1)
    return f"{sym}.{mkt}"

def to_yf_code(futu: str) -> str:
    """US.IREN → IREN   HK.09992 → 9992.HK   (strips Futu leading zero, pads to 4 digits)"""
    mkt, sym = futu.split(".", 1)
    if mkt == "US":
        return sym
    # HK: Futu uses 5-digit (e.g. 09992), Yahoo Finance uses 4-digit (e.g. 9992)
    yf_sym = sym.lstrip("0").zfill(4)
    return f"{yf_sym}.HK"

# ── FCN terms from IV ─────────────────────────────────────────────────────────
def calc_fcn_terms(iv_pct: float) -> dict:
    if iv_pct >= 80:
        return dict(coupon=27.0, strike=72, ki=58, ko=100, kiType="美式敲入", tenor=6,  risk="高")
    if iv_pct >= 60:
        return dict(coupon=22.0, strike=78, ki=63, ko=100, kiType="欧式敲入", tenor=6,  risk="中")
    if iv_pct >= 40:
        return dict(coupon=18.0, strike=82, ki=68, ko=100, kiType="欧式敲入", tenor=6,  risk="中")
    if iv_pct >= 25:
        return dict(coupon=14.0, strike=88, ki=75, ko=100, kiType="欧式敲入", tenor=6,  risk="低")
    return     dict(coupon=12.0, strike=90, ki=78, ko=100, kiType="欧式敲入", tenor=6,  risk="低")

# ── yfinance helpers ──────────────────────────────────────────────────────────
def get_sparkline(yf_code: str) -> list:
    try:
        hist = yf.Ticker(yf_code).history(period="12wk", interval="1wk")
        closes = hist["Close"].dropna().tolist()[-10:]
        return [round(p, 2) for p in closes]
    except Exception as e:
        print(f"  ⚠  yfinance sparkline {yf_code}: {e}")
        return []

def get_price_change(yf_code: str) -> float:
    try:
        hist = yf.Ticker(yf_code).history(period="5d", interval="1d")
        if len(hist) < 2:
            return 0.0
        prev, curr = hist["Close"].iloc[-2], hist["Close"].iloc[-1]
        return round((curr - prev) / prev * 100, 2)
    except:
        return 0.0

def get_realtime_context(yf_code: str, display_code: str) -> str:
    """Fetch current company info + recent news from Yahoo Finance.
    Returns a compact text block to prepend to the model prompt as ground truth."""
    lines = [f"[实时数据 · {display_code} · 抓取自 Yahoo Finance]"]
    try:
        t = yf.Ticker(yf_code)
        info = t.info or {}

        # Company facts
        fields = [
            ("longName",          "公司全名"),
            ("sector",            "板块"),
            ("industry",          "行业"),
            ("country",           "注册地"),
            ("longBusinessSummary","业务简介"),
        ]
        for key, label in fields:
            val = info.get(key, "")
            if val:
                summary = val[:200] + "…" if len(val) > 200 else val
                lines.append(f"{label}：{summary}")

        # Key financials from info
        fin_map = [
            ("marketCap",            "市值(USD)"),
            ("totalRevenue",         "年营收(USD)"),
            ("revenueGrowth",        "营收同比"),
            ("grossMargins",         "毛利率"),
            ("trailingEps",          "EPS(TTM)"),
            ("forwardPE",            "Forward P/E"),
            ("recommendationKey",    "分析师评级"),
            ("targetMeanPrice",      "目标均价"),
        ]
        fin_lines = []
        for key, label in fin_map:
            val = info.get(key)
            if val is not None:
                if isinstance(val, float) and val < 10:
                    fin_lines.append(f"{label}={val:.1%}" if "率" in label or "同比" in label else f"{label}={val:.2f}")
                else:
                    fin_lines.append(f"{label}={val:,}" if isinstance(val, (int, float)) else f"{label}={val}")
        if fin_lines:
            lines.append("财务快照：" + " | ".join(fin_lines))

        # Recent news headlines (last 8)
        news = t.news or []
        if news:
            lines.append("近期新闻（最新8条）：")
            for n in news[:8]:
                title = n.get("title", "")
                pub   = n.get("providerPublishTime", "")
                if title:
                    lines.append(f"  · {title}")
    except Exception as e:
        lines.append(f"(Yahoo Finance 获取失败: {e})")

    return "\n".join(lines)

# ── Method B: Futu real-time context ─────────────────────────────────────────

# Confirmed field IDs (cross-checked against AAPL Q2-2026 and Tencent FY2025)
# gross_profit removed: field 8003/5003 returns EBIT (operating income), NOT gross profit
# Displaying operating margin as "毛利率" was misleading the AI analysis
_FIN_FIELDS = {
    'US': {'revenue': 8001, 'net_income': 8037, 'operating_cf': 8015},
    'HK': {'revenue': 5001, 'net_income': 5051, 'operating_cf': 5015},
}

def _get_fin_field(report: dict, fid: int):
    """Return (value_float, yoy_float) for a field_id in one Futu report."""
    for item in report.get('item_list', []):
        if item.get('field_id') == fid:
            v = item.get('data')
            y = item.get('yoy')
            try:    v = float(v) if v is not None else None
            except: v = None
            try:    y = float(y) if y is not None else None
            except: y = None
            return v, y
    return None, None

def _fmt_money(v: float, currency: str) -> str:
    """Format large numbers: 1.23B USD or 45.6亿HKD."""
    if currency == 'HKD':
        yi = v / 1e8
        return f"{yi:.1f}亿HKD" if abs(yi) < 1000 else f"{yi/100:.2f}万亿HKD"
    else:
        b = v / 1e9
        return f"{b:.2f}B USD" if abs(b) >= 1 else f"{v/1e6:.0f}M USD"

def _get_futu_financials(ctx, futu_code: str, is_hk: bool) -> list:
    """Pull income statement + cashflow from Futu, return formatted lines."""
    from futu import RET_OK
    lines = []
    mkt   = 'HK' if is_hk else 'US'
    fids  = _FIN_FIELDS[mkt]
    curr  = 'HKD' if is_hk else 'USD'
    # HK: annual reports (type=7), US: quarterly TTM combo (type=9)
    fin_type   = 7 if is_hk else 9
    num_period = 2 if is_hk else 4
    period_lbl = '年度' if is_hk else '季度'

    # ── Income statement ──────────────────────────────────────────────────────
    ret, inc = ctx.get_financials_statements(
        futu_code, statement_type=1, financial_type=fin_type, num=num_period
    )
    time.sleep(1.5)
    if ret == RET_OK and inc and inc.get('report_list'):
        rows = []
        for rpt in inc['report_list']:
            period = str(rpt.get('report_date', ''))[:7]
            rev, rev_yoy = _get_fin_field(rpt, fids['revenue'])
            ni,  ni_yoy  = _get_fin_field(rpt, fids['net_income'])

            parts = [f"[{period}]"]
            if rev:
                yoy = f" YoY{rev_yoy:+.1f}%" if rev_yoy is not None else ""
                parts.append(f"营收={_fmt_money(rev, curr)}{yoy}")
            if ni:
                yoy = f" YoY{ni_yoy:+.1f}%" if ni_yoy is not None else ""
                parts.append(f"净利={_fmt_money(ni, curr)}{yoy}")
            if len(parts) > 1:
                rows.append("  " + " | ".join(parts))

        if rows:
            lines.append(f"财务报表（富途 最近{num_period}期{period_lbl}）：")
            lines.extend(rows)

    # ── Operating cash flow ───────────────────────────────────────────────────
    ret2, cf = ctx.get_financials_statements(
        futu_code, statement_type=3, financial_type=fin_type, num=2
    )
    time.sleep(1.5)
    if ret2 == RET_OK and cf and cf.get('report_list'):
        cf_parts = []
        for rpt in cf['report_list'][:2]:
            period = str(rpt.get('report_date', ''))[:7]
            ocf, _ = _get_fin_field(rpt, fids['operating_cf'])
            if ocf is not None:
                cf_parts.append(f"[{period}]{_fmt_money(ocf, curr)}")
        if cf_parts:
            lines.append("经营现金流：" + " | ".join(cf_parts))

    # ── Revenue breakdown by segment ─────────────────────────────────────────
    ret3, rbk = ctx.get_financials_revenue_breakdown(futu_code)
    time.sleep(1.5)
    if ret3 == RET_OK and rbk is not None:
        items = rbk if isinstance(rbk, list) else (rbk.get('breakdown_list') or [])
        segs = []
        for item in items[:6]:
            name = item.get('name') or item.get('segment_name', '')
            pct  = item.get('percentage') or item.get('pct')
            if name and pct:
                try:    segs.append(f"{name}:{float(pct):.0f}%")
                except: pass
        if segs:
            lines.append("收入构成：" + " | ".join(segs))

    # ── Earnings beat/miss history ────────────────────────────────────────────
    ret4, em = ctx.get_financials_earnings_price_move(futu_code, period_count=4)
    time.sleep(1.5)
    if ret4 == RET_OK and em is not None:
        records = em.to_dict('records') if hasattr(em, 'to_dict') else []
        beats = total = 0
        for row in records:
            if row.get('day_offset') == 1:
                c = float(row.get('close_price') or 0)
                p = float(row.get('last_close_price') or 0)
                if p > 0:
                    total += 1
                    if c > p: beats += 1
        if total > 0:
            lines.append(f"近{total}次财报发布后次日股价：{beats}涨/{total-beats}跌")

    return lines


def get_futu_context(futu_code: str, display_code: str) -> str:
    """Fetch analyst consensus + rating changes + financial statements from Futu."""
    try:
        from futu import OpenQuoteContext, RET_OK
        ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
    except Exception as e:
        return f"(Futu 连接失败: {e})"

    is_hk = futu_code.startswith('HK.')
    lines = [f"[富途实时数据 · {display_code} · {datetime.today().strftime('%Y-%m-%d')}]"]
    try:
        # ── Analyst consensus ─────────────────────────────────────────────────
        ret, data = ctx.get_research_analyst_consensus(futu_code)
        if ret == RET_OK and data:
            avg = data.get('average')
            buy, hold, sell = data.get('buy_cnt',0), data.get('hold_cnt',0), data.get('sell_cnt',0)
            total_cnt = (buy or 0) + (hold or 0) + (sell or 0)
            if avg:
                lines.append(
                    f"分析师共识：目标价均值={avg} | 区间=[{data.get('low')}, {data.get('high')}] | "
                    f"买入{buy}/持有{hold}/卖出{sell}（共{total_cnt}家）"
                )

        # ── Recent rating changes (90 days) ───────────────────────────────────
        from datetime import timedelta
        cutoff = (datetime.today() - timedelta(days=90)).strftime('%Y-%m-%d')
        ret2, data2 = ctx.get_research_rating_summary(
            futu_code, rating_dimension_type=1, num=15, next_key=None, uid=None
        )
        if ret2 == RET_OK and data2:
            rating_map = {1:'强力买入', 2:'买入', 3:'持有', 4:'卖出', 5:'强力卖出'}
            changes = []
            for inst in (data2.get('inst_rating_summary_list') or []):
                items = inst.get('rating_item_list') or []
                if not items: continue
                latest = items[0]
                if (latest.get('recommendation_date_str') or '') < cutoff: continue
                firm   = inst.get('inst_name_simplified') or inst.get('inst_name', '')
                date_s = latest.get('recommendation_date_str', '')
                curr_r = rating_map.get(latest.get('rating', 0), '?')
                target = latest.get('target_price')
                s = f"{firm}({date_s})→{curr_r}"
                if target: s += f" 目标价={target}"
                if len(items) >= 2:
                    prev_r = rating_map.get(items[1].get('rating', 0), '?')
                    if curr_r != prev_r:
                        arrow = '↑' if (items[0].get('rating',0) or 0) < (items[1].get('rating',0) or 0) else '↓'
                        s += f"({arrow}从{prev_r})"
                changes.append(s)
            if changes:
                lines.append("近90天评级变动：")
                for c in changes[:8]: lines.append(f"  · {c}")

        # ── Financial statements ──────────────────────────────────────────────
        fin_lines = _get_futu_financials(ctx, futu_code, is_hk)
        lines.extend(fin_lines)

    except Exception as e:
        lines.append(f"(Futu 数据获取失败: {e})")
    finally:
        try: ctx.close()
        except Exception: pass

    return "\n".join(lines)


# ── DeepSeek prompts ──────────────────────────────────────────────────────────
SYSTEM_PROMPT = """\
你是一位专业的私人银行 FCN（固定票息票据）结构化产品分析师，服务对象是香港/新加坡的高净值客户。

核心写作原则：
- 结论先行：每个板块的第一句必须是核心判断，不以背景铺垫开头
- 数据具体：财务数字必须注明年度/季度，无法核实的绝对不引用
- 白话优先：技术术语紧跟白话解释，格式「术语（白话：……）」
- 客观专业：面向私人银行 HNW 客户，语气直白有力

严格禁止：
- 捏造或杜撰任何数据
- 空洞表述（如"未来发展潜力巨大"）
- bullet 超过 40 字
- 正文板块缺少 topic sentence
- 估值分析和风险分析（analysis 四个板块均不含）
"""

BATCH_PROMPT = """\
请为以下 {n} 只股票生成投资分析内容。

数据优先级规则（严格遵守）：
1. 标注「富途实时数据」的财务数字 → 必须原样引用，不得用训练记忆覆盖
2. 标注「Yahoo Finance」的公司信息 → 用于核实公司背景
3. 训练数据知识 → 仅用于行业背景、竞争格局等无实时数据的部分
4. 无法确认的推断 → 在 data_quality.model_inferences 中注明

股票数据：
{stock_data}

---

每只股票输出以下 JSON 对象（严格按 schema，不含估值与风险分析）：

{{
  "ticker": "与输入一致的股票代码",
  "name": "公司中文全称",
  "name_en": "Company English Name",
  "sector": "行业分类（如：AI半导体、互联网、新能源、金融等）",
  "bullets": [
    "投资要点①（≤40字，结论先行，含具体数据，非空洞表述）",
    "投资要点②（≤40字，与①完全独立，不重复不互补）"
  ],
  "analysis": {{
    "intro": "公司简介（150-200字）：成立时间、总部、控股背景、上市市场与代码、当前市值、核心业务一句白话定位、关键规模数据",
    "business": "业务介绍（300-450字）：每个板块以「👉 板块名称：」开头（不使用任何markdown符号如**），结构为「行业痛点→公司解法→为什么客户选这家」，含收入占比。每板块第一句必须是直接点明商业价值的结论句",
    "highlights": [
      {{
        "emoji": "适合的emoji",
        "title": "亮点标题（具体有画面感，非专业客户一眼懂，如「美国连锁化率70%，中国才27%——未来十年都是扩张窗口」）",
        "content": "亮点正文（150-250字）：第一句结论先行。覆盖以下之一：宏观政策顺风/市场份额领导力/竞争壁垒/订单收入确定性/行业结构性机会。投行推断标注〔投行推论：来源〕，数据外推标注〔分析推断〕"
      }}
    ],
    "financials": "财务数据（200-300字，2-3段，每段topic sentence开头）：含最新年度营收（绝对值+同比）、毛利率近3年走势、净利润、分业务收入占比、行业特有核心指标。利润变动附原因，展望连接具体催化剂"
  }},
  "data_quality": {{
    "verified": ["已核实数据项"],
    "broker_views": ["投行推论（来源：XX）"],
    "model_inferences": ["分析推断内容（依据：训练数据）"]
  }}
}}

highlights 要求：3-4 条，每条标题具体有画面感（参考：「3亿会员直接订房，绕开携程——利润多出10-15%」）。

输出格式：JSON 数组 [{{...}}, {{...}}]，不输出任何其他文字。
"""

# ── DeepSeek API call ─────────────────────────────────────────────────────────
def extract_json_array(text: str) -> list:
    text = text.strip()
    # Strip markdown fences
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'\s*```\s*$', '', text, flags=re.MULTILINE)
    # Find outermost array
    m = re.search(r'\[[\s\S]*\]', text)
    raw = m.group() if m else text
    # Try strict parse first, fall back to json_repair
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        repaired = json_repair.repair_json(raw, return_objects=True)
        if isinstance(repaired, list):
            return repaired
        raise ValueError(f"Cannot parse JSON even after repair: {raw[:200]}")

def analyze_batch(client: OpenAI, batch: list) -> list:
    stock_blocks = []
    for i, s in enumerate(batch):
        # ── Method A: structured FCN screener fields ──────────────────────────
        lines = [
            f"{i+1}. 代码={s['display_code']} | 名称={s['name']} | 市场={s['market']}",
            f"   现价={s['price']:.2f} {s['currency']} | 市值={s['market_cap']:.1f}B | IV={s['iv_pct']:.1f}%({s['iv_src']})",
            f"   分析师目标价上涨空间={s['analyst_upside']:.1%} | 综合评分={s['display_score']:.1f}",
        ]
        if s.get('catalyst_raw') is not None:
            lines.append(f"   催化剂评分(0-1)={s['catalyst_raw']:.3f} | 期权OI={int(s['option_oi'] or 0):,}")
        if s.get('max_drop') is not None:
            lines.append(
                f"   过去8季最大单日跌幅={s['max_drop']:.1%} | "
                f"现价/50日均线={s['sma50_ratio']:.3f} | "
                f"50日均线斜率={s['sma50_slope']:.4f}%/日"
            )
        # ── Method B: Futu analyst consensus + rating changes ─────────────────
        futu_ctx = s.get('futu_context', '')
        if futu_ctx:
            lines.append(futu_ctx)
        # ── Yahoo Finance: business summary + news ────────────────────────────
        yf_ctx = s.get('yf_context', '')
        if yf_ctx:
            lines.append(yf_ctx)

        stock_blocks.append("\n".join(lines))
    stock_data = "\n\n".join(stock_blocks)
    prompt = BATCH_PROMPT.format(n=len(batch), stock_data=stock_data)

    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                max_tokens=8192,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": prompt}
                ]
            )
            return extract_json_array(resp.choices[0].message.content)
        except Exception as e:
            wait = 2 ** attempt * 6
            if attempt < 2:
                print(f"  ⚠  Batch retry {attempt+1}/3 in {wait}s: {e}")
                time.sleep(wait)
            else:
                print(f"  ❌  Batch failed: {e}")
                return []
    return []

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Generate FCN watchlist.json from Excel")
    parser.add_argument("--excel",        default=EXCEL_PATH)
    parser.add_argument("--output",       default=OUTPUT_PATH)
    parser.add_argument("--top",          type=int, default=TOP_N)
    parser.add_argument("--dry-run",      action="store_true", help="First 5 stocks only")
    parser.add_argument("--no-sparkline", action="store_true", help="Skip yfinance")
    parser.add_argument("--no-ai",        action="store_true", help="Skip DeepSeek API")
    parser.add_argument("--week",         default=None,        help="Override week e.g. W24")
    args = parser.parse_args()

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key and not args.no_ai:
        print("❌  DEEPSEEK_API_KEY not set"); sys.exit(1)

    client = OpenAI(api_key=api_key, base_url=API_BASE) if api_key else None
    today    = datetime.today()
    iso_wk   = today.isocalendar()[1]
    week_str = args.week or f"W{iso_wk:02d} {today.year}"

    # ── 1. Read Excel ─────────────────────────────────────────────────────────
    print(f"\n[1/4] Reading Excel: {args.excel}")
    if not Path(args.excel).exists():
        print(f"❌  Not found: {args.excel}"); sys.exit(1)

    df = pd.read_excel(args.excel)
    col_map = {}
    for col in df.columns:
        c = col.replace('\n', ' ').strip()
        if c == 'Code':                            col_map[col] = 'code'
        elif c == 'Name':                          col_map[col] = 'name'
        elif c == 'Mkt':                           col_map[col] = 'market'
        elif c == 'Price':                         col_map[col] = 'price'
        elif 'Mkt Cap' in c:                       col_map[col] = 'market_cap'
        elif 'IV 6M' in c:                         col_map[col] = 'iv6m'
        elif 'Analyst' in c and 'Upside' in c:     col_map[col] = 'analyst_upside'
        elif 'DISPLAY' in c and 'SCORE' in c:      col_map[col] = 'display_score'
        elif 'Avg Vol' in c:                       col_map[col] = 'avg_vol'
        elif c in ('Coupon%', 'Coupon', '票息%'):  col_map[col] = 'manual_coupon'
        elif c in ('Strike%', 'Strike', '行权价%'): col_map[col] = 'manual_strike'
        elif c in ('KI%', 'KI', '敲入价%'):        col_map[col] = 'manual_ki'
        elif c in ('KI Type', 'KIType', '敲入类型'): col_map[col] = 'manual_ki_type'
        elif c in ('Tenor', 'Tenor(M)', '期限'):   col_map[col] = 'manual_tenor'
        elif c in ('KO%', 'KO', '敲出价%', '敲出价'): col_map[col] = 'manual_ko'
        elif 'Catalyst' in c:                      col_map[col] = 'catalyst_raw'
        elif 'Max 1D Drop' in c:                   col_map[col] = 'max_drop'
        elif 'Price/50DMA' in c:                   col_map[col] = 'sma50_ratio'
        elif '50DMA Slope' in c:                   col_map[col] = 'sma50_slope'
        elif 'Option OI' in c:                     col_map[col] = 'option_oi'
        elif c == 'IV Src':                        col_map[col] = 'iv_src'
    df = df.rename(columns=col_map)

    n = 5 if args.dry_run else args.top
    df = df.head(n)
    print(f"  Loaded top {len(df)} stocks (Excel already sorted by score)")

    stocks = []
    for _, row in df.iterrows():
        futu   = str(row['code']).strip()
        mkt    = str(row.get('market', 'US')).strip()
        iv_raw = float(row.get('iv6m', 0) or 0)
        iv_pct = round(iv_raw * 100 if iv_raw < 2 else iv_raw, 2)
        stocks.append({
            "futu_code":      futu,
            "display_code":   to_display_code(futu),
            "yf_code":        to_yf_code(futu),
            "name":           str(row.get('name', futu)),
            "market":         mkt,
            "price":          round(float(row.get('price', 0) or 0), 2),
            "market_cap":     round(float(row.get('market_cap', 0) or 0), 2),
            "currency":       "USD" if mkt == "US" else ("HKD" if mkt == "HK" else "CNY"),
            "iv_pct":         iv_pct,
            "analyst_upside": float(row.get('analyst_upside', 0) or 0),
            "display_score":  float(row.get('display_score', 0) or 0),
            "avg_vol":        float(row.get('avg_vol', 0) or 0),
            "manual_coupon":  _opt_float(row.get('manual_coupon')),
            "manual_strike":  _opt_float(row.get('manual_strike')),
            "manual_ki":      _opt_float(row.get('manual_ki')),
            "manual_ki_type": _opt_str(row.get('manual_ki_type')),
            "manual_tenor":   _opt_int(row.get('manual_tenor')),
            # Method A: extra screener fields for LLM context
            "catalyst_raw":   _opt_float(row.get('catalyst_raw')),
            "max_drop":       _opt_float(row.get('max_drop')),
            "sma50_ratio":    _opt_float(row.get('sma50_ratio')),
            "sma50_slope":    _opt_float(row.get('sma50_slope')),
            "option_oi":      _opt_float(row.get('option_oi')),
            "iv_src":         _opt_str(row.get('iv_src')) or 'futu',
            "manual_ko":      _opt_float(row.get('manual_ko')),
        })

    # ── 2. yfinance sparklines ────────────────────────────────────────────────
    if not args.no_sparkline:
        print(f"\n[2/4] Fetching sparklines via yfinance...")
        for i, s in enumerate(stocks):
            s['sparkline']        = get_sparkline(s['yf_code'])
            s['priceChange']      = get_price_change(s['yf_code'])
            s['yf_context']       = get_realtime_context(s['yf_code'], s['display_code'])
            s['futu_context']     = get_futu_context(s['futu_code'], s['display_code'])
            print(f"  [{i+1:2d}/{len(stocks)}] {s['display_code']:<14} "
                  f"{len(s['sparkline'])} weeks  Δ{s['priceChange']:+.1f}%")
            time.sleep(0.35)
    else:
        for s in stocks:
            s['sparkline']        = []
            s['priceChange']      = 0.0
            s['yf_context']       = get_realtime_context(s['yf_code'], s['display_code'])
            s['futu_context']     = get_futu_context(s['futu_code'], s['display_code'])
        print("\n[2/4] Sparklines skipped (--no-sparkline)")

    # ── 3. DeepSeek analysis ──────────────────────────────────────────────────
    def _validate_ana(ana: dict) -> tuple[bool, list]:
        """Check all required fields are present and non-empty."""
        inner = ana.get("analysis", ana)
        issues = []
        if not inner.get("intro"):        issues.append("no intro")
        if not inner.get("business"):     issues.append("no business")
        hl = inner.get("highlights") or []
        if not hl:                        issues.append("no highlights")
        elif len(hl) < 3:                 issues.append(f"highlights={len(hl)}<3")
        if not inner.get("financials"):   issues.append("no financials")
        return len(issues) == 0, issues

    analysis_map = {}
    if not args.no_ai:
        print(f"\n[3/4] Generating analysis ({MODEL})...")
        batches   = [stocks[i:i+BATCH_SIZE] for i in range(0, len(stocks), BATCH_SIZE)]
        completed = 0

        def _run(bi, batch):
            return bi, batch, analyze_batch(client, batch)

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as exe:
            futs = {exe.submit(_run, i, b): i for i, b in enumerate(batches)}
            for fut in as_completed(futs):
                _, batch, results = fut.result()
                for stock, ana in zip(batch, results):
                    analysis_map[stock['display_code']] = ana
                    completed += 1
                    print(f"  ✅ [{completed:2d}/{len(stocks)}] "
                          f"{stock['display_code']} {stock['name']} — 完成")

        # ── 单股重试：修复 batch 中格式不完整的股票 ──────────────────────────
        retry_stocks = []
        for s in stocks:
            ana = analysis_map.get(s['display_code'], {})
            ok, issues = _validate_ana(ana)
            if not ok:
                print(f"  ⚠  {s['display_code']} 分析不完整 ({issues})，单股重试...")
                retry_stocks.append(s)

        for s in retry_stocks:
            for attempt in range(3):
                results = analyze_batch(client, [s])
                if results:
                    ok, issues = _validate_ana(results[0])
                    if ok:
                        analysis_map[s['display_code']] = results[0]
                        print(f"  ✅  {s['display_code']} 重试成功")
                        break
                    print(f"  ⚠  {s['display_code']} 重试 {attempt+1}/3 仍不完整: {issues}")
                else:
                    print(f"  ⚠  {s['display_code']} 重试 {attempt+1}/3 无输出")
                time.sleep(6)
            else:
                print(f"  ❌  {s['display_code']} 重试耗尽，保留空分析")
    else:
        print("\n[3/4] DeepSeek skipped (--no-ai)")

    # ── 4. Merge and write ────────────────────────────────────────────────────
    def _strip_md_bold(text: str) -> str:
        """Remove **bold** markdown markers from AI output."""
        return re.sub(r'\*\*([^*]+)\*\*', r'\1', text) if text else text

    print(f"\n[4/4] Writing {args.output}...")
    score_max = max((s['display_score'] for s in stocks), default=100) or 100

    output_stocks = []
    for rank, s in enumerate(stocks):
        code = s['display_code']
        ana  = analysis_map.get(code, {})
        fcn  = calc_fcn_terms(s['iv_pct'])
        # Manual Excel values override IV-estimated terms
        if s['manual_coupon']  is not None: fcn['coupon'] = s['manual_coupon']
        if s['manual_strike']  is not None: fcn['strike'] = s['manual_strike']
        if s['manual_ki']      is not None: fcn['ki']     = s['manual_ki']
        if s['manual_ko']      is not None: fcn['ko']     = s['manual_ko']
        if s['manual_ki_type'] is not None: fcn['kiType'] = s['manual_ki_type']
        if s['manual_tenor']   is not None: fcn['tenor']  = s['manual_tenor']

        score_10 = round(s['display_score'] / score_max * 10, 1)
        score_bd = {
            "fundamental": min(round(s['display_score'] / score_max * 10, 1), 10),
            "volatility":  min(round(s['iv_pct'] / 120 * 10, 1), 10),
            "liquidity":   min(round(min(s['avg_vol'], 5000) / 5000 * 10, 1), 10),
            "momentum":    min(round(max(s['analyst_upside'] * 20, 0), 1), 10),
        }

        if rank == 0:     tag = "本周精选"
        elif s['iv_pct'] >= 70: tag = "高 IV"
        elif fcn['risk'] == "低": tag = "稳健"
        else:             tag = ""

        output_stocks.append({
            "code":           code,
            "name":           ana.get("name") or s['name'],
            "name_en":        ana.get("name_en", ""),
            "industry":       ana.get("sector", ""),
            "market":         s['market'],
            "price":          s['price'],
            "marketCap":      s['market_cap'],
            "currency":       s['currency'],
            "priceChange":    s['priceChange'],
            "sparkline":      s['sparkline'],
            "iv30":           s['iv_pct'],
            "score":          score_10,
            "scoreBreakdown": score_bd,
            "risk":           fcn['risk'],
            "tag":            tag,
            "coupon":         fcn['coupon'],
            "strike":         fcn['strike'],
            "ki":             fcn['ki'],
            "ko":             fcn['ko'],
            "kiType":         fcn['kiType'],
            "tenor":          fcn['tenor'],
            "bullets":        ana.get("bullets", []),
            "analysis":       {**ana.get("analysis", {}),
                               "business": _strip_md_bold(ana.get("analysis", {}).get("business", ""))},
            "data_quality":   ana.get("data_quality", {}),
        })

    featured = [s['code'] for s in output_stocks[:5]]
    watchlist = {
        "_generated": {
            "by":    "generate_watchlist.py",
            "model": MODEL,
            "at":    today.isoformat(),
            "count": len(output_stocks),
            "excel": Path(args.excel).name,
        },
        "meta": {
            "week":        week_str,
            "theme":       "",
            "publishDate": today.strftime("%Y-%m-%d"),
            "nextUpdate":  (today + timedelta(days=7)).strftime("%Y-%m-%d"),
            "featuredIds": featured,
        },
        "stocks": output_stocks
    }

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(watchlist, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*55}")
    print(f"✅  Done — {len(output_stocks)} stocks → {args.output}")
    print(f"   Week: {week_str}  |  Model: {MODEL}")
    print(f"   Top 3: {', '.join(s['code'] for s in output_stocks[:3])}")
    print(f"\n   Next step:")
    print(f"   git add watchlist.json && git commit -m \"{week_str} weekly update\" && git push")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
