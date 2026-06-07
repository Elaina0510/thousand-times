# fundamental_analysis.py — 基本面分析模块

> 最小可执行任务列表，用于 Vibe Coding

---

## 任务 1：数据结构定义

- [ ] 创建 `src/fundamental_analysis.py` 文件
- [ ] 定义 `FundamentalData` dataclass（pe_ttm, pb, market_cap, profit_growth, revenue_growth）

## 任务 2：数据获取

- [ ] 实现调用 `ak.stock_financial_analysis_indicator()` 获取财务指标
- [ ] 实现 `get_fundamental_data(code: str) -> FundamentalData`
- [ ] 添加重试机制（3次）
- [ ] 处理数据缺失（次新股无同比数据时设为 None）

## 任务 3：评分逻辑

- [ ] 实现 `calc_fundamental_score(data, weights) -> float`（0~30分）
- [ ] PE评分：10 < PE < 30 → +8，30 ≤ PE < 60 → +3，PE ≥ 60 → 0
- [ ] PB评分：1 < PB < 5 → +5
- [ ] 净利润评分：>20% → +10，0~20% → +5，<0% → 0
- [ ] 营收评分：>15% → +7，0~15% → +3，<0% → 0

## 任务 4：单元测试

- [ ] 测试 PE=25, PB=3, 净利润+25%, 营收+20% → 评分 = 30
- [ ] 测试 PE=80, PB=10, 净利润-10%, 营收-5% → 评分 = 0
- [ ] 测试数据缺失时评分不崩溃
