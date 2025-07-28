import unittest
import sys
import os
import json
from unittest.mock import Mock, patch, MagicMock

# Add the correct path to find the bridge module
current_dir = os.path.dirname(__file__)
server_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
sys.path.append(server_dir)

from services.knowflow.ragflow_chat import RAGFlowChat


class TestRAGFlowChat(unittest.TestCase):
    def setUp(self):
        """设置测试环境"""
        self.plugin = RAGFlowChat()
        
        # 使用提供的 dialog_id 和测试配置
        self.test_config = {
            "api_key": "ragflow-IyZjQ3NWI4M2QwOTExZjA4MDMwMGE5NT",
            "host_address": "154.219.102.235",
            "dialog_id": "f48e23383df611f09c9b26d7d2ef55ce"
        }
        
        # Mock 配置加载
        self.plugin.cfg = self.test_config
        
        # 测试用的 session_id
        self.test_session_id = "test_user_12345"
        self.test_question = "你好，请介绍一下自己"

    def test_config_loading(self):
        """测试配置加载"""
        self.assertIsNotNone(self.plugin.cfg)
        self.assertIn("api_key", self.plugin.cfg)
        self.assertIn("host_address", self.plugin.cfg)
        self.assertIn("dialog_id", self.plugin.cfg)
        self.assertEqual(self.plugin.cfg["dialog_id"], "f48e23383df611f09c9b26d7d2ef55ce")

    @patch('requests.post')
    def test_session_creation_success(self, mock_post):
        """测试会话创建成功"""
        # Mock 成功的会话创建响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": 0,
            "data": {
                "id": "test_session_id_123",
                "name": f"Session_{self.test_session_id}",
                "chat_id": self.test_config["dialog_id"]
            }
        }
        mock_post.return_value = mock_response
        
        # 调用会话创建方法
        session_id = self.plugin.get_or_create_session(self.test_session_id)
        
        # 验证结果
        self.assertIsNotNone(session_id)
        self.assertEqual(session_id, "test_session_id_123")
        self.assertIn(self.test_session_id, self.plugin.user_sessions)
        
        # 验证API调用
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertIn(f"/api/v1/chats/{self.test_config['dialog_id']}/sessions", call_args[1]['url'])

    @patch('requests.post')
    def test_session_creation_failure(self, mock_post):
        """测试会话创建失败"""
        # Mock 失败的会话创建响应
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "code": 102,
            "message": "Name cannot be empty."
        }
        mock_post.return_value = mock_response
        
        # 调用会话创建方法
        session_id = self.plugin.get_or_create_session(self.test_session_id)
        
        # 验证结果
        self.assertIsNone(session_id)

    @patch('requests.post')
    def test_get_ragflow_reply_success(self, mock_post):
        """测试获取RAGFlow回复成功"""
        # 首先设置一个已存在的会话
        self.plugin.user_sessions[self.test_session_id] = "existing_session_123"
        
        # Mock 成功的完成响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": 0,
            "data": {
                "answer": "你好！我是RAGFlow助手，很高兴为您服务。",
                "reference": [],
                "session_id": "existing_session_123"
            }
        }
        mock_post.return_value = mock_response
        
        # 调用获取回复方法
        reply = self.plugin.get_ragflow_reply(self.test_question, self.test_session_id)
        
        # 验证结果
        self.assertIsNotNone(reply)
        self.assertIn("RAGFlow助手", reply)
        
        # 验证API调用
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertIn(f"/api/v1/chats/{self.test_config['dialog_id']}/completions", call_args[1]['url'])
        
        # 验证请求体
        request_data = call_args[1]['json']
        self.assertEqual(request_data['question'], self.test_question)
        self.assertEqual(request_data['session_id'], "existing_session_123")
        self.assertFalse(request_data['stream'])

    @patch('requests.post')
    def test_full_conversation_flow(self, mock_post):
        """测试完整的对话流程"""
        # Mock 两次API调用：会话创建 + 对话完成
        responses = [
            # 第一次调用：创建会话
            Mock(status_code=200, json=Mock(return_value={
                "code": 0,
                "data": {
                    "id": "full_test_session_456",
                    "name": f"Session_{self.test_session_id}",
                    "chat_id": self.test_config["dialog_id"]
                }
            })),
            # 第二次调用：获取回复
            Mock(status_code=200, json=Mock(return_value={
                "code": 0,
                "data": {
                    "answer": "这是一个完整流程的测试回复。",
                    "reference": [],
                    "session_id": "full_test_session_456"
                }
            }))
        ]
        mock_post.side_effect = responses
        
        # 调用完整流程
        reply = self.plugin.get_ragflow_reply(self.test_question, self.test_session_id)
        
        # 验证结果
        self.assertIsNotNone(reply)
        self.assertIn("完整流程", reply)
        
        # 验证会话已被缓存
        self.assertIn(self.test_session_id, self.plugin.user_sessions)
        self.assertEqual(self.plugin.user_sessions[self.test_session_id], "full_test_session_456")
        
        # 验证API被调用了两次
        self.assertEqual(mock_post.call_count, 2)

    @patch('requests.post')
    def test_session_reuse(self, mock_post):
        """测试会话重用功能"""
        # 预设一个已存在的会话
        existing_session_id = "reuse_test_session_789"
        self.plugin.user_sessions[self.test_session_id] = existing_session_id
        
        # Mock 只需要对话完成的响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": 0,
            "data": {
                "answer": "重用会话的测试回复。",
                "reference": [],
                "session_id": existing_session_id
            }
        }
        mock_post.return_value = mock_response
        
        # 调用获取回复方法
        reply = self.plugin.get_ragflow_reply("第二条消息", self.test_session_id)
        
        # 验证结果
        self.assertIsNotNone(reply)
        self.assertIn("重用会话", reply)
        
        # 验证只调用了一次API（没有创建新会话）
        mock_post.assert_called_once()
        
        # 验证调用的是completions端点
        call_args = mock_post.call_args
        self.assertIn("/completions", call_args[1]['url'])

    def test_extract_image_urls(self):
        """测试图片URL提取功能"""
        text_with_images = "这是一段包含图片的文本 https://example.com/image1.jpg 和另一张图片 https://example.com/image2.png?size=large"
        urls = self.plugin.extract_image_urls(text_with_images)
        
        self.assertEqual(len(urls), 2)
        self.assertIn("https://example.com/image1.jpg", urls)
        self.assertIn("https://example.com/image2.png?size=large", urls)

    def test_missing_configuration(self):
        """测试配置缺失的情况"""
        # 清空配置
        self.plugin.cfg = {}
        
        session_id = self.plugin.get_or_create_session(self.test_session_id)
        self.assertIsNone(session_id)

    @patch('requests.post')
    def test_api_error_handling(self, mock_post):
        """测试API错误处理"""
        # Mock 网络错误
        mock_post.side_effect = Exception("Network error")
        
        session_id = self.plugin.get_or_create_session(self.test_session_id)
        self.assertIsNone(session_id)


class TestRAGFlowChatIntegration(unittest.TestCase):
    """集成测试 - 需要真实的API配置"""
    
    def setUp(self):
        """设置集成测试环境"""
        self.plugin = RAGFlowChat()
        self.plugin.cfg = {
            "api_key": "ragflow-M4NzNjYzQwMGJiZTExZjA5MTY1MTZhZG",
            "host_address": "www.knowflowchat.cn",
            "dialog_id": "f48e23383df611f09c9b26d7d2ef55ce"
        }
        self.test_session_id = f"integration_test_{os.getpid()}"

    @unittest.skip("需要真实API配置才能运行")
    def test_real_api_call(self):
        """真实API调用测试（需要有效的API配置）"""
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
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加单元测试
    suite.addTests(loader.loadTestsFromTestCase(TestRAGFlowChat))
    
    # 添加集成测试（默认跳过）
    suite.addTests(loader.loadTestsFromTestCase(TestRAGFlowChatIntegration))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    # 运行测试
    success = run_tests()
    
    if success:
        print("\n✅ 所有测试通过!")
    else:
        print("\n❌ 部分测试失败!")
        sys.exit(1) 