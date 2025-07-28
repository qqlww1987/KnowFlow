#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
综合测试脚本：验证完整的配置系统
包括开发模式、分块方法配置、临时文件管理等
"""

import os
import sys
from pathlib import Path

# 添加必要的路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'services', 'knowledgebases', 'mineru_parse'))

try:
    from utils import (
        is_dev_mode, 
        should_cleanup_temp_files, 
        get_configured_chunk_method,
        split_markdown_to_chunks_configured,
        num_tokens_from_string
    )
except ImportError as e:
    print(f"导入错误: {e}")
    sys.exit(1)


def test_complete_configuration():
    """测试完整的配置系统"""
    
    print("🚀 KnowFlow 完整配置系统测试")
    print("="*80)
    
    # 测试内容
    test_content = """
# 系统架构文档

## 核心模块

本系统包含以下核心模块：

### 数据处理模块
负责处理各种数据格式的输入和转换。

### 存储模块  
| 组件 | 功能 | 状态 |
|------|------|------|
| Redis | 缓存 | 运行中 |
| MySQL | 数据库 | 运行中 |
| MinIO | 对象存储 | 运行中 |

### API模块
```python
@app.route('/api/process')
def process_document():
    # 处理文档的核心逻辑
    return {"status": "success"}
```

## 部署配置

系统支持多种部署方式：
1. Docker容器部署
2. Kubernetes集群部署
3. 传统服务器部署

