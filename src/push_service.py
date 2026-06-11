"""微信推送模块 — 调用PushPlus发送消息。"""

from __future__ import annotations

import logging

import requests

from utils import retry

logger = logging.getLogger("thousand-times")

# PushPlus API 地址
PUSHPLUS_API = "https://www.pushplus.plus/send"


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

    # PushPlus 内容长度限制（约 20000 字符）
    MAX_CONTENT_LENGTH = 19000
    if len(content) > MAX_CONTENT_LENGTH:
        logger.warning(f"推送内容过长（{len(content)} 字符），将截断至 {MAX_CONTENT_LENGTH} 字符")
        content = content[:MAX_CONTENT_LENGTH] + "\n\n... (内容过长已截断)"

    payload = {
        "token": token,
        "title": title,
        "content": content,
        "template": template,
    }

    try:
        # 记录请求信息（不包含 token）
        logger.info(f"PushPlus 请求: title={title}, template={template}, content_length={len(content)}")

        response = requests.post(PUSHPLUS_API, json=payload, timeout=30)
        result = response.json()

        logger.info(f"PushPlus 响应: code={result.get('code')}, msg={result.get('msg')}")

        if result.get("code") == 200:
            logger.info(f"推送成功: {title}")
            return True
        else:
            error_msg = result.get("msg", "未知错误")
            logger.error(f"推送失败: {error_msg} (code={result.get('code')})")

            # 详细的错误提示
            if result.get("code") == 999:
                logger.error("错误码 999 可能原因:")
                logger.error("1. Token 无效或过期，请登录 https://www.pushplus.plus/ 检查")
                logger.error("2. 推送内容过长（当前长度: {} 字符）".format(len(content)))
                logger.error("3. PushPlus 服务端临时故障")
            elif "token" in error_msg.lower() or result.get("code") in [400, 401]:
                logger.error("请检查 PUSHPLUS_TOKEN 是否正确，可在 https://www.pushplus.plus/ 获取")

            return False

    except requests.Timeout as e:
        logger.error("推送超时")
        raise RuntimeError("推送超时") from e
    except requests.RequestException as e:
        logger.error(f"推送请求失败: {e}")
        raise RuntimeError(f"推送请求失败: {e}") from e
