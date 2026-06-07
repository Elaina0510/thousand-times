# push_service.py — 微信推送模块

> 最小可执行任务列表，用于 Vibe Coding

---

## 任务 1：PushPlus API 对接

- [ ] 创建 `src/push_service.py` 文件
- [ ] 定义 `PUSHPLUS_API` 常量（http://www.pushplus.plus/send）
- [ ] 实现 `push_to_wechat(title, content, token, template="markdown") -> bool`

## 任务 2：请求实现

- [ ] 构建请求 payload（token, title, content, template）
- [ ] 使用 requests.post 发送请求（timeout=30）
- [ ] 解析返回结果，判断 code == 200 为成功

## 任务 3：异常处理

- [ ] 网络超时重试2次
- [ ] API返回错误时记录错误码和消息，返回 False
- [ ] Token无效时抛出明确异常

## 任务 4：单元测试

- [ ] 测试正常推送返回 True
- [ ] 测试 Token 无效返回 False
- [ ] 测试网络超时重试后返回 False
