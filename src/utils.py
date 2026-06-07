"""通用工具模块 — 重试装饰器、随机延迟、日志配置。"""

import functools
import logging
import random
import time
from collections.abc import Callable
from typing import Any, TypeVar

logger = logging.getLogger("thousand-times")

F = TypeVar("F", bound=Callable[..., Any])


def retry(max_attempts: int = 3, backoff_factor: float = 2.0) -> Callable[[F], F]:
    """通用重试装饰器，支持指数退避。

    Args:
        max_attempts: 最大重试次数。
        backoff_factor: 退避因子，等待时间 = backoff_factor ** attempt。

    Returns:
        装饰后的函数。
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        raise
                    wait = backoff_factor ** attempt
                    logger.warning(f"{func.__name__} 第{attempt + 1}次失败，{wait}秒后重试: {e}")
                    time.sleep(wait)
            return None  # unreachable, but satisfies type checker

        return wrapper  # type: ignore[return-value]

    return decorator


def random_delay(min_sec: float = 1.0, max_sec: float = 5.0) -> None:
    """随机延迟，避免触发API频率限制。

    Args:
        min_sec: 最小延迟秒数。
        max_sec: 最大延迟秒数。
    """
    delay = random.uniform(min_sec, max_sec)
    time.sleep(delay)
