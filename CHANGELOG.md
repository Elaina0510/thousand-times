# 更新日志

## 2026-06-23

### 兼容性与降级 (Phase 13)

- **BaoStock 可用性检测**：`main.py` 启动时检测 BaoStock 是否可用，不可用时自动降级到 Ashare/AKShare 数据源，无需手动切换
- **K线数据降级**：当 BaoStock 不可用时，K 线批量获取自动降级为逐只获取模式
- **测试 Mock 基础设施**：新增 `tests/mocks.py`，提供完整的数据工厂函数和 Mock 模块注册，支持在无网络环境下运行核心流程
  - `make_stock_pool_df()` — 生成测试用股票池
  - `make_kline_data()` / `make_kline_dataframe()` — 生成 K 线数据
  - `make_fundamental_data()` — 生成基本面数据
  - `make_policy_impact()` — 生成政策影响数据
  - `register_all_mocks()` — 注册所有外部依赖 Mock
  - `run_main_mocked()` — 在完全 Mock 环境中运行 main()

### 场景测试 (Phase 13)

- **14 种典型场景**：新增 `tests/scenario_14stocks.py`，覆盖 14 种股票场景共 30 个测试用例
  - 场景 1~4：各类推荐/风险股票（强烈买入、买入、回避、基本面超强）
  - 场景 5~8：边界条件（零分、满分、缺失数据、冲突信号）
  - 场景 9~11：ETF 场景（强烈买入、中性、全看空）
  - 场景 12~14：综合场景（新闻利好推动、新闻利空拖累、行业趋势匹配）
- **边界测试补充**：新增 12 个评分边界测试
  - 评分阈值精确边界（75/60/45 分）
  - 盈利概率单调性验证
  - 负新闻评分截断
  - fund_flow=None 处理
  - ETF 负新闻处理

### 测试结果

- 总测试数：226 个（新增 42 个）
- 全部通过 ✅
