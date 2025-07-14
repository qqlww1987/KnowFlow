#!/usr/bin/env python3
"""
KnowFlow 插件测试脚本
测试 batch_add_chunk 插件功能
"""

import requests
import json
import time
from typing import List, Dict, Optional


class KnowFlowPluginTester:
    """KnowFlow 插件测试器"""
    
    def __init__(self, base_url: str = "http://localhost", api_key: str = ""):
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
    
    def test_plugin_batch_add_chunks(self, 
                                   dataset_id: str, 
                                   document_id: str, 
                                   chunks: List[Dict],
                                   batch_size: Optional[int] = None) -> Dict:
        """
        测试插件版本的批量添加 chunks
        
        Args:
            dataset_id: 数据集ID
            document_id: 文档ID
            chunks: chunk数据列表
            batch_size: 批量处理大小
            
        Returns:
            API响应结果
        """
        # 新的插件 API 端点（使用正确的路径）
        url = f"{self.base_url}/api/v1/datasets/{dataset_id}/documents/{document_id}/chunks/batch"
        
        payload = {"chunks": chunks}
        if batch_size:
            payload["batch_size"] = batch_size
        
        print(f"🔌 测试 KnowFlow 插件 API: {url}")
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
                self._print_plugin_success_result(result)
                return result
            else:
                print(f"❌ 插件请求失败:")
                print(f"   状态码: {response.status_code}")
                print(f"   响应: {response.text}")
                return {"error": response.text}
                
        except requests.exceptions.RequestException as e:
            print(f"❌ 网络请求异常: {e}")
            return {"error": str(e)}
    
    def _print_plugin_success_result(self, result: Dict):
        """打印插件测试成功结果"""
        print("接口原始返回：", result)
        data = result.get('data', {})
        if data is None:
            print("警告：接口 data 字段为 None，后端未返回有效数据！")
            data = {}
        
        print("✅ KnowFlow 插件测试成功!")
        print(f"   ✅ 成功添加: {data.get('total_added', 0)} chunks")
        
        if data.get('total_failed', 0) > 0:
            print(f"   ❌ 失败数量: {data.get('total_failed', 0)} chunks")
        
        # 处理统计信息
        stats = data.get('processing_stats', {})
        if stats:
            print("📊 插件处理统计:")
            print(f"   📥 请求总数: {stats.get('total_requested', 0)}")
            print(f"   🔄 分片大小: {stats.get('batch_size_used', 0)}")
            print(f"   📦 处理批次: {stats.get('batches_processed', 0)}")
            print(f"   💰 嵌入成本: {stats.get('embedding_cost', 0)}")
            
            errors = stats.get('processing_errors')
            if errors:
                print(f"   ⚠️  处理错误: {len(errors)} 个")
                for error in errors[:3]:
                    print(f"      - {error}")
        
        # 检查是否有插件特有的字段
        chunks_result = data.get('chunks', [])
        if chunks_result:
            print(f"   📄 返回chunks: {len(chunks_result)} 个")
    
    def create_test_chunks(self, count: int = 5, content_prefix: str = "KnowFlow插件测试") -> List[Dict]:
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
                "content": f"{content_prefix} {i+1} - 这是一个用于测试KnowFlow插件系统的示例文本内容。验证增量插件是否正常工作，而不需要替换整个enhanced_doc.py文件。",
                "important_keywords": [f"插件{i+1}", f"测试{i+1}", "KnowFlow", "增量挂载"],
                "questions": [
                    f"什么是{content_prefix} {i+1}？",
                    f"KnowFlow插件系统如何工作？"
                ]
            }
            chunks.append(chunk)
        return chunks
    
    def create_test_chunks_with_positions(self, count: int = 3, content_prefix: str = "位置插件测试") -> List[Dict]:
        """
        创建包含位置信息的测试 chunk 数据
        
        Args:
            count: 创建的chunk数量
            content_prefix: 内容前缀
            
        Returns:
            包含位置信息的chunk数据列表
        """
        chunks = []
        for i in range(count):
            chunk = {
                "content": f"{content_prefix} {i+1} - 这是一个包含位置信息的KnowFlow插件测试内容。验证位置信息处理是否正确。",
                "important_keywords": [f"位置{i+1}", f"插件{i+1}", "KnowFlow", "位置测试"],
                "questions": [
                    f"什么是{content_prefix} {i+1}的位置？",
                    f"插件如何处理位置信息？"
                ],
                "positions": [
                    [i+1, 100 + i*50, 500 + i*50, 200 + i*30, 250 + i*30],
                    [i+1, 100 + i*50, 500 + i*50, 260 + i*30, 310 + i*30]
                ]
            }
            chunks.append(chunk)
        return chunks
    
    def run_plugin_test_suite(self, dataset_id: str, document_id: str):
        """
        运行完整的插件测试套件
        
        Args:
            dataset_id: 数据集ID
            document_id: 文档ID
        """
        print("🧪 KnowFlow 插件系统测试套件")
        print("=" * 60)
        
        # 测试1: 基础插件功能测试
        print("\n📋 测试1: 基础插件功能 (5 chunks)")
        print("-" * 40)
        basic_chunks = self.create_test_chunks(5, "基础插件测试")
        result1 = self.test_plugin_batch_add_chunks(dataset_id, document_id, basic_chunks, batch_size=2)
        
        time.sleep(2)
        
        # 测试2: 位置信息插件测试
        print("\n📋 测试2: 位置信息插件测试 (3 chunks)")
        print("-" * 40)
        position_chunks = self.create_test_chunks_with_positions(3, "位置插件测试")
        result2 = self.test_plugin_batch_add_chunks(dataset_id, document_id, position_chunks, batch_size=1)
        
        time.sleep(2)
        
        # 测试3: 大批量插件测试
        print("\n📋 测试3: 大批量插件测试 (20 chunks)")
        print("-" * 40)
        large_chunks = self.create_test_chunks(20, "大批量插件测试")
        result3 = self.test_plugin_batch_add_chunks(dataset_id, document_id, large_chunks, batch_size=5)
        
        # 测试总结
        print("\n📊 插件测试总结")
        print("=" * 60)
        
        tests = [
            ("基础插件测试", result1),
            ("位置信息插件测试", result2),
            ("大批量插件测试", result3)
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
        
        print(f"\n🎯 插件系统总计:")
        print(f"   ✅ 成功添加: {total_added} chunks")
        print(f"   ❌ 失败数量: {total_failed} chunks")
        print(f"   📈 成功率: {(total_added/(total_added+total_failed)*100):.1f}%" if (total_added + total_failed) > 0 else "N/A")
        
        if total_added > 0:
            print(f"\n🎉 KnowFlow 插件系统测试通过!")
            print(f"   🔌 插件正常工作，无需维护整个 enhanced_doc.py")
            print(f"   📦 增量挂载方式验证成功")


def main():
    """主函数"""
    print("🚀 KnowFlow 插件系统测试工具")
    print("=" * 60)
    
    # 配置参数
    BASE_URL = "http://localhost:9380"
    API_KEY = "ragflow-EzZDcyMGM0NWY5ZDExZjBhODQ2NDY0N2"
    
    # 测试参数
    DATASET_ID = "abea3a645f9c11f092b39a1d66cae0eb"
    DOCUMENT_ID = "dececf525ff711f09df566fc51ac58de"
    
    # 检查参数
    if DATASET_ID == "your_dataset_id_here" or DOCUMENT_ID == "your_document_id_here":
        print("⚠️  请先配置测试参数!")
        print("请在脚本中修改以下变量:")
        print(f"   DATASET_ID = '{DATASET_ID}'")
        print(f"   DOCUMENT_ID = '{DOCUMENT_ID}'")
        return
    
    # 创建测试器
    tester = KnowFlowPluginTester(BASE_URL, API_KEY)
    
    print("\n🔌 开始测试 KnowFlow 插件系统...")
    print("注意: 确保已正确配置 Docker 挂载:")
    print("   ./knowflow_plugins:/ragflow/api/apps/knowflow_plugins:ro")
    print("")
    
    # 运行插件测试套件
    tester.run_plugin_test_suite(DATASET_ID, DOCUMENT_ID)


if __name__ == "__main__":
    main()