# Thousand Times 多 Agent 并行优化工作流

> 此 Prompt 用于 Workflow 工具执行。包含 4 个阶段、6 个 Agent、验证闭环。
> 运行方式：将下文传给 Workflow 工具，或作为 workflow script 直接执行。

---

## 使用说明

将此 prompt 输入给 Claude Code 的 Workflow 工具，将自动启动 4 阶段多 Agent 并行执行，每阶段完成后自动验证。

**前置条件**：
- 工作目录为 `h:/code/thousand times`
- 所有 Agent 在 `isolation: "worktree"` 模式下运行以避免文件冲突
- 阶段 1 的 3 个 Agent 操作**互不重叠的文件**，确保并行安全

---

## Workflow Script

```javascript
export const meta = {
  name: 'thousand-times-p0-p1-optimization',
  description: '执行 P0+P1 优化计划：基本面修复、评分校准、效率提升、报告增强，含验证',
  phases: [
    { title: 'P1: 并行修复', detail: 'Agent A=基本面管道, Agent B=ETF API修复, Agent C=评分诊断日志' },
    { title: 'P2: 评分校准', detail: '基于诊断结果，引入百分位排名+MA60优化+基线分' },
    { title: 'P3: 效率+报告', detail: 'Agent E=数据源+K线优化, Agent F=信号跟踪+报告增强' },
    { title: 'P4: 验证闭环', detail: '运行测试→检查基本面→检查信号→检查报告格式' },
  ],
}

// ============================================================
// 阶段 1：三个 Agent 并行修复（操作互不重叠的文件）
// ============================================================
phase('P1: 并行修复')

const [fundamentalResult, etfResult, diagResult] = await parallel([
  // ── Agent A: 基本面数据管道修复 ──
  () => agent(`
你是一个 Python 量化系统开发者。你需要修复 A 股分析系统中基本面数据完全失效的问题。

**背景**：当前系统使用 BaoStock 获取财务数据，但在 CI 环境（GitHub Actions）中，BaoStock 的 TCP 连接极不稳定，导致 1000 只股票 0 只获取到有效基本面数据。需要改用 AKShare 作为主数据源。

