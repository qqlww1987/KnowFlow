#!/usr/bin/env python3
"""
简化版 RAGFlow Chat Plugin 测试
不依赖于 bridge 模块的独立测试
"""

import unittest
import sys
import os
import json
import requests
from unittest.mock import Mock, patch, MagicMock

class MockRAGFlowChat:
    """模拟 RAGFlowChat 类，不依赖 bridge 模块"""
    
    def __init__(self):
        self.cfg = {}
        self.user_sessions = {}
        
    def load_config(self):
        """加载配置"""
        try:
            config_path = os.path.join(os.path.dirname(__file__), 'config.json')
            with open(config_path, 'r', encoding='utf-8') as f:
                self.cfg = json.load(f)
            return True
        except Exception as e:
            print(f"配置加载失败: {e}")
            return False
    
    def get_or_create_session(self, session_id):
        """获取或创建会话"""
        if not self.cfg:
            self.load_config()
            
        if not all(key in self.cfg for key in ["api_key", "host_address", "dialog_id"]):
            print("配置信息不完整")
            return None
        
        # 检查是否已有会话
        if session_id in self.user_sessions:
            return self.user_sessions[session_id]
        
        # 创建新会话
        try:
            url = f"http://{self.cfg['host_address']}/api/v1/chats/{self.cfg['dialog_id']}/sessions"
            headers = {
                "Authorization": f"Bearer {self.cfg['api_key']}",
                "Content-Type": "application/json"
            }
            payload = {"name": f"Session_{session_id}"}
            
            response = requests.post(url, headers=headers, json=payload, timeout=30, verify=False)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 0:
                    ragflow_session_id = data["data"]["id"]
                    self.user_sessions[session_id] = ragflow_session_id
                    return ragflow_session_id
                    
        except Exception as e:
            print(f"创建会话失败: {e}")
            
        return None
    
    def get_ragflow_reply(self, question, session_id):
        """获取 RAGFlow 回复"""
        if not self.cfg:
            self.load_config()
            
        # 获取或创建会话
        ragflow_session_id = self.get_or_create_session(session_id)
        if not ragflow_session_id:
            return None
            
        try:
            url = f"http://{self.cfg['host_address']}/api/v1/chats/{self.cfg['dialog_id']}/completions"
            headers = {
                "Authorization": f"Bearer {self.cfg['api_key']}",
                "Content-Type": "application/json"
            }
            payload = {
                "question": question,
                "stream": False,
                "session_id": ragflow_session_id
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=60, verify=False)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 0:
                    return data["data"].get("answer", "")
                    
        except Exception as e:
            print(f"获取回复失败: {e}")
            
        return None

class TestRAGFlowChatSimple(unittest.TestCase):
    """简化版测试类"""
    
    def setUp(self):
        """设置测试环境"""
        self.plugin = MockRAGFlowChat()
        self.test_session_id = "test_user_12345"
        self.test_question = "你好，请介绍一下自己"

    def test_config_loading(self):
        """测试配置加载"""
        result = self.plugin.load_config()
        self.assertTrue(result)
        self.assertIsNotNone(self.plugin.cfg)
        self.assertIn("api_key", self.plugin.cfg)
        self.assertIn("host_address", self.plugin.cfg)
        self.assertIn("dialog_id", self.plugin.cfg)

    @patch('requests.post')
    def test_session_creation_success(self, mock_post):
        """测试会话创建成功"""
        # 设置配置
        self.plugin.cfg = {
            "api_key": "ragflow-IyZjQ3NWI4M2QwOTExZjA4MDMwMGE5NT",
            "host_address": "154.219.102.235",
            "dialog_id": "f48e23383df611f09c9b26d7d2ef55ce"
        }
        
        # Mock 成功的会话创建响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": 0,
            "data": {
                "id": "test_session_id_123",
                "name": f"Session_{self.test_session_id}",
                "chat_id": self.plugin.cfg["dialog_id"]
            }
        }
        mock_post.return_value = mock_response
        
        # 调用会话创建方法
        session_id = self.plugin.get_or_create_session(self.test_session_id)
        
        # 验证结果
        self.assertIsNotNone(session_id)
        self.assertEqual(session_id, "test_session_id_123")
        self.assertIn(self.test_session_id, self.plugin.user_sessions)

    @patch('requests.post')
    def test_get_ragflow_reply_success(self, mock_post):
        """测试获取RAGFlow回复成功"""
        # 设置配置
        self.plugin.cfg = {
            "api_key": "ragflow-IyZjQ3NWI4M2QwOTExZjA4MDMwMGE5NT",
            "host_address": "154.219.102.235",
            "dialog_id": "f48e23383df611f09c9b26d7d2ef55ce"
        }
        
        # 首先设置一个已存在的会话
        self.plugin.user_sessions[self.test_session_id] = "existing_session_123"
        
        # Mock 成功的完成响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": 0,
            "data": {
                "answer": "你好！我是RAGFlow助手，很高兴为您服务。",
                "reference": {},
                "session_id": "existing_session_123"
            }
        }
        mock_post.return_value = mock_response
        
        # 调用获取回复方法
        reply = self.plugin.get_ragflow_reply(self.test_question, self.test_session_id)
        
        # 验证结果
        self.assertIsNotNone(reply)
        self.assertIn("RAGFlow助手", reply)

    @unittest.skip("需要真实API配置才能运行")
    def test_real_api_integration(self):
        """真实API集成测试"""
        try:
            # 测试会话创建
            session_id = self.plugin.get_or_create_session(self.test_session_id)
            self.assertIsNotNone(session_id, "会话创建失败")
            
            # 测试获取回复
            reply = self.plugin.get_ragflow_reply("你好，请简单介绍一下自己", self.test_session_id)
            self.assertIsNotNone(reply, "获取回复失败")
            self.assertNotEqual(reply, "", "回复内容为空")
            
            print(f"API测试成功!")
            print(f"Session ID: {session_id}")
            print(f"Reply: {reply}")
            
        except Exception as e:
            self.fail(f"集成测试失败: {str(e)}")

def run_tests():
    """运行测试套件"""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestRAGFlowChatSimple)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()

if __name__ == "__main__":
    print("🧪 RAGFlow Chat Plugin 简化版测试")
    print("=" * 50)
    
    success = run_tests()
    
    if success:
        print("\n✅ 所有测试通过!")
    else:
        print("\n❌ 部分测试失败!")
        sys.exit(1) 