每种部署方式都有其特定的配置要求和优势。
"""

    # 测试配置组合
    test_scenarios = [
        {
            "name": "开发环境 - 智能分块",
            "config": {"DEV": "true", "CHUNK_METHOD": "smart", "CLEANUP_TEMP_FILES": "false"},
            "expected": {"dev": True, "method": "smart", "cleanup": False}
        },
        {
            "name": "测试环境 - 高级分块",
            "config": {"DEV": "true", "CHUNK_METHOD": "advanced", "CLEANUP_TEMP_FILES": "false"},
            "expected": {"dev": True, "method": "advanced", "cleanup": False}
        },
        {
            "name": "生产环境 - 质量优先",
            "config": {"DEV": "false", "CHUNK_METHOD": "advanced", "CLEANUP_TEMP_FILES": "true"},
            "expected": {"dev": False, "method": "advanced", "cleanup": True}
        },
        {
            "name": "生产环境 - 性能优先",
            "config": {"DEV": "false", "CHUNK_METHOD": "smart"},
            "expected": {"dev": False, "method": "smart", "cleanup": True}
        },
        {
            "name": "调试环境",
            "config": {"DEV": "false", "CHUNK_METHOD": "advanced", "CLEANUP_TEMP_FILES": "false"},
            "expected": {"dev": False, "method": "advanced", "cleanup": False}
        }
    ]
    
    results = []
    
    for scenario in test_scenarios:
        print(f"\n🧪 测试场景: {scenario['name']}")
        print("-" * 60)
        
        # 备份原始环境变量
        original_env = {}
        for key in ["DEV", "CHUNK_METHOD", "CLEANUP_TEMP_FILES"]:
            original_env[key] = os.environ.get(key)
        
        try:
            # 清理环境变量
            for key in ["DEV", "CHUNK_METHOD", "CLEANUP_TEMP_FILES"]:
                os.environ.pop(key, None)
            
            # 设置测试配置
            for key, value in scenario["config"].items():
                os.environ[key] = value
            
            # 获取实际结果
            actual_dev = is_dev_mode()
            actual_method = get_configured_chunk_method()
            actual_cleanup = should_cleanup_temp_files()
            
            print(f"📋 配置设置: {scenario['config']}")
            print(f"📊 实际结果:")
            print(f"  • 开发模式: {actual_dev}")
            print(f"  • 分块方法: {actual_method}")
            print(f"  • 清理文件: {actual_cleanup}")
            
            # 验证结果
            expected = scenario["expected"]
            dev_ok = actual_dev == expected["dev"]
            method_ok = actual_method == expected["method"]
            cleanup_ok = actual_cleanup == expected["cleanup"]
            
            if dev_ok and method_ok and cleanup_ok:
                print("✅ 配置验证通过")
                
                # 运行分块测试
                try:
                    chunks = split_markdown_to_chunks_configured(
                        test_content,
                        chunk_token_num=200,
                        include_metadata=(actual_method == "advanced")
                    )
                    
                    # 分析分块结果
                    if chunks:
                        if isinstance(chunks[0], dict):
                            # 高级分块的元数据结果
                            token_counts = [chunk.get('token_count', 0) for chunk in chunks]
                            chunk_types = {}
                            for chunk in chunks:
                                chunk_type = chunk.get('chunk_type', 'unknown')
                                chunk_types[chunk_type] = chunk_types.get(chunk_type, 0) + 1
                            
                            print(f"📈 分块结果: {len(chunks)} 个分块")
                            print(f"   Token分布: {min(token_counts)}-{max(token_counts)} (平均: {sum(token_counts)/len(token_counts):.1f})")
                            print(f"   分块类型: {chunk_types}")
                        else:
                            # 基础/智能分块的字符串结果
                            token_counts = [num_tokens_from_string(chunk) for chunk in chunks]
                            print(f"📈 分块结果: {len(chunks)} 个分块")
                            print(f"   Token分布: {min(token_counts)}-{max(token_counts)} (平均: {sum(token_counts)/len(token_counts):.1f})")
                            print(f"   格式: 字符串列表")
                        
                        results.append({
                            "scenario": scenario["name"],
                            "status": "✅ 成功",
                            "chunks": len(chunks),
                            "method": actual_method,
                            "dev_mode": actual_dev
                        })
                    else:
                        print("⚠️ 分块结果为空")
                        results.append({
                            "scenario": scenario["name"],
                            "status": "⚠️ 分块为空",
                            "chunks": 0,
                            "method": actual_method,
                            "dev_mode": actual_dev
                        })
                        
                except Exception as chunk_error:
                    print(f"❌ 分块测试失败: {chunk_error}")
                    results.append({
                        "scenario": scenario["name"],
                        "status": f"❌ 分块失败: {chunk_error}",
                        "chunks": 0,
                        "method": actual_method,
                        "dev_mode": actual_dev
                    })
            else:
                print("❌ 配置验证失败")
                if not dev_ok:
                    print(f"   开发模式: 期望 {expected['dev']}, 实际 {actual_dev}")
                if not method_ok:
                    print(f"   分块方法: 期望 {expected['method']}, 实际 {actual_method}")
                if not cleanup_ok:
                    print(f"   清理文件: 期望 {expected['cleanup']}, 实际 {actual_cleanup}")
                
                results.append({
                    "scenario": scenario["name"],
                    "status": "❌ 配置失败",
                    "chunks": 0,
                    "method": actual_method,
                    "dev_mode": actual_dev
                })
                
        except Exception as e:
            print(f"❌ 测试异常: {e}")
            results.append({
                "scenario": scenario["name"],
                "status": f"❌ 异常: {e}",
                "chunks": 0,
                "method": "unknown",
                "dev_mode": False
            })
            
        finally:
            # 恢复原始环境变量
            for key, value in original_env.items():
                if value is not None:
                    os.environ[key] = value
                else:
                    os.environ.pop(key, None)
    
    # 生成总结报告
    print(f"\n{'='*80}")
    print("📊 测试总结报告")
    print(f"{'='*80}")
    
    print(f"{'场景':<20} {'状态':<15} {'分块数':<8} {'方法':<10} {'开发模式'}")
    print("-" * 80)
    
    for result in results:
        print(f"{result['scenario']:<20} {result['status']:<15} {result['chunks']:<8} {result['method']:<10} {result['dev_mode']}")
    
    success_count = sum(1 for r in results if "成功" in r["status"])
    total_count = len(results)
    
    print(f"\n🎯 测试统计:")
    print(f"  • 总测试数: {total_count}")
    print(f"  • 成功数: {success_count}")
    print(f"  • 成功率: {success_count/total_count*100:.1f}%")
    
    if success_count == total_count:
        print("\n🎉 所有测试通过！配置系统工作正常。")
    else:
        print(f"\n⚠️ 有 {total_count - success_count} 个测试失败，请检查配置。")
    
    return success_count == total_count


if __name__ == "__main__":
    success = test_complete_configuration()
    
    print(f"\n{'='*80}")
    print("💡 使用提示")
    print(f"{'='*80}")
    print("""
在您的 .env 文件中配置：

# 开发环境（推荐）
DEV=true
CHUNK_METHOD=smart

# 生产环境 
DEV=false
CHUNK_METHOD=advanced

详细配置请参考：
- server/test/CHUNK_CONFIGURATION_GUIDE.md
- server/test/example_env_with_dev_mode.txt
""")
    
    if not success:
        sys.exit(1) 