#!/usr/bin/env python3
"""
快速API测试脚本
专门测试 dialog_id: f48e23383df611f09c9b26d7d2ef55ce 的接口
"""

import requests
import json
import time
import sys
import urllib3

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 配置信息
CONFIG = {
    "api_key": "ragflow-IyZjQ3NWI4M2QwOTExZjA4MDMwMGE5NT",
    "host_address": "154.219.102.235",
    "dialog_id": "f48e23383df611f09c9b26d7d2ef55ce"
}

def test_connection():
    """测试基本连接"""
    print("🔗 测试基本连接...")
    
    # 尝试多种协议
    protocols = ['https', 'http']
    
    for protocol in protocols:
        try:
            test_url = f"{protocol}://{CONFIG['host_address']}"
            print(f"尝试连接: {test_url}")
            
            response = requests.get(test_url, timeout=10, verify=False)
            print(f"✅ {protocol.upper()} 连接成功! 状态码: {response.status_code}")
            return protocol
            
        except Exception as e:
            print(f"❌ {protocol.upper()} 连接失败: {e}")
            continue
    
    print("❌ 所有协议连接都失败")
    return None

def test_session_creation(protocol='https'):
    """测试会话创建"""
    print("🔄 测试会话创建...")
    
    url = f"{protocol}://{CONFIG['host_address']}/api/v1/chats/{CONFIG['dialog_id']}/sessions"
    headers = {
        "Authorization": f"Bearer {CONFIG['api_key']}",
        "Content-Type": "application/json"
    }
    payload = {
        "name": f"Test_Session_{int(time.time())}"
    }
    
    try:
        print(f"请求URL: {url}")
        print(f"请求头: {headers}")
        print(f"请求体: {json.dumps(payload, ensure_ascii=False)}")
        
        response = requests.post(
            url, 
            headers=headers, 
            json=payload, 
            timeout=30,
            verify=False  # 忽略SSL证书验证
        )
        print(f"状态码: {response.status_code}")
        print(f"响应头: {dict(response.headers)}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"响应数据: {json.dumps(data, indent=2, ensure_ascii=False)}")
            
            if data.get("code") == 0:
                session_id = data["data"]["id"]
                print(f"✅ 会话创建成功! Session ID: {session_id}")
                return session_id
            else:
                print(f"❌ 会话创建失败: {data.get('message')}")
                return None
        else:
            print(f"❌ HTTP错误: {response.status_code}")
            print(f"响应内容: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ 请求异常: {e}")
        print(f"异常类型: {type(e).__name__}")
        return None

def test_chat_completion(session_id, question="你好，请简单介绍一下自己", protocol='https'):
    """测试对话完成"""
    print(f"💬 测试对话完成: {question}")
    
    url = f"{protocol}://{CONFIG['host_address']}/api/v1/chats/{CONFIG['dialog_id']}/completions"
    headers = {
        "Authorization": f"Bearer {CONFIG['api_key']}",
        "Content-Type": "application/json"
    }
    payload = {
        "question": question,
        "stream": False,
        "session_id": session_id
    }
    
    try:
        print(f"请求URL: {url}")
        
        response = requests.post(
            url, 
            headers=headers, 
            json=payload, 
            timeout=60,
            verify=False  # 忽略SSL证书验证
        )
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"响应数据: {json.dumps(data, indent=2, ensure_ascii=False)}")
            
            if data.get("code") == 0:
                answer = data["data"].get("answer", "")
                print(f"✅ 获取回复成功!")
                print(f"📝 回复内容: {answer}")
                return answer
            else:
                print(f"❌ 获取回复失败: {data.get('message')}")
                return None
        else:
            print(f"❌ HTTP错误: {response.status_code}")
            print(f"响应内容: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ 请求异常: {e}")
        return None

def test_multiple_conversations(session_id, protocol='https'):
    """测试多轮对话"""
    print("🔄 测试多轮对话...")
    
    questions = [
        "你能做什么？",
        "请告诉我关于人工智能的信息",
        "谢谢你的帮助"
    ]
    
    for i, question in enumerate(questions, 1):
        print(f"\n--- 第 {i} 轮对话 ---")
        answer = test_chat_completion(session_id, question, protocol)
        if answer is None:
            print(f"❌ 第 {i} 轮对话失败")
            return False
        time.sleep(1)  # 避免请求过于频繁
    
    return True

def main():
    """主测试函数"""
    print("🚀 RAGFlow API 快速测试")
    print(f"📋 测试 Dialog ID: {CONFIG['dialog_id']}")
    print(f"🌐 服务器地址: {CONFIG['host_address']}")
    print("=" * 60)
    
    # 步骤0: 测试基本连接
    protocol = test_connection()
    if protocol is None:
        print("\n❌ 无法建立基本连接，请检查网络和服务器状态")
        return 1
    
    print(f"\n✅ 使用 {protocol.upper()} 协议继续测试")
    print("\n" + "="*60)
    
    # 步骤1: 测试会话创建
    session_id = test_session_creation(protocol)
    if session_id is None:
        print("\n❌ 会话创建失败，可能的原因:")
        print("  - API密钥无效")
        print("  - Dialog ID不存在")
        print("  - 服务器内部错误")
        print("  - 网络连接问题")
        return 1
    
    print("\n" + "="*60)
    
    # 步骤2: 测试单次对话
    answer = test_chat_completion(session_id, protocol=protocol)
    if answer is None:
        print("\n❌ 对话测试失败")
        return 1
    
    print("\n" + "="*60)
    
    # 步骤3: 测试多轮对话
    success = test_multiple_conversations(session_id, protocol)
    
    print("\n" + "="*60)
    print("📊 测试结果总结:")
    print(f"  基本连接: ✅ 成功 ({protocol.upper()})")
    print(f"  会话创建: ✅ 成功")
    print(f"  单次对话: ✅ 成功")
    print(f"  多轮对话: {'✅ 成功' if success else '❌ 失败'}")
    
    if success:
        print("\n🎉 所有API测试通过！接口功能正常。")
        return 0
    else:
        print("\n⚠️  部分测试失败。")
        return 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n🛑 测试被用户中断")
        sys.exit(1) 