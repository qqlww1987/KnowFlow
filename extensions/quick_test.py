#!/usr/bin/env python3
"""
KnowFlow 批量 API 快速测试脚本
"""

import requests
import json

def quick_test():
    """快速测试批量添加功能"""
    
    # 配置 - 请修改为你的实际值
    BASE_URL = "http://localhost:9380"
    DATASET_ID = "your_dataset_id_here"      # 请替换
    DOCUMENT_ID = "your_document_id_here"    # 请替换
    API_KEY = ""  # 如果需要的话
    
    if DATASET_ID == "your_dataset_id_here":
        print("⚠️  请先在脚本中配置 DATASET_ID 和 DOCUMENT_ID")
        return
    
    # 准备测试数据
    chunks = [
        {
            "content": "这是第一个测试chunk - KnowFlow批量处理功能测试",
            "important_keywords": ["测试", "KnowFlow", "批量"],
            "questions": ["什么是KnowFlow？", "如何使用批量功能？"]
        },
        {
            "content": "这是第二个测试chunk - 演示向量化和搜索能力",
            "important_keywords": ["向量化", "搜索", "演示"],
            "questions": ["如何进行向量搜索？", "搜索效果如何？"]
        },
        {
            "content": "这是第三个测试chunk - 验证批量插入性能优化",
            "important_keywords": ["性能", "优化", "批量插入"],
            "questions": ["性能提升有多少？", "如何优化批量处理？"]
        }
    ]
    
    # 发送请求
    url = f"{BASE_URL}/api/v1/datasets/{DATASET_ID}/documents/{DOCUMENT_ID}/chunks/batch"
    headers = {
        'Content-Type': 'application/json'
    }
    if API_KEY:
        headers['Authorization'] = f'Bearer {API_KEY}'
    
    payload = {
        "chunks": chunks,
        "batch_size": 2
    }
    
    print(f"🚀 发送请求到: {url}")
    print(f"📊 测试数据: {len(chunks)} chunks")
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        print(f"📤 状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            data = result.get('data', {})
            
            print("✅ 测试成功!")
            print(f"   添加数量: {data.get('total_added', 0)}")
            print(f"   失败数量: {data.get('total_failed', 0)}")
            
            stats = data.get('processing_stats', {})
            if stats:
                print(f"   批量大小: {stats.get('batch_size_used', 0)}")
                print(f"   处理批次: {stats.get('batches_processed', 0)}")
        else:
            print("❌ 测试失败:")
            print(f"   响应: {response.text}")
            
    except Exception as e:
        print(f"❌ 请求异常: {e}")

if __name__ == "__main__":
    quick_test() 