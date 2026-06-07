"""push_service.py 单元测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from push_service import push_to_wechat


class TestPushToWechat:
    """微信推送测试。"""

    @patch("push_service.requests.post")
    def test_success(self, mock_post: MagicMock) -> None:
        """正常推送返回 True。"""
        mock_post.return_value = MagicMock(
            json=lambda: {"code": 200, "msg": "请求成功"}
        )

        result = push_to_wechat("测试标题", "测试内容", "test-token")

        assert result is True

    @patch("push_service.requests.post")
    def test_failure(self, mock_post: MagicMock) -> None:
        """API返回错误返回 False。"""
        mock_post.return_value = MagicMock(
            json=lambda: {"code": 400, "msg": "Token无效"}
        )

        result = push_to_wechat("测试标题", "测试内容", "invalid-token")

        assert result is False

    def test_empty_token(self) -> None:
        """Token为空抛出异常。"""
        with pytest.raises(ValueError, match="Token 不能为空"):
            push_to_wechat("测试标题", "测试内容", "")

    @patch("push_service.requests.post")
    def test_timeout(self, mock_post: MagicMock) -> None:
        """网络超时抛出异常。"""
        import requests
        mock_post.side_effect = requests.Timeout("超时")

        with pytest.raises(RuntimeError, match="推送超时"):
            push_to_wechat("测试标题", "测试内容", "test-token")

    @patch("push_service.requests.post")
    def test_request_error(self, mock_post: MagicMock) -> None:
        """请求错误抛出异常。"""
        import requests
        mock_post.side_effect = requests.RequestException("连接失败")

        with pytest.raises(RuntimeError, match="推送请求失败"):
            push_to_wechat("测试标题", "测试内容", "test-token")