**你需要修改的文件**：
1. \`requirements.txt\` — 锁定 akshare 版本
2. \`src/fundamental_analysis.py\` — 新增 AKShare 数据源，调整优先级
3. \`src/cache_manager.py\` — 延长基本面缓存 TTL

**具体任务**：

### 任务 1.1：锁定 AKShare 版本
编辑 requirements.txt，将 \`akshare>=1.14.0\` 改为 \`akshare==1.14.0\`

### 任务 1.2：新增 AKShare 基本面数据源
在 fundamental_analysis.py 中新增函数 \`_fetch_fundamental_akshare(code: str) -> dict\`：
- 使用 \`ak.stock_yjbb_em(symbol=code)\` 获取业绩报表数据
- 从返回的 DataFrame 中提取最新一行，映射为字典：
  - \`roeAvg\` ← 净资产收益率（注意单位转换，若为小数需×100）
  - \`epsTTM\` ← 每股收益
  - \`profit_growth\` ← 净利润同比增长率（注意单位）
  - \`revenue_growth\` ← 营收同比增长率
  - \`debt_ratio\` ← 资产负债率
  - \`gross_margin\` ← 毛利率
  - \`cash_flow\` ← 每股经营现金流（若 AKShare 无此字段，设为 None）
- 如果 API 调用失败，返回空字典 {}
- 添加 try/except 和合适的日志

### 任务 1.3：调整数据源优先级
修改 \`get_fundamental_data_batch(codes)\` 函数：
- 将数据获取优先级改为：**先尝试 AKShare（_fetch_fundamental_akshare），失败再回退到 BaoStock**
- 保持原有的重连和错误处理逻辑
- AKShare 不需要 login/logout，直接 HTTP 调用
- 对每只股票：先调 AKShare，如果返回数据有效（roe>0 或 eps>0）则直接用，否则 fallback 到 BaoStock
- 保留原有的 \`_dict_to_fundamental_data\` 和 \`_empty_fundamental_data\` 转换逻辑

### 任务 1.4：延长基本面缓存
在 cache_manager.py 中，找到 \`FUND_CACHE_TTL\` 常量，将其值从当前的秒数改为 **90 天**（7776000 秒）。添加注释说明"季报数据每季度更新一次"。

**验证要求**：修改完成后，检查代码语法正确，import 路径正确，函数签名与调用处一致。
`, { label: 'Agent-A: 基本面管道', phase: 'P1: 并行修复' }),

  // ── Agent B: ETF API 兼容性修复 ──
  () => agent(`
你是一个 Python 开发者。需要修复 ETF 份额数据获取的 AKShare API 兼容性问题。

**背景**：日志中出现 \`fund_etf_fund_daily_em() got an unexpected keyword argument 'symbol'\` 错误，导致 11 只 ETF 全部回退到默认评分 3.0。

**你需要修改的文件**：
- \`src/etf_analyzer.py\`

**具体任务**：

### 任务 3.1 & 3.2：修复 _fetch_etf_fund_daily()
阅读 etf_analyzer.py 中的 \`_fetch_etf_fund_daily(code, timeout=30)\` 函数（约第 47-99 行）：

当前代码已经尝试无参数调用 \`ak.fund_etf_fund_daily_em()\`，但返回列的映射可能有问题。

请做以下检查并修复：
1. 确认 \`ak.fund_etf_fund_daily_em()\` 不需要参数（当前写法正确）
2. 检查返回 DataFrame 的列名——第一列是基金代码，其他列可能包含份额变化数据
3. 更新 column_mapping（第 244-249 行）以匹配实际的列名
4. 如果实际列名不同于映射中的任何一个，增加"从数值列自动推断"的逻辑——遍历所有列，将第一个包含"份额"、"变化"、"变动"关键字的数值列作为 share_change
5. 确保 fallback 到 BaoStock 时也能正确获取数据

**验证要求**：代码能正确处理 AKShare 返回的各种列名格式。
`, { label: 'Agent-B: ETF API修复', phase: 'P1: 并行修复' }),

  // ── Agent C: 评分分布诊断日志 ──
  () => agent(`
你是一个 Python 开发者。需要在系统中添加评分分布诊断日志，以便后续校准评分模型。

**你需要修改的文件**：
- \`src/main.py\`

**具体任务（Task 2.1）**：

在 main.py 中找到 V1 管道的信号生成部分（\`generate_buy_sell_signal\` 调用之后的区域，约第 730 行附近），以及 V2 管道的信号生成部分（\`_run_v2_pipeline\` 函数中 \`generate_signals\` 调用之后）。

在**两个管道**的信号生成完成后，各添加一段评分分布诊断代码：

\`\`\`python
import numpy as np

# 收集所有评分
stock_scores = [s.total_score for s in stock_results] if 'stock_results' in dir() else []
etf_scores = [s.total_score for s in etf_results] if 'etf_results' in dir() else []
all_scores = stock_scores + etf_scores

if all_scores:
    arr = np.array(all_scores)
    logger.info("=" * 40)
    logger.info("评分分布诊断")
    logger.info(f"  样本数: {len(arr)}")
    logger.info(f"  范围: [{arr.min():.1f}, {arr.max():.1f}]")
    logger.info(f"  均值: {arr.mean():.1f}  标准差: {arr.std():.1f}")
    for p in [5, 25, 50, 75, 95]:
        logger.info(f"  {p}th 分位: {np.percentile(arr, p):.1f}")
    
    # 分档统计
    buy_count = sum(1 for s in all_scores if s >= 70)
    watch_count = sum(1 for s in all_scores if 30 <= s < 70)
    sell_count = sum(1 for s in all_scores if s < 30)
    logger.info(f"  买入区(≥70): {buy_count}, 观望区(30-69): {watch_count}, 卖出区(<30): {sell_count}")
    logger.info("=" * 40)
\`\`\`

同时在 technical_score 维度也打印分布：
\`\`\`python
tech_scores = [s.technical_score for s in stock_results if hasattr(s, 'technical_score')]
if tech_scores:
    t_arr = np.array(tech_scores)
    logger.info(f"技术评分分布: min={t_arr.min():.1f} max={t_arr.max():.1f} mean={t_arr.mean():.1f}")
\`\`\`

**注意**：
- V1 管道中变量名为 \`stock_results\` / \`etf_results\`（ScoreResult 列表）
- V2 管道中需要根据 pipeline/signal.py 的信号对象调整
- 只加日志，不改任何业务逻辑
- 确保 import numpy 在文件顶部

**验证要求**：运行 \`python src/main.py\` 后日志中出现 "评分分布诊断" 字样和完整统计数据。
`, { label: 'Agent-C: 诊断日志', phase: 'P1: 并行修复' }),
])

