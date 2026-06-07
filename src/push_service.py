"""微信推送模块 — 调用PushPlus发送消息。"""

from __future__ import annotations

import logging

import requests

from utils import retry

logger = logging.getLogger("thousand-times")

# PushPlus API 地址
PUSHPLUS_API = "http://www.pushplus.plus/send"


@retry(max_attempts=3, backoff_factor=2.0)
def push_to_wechat(
    title: str,
    content: str,
    token: str,
    template: str = "markdown",
) -> bool:
    """通过PushPlus推送消息到微信。

    Args:
        title: 消息标题。
        content: 消息内容（Markdown格式）。
        token: PushPlus令牌。
        template: 模板类型。

    Returns:
        是否推送成功。

    Raises:
        ValueError: Token 无效。
        RuntimeError: 推送失败。
    """
    if not token:
        raise ValueError("PushPlus Token 不能为空")

    payload = {
        "token": token,
        "title": title,
        "content": content,
        "template": template,
    }

    try:
        response = requests.post(PUSHPLUS_API, json=payload, timeout=30)
        result = response.json()

        if result.get("code") == 200:
            logger.info(f"推送成功: {title}")
            return True
        else:
            error_msg = result.get("msg", "未知错误")
            logger.error(f"推送失败: {error_msg}")
            return False

    except requests.Timeout as e:
        logger.error("推送超时")
        raise RuntimeError("推送超时") from e
    except requests.RequestException as e:
        logger.error(f"推送请求失败: {e}")
        raise RuntimeError(f"推送请求失败: {e}") from e
