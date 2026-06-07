# chart_generator.py — 图表生成模块

> 最小可执行任务列表，用于 Vibe Coding

---

## 任务 1：样式配置

- [ ] 创建 `src/chart_generator.py` 文件
- [ ] 定义 `CHART_STYLE` 配置字典（figsize, 颜色方案, 背景色, 网格色）
- [ ] 配置K线区域与MACD区域比例（3:1）

## 任务 2：K线图绘制

- [ ] 使用 mplfinance 绘制蜡烛图
- [ ] 叠加 MA5（金色）、MA10（蓝色）、MA20（紫色）、MA60（绿色）均线
- [ ] 设置深色背景（#1A1A2E）

## 任务 3：MACD子图绘制

- [ ] 在K线下方绘制MACD子图
- [ ] 绘制 DIF 线（白色）和 DEA 线（金色）
- [ ] 绘制 MACD 柱状图（涨红跌绿）
- [ ] 绘制零轴虚线

## 任务 4：图表生成接口

- [ ] 实现 `generate_chart(code, name, kline, save_path) -> str`
- [ ] 设置标题为 `{name} ({code}) — K线图 + MA均线`
- [ ] 输出 PNG 格式图片
- [ ] 处理中文名称的文件名

## 任务 5：单元测试

- [ ] 测试正常数据生成 PNG 文件（文件大小 > 0）
- [ ] 测试数据不足时不崩溃
- [ ] 测试特殊字符名称的文件名处理
