# RAGFlow Chat Plugin 测试指南

本指南将帮助您测试 dialog_id `f48e23383df611f09c9b26d7d2ef55ce` 的接口功能。

## 🚀 快速开始

### 方法一：快速API测试（推荐）

这是最简单的方法，直接测试您的API接口：

```bash
cd server/services/knowflow
python quick_api_test.py
```

这个脚本会：
- ✅ 测试会话创建
- ✅ 测试单次对话
- ✅ 测试多轮对话
- 📝 显示详细的API响应

### 方法二：完整测试套件

运行包含单元测试和集成测试的完整套件：

```bash
cd server/services/knowflow
python run_tests.py
```

### 方法三：仅运行单元测试

如果您想运行不需要真实API的Mock测试：

```bash
cd server/services/knowflow
python test_ragflow_chat.py
```

## 📋 测试内容

### 🧪 单元测试 (Mock)
- ✅ 配置加载测试
- ✅ 会话创建成功/失败场景
- ✅ 对话回复测试
- ✅ 完整对话流程测试
- ✅ 会话重用功能测试
- ✅ 图片URL提取测试
- ✅ 错误处理测试

### 🌐 集成测试 (真实API)
- ✅ 真实API会话创建
- ✅ 真实API对话测试
- ✅ 多轮对话测试

## 🔧 配置信息

测试使用的配置：
```json
{
    "api_key": "ragflow-M4NzNjYzQwMGJiZTExZjA5MTY1MTZhZG",
    "host_address": "www.knowflowchat.cn",
    "dialog_id": "f48e23383df611f09c9b26d7d2ef55ce"
}
```

## 📊 预期输出

### 成功的测试输出示例：

```
🚀 RAGFlow API 快速测试
📋 测试 Dialog ID: f48e23383df611f09c9b26d7d2ef55ce
🌐 服务器地址: www.knowflowchat.cn
============================================================

🔄 测试会话创建...
状态码: 200
响应数据: {
  "code": 0,
  "data": {
    "id": "session_123456",
    "name": "Test_Session_1703123456",
    "chat_id": "f48e23383df611f09c9b26d7d2ef55ce"
  }
}
✅ 会话创建成功! Session ID: session_123456

============================================================

💬 测试对话完成: 你好，请简单介绍一下自己
状态码: 200
✅ 获取回复成功!
📝 回复内容: 你好！我是RAGFlow助手...

============================================================

📊 测试结果总结:
  会话创建: ✅ 成功
  单次对话: ✅ 成功
  多轮对话: ✅ 成功

🎉 所有API测试通过！接口功能正常。
```

## 🔍 故障排除

### 常见错误及解决方案：

1. **401 Unauthorized**
   - 检查API密钥是否正确
   - 确认API密钥未过期

2. **404 Not Found**
   - 验证 dialog_id 是否正确
   - 检查服务器地址是否正确

3. **网络连接错误**
   - 检查网络连接
   - 确认服务器地址可访问

4. **依赖缺失**
   ```bash
   pip install requests
   ```

## 📝 自定义测试

您可以修改 `quick_api_test.py` 中的测试问题：

```python
# 在 test_multiple_conversations 函数中修改
questions = [
    "你的自定义问题1",
    "你的自定义问题2",
    "你的自定义问题3"
]
```

## 🔗 API端点

测试脚本使用的API端点：

1. **创建会话**
   ```
   POST https://www.knowflowchat.cn/api/v1/chats/f48e23383df611f09c9b26d7d2ef55ce/sessions
   ```

2. **对话完成**
   ```
   POST https://www.knowflowchat.cn/api/v1/chats/f48e23383df611f09c9b26d7d2ef55ce/completions
   ```

## 📞 支持

如果测试过程中遇到问题，请检查：
- 网络连接状态
- API密钥有效性
- dialog_id 是否正确
- 服务器是否正常运行 