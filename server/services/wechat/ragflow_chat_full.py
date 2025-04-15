import logging
import re
import requests
import json
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from plugins import Plugin, register
from plugins.event import Event, EventContext, EventAction

@register(name="RAGFlowChat", desc="Use RAGFlow API to chat", version="1.0", author="Your Name")
class RAGFlowChat(Plugin):
    def __init__(self):
        super().__init__()
        self.cfg = self.load_config()
        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        self.conversations = {}
        logging.info("[RAGFlowChat] Plugin initialized")

    def on_handle_context(self, e_context: EventContext):
        context = e_context['context']
        if context.type != ContextType.TEXT:
            return

        user_input = context.content.strip()
        session_id = context['session_id']

        reply_text = self.get_ragflow_reply(user_input, session_id)
        if reply_text:
            reply = Reply()
            reply.type = ReplyType.TEXT
            reply.content = reply_text
            e_context['reply'] = reply
            e_context.action = EventAction.BREAK_PASS
        else:
            e_context.action = EventAction.CONTINUE

    def get_ragflow_reply(self, user_input, session_id):
        url = "https://www.knowflowchat.cn/api/v1/chats/0ae81e340faf11f0bc8916ade234bc5a/completions"
        api_token = self.cfg.get("api_key")
        
        if not api_token:
            logging.error("[RAGFlowChat] Missing API token")
            return "插件配置缺少 API Token，请检查配置。"

        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }

        payload = {
            "question": user_input,
            "stream": False,
            "session_id": '7d099d6ab46a4a409e5e9d7e9b86c117'
        }

        try:
            response = requests.post(url, headers=headers, json=payload)
            logging.debug(f"[RAGFlowChat] Completion response: {response.text}")
            
            if response.status_code != 200:
                logging.error(f"[RAGFlowChat] HTTP error: {response.status_code}")
                return f"API 请求失败，状态码：{response.status_code}"
            
            try:
                data = response.json()
                if not data:
                    logging.error("[RAGFlowChat] Empty response data")
                    return "API返回了空数据"
                
                # 检查返回码
                if data.get("code") != 0:
                    logging.error(f"[RAGFlowChat] API returned error code: {data.get('code')}")
                    return "API返回错误状态码"
                
                # 直接获取answer字段
                answer_data = data.get("data", {})
                raw_answer = answer_data.get("answer", "")
                
                if not raw_answer:
                    logging.error(f"[RAGFlowChat] No answer in response: {data}")
                    return "API返回数据格式异常: 缺少answer字段"

                #
                final_answer = re.sub(r"<think>[\s\S]*?</think>", "", raw_answer).strip()
                return final_answer if final_answer else "对不起，未找到有效回答。"

            except ValueError as e:
                logging.error(f"[RAGFlowChat] JSON decode error: {response.text}")
                return "API返回数据解析失败"
                
        except Exception as e:
            logging.exception("[RAGFlowChat] Exception during API request")
            return f"发生错误：{str(e)}"
