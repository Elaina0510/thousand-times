# news_analysis.py — 政策新闻分析模块

> 最小可执行任务列表，用于 Vibe Coding

---

## 任务 1：数据结构定义

- [ ] 创建 `src/news_analysis.py` 文件
- [ ] 定义 `NewsItem` dataclass（title, source, url, publish_time, content）
- [ ] 定义 `PolicyImpact` dataclass（news_title, affected_industries, impact_direction, impact_degree, impact_score, summary）

## 任务 2：新闻抓取

- [ ] 实现调用 AKShare 接口获取当日财经新闻
- [ ] 实现 `fetch_news() -> list[NewsItem]`
- [ ] 添加重试机制和随机延迟

## 任务 3：可信度过滤

- [ ] 实现 `filter_by_credibility(news) -> list[NewsItem]`
- [ ] 定义来源白名单（新浪财经、东方财富、同花顺）
- [ ] 过滤低可信来源（自媒体、论坛传闻）

## 任务 4：LLM 政策分析

- [ ] 实现 `analyze_policy_impact(news, llm_config) -> list[PolicyImpact]`
- [ ] 编写 LLM Prompt（要求返回JSON格式：行业、方向、程度、评分、摘要）
- [ ] 解析 LLM 返回的 JSON 结果
- [ ] 处理 LLM 返回格式异常（降级为中性评分 +5）
- [ ] 添加重试机制（2次）

## 任务 5：行业影响汇总

- [ ] 实现 `get_industry_impact_score(industry, impacts) -> float`（-20 ~ +20）
- [ ] 多条新闻同一行业时正确累加/合并

## 任务 6：单元测试

- [ ] 测试模拟LLM返回的解析结果
- [ ] 测试LLM返回异常格式时降级为中性评分
- [ ] 测试新闻抓取失败时返回空列表
- [ ] 测试多条新闻同一行业的评分合并
