# technical_analysis.py — 技术指标计算模块

> 最小可执行任务列表，用于 Vibe Coding

---

## 任务 1：数据结构定义

- [ ] 创建 `src/technical_analysis.py` 文件
- [ ] 定义 `TechnicalSignals` dataclass（13个布尔信号字段）
- [ ] 定义 `KlineData` dataclass（日期、OHLCV、MA5/10/20/60、DIF/DEA/MACD柱）

## 任务 2：K线数据获取

- [ ] 实现调用 `ak.stock_zh_a_hist()` 获取个股历史行情（60日）
- [ ] 实现调用 `ak.fund_etf_hist_em()` 获取ETF历史行情（60日）
- [ ] 实现 `get_kline_data(code, days=60, is_etf=False) -> KlineData`
- [ ] 添加重试机制和随机延迟

## 任务 3：技术指标计算

- [ ] 实现 MA 计算：MA5、MA10、MA20、MA60
- [ ] 实现 EMA 计算（MACD前置）
- [ ] 实现 MACD 计算：DIF = EMA(12) - EMA(26)，DEA = DIF的EMA(9)，MACD柱 = (DIF-DEA)*2
- [ ] 实现量比计算：当日成交量 / 近5日平均成交量

## 任务 4：信号判定

- [ ] 判定 MA5/10 金叉（近3日内 MA5 从 < MA10 变为 > MA10）
- [ ] 判定 MA5/10 死叉（近3日内 MA5 从 > MA10 变为 < MA10）
- [ ] 判定 MA20/60 金叉（近5日内发生）
- [ ] 判定多头排列（MA5 > MA10 > MA20 > MA60）
- [ ] 判定股价站上 MA20（收盘价 > MA20）
- [ ] 判定 MACD 金叉/死叉（近3日内）
- [ ] 判定零轴上方金叉（金叉且 DIF > 0 且 DEA > 0）
- [ ] 判定 MACD 底背离（近10日内股价新低但MACD不新低）
- [ ] 判定放量上涨（涨幅 > 0 且量比 > 1.5）
- [ ] 判定放量下跌（跌幅 > 2% 且量比 > 2.0）
- [ ] 判定天量见天价（成交量60日新高且股价高位）
- [ ] 判定缩量回调到位（回调至MA20附近±2%且量比 < 0.7）

## 任务 5：评分计算

- [ ] 实现 `calc_technical_signals(kline: KlineData) -> TechnicalSignals`
- [ ] 实现 `calc_technical_score(signals, weights) -> float`（0~40分，负分截断到0）

## 任务 6：单元测试

- [ ] 测试已知K线数据的MA/MACD计算结果
- [ ] 测试金叉/死叉场景的信号判定
- [ ] 测试数据不足60日时的降级处理
- [ ] 测试ETF与个股使用同一接口
