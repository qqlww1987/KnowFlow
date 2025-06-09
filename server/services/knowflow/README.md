# RAGFlow Chat 插件

本插件集成 RAGFlow API，利用知识库提供智能对话回复功能。

## 功能特性

- **自动会话管理**: 为每个用户自动创建和管理 RAGFlow 会话
- **动态会话创建**: 使用上下文中的 `session_id` 创建唯一的 RAGFlow 会话
- **图片支持**: 从 RAGFlow 响应中提取并发送图片
- **异步处理**: 非阻塞消息处理，提供初始加载响应

## 配置说明

通过编辑 `config.json` 配置插件：

```json
{
    "api_key": "your-ragflow-api-key",
    "host_address": "your-ragflow-host.com",
    "dialog_id": "your-dialog-id"
}
```

### 配置参数

- `api_key`: 您的 RAGFlow API 密钥（必需）
- `host_address`: RAGFlow 服务器地址（必需）  
- `dialog_id`: RAGFlow 对话/助手 ID（必需）

## 工作原理

1. **会话管理**: 当用户发送第一条消息时，插件会使用用户的 `session_id` 自动创建一个新的 RAGFlow 会话
2. **会话缓存**: 会话按用户缓存，避免为后续消息重复创建会话
3. **API 集成**: 使用 RAGFlow 基于会话的聊天完成 API
4. **响应处理**: 处理来自 RAGFlow 的文本和图片响应

## 使用的 API 端点

基于 [RAGFlow HTTP API 参考文档](https://ragflow.io/docs/dev/http_api_reference)：

- `POST /api/v1/chats/{dialog_id}/sessions` - 创建会话
- `POST /api/v1/chats/{dialog_id}/completions` - 获取聊天完成

## 会话流程

```
用户消息 → 从上下文获取 session_id → 
检查 RAGFlow 会话是否存在 → 
如果不存在，通过 API 创建新会话 → 
向 RAGFlow 发送消息 → 
处理响应（文本 + 图片） → 
发送回复给用户
```

## 与之前版本的变化

- **移除硬编码的 `conversation_id`**: 不再需要手动配置会话
- **添加自动会话创建**: 按需为用户创建会话
- **改进用户隔离**: 每个用户都有自己的 RAGFlow 会话
- **更好的错误处理**: 为会话创建失败提供更详细的错误信息

## 错误处理

插件处理各种错误场景：
- 配置参数缺失
- 会话创建失败
- API 请求失败
- 响应解析错误

所有错误都会被记录，并返回用户友好的错误消息。

## 测试工具

本插件提供了完整的测试套件：

### 快速 API 测试
```bash
python quick_api_test.py
```
- 测试基本连接
- 验证会话创建
- 测试多轮对话

### 单元测试
```bash
python test_ragflow_chat_simple.py
```
- Mock 测试会话创建
- 测试配置加载
- 验证错误处理

### 配置更新工具
```bash
python update_config.py
```
- 交互式配置更新
- API 密钥管理
- 连接测试

## 技术实现

### 核心方法

1. **`get_or_create_session(session_id)`**
   - 检查会话缓存
   - 创建新的 RAGFlow 会话
   - 缓存会话映射

2. **`get_ragflow_reply(question, session_id)`**
   - 获取或创建会话
   - 发送问题到 RAGFlow
   - 处理响应和图片

### 会话缓存机制

使用 `user_sessions` 字典维护 `session_id` 到 `ragflow_session_id` 的映射：

```python
user_sessions = {
    "user_session_123": "ragflow_session_abc",
    "user_session_456": "ragflow_session_def"
}
```

这确保：
- 每个用户会话对应一个 RAGFlow 会话
- 避免重复创建会话
- 支持多轮对话连续性

## 最佳实践

1. **定期检查 API 密钥有效性**
2. **监控会话创建成功率**
3. **定期清理过期会话缓存**
4. **配置适当的请求超时时间**

## 故障排除

### 常见问题

1. **401 Unauthorized**
   - 检查 API 密钥是否正确
   - 确认 API 密钥未过期

2. **404 Not Found**
   - 验证 dialog_id 是否正确
   - 检查服务器地址是否正确

3. **连接超时**
   - 检查网络连接
   - 增加请求超时时间

4. **会话创建失败**
   - 检查 RAGFlow 服务状态
   - 验证 dialog_id 权限

更多问题请参考 `TEST_GUIDE.md` 文档。