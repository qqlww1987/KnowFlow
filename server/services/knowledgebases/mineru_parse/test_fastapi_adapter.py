#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MinerU FastAPI 适配器测试脚本

用于测试 FastAPI 适配器的基本功能和连接性。
"""

import os
import sys
import tempfile
from pathlib import Path

# 添加项目路径
current_dir = Path(__file__).parent
server_dir = current_dir.parent.parent.parent
sys.path.insert(0, str(server_dir))

from .fastapi_adapter import get_global_adapter, test_adapter_connection, configure_adapter
from .adapter_config import get_config, configure_fastapi
from .process_pdf import process_pdf_entry, configure_fastapi as process_configure


def test_adapter_config():
    """测试适配器配置"""
    print("=== 测试适配器配置 ===")
    
    config = get_config()
    config.print_config()
    
    print("\n当前配置信息:")
    fastapi_config = config.get_fastapi_config()
    for key, value in fastapi_config.items():
        print(f"  {key}: {value}")


def test_fastapi_connection():
    """测试 FastAPI 连接"""
    print("\n=== 测试 FastAPI 连接 ===")
    
    # 测试默认连接
    result = test_adapter_connection()
    print(f"连接测试结果: {result['status']}")
    print(f"服务地址: {result['url']}")
    print(f"消息: {result['message']}")
    
    return result['status'] == 'success'


def test_adapter_initialization():
    """测试适配器初始化"""
    print("\n=== 测试适配器初始化 ===")
    
    try:
        adapter = get_global_adapter()
        print(f"适配器初始化成功")
        print(f"  基础URL: {adapter.base_url}")
        print(f"  默认后端: {adapter.backend}")
        print(f"  超时时间: {adapter.timeout}秒")
        return True
    except Exception as e:
        print(f"适配器初始化失败: {e}")
        return False


def test_process_functions():
    """测试处理函数"""
    print("\n=== 测试处理函数 ===")
    
    # 创建临时测试文件（实际测试时需要真实PDF文件）
    test_file = "/tmp/test_demo.pdf"
    
    if not os.path.exists(test_file):
        print(f"测试文件不存在: {test_file}")
        print("请确保有可用的测试PDF文件")
        return False
    
    def mock_progress(progress, message):
        print(f"进度 {progress*100:.1f}%: {message}")
    
    try:
        print("开始测试 process_pdf_entry...")
        result = process_pdf_entry(
            doc_id="test_doc_001",
            pdf_path=test_file,
            kb_id="test_kb_001", 
            update_progress=mock_progress
        )
        
        if result and result != 0:
            print(f"处理成功，返回结果类型: {type(result)}")
            return True
        else:
            print("处理失败或返回空结果")
            return False
            
    except Exception as e:
        print(f"处理过程出错: {e}")
        return False


def test_configuration_changes():
    """测试配置变更"""
    print("\n=== 测试配置变更 ===")
    
    # 保存原始配置
    original_url = os.environ.get('MINERU_FASTAPI_URL')
    original_backend = os.environ.get('MINERU_FASTAPI_BACKEND')
    
    try:
        # 测试配置更改
        configure_fastapi('http://localhost:9999', 'vlm-transformers')
        
        # 验证配置是否生效
        adapter = get_global_adapter()
        print(f"新配置 - URL: {adapter.base_url}, 后端: {adapter.backend}")
        
        # 恢复原始配置
        if original_url:
            os.environ['MINERU_FASTAPI_URL'] = original_url
        if original_backend:
            os.environ['MINERU_FASTAPI_BACKEND'] = original_backend
        else:
            os.environ['MINERU_FASTAPI_BACKEND'] = 'pipeline'
            
        # 重新配置适配器
        configure_adapter()
        
        print("配置变更测试完成")
        return True
        
    except Exception as e:
        print(f"配置变更测试失败: {e}")
        return False


def main():
    """主测试函数"""
    print("🚀 MinerU FastAPI 适配器测试")
    print("=" * 50)
    
    tests = [
        ("配置测试", test_adapter_config),
        ("连接测试", test_fastapi_connection), 
        ("初始化测试", test_adapter_initialization),
        ("配置变更测试", test_configuration_changes),
        # ("处理函数测试", test_process_functions),  # 需要真实PDF文件
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"{test_name} 执行出错: {e}")
            results.append((test_name, False))
    
    # 输出测试总结
    print("\n" + "=" * 50)
    print("📊 测试结果总结")
    print("=" * 50)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1
    
    print(f"\n总体结果: {passed}/{len(results)} 个测试通过")
    
    if passed == len(results):
        print("🎉 所有测试通过！FastAPI 适配器运行正常")
    else:
        print("⚠️  部分测试失败，请检查配置和服务状态")


if __name__ == '__main__':
    main() 