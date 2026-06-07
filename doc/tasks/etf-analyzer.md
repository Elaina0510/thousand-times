# etf_analyzer.py — ETF分析模块

> 最小可执行任务列表，用于 Vibe Coding

---

## 任务 1：数据结构定义

- [ ] 创建 `src/etf_analyzer.py` 文件
- [ ] 定义 `EtfInfo` dataclass（code, name, current_price, change_pct）

## 任务 2：ETF行情获取

- [ ] 实现调用 `ak.fund_etf_hist_em()` 获取ETF历史行情
- [ ] 实现 `get_etf_pool(config: AppConfig) -> list[EtfInfo]`
- [ ] 遍历 ETF 池，获取每只ETF的当前行情
- [ ] 添加重试机制和随机延迟

## 任务 3：资金流向评分

- [ ] 实现调用 `ak.fund_etf_fund_daily_em()` 获取ETF份额数据
- [ ] 实现 `calc_fund_flow_score(share_changes: list[float]) -> float`
- [ ] 评分规则：连续增长 8~10 分
- [ ] 评分规则：总体增长但有波动 4~7 分
- [ ] 评分规则：基本持平 3 分
- [ ] 评分规则：连续减少 0~2 分
- [ ] 实现 `get_etf_fund_flow(code: str, days: int = 5) -> float`

## 任务 4：单元测试

- [ ] 测试份额连续增长评分在 8~10 范围
- [ ] 测试份额连续减少评分在 0~2 范围
- [ ] 测试份额持平评分 = 3
- [ ] 测试数据不足时使用可用数据计算
