# 千倍系统 V2 重构 - 执行指南

> **使用方式**: 将此文件作为执行prompt，按阶段逐步实施。每完成一个阶段后运行自检，确认无误后再进入下一阶段。

---

## 项目目标

重构A股量化分析系统为五阶段管道架构，解决三大痛点：
1. 评分荒谬（行业趋势维度摆设）
2. 不看大环境（2个布尔信号太粗糙）
3. 无回测验证（信号不一致）

## 执行顺序

```
Phase 1 (基础设施) → Phase 2 (数据采集) → Phase 3 (环境判断)
                                              ↓
                                         Phase 4 (因子库)
                                              ↓
                                         Phase 5 (因子引擎)
                                              ↓
                                         Phase 6 (信号生成)
                                              ↓
                                         Phase 7 (回测引擎)
                                              ↓
                                         Phase 8 (输出集成)
```

**必须按顺序执行，每个Phase依赖前一个Phase的产出。**

---

## 阶段检查清单

### Phase 1: 基础设施
**计划文件**: `doc/plans/2026-06-23-phase1-infrastructure.md`

- [ ] Task 1: 创建目录结构 (pipeline/, data_sources/, factors/)
- [ ] Task 2: 扩展 config.py (RegimeConfig, FactorWeightConfig, SignalConfig, RealtimeConfig, BacktestConfig)
- [ ] Task 3: 实现北向资金数据源 (data_sources/capital_flow.py)
- [ ] Task 4: 实现涨跌停统计数据源 (data_sources/sentiment.py)
- [ ] Task 5: 更新 data_sources 包导出

**自检命令**:
```bash
pytest tests/test_config_v2.py tests/test_data_sources.py -v
mypy --strict src/config.py src/data_sources/
ruff check src/config.py src/data_sources/
```

**自检清单**:
- [ ] 所有测试通过
- [ ] 类型检查通过
- [ ] 代码质量检查通过
- [ ] 配置类可正确实例化: `AppConfig()` 包含所有新字段
- [ ] 数据源函数有异常处理: API失败时返回空数据而非抛异常

---

### Phase 2: 数据采集
**计划文件**: `doc/plans/2026-06-23-phase2-collect.md`

- [ ] Task 1: 定义 DataBundle 和 FundamentalData 数据结构
- [ ] Task 2: 实现指数数据采集 (fetch_index_kline)
- [ ] Task 3: 实现个股数据批量采集 (fetch_stock_kline, fetch_stock_fundamental, batch_fetch_klines)
- [ ] Task 4: 实现 stage_collect 主函数

**自检命令**:
```bash
pytest tests/test_pipeline_collect.py -v
mypy --strict src/pipeline/collect.py
```

**自检清单**:
- [ ] 所有测试通过
- [ ] DataBundle 包含设计文档中所有字段
- [ ] 单只股票获取失败不影响整体流程
- [ ] stage_collect(regime: MarketRegime | None) 签名正确
- [ ] 集成 news_analysis 模块获取新闻数据

---

### Phase 3: 市场环境判断
**计划文件**: `doc/plans/2026-06-23-phase3-regime.md`

- [ ] Task 1: 定义 MarketRegime 和 RegimeVote 数据结构
- [ ] Task 2: 实现趋势信号和成交量信号
- [ ] Task 3: 实现北向资金、涨跌比、估值信号
- [ ] Task 4: 实现投票决策和 judge_market_regime 主函数

**自检命令**:
```bash
pytest tests/test_pipeline_regime.py -v
mypy --strict src/pipeline/regime.py
```

**自检清单**:
- [ ] 所有测试通过
- [ ] 5个信号全部实现: trend, volume, north_flow, advance_decline, valuation
- [ ] 投票决策正确: >=3票bull→牛市, >=3票bear→熊市, 其他→震荡
- [ ] 仓位建议计算正确: 牛市0.7-1.0, 熊市0.0-0.3, 震荡0.5
- [ ] 单个信号失败时返回 neutral，不影响整体
- [ ] 使用 RegimeVote（不是 VoteSignal）

---

### Phase 4: 因子库
**计划文件**: `doc/plans/2026-06-23-phase4-factors-lib.md`

