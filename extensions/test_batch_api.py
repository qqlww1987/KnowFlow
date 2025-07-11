#!/usr/bin/env python3
"""
KnowFlow 批量 Chunk 添加 API 测试脚本
测试新增的 POST /datasets/<dataset_id>/documents/<document_id>/chunks/batch 接口
"""

import requests
import json
import time
from typing import List, Dict, Optional

class KnowFlowBatchTester:
    def __init__(self, base_url: str = "http://localhost:9380", api_key: str = ""):
        """
        初始化测试器
        
        Args:
            base_url: RAGFlow 服务的基础URL
            api_key: API密钥
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}' if api_key else ''
        }
    
    def test_batch_add_chunks(self, 
                             dataset_id: str, 
                             document_id: str, 
                             chunks: List[Dict],
                             batch_size: Optional[int] = None) -> Dict:
        """
        测试批量添加 chunks
        
        Args:
            dataset_id: 数据集ID
            document_id: 文档ID
            chunks: chunk数据列表
            batch_size: 批量处理大小
            
        Returns:
            API响应结果
        """
        url = f"{self.base_url}/api/v1/datasets/{dataset_id}/documents/{document_id}/chunks/batch"
        
        payload = {"chunks": chunks}
        if batch_size:
            payload["batch_size"] = batch_size
        
        print(f"🚀 发送批量请求到: {url}")
        print(f"📊 批量大小: {len(chunks)} chunks")
        if batch_size:
            print(f"🔧 处理分片: {batch_size}")
        
        try:
            start_time = time.time()
            response = requests.post(url, headers=self.headers, json=payload, timeout=60)
            end_time = time.time()
            
            print(f"⏱️  请求耗时: {end_time - start_time:.2f} 秒")
            print(f"📤 HTTP状态码: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                self._print_success_result(result)
                return result
            else:
                print(f"❌ 请求失败:")
                print(f"   状态码: {response.status_code}")
                print(f"   响应: {response.text}")
                return {"error": response.text}
                
        except requests.exceptions.RequestException as e:
            print(f"❌ 网络请求异常: {e}")
            return {"error": str(e)}
    
    def _print_success_result(self, result: Dict):
        """打印成功结果的统计信息"""
        data = result.get('data', {})
        
        print("✅ 批量添加成功!")
        print(f"   ✅ 成功添加: {data.get('total_added', 0)} chunks")
        
        if data.get('total_failed', 0) > 0:
            print(f"   ❌ 失败数量: {data.get('total_failed', 0)} chunks")
        
        # 处理统计信息
        stats = data.get('processing_stats', {})
        if stats:
            print("📊 处理统计:")
            print(f"   📥 请求总数: {stats.get('total_requested', 0)}")
            print(f"   🔄 分片大小: {stats.get('batch_size_used', 0)}")
            print(f"   📦 处理批次: {stats.get('batches_processed', 0)}")
            print(f"   💰 嵌入成本: {stats.get('embedding_cost', 0)}")
            
            errors = stats.get('processing_errors')
            if errors:
                print(f"   ⚠️  处理错误: {len(errors)} 个")
                for error in errors[:3]:  # 只显示前3个错误
                    print(f"      - {error}")
    
    def create_test_chunks(self, count: int = 10, content_prefix: str = "测试内容") -> List[Dict]:
        """
        创建测试用的 chunk 数据
        
        Args:
            count: 创建的chunk数量
            content_prefix: 内容前缀
            
        Returns:
            chunk数据列表
        """
        chunks = []
        for i in range(count):
            chunk = {
                "content": f"{content_prefix} {i+1} - 这是一个用于测试KnowFlow批量添加功能的示例文本内容。包含了一些有意义的信息用于测试向量化和搜索功能。",
                "important_keywords": [f"关键词{i+1}", f"测试{i+1}", "KnowFlow", "批量处理"],
                "questions": [
                    f"什么是{content_prefix} {i+1}？",
                    f"如何使用{content_prefix} {i+1}？"
                ]
            }
            chunks.append(chunk)
        return chunks
    
    def run_test_suite(self, dataset_id: str, document_id: str):
        """
        运行完整的测试套件
        
        Args:
            dataset_id: 数据集ID
            document_id: 文档ID
        """
        print("🧪 KnowFlow 批量 Chunk 添加测试套件")
        print("=" * 60)
        
        # 测试1: 小批量测试 (5个chunk)
        print("\n📋 测试1: 小批量测试 (5 chunks)")
        print("-" * 40)
        small_chunks = self.create_test_chunks(5, "小批量测试")
        result1 = self.test_batch_add_chunks(dataset_id, document_id, small_chunks, batch_size=2)
        
        time.sleep(2)  # 等待2秒
        
        # 测试2: 中等批量测试 (20个chunk)
        print("\n📋 测试2: 中等批量测试 (20 chunks)")
        print("-" * 40)
        medium_chunks = self.create_test_chunks(20, "中等批量测试")
        result2 = self.test_batch_add_chunks(dataset_id, document_id, medium_chunks, batch_size=5)
        
        time.sleep(2)  # 等待2秒
        
        # 测试3: 大批量测试 (50个chunk)
        print("\n📋 测试3: 大批量测试 (50 chunks)")
        print("-" * 40)
        large_chunks = self.create_test_chunks(50, "大批量测试")
        result3 = self.test_batch_add_chunks(dataset_id, document_id, large_chunks, batch_size=10)
        
        # 测试总结
        print("\n📊 测试总结")
        print("=" * 60)
        
        tests = [
            ("小批量测试", result1),
            ("中等批量测试", result2),
            ("大批量测试", result3)
        ]
        
        total_added = 0
        total_failed = 0
        
        for test_name, result in tests:
            if 'error' not in result:
                data = result.get('data', {})
                added = data.get('total_added', 0)
                failed = data.get('total_failed', 0)
                total_added += added
                total_failed += failed
                print(f"✅ {test_name}: +{added} chunks (失败: {failed})")
            else:
                print(f"❌ {test_name}: 测试失败")
        
        print(f"\n🎯 总计:")
        print(f"   ✅ 成功添加: {total_added} chunks")
        print(f"   ❌ 失败数量: {total_failed} chunks")
        print(f"   📈 成功率: {(total_added/(total_added+total_failed)*100):.1f}%" if (total_added + total_failed) > 0 else "N/A")

def main():
    """主函数"""
    print("🚀 KnowFlow 批量 Chunk 添加 API 测试工具")
    print("=" * 60)
    
    # 配置参数 - 请根据实际情况修改
    BASE_URL = "http://localhost:9380"  # RAGFlow 服务地址
    API_KEY = ""  # 你的API密钥，如果需要的话
    
    # 测试参数 - 请根据实际情况修改
    DATASET_ID = "your_dataset_id_here"      # 替换为实际的数据集ID
    DOCUMENT_ID = "your_document_id_here"    # 替换为实际的文档ID
    
    # 检查参数
    if DATASET_ID == "your_dataset_id_here" or DOCUMENT_ID == "your_document_id_here":
        print("⚠️  请先配置测试参数!")
        print("请在脚本中修改以下变量:")
        print(f"   DATASET_ID = '{DATASET_ID}'")
        print(f"   DOCUMENT_ID = '{DOCUMENT_ID}'")
        print(f"   BASE_URL = '{BASE_URL}'")
        print(f"   API_KEY = '{API_KEY}' (如果需要)")
        print("\n💡 获取ID的方法:")
        print("   1. 通过 RAGFlow Web界面查看URL")
        print("   2. 通过 GET /api/v1/datasets 获取数据集列表")
        print("   3. 通过 GET /api/v1/datasets/{dataset_id}/documents 获取文档列表")
        return
    
    # 创建测试器
    tester = KnowFlowBatchTester(BASE_URL, API_KEY)
    
    # 询问测试类型
    print("\n选择测试类型:")
    print("1. 运行完整测试套件 (推荐)")
    print("2. 自定义单次测试")
    
    choice = input("请选择 (1 或 2): ").strip()
    
    if choice == "1":
        # 运行完整测试套件
        tester.run_test_suite(DATASET_ID, DOCUMENT_ID)
    
    elif choice == "2":
        # 自定义测试
        print("\n自定义测试配置:")
        chunk_count = int(input("输入chunk数量 (默认10): ") or "10")
        batch_size = int(input("输入批量大小 (默认5): ") or "5")
        content_prefix = input("输入内容前缀 (默认'自定义测试'): ") or "自定义测试"
        
        chunks = tester.create_test_chunks(chunk_count, content_prefix)
        result = tester.test_batch_add_chunks(DATASET_ID, DOCUMENT_ID, chunks, batch_size)
        
        if 'error' not in result:
            print("\n✅ 自定义测试完成!")
        else:
            print("\n❌ 自定义测试失败!")
    
    else:
        print("❌ 无效选择")

if __name__ == "__main__":
    main() 