#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试开发模式（dev模式）功能
验证DEV环境变量和CLEANUP_TEMP_FILES的行为
"""

import os
import sys
from pathlib import Path

# 添加必要的路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'services', 'knowledgebases', 'mineru_parse'))

try:
    from utils import is_dev_mode, should_cleanup_temp_files
except ImportError as e:
    print(f"导入错误: {e}")
    sys.exit(1)


def test_dev_mode_configuration():
    """测试开发模式配置"""
    
    print("🔧 测试开发模式配置")
    
    # 测试不同的配置组合
    test_cases = [
        # (DEV, CLEANUP_TEMP_FILES, 期望的dev模式, 期望的清理行为)
        ('false', 'true', False, True),
        ('true', 'false', True, False),
        ('true', 'true', True, True),
        ('false', 'false', False, False),
        ('1', None, True, False),  # dev模式下默认不清理
        ('0', None, False, True),  # 非dev模式下默认清理
        (None, 'true', False, True),  # 默认非dev模式
        (None, None, False, True),  # 全部默认值
    ]
    
    for dev_val, cleanup_val, expected_dev, expected_cleanup in test_cases:
        print(f"\n{'='*60}")
        print(f"🧪 测试配置: DEV={dev_val}, CLEANUP_TEMP_FILES={cleanup_val}")
        print(f"{'='*60}")
        
        # 备份原始环境变量
        original_dev = os.environ.get('DEV')
        original_cleanup = os.environ.get('CLEANUP_TEMP_FILES')
        
        try:
            # 设置测试环境变量
            if dev_val is not None:
                os.environ['DEV'] = dev_val
            else:
                os.environ.pop('DEV', None)
                
            if cleanup_val is not None:
                os.environ['CLEANUP_TEMP_FILES'] = cleanup_val
            else:
                os.environ.pop('CLEANUP_TEMP_FILES', None)
            
            # 测试函数结果
            actual_dev = is_dev_mode()
            actual_cleanup = should_cleanup_temp_files()
            
            print(f"📝 实际结果:")
            print(f"  • 开发模式: {actual_dev} (期望: {expected_dev})")
            print(f"  • 清理临时文件: {actual_cleanup} (期望: {expected_cleanup})")
            
            # 验证结果
            dev_correct = actual_dev == expected_dev
            cleanup_correct = actual_cleanup == expected_cleanup
            
            if dev_correct and cleanup_correct:
                print("✅ 测试通过")
            else:
                print("❌ 测试失败")
                if not dev_correct:
                    print(f"   开发模式不匹配: 实际{actual_dev} != 期望{expected_dev}")
                if not cleanup_correct:
                    print(f"   清理行为不匹配: 实际{actual_cleanup} != 期望{expected_cleanup}")
                    
        except Exception as e:
            print(f"❌ 测试异常: {e}")
            
        finally:
            # 恢复原始环境变量
            if original_dev is not None:
                os.environ['DEV'] = original_dev
            else:
                os.environ.pop('DEV', None)
                
            if original_cleanup is not None:
                os.environ['CLEANUP_TEMP_FILES'] = original_cleanup
            else:
                os.environ.pop('CLEANUP_TEMP_FILES', None)


def test_dev_mode_logic():
    """测试开发模式的逻辑说明"""
    print(f"\n{'='*60}")
    print("📋 开发模式逻辑说明")
    print(f"{'='*60}")
    
    logic_explanation = """
开发模式配置逻辑：

1. 开发模式检查 (is_dev_mode):
   - DEV=true/1/yes/on → 启用开发模式
   - 其他值或未设置 → 关闭开发模式

2. 临时文件清理 (should_cleanup_temp_files):
   - 开发模式下：
     • CLEANUP_TEMP_FILES=true → 清理文件
     • CLEANUP_TEMP_FILES=false/未设置 → 保留文件（默认）
   - 生产模式下：
     • CLEANUP_TEMP_FILES=false → 保留文件
     • CLEANUP_TEMP_FILES=true/未设置 → 清理文件（默认）

3. 文档解析行为：
   - 开发模式：跳过MinerU，使用现有markdown文件
   - 生产模式：执行完整的MinerU处理流程

推荐配置：
• 开发环境：DEV=true (自动保留临时文件，快速测试)
• 生产环境：DEV=false 或不设置 (完整处理，清理临时文件)
• 调试模式：DEV=false, CLEANUP_TEMP_FILES=false (生产流程但保留文件)
"""
    
    print(logic_explanation)


def show_env_file_examples():
    """显示.env文件配置示例"""
    print(f"\n{'='*60}")
    print("📝 .env 文件配置示例")
    print(f"{'='*60}")
    
    examples = {
        "开发环境": """
# 开发环境配置
DEV=true
CLEANUP_TEMP_FILES=false  # 可选，dev模式下默认为false
CHUNK_METHOD=smart
""",
        "生产环境": """
# 生产环境配置  
DEV=false  # 或者不设置此变量
CLEANUP_TEMP_FILES=true  # 可选，生产模式下默认为true
CHUNK_METHOD=advanced
""",
        "调试环境": """
# 调试环境配置（完整流程但保留文件）
DEV=false
CLEANUP_TEMP_FILES=false
CHUNK_METHOD=advanced
"""
    }
    
    for env_name, config in examples.items():
        print(f"\n🔸 {env_name}:")
        print(config)


if __name__ == "__main__":
    test_dev_mode_configuration()
    test_dev_mode_logic()
    show_env_file_examples()
    print("\n✅ 开发模式测试完成！") 