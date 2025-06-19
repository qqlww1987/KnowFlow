# RAGFlow Chat 插件用于 ChatGPT-on-WeChat
本文件夹包含 ragflow_chat 插件的源代码，该插件扩展了 RAGFlow API 的核心功能，支持基于检索增强生成（RAG）的对话交互。该插件可无缝集成到 ChatGPT-on-WeChat 项目中，使微信及其他平台能够在聊天交互中利用 RAGFlow 提供的知识检索能力。

### 功能特性
- 对话交互 ：将微信的对话界面与强大的 RAG（检索增强生成）能力结合。
- 基于知识的回复 ：通过检索外部知识源中的相关数据并将其融入聊天回复，丰富对话内容。
- 多平台支持 ：可在微信、企业微信以及 ChatGPT-on-WeChat 框架支持的多种平台上运行。

### 插件与 ChatGPT-on-WeChat 配置说明
注意 ：本集成涉及两个不同的配置文件——一个用于 ChatGPT-on-WeChat 核心项目，另一个专用于 ragflow_chat 插件。请务必正确配置两者，以确保顺利集成。
 ChatGPT-on-WeChat 根配置（ config.json ）
该文件位于 ChatGPT-on-WeChat 项目的根目录，用于定义通信渠道和整体行为。例如，它负责配置微信、企业微信以及飞书、钉钉等服务。

微信渠道的 config.json 示例：

```json
{
  "channel_type": "wechatmp",
  "wechatmp_app_id": "YOUR_APP_ID",
  "wechatmp_app_secret": "YOUR_APP_SECRET",
  "wechatmp_token": "YOUR_TOKEN",
  "wechatmp_port": 80,
  ...
}
 ```

该文件也可修改以支持其他通信平台，例如：

- 个人微信 （ channel_type: wx ）
- 微信公众号 （ wechatmp 或 wechatmp_service ）
- 企业微信 （ wechatcom_app ）
- 飞书 （ feishu ）
- 钉钉 （ dingtalk ）
详细配置选项请参见官方 LinkAI 文档 。
 RAGFlow Chat 插件配置（ plugins/ragflow_chat/config.json ）
该配置文件专用于 ragflow_chat 插件，用于设置与 RAGFlow 服务器的通信。请确保你的 RAGFlow 服务器已启动，并将插件的 config.json 文件更新为你的服务器信息：

ragflow_chat 的 config.json 示例：

```json
{
    "api_key": "your-ragflow-api-key",
    "host_address": "your-ragflow-host.com",
    "dialog_id": "your-dialog-id"
}
 ```

该文件必须正确指向你的 RAGFlow 实例，`api_key` 和 `host_address` 字段需正确设置。 `dialog_id` 可在 RAGFlow 前端页面 url 或者调试模式中获取。
 

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



### 使用要求
在使用本插件前，请确保：

1. 你已安装并配置好 `ChatGPT-on-WeChat`。
2. 将 knowflow 文件夹放到 `chatgpt-on-wechat/plugins/` 目录下
3. 在 knowflow 目录下运行 `pip instal -r requirement.txt`
4. 重启 ChatGPT-on-WeChat 服务
5. 你已部署并运行 RAGFlow 服务器
请确保上述两个 config.json 文件（ChatGPT-on-WeChat 和 RAGFlow Chat 插件）均已按示例正确配置。