# scoring.py — 综合评分模块

> 最小可执行任务列表，用于 Vibe Coding

---

## 任务 1：数据结构定义

- [ ] 创建 `src/scoring.py` 文件
- [ ] 定义 `ScoreResult` dataclass（code, name, is_etf, 各维度评分, total_score, profit_probability, judgment, technical_signals, news_summary）

## 任务 2：综合评分计算

- [ ] 实现 `calc_total_score(technical, fundamental, news, industry, fund_flow, is_etf, config) -> float`
- [ ] 个股公式：technical * 0.40 + fundamental * 0.30 + news * 0.20 + industry * 0.10
- [ ] ETF公式：technical * 0.55 + news * 0.35 + fund_flow * 0.10
- [ ] 评分截断到 [0, 100] 范围

## 任务 3：盈利概率转换

- [ ] 实现 `score_to_probability(score: float) -> float`
- [ ] 使用 sigmoid 函数：P = 1 / (1 + e^(-0.1*(x-50)))
- [ ] 归一化到 0~100% 范围
- [ ] 验证：50分→50%，70分→~88%，30分→~12%

## 任务 4：评分判定

- [ ] 实现 `judge_score(score, high_threshold, low_threshold) -> str`
- [ ] ≥70 → "recommend"
- [ ] 50~69 → "watch"
- [ ] 30~49 → "bearish"
- [ ] <30 → "risk"

## 任务 5：行业趋势评分（仅个股）

- [ ] 实现 `get_industry_trend_score(industry, etf_pool, config) -> float`（0~10分）
- [ ] 维护行业→ETF映射表
- [ ] 获取对应ETF的K线数据，判断均线排列
- [ ] 多头排列 → 8~10分，横盘 → 4~5分，空头 → 0~2分

## 任务 6：单元测试

- [ ] 测试满分场景（各维度满分 → 综合评分 = 100）
- [ ] 测试零分场景（各维度零分 → 综合评分 = 0）
- [ ] 测试评分截断（负分→0，超100→100）
- [ ] 测试概率转换准确性
- [ ] 测试ETF权重正确分配
