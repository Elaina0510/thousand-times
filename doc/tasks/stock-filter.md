# stock_filter.py — 股票池筛选模块

> 最小可执行任务列表，用于 Vibe Coding

---

## 任务 1：AKShare 数据获取

- [ ] 创建 `src/stock_filter.py` 文件
- [ ] 实现调用 `ak.stock_zh_a_spot_em()` 获取全市场实时行情
- [ ] 实现调用 `ak.stock_info_a_code_name()` 获取上市日期信息
- [ ] 添加重试装饰器（3次，间隔 2s/4s/8s）
- [ ] 添加随机延迟（1~5秒）

## 任务 2：过滤逻辑

- [ ] 过滤：剔除总市值 < 20亿的股票
- [ ] 过滤：剔除名称含"ST"的股票
- [ ] 过滤：剔除 PE-TTM ≤ 0 的股票
- [ ] 过滤：剔除上市不满3个月的股票
- [ ] 处理个别字段缺失的情况（记录警告日志，跳过该股票）

## 任务 3：排序与截取

- [ ] 按总市值降序排序
- [ ] 取前 1000 条返回

## 任务 4：接口实现

- [ ] 实现 `get_stock_pool(config: FilterConfig) -> pd.DataFrame`
- [ ] 确保返回 DataFrame 包含列：code, name, market_cap, pe_ttm, pb, listing_date, industry

## 任务 5：单元测试

- [ ] 测试正常数据返回正确列和数量
- [ ] 测试结果中无ST股票
- [ ] 测试结果中市值均 ≥ 20亿
- [ ] 测试结果中PE均 > 0
- [ ] 测试AKShare失败时重试3次后抛出异常