log(`P1 完成: 基本面=${fundamentalResult ? 'OK' : 'FAIL'}, ETF=${etfResult ? 'OK' : 'FAIL'}, 诊断=${diagResult ? 'OK' : 'FAIL'}`)

// ============================================================
// 阶段 2：评分模型校准（依赖 P1 完成）
// ============================================================
phase('P2: 评分校准')

const scoringResult = await agent(`
你是一个量化策略开发者。需要重新校准评分模型，解决 "买入 0, 卖出 0" 的问题。

**背景**：P1 阶段已修复基本面数据管道并添加了诊断日志。现在需要校准评分模型，让评分产生有意义的区分度。

**你需要修改的文件**：
- \`src/buy_sell_signal.py\` — 新增百分位相对排名信号
- \`src/technical_analysis.py\` — MA60 优化 + 基线分
- \`src/config.py\` — 不变（保持现有阈值作为参考）

### 任务 2.2：引入百分位相对排名信号

在 buy_sell_signal.py 中新增函数 \`apply_percentile_override\`:

\`\`\`python
def apply_percentile_override(
    code: str,
    total_score: float,
    all_scores: list[float],
    config: BuySellSignalConfig,
    top_pct: float = 0.20,
    bottom_pct: float = 0.20,
) -> tuple[str, str]:
    """百分位相对排名覆盖。
    
    即使绝对分数未达阈值，如果排名在股票池前 top_pct，也标记为买入关注；
    即使绝对分数未低到卖出阈值，如果排名在后 bottom_pct，也标记为风险警示。
    
    Args:
        code: 股票代码
        total_score: 绝对评分
        all_scores: 股票池中所有股票的评分列表
        config: 买卖信号配置
        top_pct: 头部比例（默认 20%）
        bottom_pct: 尾部比例（默认 20%）
    
    Returns:
        (signal_zone, signal_emoji) 元组
    """
    if not all_scores or len(all_scores) < 5:
        # 股票太少，直接用绝对阈值
        return determine_signal_zone(total_score, config)
    
    sorted_scores = sorted(all_scores, reverse=True)
    top_threshold = sorted_scores[max(0, int(len(sorted_scores) * top_pct) - 1)]
    bottom_threshold = sorted_scores[min(len(sorted_scores) - 1, int(len(sorted_scores) * (1 - bottom_pct)))]
    
    if total_score >= top_threshold and total_score >= config.buy_threshold * 0.7:
        return ("买入关注", "🟢")
    elif total_score <= bottom_threshold and total_score <= config.sell_threshold * 1.5:
        return ("风险警示", "🔴")
    else:
        return determine_signal_zone(total_score, config)
\`\`\`

**重要**：这个函数应与现有的 \`determine_signal_zone\` 配合使用——在 main.py 的 V1 管道中，先生成 BuySellSignal 后再用此函数做覆盖。

### 任务 2.3：降低 MA60 对新股阻塞

在 technical_analysis.py 的 \`_df_to_kline_data\` 函数中修改 MA60 计算逻辑：
- 当数据长度 < 60 天时，\`min_periods\` 降为实际数据长度（而非固定 60）
- 在 \`calc_technical_signals\` 中，对 MA20/60 金叉和多头排列信号增加判断：如果 MA60 数据量 < 60 天，该信号的权重 \`× 0.5\`（在 TechnicalSignals 中通过属性值表示，或在 calc_technical_score 中处理）

具体修改：
1. \`_df_to_kline_data\`: \`ma60 = _calc_ma(closes, 60, min_periods=min(60, len(closes)))\`
2. 在 TechnicalSignals dataclass 中新增可选字段 \`ma60_data_days: int = 60\`
3. 在 calc_technical_signals 中设置 \`signals.ma60_data_days = n\`（实际数据天数）
4. 在 calc_technical_score 中：如果 \`signals.ma60_data_days < 60\`，对 ma20_60_golden 和 bullish_alignment 的加分 \`× 0.5\`
5. 更新 TechnicalSignals 的定义（在 scoring.py 中）

### 任务 2.4：提高技术评分基线

在 calc_technical_score（两个文件都有此函数：scoring.py 和 technical_analysis.py，**以 technical_analysis.py 中的为准**）中，在现有计算逻辑的**末尾、截断之前**，增加：

\`\`\`python
# 基线分：近期涨跌幅
kline_for_baseline = ... # 需要传入 KlineData 或者 closes 数据
# 方案：修改 calc_technical_score 的函数签名，增加一个可选参数 baseline_kline: KlineData | None = None
\`\`\`

实际上，为了保持向后兼容，更好的做法是新增一个函数 \`calc_technical_score_with_baseline\`，或修改调用处传入 KlineData。

**简化方案**（推荐）：在 \`scoring.py\` 的 \`calc_technical_score\`（模块级函数）中增加一个可选参数 \`kline\`，如果传入则计算：
\`\`\`python
if kline is not None and len(kline.closes) >= 5:
    closes_arr = np.array(kline.closes)
    change_5d = (closes_arr[-1] - closes_arr[-5]) / closes_arr[-5] * 100 if closes_arr[-5] > 0 else 0
    change_20d = (closes_arr[-1] - closes_arr[-20]) / closes_arr[-20] * 100 if len(closes_arr) >= 20 and closes_arr[-20] > 0 else 0
    if change_5d > 0:
        score += 5.0
    if change_20d > 0:
        score += 3.0
\`\`\`

同时需要更新 main.py 中所有调用 \`calc_technical_score\` 的地方，传入 kline 参数。

**验证要求**：确保所有修改不破坏现有测试。关注 scoring.py 和 technical_analysis.py 中是否都有 calc_technical_score 函数——需要统一修改或明确哪个是主函数。
`, { label: 'Agent-D: 评分校准', phase: 'P2: 评分校准' })

