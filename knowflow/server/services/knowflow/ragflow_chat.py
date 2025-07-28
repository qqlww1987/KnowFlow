import logging
import re
import requests
import json
import threading
import time
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
        # Store session_id for each user (session_id -> ragflow_session_id)
        self.user_sessions = {}
        logging.info("[RAGFlowChat] Plugin initialized")

    def on_handle_context(self, e_context: EventContext):
        context = e_context['context']
        if context.type != ContextType.TEXT:
            return

        user_input = context.content.strip()
        
        # 发送第一条回复
        reply = Reply()
        reply.type = ReplyType.TEXT
        reply.content = "正在查询相关知识库，请稍候..."
        e_context['reply'] = reply
        e_context.action = EventAction.BREAK_PASS
        
        # 创建线程异步处理请求，发送后续消息
        threading.Thread(target=self.send_messages, args=(user_input, e_context['channel'], context)).start()

    def send_messages(self, user_input, channel, context):
        """发送多条消息，包括文本和图片"""
        try:
            # 获取session_id
            session_id = context.get('session_id')
            
            # 获取实际回复
            reply_text = self.get_ragflow_reply(user_input, session_id)
            
            # 提取图片URL
            img_urls = self.extract_image_urls(reply_text)
            
            # 如果有图片URL，从文本中移除
            if img_urls:
                # 移除文本中的img标签
                reply_text = re.sub(r'<img\s+[^>]*src=[\'"][^\'"]+[\'"][^>]*>', '', reply_text)
                
                # 移除文本中的直接图片URL
                for url in img_urls:
                    reply_text = reply_text.replace(url, "")
                
                # 清理文本（移除多余空行等）
                reply_text = re.sub(r'\n\s*\n', '\n\n', reply_text).strip()
            
            # 发送文本回复
            if reply_text:
                reply = Reply()
                reply.type = ReplyType.TEXT
                reply.content = reply_text
                channel.send(reply, context)
                
               
            # 发送图片
            for url in img_urls:
                img_reply = Reply()
                img_reply.type = ReplyType.IMAGE_URL
                img_reply.content = url
                channel.send(img_reply, context)
                
                
        except Exception as e:
            logging.exception("[RAGFlowChat] Error in async processing")
            reply = Reply()
            reply.type = ReplyType.TEXT
            reply.content = f"处理过程中发生错误: {str(e)}"
            channel.send(reply, context)
    
    def extract_image_urls(self, text):
        """从文本中提取图片URL"""
        # 匹配常见的图片URL格式
        url_pattern = r'(https?://\S+\.(jpg|jpeg|png|gif|webp)(\?\S*)?)'
        matches = re.findall(url_pattern, text, re.IGNORECASE)
        # Extract the full URL from each match (first element of each tuple)
        return [match[0] for match in matches]

    def get_or_create_session(self, session_id):
        """获取或创建RAGFlow会话"""
        # 如果已经有该用户的会话，直接返回
        if session_id in self.user_sessions:
            return self.user_sessions[session_id]
        
        # 创建新会话
        dialog_id = self.cfg.get('dialog_id')  
        host_address = self.cfg.get("host_address")
        api_token = self.cfg.get("api_key")
        
        if not dialog_id or not host_address or not api_token:
            logging.error("[RAGFlowChat] Missing required configuration")
            return None
            
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }
        
        # 创建会话的API调用 (根据RAGFlow API文档)
        url = f"https://{host_address}/api/v1/chats/{dialog_id}/sessions"
        payload = {
            "name": f"Session_{session_id}"  # 使用session_id作为会话名称
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload)
            logging.debug(f"[RAGFlowChat] Create session response: {response.text}")
            
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 0:
                    ragflow_session_id = data["data"]["id"]
                    self.user_sessions[session_id] = ragflow_session_id
                    logging.info(f"[RAGFlowChat] Created new session: {ragflow_session_id} for user: {session_id}")
                    return ragflow_session_id
                else:
                    logging.error(f"[RAGFlowChat] Failed to create session: {data.get('message')}")
                    return None
            else:
                logging.error(f"[RAGFlowChat] HTTP error when creating session: {response.status_code}")
                return None
                
        except Exception as e:
            logging.exception("[RAGFlowChat] Exception when creating session")
            return None

    def get_ragflow_reply(self, user_input, session_id):
        # 获取或创建会话
        ragflow_session_id = self.get_or_create_session(session_id)
        if not ragflow_session_id:
            return "无法创建或获取会话，请检查配置。"
            
        dialog_id = self.cfg.get('dialog_id')  
        host_address = self.cfg.get("host_address")
        api_token = self.cfg.get("api_key")
        
        if not host_address or not api_token:
            logging.error("[RAGFlowChat] Missing configuration")
            return "插件配置不完整，请检查配置。"
            
        url = f"https://{host_address}/api/v1/chats/{dialog_id}/completions"

        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }

        payload = {
            "question": user_input,
            "stream": False,
            "session_id": ragflow_session_id  # 使用动态创建的session_id
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

            
                final_answer = re.sub(r"<think>[\s\S]*?</think>", "", raw_answer).strip()
                return final_answer if final_answer else "对不起，未找到有效回答。"

            except ValueError as e:
                logging.error(f"[RAGFlowChat] JSON decode error: {response.text}")
                return "API返回数据解析失败"
                
        except Exception as e:
            logging.exception("[RAGFlowChat] Exception during API request")
            return f"发生错误：{str(e)}"
