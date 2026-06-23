"""Pipeline package - 五阶段管道架构.

阶段:
    1. regime - 市场环境判断
    2. collect - 数据采集
    3. factors - 多因子计算
    4. signal - 信号生成
    5. output - 报告输出
"""

from __future__ import annotations

__all__ = ["regime", "collect", "factors", "signal", "output"]