log(`P2 完成: 评分校准 = ${scoringResult ? 'OK' : 'FAIL'}`)

// ============================================================
// 阶段 3：效率优化 + 报告增强（并行，互不重叠的文件）
// ============================================================
phase('P3: 效率+报告')

const [efficiencyResult, reportResult] = await parallel([
  // ── Agent E: 数据源优先级 + K线效率 ──
  () => agent(`
你是一个 Python 性能优化工程师。需要优化数据获取效率。

**你需要修改的文件**：
- \`src/main.py\` — 数据源优先级 + 线程池 + CI 延迟
- \`src/stock_filter.py\` — 数据源优先级
- \`src/cache_manager.py\` — K线增量更新
- \`src/config.py\` — CI 延迟配置

### 任务 4.1：AKShare 提升为主数据源

在 stock_filter.py 的 \`get_stock_pool()\` 中：
- 当前优先级：远程 API → AKShare → BaoStock
- 修改为：**AKShare → 远程 API → BaoStock**（AKShare 在 CI 环境更稳定）
- 同时将 AKShare 超时从 60 秒延长到 90 秒（海外 CI 网络慢）

在 main.py 的 \`_fetch_kline_batch\` (boilerplate, 约第 476-488 行):
- 在 \`BAOSTOCK_AVAILABLE\` 为 True 时，仍然优先尝试 AKShare
- 修改逻辑：先尝试 \`ak.stock_zh_a_hist()\` 逐只获取 → 失败再回退 BaoStock

### 任务 4.2：AKShare 逐只获取 K 线

在 main.py 中新增函数 \`_fetch_kline_akshare(code, days)\`:
\`\`\`python
def _fetch_kline_akshare(code: str, days: int = 120) -> pd.DataFrame:
    """使用 AKShare 获取个股历史K线。"""
    try:
        import akshare as ak
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
        df = ak.stock_zh_a_hist(symbol=code, period="daily", 
                                start_date=start_date, end_date=end_date, adjust="qfq")
        if df is not None and not df.empty:
            # 重命名为与其他源一致的列名
            df = df.rename(columns={
                "日期": "日期", "开盘": "开盘", "收盘": "收盘",
                "最高": "最高", "最低": "最低", "成交量": "成交量",
            })
            return df
    except Exception as e:
        logger.debug(f"AKShare 获取 {code} K线失败: {e}")
    return pd.DataFrame()
\`\`\`

然后在 \`_fetch_kline_batch\` 中：先尝试对每只股票调用 \`_fetch_kline_akshare\`，失败再用 BaoStock。

### 任务 4.3 + 5.1：CI 延迟削减 + 增大线程池

在 main.py 中：
- 找到 \`workers=4\`（第 97 行），改为 \`workers=8 if is_ci else 4\`
- 在 config.py 加载完成后（main.py 约第 366 行），如果是 CI 环境，override 延迟：
\`\`\`python
if is_ci:
    config.request_delay_range = (0.1, 0.3)
\`\`\`

### 任务 5.2：K 线增量更新

在 cache_manager.py 中修改 \`needs_kline_update(df, report_date)\`：
- 当前逻辑：检查 DataFrame 最后一行日期是否 < report_date
- 增强：返回需要获取的起始日期（而非布尔值）
- 如果是增量更新，只拉取从最后缓存日期到今天的 K 线
- 在 main.py 中对应修改增量获取逻辑

\`\`\`python
def get_kline_update_start(df: pd.DataFrame, report_date: str) -> str | None:
    """返回增量更新的起始日期。如果不需要更新返回 None。"""
    if df is None or df.empty:
        return None
    date_col = "日期" if "日期" in df.columns else "date"
    if date_col not in df.columns:
        return None
    last_date = str(df[date_col].iloc[-1])[:10]
    if last_date >= report_date:
        return None  # 已是最新
    return last_date  # 从这个日期开始拉增量
\`\`\`

**验证要求**：所有改动不引入 import 错误，逻辑正确。
`, { label: 'Agent-E: 效率优化', phase: 'P3: 效率+报告' }),

  // ── Agent F: 信号跟踪 + 报告增强 ──
  () => agent(`
你是一个 Python 全栈开发者。需要添加信号跟踪功能和增强报告内容。

**你需要修改/新增的文件**：
- \`src/report_generator.py\` — 报告增强
- \`src/cache_manager.py\` — 推荐记录数据库
- 新增 \`src/signal_tracker.py\` — SQLite 信号历史

### 任务 6.1：信号跟踪数据库

新增 \`src/signal_tracker.py\`：

\`\`\`python
"""信号跟踪模块 — 记录推荐历史并计算回顾表现。"""
from __future__ import annotations
import sqlite3
import os
import logging
from datetime import datetime, timedelta

logger = logging.getLogger("thousand-times")

DB_PATH = "cache/recommendations.db"

def _get_conn() -> sqlite3.Connection:
    os.makedirs("cache", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS recommendations (
            date TEXT, code TEXT, name TEXT, action TEXT, 
            score REAL, price REAL,
            PRIMARY KEY (date, code)
        )
    """)
    return conn

def record_signals(signals: list[dict]) -> None:
    """批量记录信号。signals: [{"code","name","action","score","price","date"}]"""
    if not signals:
        return
    try:
        conn = _get_conn()
        for s in signals:
            conn.execute(
                "INSERT OR REPLACE INTO recommendations VALUES (?,?,?,?,?,?)",
                (s["date"], s["code"], s["name"], s["action"], s["score"], s["price"])
            )
        conn.commit()
        conn.close()
        logger.info(f"信号记录完成: {len(signals)} 条")
    except Exception as e:
        logger.warning(f"信号记录失败: {e}")

def get_yesterday_recommendations(today: str) -> list[dict]:
    """获取昨日的推荐信号。"""
    try:
        yesterday = (datetime.strptime(today, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
        conn = _get_conn()
        cur = conn.execute(
            "SELECT code, name, action, score, price FROM recommendations WHERE date = ?",
            (yesterday,)
        )
        rows = [{"code": r[0], "name": r[1], "action": r[2], "score": r[3], "price": r[4]} 
                for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception:
        return []
\`\`\`

### 任务 6.2：昨日推荐回顾

在 report_generator.py 中新增 \`_build_retrospective_section(report_date, current_prices)\` 函数：
- 从 signal_tracker 查询昨日推荐
- 与当前价格对比，计算涨跌幅
- 输出格式：
\`\`\`
📈 昨日推荐回顾
  买入信号 5 只，今日平均涨跌幅 +1.2%
  风险警示 3 只，今日平均涨跌幅 -0.8%
\`\`\`

在 \`generate_report()\` 中调用并插入到报告顶部（市场概况之后）。

### 任务 6.3：Top 10 排名

在 report_generator.py 中新增 \`_build_top_ranking(stock_results, n=10)\` 函数：
- 按 total_score 降序取前 10 只
- 格式：
\`\`\`
🏆 评分排名 Top 10
  1. 贵州茅台 (600519) — 68分 buy | 技术45 基本面18 新闻5
  2. ...
\`\`\`

### 任务 8.1：市场概况板块

在 \`generate_report()\` 开头增加 \`📊 市场概况\` 区块。需要接受新参数：
- \`market_regime\` — 市场状态描述（已有）
- \`north_flow\` — 北向资金净流入（已有数据）
- \`pmi\` — PMI 数据（已有）
- \`m2\` — M2 增速（已有）
- \`advance_decline\` — 涨跌比（从 stock_pool 计算）

### 任务 8.2：行业热力图

新增 \`_build_sector_heatmap(etf_results)\` 函数：
- 遍历 ETF 评分结果
- 按涨跌幅排序，用 ASCII bar 展示
- 格式：\`半导体 +2.3% ████████ | 消费 -1.2% ████\`

### 任务 8.3：ETF 名称统一

在 report_generator.py 中，所有引用 ETF 名称的地方，使用 etf_analyzer.py 中的 ETF_NAME_MAP 进行映射。
对于以 "ETF_" 开头的名称，去掉前缀并查映射表。

**验证要求**：所有新增函数应有 Google 风格 docstring。不破坏现有 report_generator.py 的其他函数。
`, { label: 'Agent-F: 报告增强', phase: 'P3: 效率+报告' }),
])

