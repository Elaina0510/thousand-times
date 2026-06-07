# 总体进度

> A股智能选股分析与推送系统 — 模块完成状态

---

## 模块清单

- [x] [config.py](config.md) — 配置管理（数据结构、ETF池、配置加载）
- [x] [stock_filter.py](stock-filter.md) — 股票池筛选（AKShare数据获取、过滤、排序）
- [x] [etf_analyzer.py](etf-analyzer.md) — ETF分析（行情获取、资金流向评分）
- [x] [technical_analysis.py](technical-analysis.md) — 技术指标计算（MA/MACD/成交量信号）
- [x] [fundamental_analysis.py](fundamental-analysis.md) — 基本面分析（PE/PB/净利润/营收）
- [x] [news_analysis.py](news-analysis.md) — 政策新闻分析（新闻抓取、LLM分析、行业关联）
- [x] [scoring.py](scoring.md) — 综合评分（权重计算、概率转换、判定）
- [x] [chart_generator.py](chart-generator.md) — 图表生成（K线+MACD图表）
- [x] [report_generator.py](report-generator.md) — 报告生成（推送文本组装）
- [x] [push_service.py](push-service.md) — 微信推送（PushPlus API对接）
- [x] [main.py](main.md) — 主程序（流水线编排、异常隔离）
- [x] [基础设施](infra.md) — 项目初始化、通用工具、CI/CD

---

## 开发顺序建议

```
阶段1：基础（无外部依赖，可独立测试）
  config.py → scoring.py → report_generator.py

阶段2：数据层（依赖 AKShare）
  stock_filter.py → technical_analysis.py → fundamental_analysis.py

阶段3：分析层（依赖 LLM API）
  etf_analyzer.py → news_analysis.py

阶段4：输出层
  chart_generator.py → push_service.py

阶段5：集成
  main.py → 基础设施（CI/CD）
```

---

## 统计

| 状态 | 数量 |
|------|------|
| 未开始 | 0 |
| 进行中 | 0 |
| 已完成 | 12 |
