# 基础设施 — 项目初始化与CI/CD

> 最小可执行任务列表，用于 Vibe Coding

---

## 任务 1：项目初始化

- [ ] 创建 `requirements.txt`（akshare, pandas, numpy, mplfinance, matplotlib, requests, beautifulsoup4）
- [ ] 创建 `src/__init__.py`
- [ ] 创建 `README.md`（项目说明、使用方法）

## 任务 2：通用工具

- [ ] 实现重试装饰器 `retry(max_attempts=3, backoff_factor=2)`
- [ ] 实现随机延迟函数 `random_delay(min_sec=1.0, max_sec=5.0)`
- [ ] 配置统一日志格式

## 任务 3：GitHub Actions

- [ ] 创建 `.github/workflows/daily_analysis.yml`
- [ ] 配置定时调度（工作日 UTC 04:00 = 北京时间 12:00）
- [ ] 配置手动触发（workflow_dispatch）
- [ ] 配置 Python 3.10 环境
- [ ] 配置依赖安装步骤
- [ ] 配置环境变量（PUSHPLUS_TOKEN, LLM_API_URL, LLM_API_KEY from secrets）
- [ ] 配置失败时上传日志

## 任务 4：目录结构

- [ ] 创建 `charts/` 目录（图表输出）
- [ ] 创建 `logs/` 目录（日志输出）
- [ ] 创建 `.gitignore`（忽略 charts/, logs/, __pycache__/）