log(`P3 完成: 效率=${efficiencyResult ? 'OK' : 'FAIL'}, 报告=${reportResult ? 'OK' : 'FAIL'}`)

// ============================================================
// 阶段 4：验证闭环
// ============================================================
phase('P4: 验证闭环')

const verifyResults = await pipeline(
  [
    { key: 'syntax', desc: 'Python 语法检查' },
    { key: 'imports', desc: '模块导入检查' },
    { key: 'tests', desc: '单元测试运行' },
    { key: 'signal', desc: '信号输出检查' },
  ],
  // Stage 1: 执行检查
  async (item) => {
    if (item.key === 'syntax') {
      return await agent(`
运行以下命令检查所有修改过的 Python 文件是否有语法错误：
\`\`\`bash
cd "h:/code/thousand times" && python -m py_compile src/fundamental_analysis.py && echo "fundamental_analysis.py OK"
python -m py_compile src/etf_analyzer.py && echo "etf_analyzer.py OK"
python -m py_compile src/main.py && echo "main.py OK"
python -m py_compile src/scoring.py && echo "scoring.py OK"
python -m py_compile src/buy_sell_signal.py && echo "buy_sell_signal.py OK"
python -m py_compile src/technical_analysis.py && echo "technical_analysis.py OK"
python -m py_compile src/report_generator.py && echo "report_generator.py OK"
python -m py_compile src/cache_manager.py && echo "cache_manager.py OK"
python -m py_compile src/signal_tracker.py 2>/dev/null && echo "signal_tracker.py OK" || echo "signal_tracker.py not found (expected if Agent-F created it)"
\`\`\`
报告每个文件的编译结果，汇总 FAIL 数量。
      `, { label: '验证: 语法检查', schema: {
        type: 'object', properties: {
          total: { type: 'integer' },
          passed: { type: 'integer' },
          failed: { type: 'integer' },
          failed_files: { type: 'array', items: { type: 'string' } },
        }, required: ['total', 'passed', 'failed']
      }})
    }

    if (item.key === 'imports') {
      return await agent(`
运行以下命令检查模块导入是否正常：
\`\`\`bash
cd "h:/code/thousand times" && python -c "
import sys
sys.path.insert(0, 'src')
errors = []
for mod in ['fundamental_analysis', 'etf_analyzer', 'scoring', 'buy_sell_signal', 
            'technical_analysis', 'report_generator', 'cache_manager', 'config']:
    try:
        __import__(mod)
        print(f'{mod} import OK')
    except Exception as e:
        errors.append(f'{mod}: {e}')
        print(f'{mod} import FAILED: {e}')
if errors:
    print(f'\\n{len(errors)} import errors')
else:
    print('\\nAll imports OK')
"
\`\`\`
报告导入结果，如果有错误给出具体信息。
      `, { label: '验证: 导入检查', schema: {
        type: 'object', properties: {
          all_passed: { type: 'boolean' },
          errors: { type: 'array', items: { type: 'string' } },
        }, required: ['all_passed']
      }})
    }

    if (item.key === 'tests') {
      return await agent(`
运行项目现有的单元测试：
\`\`\`bash
cd "h:/code/thousand times" && python -m pytest tests/ -v --tb=short 2>&1 | tail -100
\`\`\`
报告测试结果：total / passed / failed / errors。
如果部分测试因为网络原因失败（需要外部 API），标记为 skipped 而非 failed。
      `, { label: '验证: 单元测试', schema: {
        type: 'object', properties: {
          total: { type: 'integer' },
          passed: { type: 'integer' },
          failed: { type: 'integer' },
          key_failures: { type: 'array', items: { type: 'string' } },
        }, required: ['total', 'passed', 'failed']
      }})
    }

    if (item.key === 'signal') {
      return await agent(`
检查修改后的代码逻辑是否能产生有效信号。不需要实际运行（因为没有网络），而是检查代码逻辑：

1. 在 fundamental_analysis.py 中：确认 \`_fetch_fundamental_akshare\` 函数存在且被 \`get_fundamental_data_batch\` 调用
2. 在 buy_sell_signal.py 中：确认 \`apply_percentile_override\` 函数存在且逻辑正确
3. 在 main.py 中：确认 V1 管道调用了 \`apply_percentile_override\`
4. 在 report_generator.py 中：确认 \`_build_retrospective_section\` 和 \`_build_top_ranking\` 存在

对于每个检查项，报告 "OK" 或 "MISSING: <具体说明>"。
      `, { label: '验证: 信号逻辑', schema: {
        type: 'object', properties: {
          fundamental_pipeline: { type: 'string' },
          percentile_override: { type: 'string' },
          main_integration: { type: 'string' },
          report_enhancement: { type: 'string' },
          all_ok: { type: 'boolean' },
        }, required: ['all_ok']
      }})
    }
  },
  // Stage 2: 汇总
  async (results) => {
    const syntax = results.find(r => r?.total !== undefined && r?.failed !== undefined)
    const imports = results.find(r => r?.all_passed !== undefined)
    const tests = results.find(r => r?.total !== undefined && r?.failed !== undefined && r?.key_failures)
    const signal = results.find(r => r?.all_ok !== undefined)

    const summary = {
      syntax_ok: syntax ? syntax.failed === 0 : false,
      imports_ok: imports ? imports.all_passed : false,
      tests_ok: tests ? tests.failed === 0 : false,
      signal_logic_ok: signal ? signal.all_ok : false,
      overall_ok: false,
      issues: [],
    }

    if (!summary.syntax_ok) issues.push('语法错误: ' + (syntax?.failed_files?.join(', ') || 'unknown'))
    if (!summary.imports_ok) issues.push('导入错误: ' + (imports?.errors?.join('; ') || 'unknown'))
    if (!summary.tests_ok) issues.push('测试失败: ' + (tests?.key_failures?.join(', ') || 'unknown'))
    if (!summary.signal_logic_ok) issues.push('信号逻辑缺失')

    summary.overall_ok = summary.syntax_ok && summary.imports_ok && summary.tests_ok && summary.signal_logic_ok

    log(\`\n========================================\`)
    log(\`  验证结果汇总\`)
    log(\`  语法检查: \${summary.syntax_ok ? '✅' : '❌'}\`)
    log(\`  导入检查: \${summary.imports_ok ? '✅' : '❌'}\`)
    log(\`  单元测试: \${summary.tests_ok ? '✅' : '❌'}\`)
    log(\`  信号逻辑: \${summary.signal_logic_ok ? '✅' : '❌'}\`)
    log(\`  总体: \${summary.overall_ok ? '✅ 全部通过' : '❌ 存在问题'}\`)
    if (summary.issues.length > 0) {
      log(\`  问题列表:\`)
      summary.issues.forEach(i => log(\`    - \${i}\`))
    }
    log(\`========================================\n\`)

    return summary
  }
)

return {
  phases: {
    p1: { fundamental: !!fundamentalResult, etf: !!etfResult, diagnostics: !!diagResult },
    p2: { scoring: !!scoringResult },
    p3: { efficiency: !!efficiencyResult, report: !!reportResult },
    p4: { verification: verifyResults },
  },
  overall_pass: verifyResults?.overall_ok || false,
}
```

---

## 执行说明

### 方式一：Workflow 工具直接运行

将上面的 JavaScript 脚本作为 Workflow 的 `script` 参数传入：

```
使用 Workflow 工具，script 为上述内容
```

### 方式二：分阶段手动执行

如果 Workflow 不可用，可按以下顺序手动触发 Agent：

```
# 第 1 轮（并行）
Agent 1: 执行 Agent-A 的 prompt（基本面管道修复）
Agent 2: 执行 Agent-B 的 prompt（ETF API 修复）
Agent 3: 执行 Agent-C 的 prompt（评分诊断日志）

# 第 2 轮（依赖第 1 轮完成）
Agent 4: 执行 Agent-D 的 prompt（评分模型校准）

# 第 3 轮（并行）
Agent 5: 执行 Agent-E 的 prompt（效率优化）
Agent 6: 执行 Agent-F 的 prompt（报告增强）

# 第 4 轮（验证）
Agent 7: 语法检查 + 导入检查
Agent 8: 单元测试
Agent 9: 信号逻辑验证
```

### 预期产出

| 文件 | 改动类型 | 负责 Agent |
|------|----------|-----------|
| `requirements.txt` | 修改（版本锁定） | A |
| `src/fundamental_analysis.py` | 修改（新增 AKShare 源） | A |
| `src/cache_manager.py` | 修改（TTL + 增量更新） | A + E |
| `src/etf_analyzer.py` | 修改（API 兼容） | B |
| `src/main.py` | 修改（诊断日志 + 数据源 + 线程池 + CI 延迟） | C + E |
| `src/buy_sell_signal.py` | 修改（百分位排名） | D |
| `src/technical_analysis.py` | 修改（MA60 优化） | D |
| `src/scoring.py` | 修改（基线分 + TechnicalSignals 更新） | D |
| `src/config.py` | 微调 | E |
| `src/signal_tracker.py` | **新增**（SQLite 信号历史） | F |
| `src/report_generator.py` | 修改（回顾+排名+概况+热力图+名称统一） | F |