- [ ] Task 1: 实现技术面因子 (factors/technical.py)
- [ ] Task 2: 实现基本面因子 (factors/fundamental.py)
- [ ] Task 3: 实现资金面因子 (factors/capital.py)
- [ ] Task 4: 实现情绪面因子和动量因子
- [ ] Task 5: 更新 factors 包导出

**自检命令**:
```bash
pytest tests/test_factors_technical.py tests/test_factors_fundamental.py tests/test_factors_capital.py tests/test_factors_sentiment.py tests/test_factors_momentum.py -v
mypy --strict src/factors/
ruff check src/factors/
```

**自检清单**:
- [ ] 所有因子测试通过
- [ ] 每个因子返回值范围 0-100
- [ ] 空数据/异常数据返回中性分 50
- [ ] 5个因子模块全部实现: technical, fundamental, capital, sentiment, momentum

---

### Phase 5: 多因子引擎
**计划文件**: `doc/plans/2026-06-23-phase5-factors-engine.md`

- [ ] Task 1: 定义 FactorScores 和百分位排名工具
- [ ] Task 2: 实现 calc_factors 主函数（含截面百分位排名）
- [ ] Task 3: 实现因子有效性检验 (IC/IC_IR)

**自检命令**:
```bash
pytest tests/test_pipeline_factors.py -v
mypy --strict src/pipeline/factors.py
```

**自检清单**:
- [ ] 所有测试通过
- [ ] FactorScores 包含所有字段
- [ ] 百分位排名正确: 最高因子值→100分，最低→0分
- [ ] 权重按配置选择: bull/bear/sideways 三套权重
- [ ] calc_factors(regime_state) 参数正确传递
- [ ] IC/IC_IR 计算正确

---

### Phase 6: 信号生成
**计划文件**: `doc/plans/2026-06-23-phase6-signal.md`

- [ ] Task 1: 定义信号数据结构 (SignalVote, KeyPrices, Signal)
- [ ] Task 2: 实现5个投票信号
- [ ] Task 3: 实现关键价位计算
- [ ] Task 4: 实现 generate_signals 主函数

**自检命令**:
```bash
pytest tests/test_pipeline_signal.py -v
mypy --strict src/pipeline/signal.py
```

**自检清单**:
- [ ] 所有测试通过
- [ ] 5票投票制: >=3 buy且<=1 sell → 买入信号
- [ ] 盈亏比过滤: < 2:1 的买入信号降级为hold
- [ ] 支撑位/压力位基于20日数据计算
- [ ] ATR目标价和止损价计算正确
- [ ] 使用 SignalVote（不是 VoteSignal）

---

### Phase 7: 回测引擎
**计划文件**: `doc/plans/2026-06-23-phase7-backtest.md`

- [ ] Task 1: 定义回测数据结构 (BacktestResult, BacktestTrade)
- [ ] Task 2: 实现统计指标计算 (夏普/最大回撤/卡玛/盈亏比)
- [ ] Task 3: 实现模拟交易和回测主函数

**自检命令**:
```bash
pytest tests/test_backtest_v2.py -v
mypy --strict src/backtest.py
```

**自检清单**:
- [ ] 所有测试通过
- [ ] 夏普比率计算正确 (年化 * sqrt(252))
- [ ] 最大回撤计算正确 (峰值到谷值)
- [ ] 卡玛比率计算正确 (年化收益率/|最大回撤|)
- [ ] 模拟交易含手续费和滑点
- [ ] run_backtest 实现逐日回测循环，复用 pipeline/factors.py + pipeline/signal.py
- [ ] 回测结果包含完整统计指标

---

### Phase 8: 输出与集成
**计划文件**: `doc/plans/2026-06-23-phase8-output-integration.md`

- [ ] Task 1: 实现输出模块 (pipeline/output.py)
- [ ] Task 2: 精简 main.py 为管道编排器
- [ ] Task 3: 实现实时监控模式和命令行入口
- [ ] Task 4: 更新 pipeline 包导出

**自检命令**:
```bash
pytest tests/test_pipeline_output.py -v
python -m src.main --help
mypy --strict src/pipeline/output.py src/main.py
```

