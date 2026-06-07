# config.py — 配置管理模块

> 最小可执行任务列表，用于 Vibe Coding

---

## 任务 1：定义数据结构

- [ ] 创建 `src/config.py` 文件
- [ ] 定义 `TechnicalWeightConfig` dataclass（技术指标评分权重，含13个字段）
- [ ] 定义 `FundamentalWeightConfig` dataclass（基本面评分权重，含10个字段）
- [ ] 定义 `NewsWeightConfig` dataclass（政策新闻评分权重，含5个字段）
- [ ] 定义 `IndustryTrendWeightConfig` dataclass（行业趋势权重，含3个字段）
- [ ] 定义 `EtfFundFlowWeightConfig` dataclass（ETF资金流向权重，含4个字段）
- [ ] 定义 `ScoreWeightConfig` dataclass（综合评分维度权重，含7个字段）
- [ ] 定义 `FilterConfig` dataclass（股票池筛选配置，含3个字段）
- [ ] 定义 `AppConfig` dataclass（应用总配置，聚合所有子配置）

## 任务 2：ETF池默认配置

- [ ] 定义 `DEFAULT_ETF_POOL` 常量列表（11只ETF：4只宽基 + 7只行业）

## 任务 3：配置加载函数

- [ ] 实现 `load_config() -> AppConfig` 函数
- [ ] 从环境变量读取 `PUSHPLUS_TOKEN`、`LLM_API_URL`、`LLM_API_KEY`
- [ ] 使用默认值填充所有配置字段
- [ ] 返回完整的 `AppConfig` 实例

## 任务 4：单元测试

- [ ] 验证默认配置完整性（所有必要字段均有值）
- [ ] 验证个股四项权重之和 = 1.0
- [ ] 验证ETF三项权重之和 = 1.0
- [ ] 验证环境变量覆盖逻辑