**自检清单**:
- [ ] 所有测试通过
- [ ] 命令 `python -m src.main --help` 正常输出
- [ ] V2 管道 5 阶段正确串联
- [ ] 实时监控在非交易时段自动休眠
- [ ] 每阶段独立异常处理，单阶段失败不崩溃
- [ ] 报告包含环境、买入信号、卖出信号三部分
- [ ] 新旧双轨通过 use_v2_pipeline 切换
- [ ] pipeline/__init__.py 正确导出所有模块

---

## 全局自检（所有Phase完成后）

### 功能验证
```bash
# 1. 运行全部测试
pytest tests/ -v

# 2. 类型检查
mypy --strict src/

# 3. 代码质量
ruff check src/

# 4. 验证配置
python -c "from src.config import AppConfig; c = AppConfig(); print('Config OK')"

# 5. 验证管道导入
python -c "from src.pipeline import MarketRegime, DataBundle, FactorScores, Signal, stage_collect, calc_factors, generate_signals, stage_output; print('Pipeline OK')"

# 6. 验证命令行
python -m src.main --help
```

### 集成测试
```bash
# 测试V2管道（使用mock数据）
python -c "
from src.config import AppConfig
from src.main import run_pipeline
config = AppConfig()
config.use_v2_pipeline = True
# run_pipeline(config)  # 取消注释运行实际管道
print('Pipeline integration test passed')
"
```

### 回测验证
```bash
# 运行回测
python -c "
from src.config import AppConfig
from src.backtest import run_backtest
config = AppConfig()
results = run_backtest(config)
for r in results:
    print(f'{r.period}: 胜率={r.win_rate:.1%} 夏普={r.sharpe_ratio:.2f}')
"
```

---

## 错误处理指南

### 常见问题

1. **ImportError: No module named 'xxx'**
   - 检查 `__init__.py` 文件是否存在
   - 检查模块路径是否正确

2. **TypeError: xxx() takes no arguments**
   - 检查函数签名是否与计划文件一致
   - 特别注意 `regime_state` 参数

3. **AttributeError: 'xxx' object has no attribute 'yyy'**
   - 检查 dataclass 字段定义
   - 特别注意 `RegimeVote` vs `SignalVote` 的区分

4. **测试失败但代码看起来正确**
   - 检查 mock 是否正确设置
   - 检查测试数据是否符合预期格式

### 回滚策略

如果某个Phase实施失败：
1. 使用 `git stash` 保存当前进度
2. 回退到上一个成功的commit
3. 分析失败原因
4. 重新实施该Phase

---

## 关键设计决策备忘

1. **命名区分**:
   - `RegimeVote`: 市场环境投票 (bull/bear/neutral)
   - `SignalVote`: 交易信号投票 (buy/sell/neutral)

2. **参数传递**:
   - `calc_factors(data, config, regime_state="sideways")`
   - `stage_collect(config, regime=None)`

3. **百分位排名**:
   - 在 `calc_factors` 中对所有股票做截面排名
   - 使用 `percentile_to_0_100()` 函数

4. **异常处理**:
   - 单只股票失败不影响整体
   - 单个信号失败返回 neutral
   - 每阶段独立 try-except

---

## 执行确认

完成所有Phase后，运行以下命令确认系统正常：

```bash
# 完整验证套件
echo "=== 1. 运行全部测试 ===" && \
pytest tests/ -v && \
echo "=== 2. 类型检查 ===" && \
mypy --strict src/ && \
echo "=== 3. 代码质量 ===" && \
ruff check src/ && \
echo "=== 4. 管道导入验证 ===" && \
python -c "from src.pipeline import *; print('OK')" && \
echo "=== 5. 命令行验证 ===" && \
python -m src.main --help && \
echo "=== 全部验证通过 ==="
```

**预期输出**: 所有测试通过，无类型错误，无代码质量警告，管道正常导入，命令行帮助正常显示。

---

## 下一步

完成实施后：
1. 运行回测验证因子有效性
2. 根据回测结果调整因子权重
3. 切换到V2管道: `config.use_v2_pipeline = True`
4. 观察1-2周确认稳定
5. 删除旧模块: scoring.py, market_regime.py, buy_sell_signal.py
