#!/usr/bin/env python3
"""
验证父子分块功能安装状态
"""

import sys
import os

# 添加项目路径
sys.path.append('/Users/zxwei/zhishi/KnowFlow')

def check_database_tables():
    """检查数据库表是否正确创建"""
    
    print("🗄️ 检查数据库表...")
    
    try:
        from api.db.parent_child_models import ParentChunk, ChildChunk, ParentChildMapping, ParentChildConfig
        
        tables = [
            (ParentChunk, "parent_chunk"),
            (ChildChunk, "child_chunk"), 
            (ParentChildMapping, "parent_child_mapping"),
            (ParentChildConfig, "parent_child_config")
        ]
        
        all_ok = True
        for model, name in tables:
            try:
                count = model.select().count()
                print(f"  ✅ {name}: 正常 ({count} 条记录)")
            except Exception as e:
                print(f"  ❌ {name}: 异常 - {e}")
                all_ok = False
        
        return all_ok
        
    except Exception as e:
        print(f"❌ 数据库检查失败: {e}")
        return False


def check_chunking_integration():
    """检查分块集成是否正常"""
    
    print("\n🔧 检查分块器集成...")
    
    try:
        # 检查utils.py中的父子分块函数
        sys.path.append('/Users/zxwei/zhishi/KnowFlow/knowflow/server/services/knowledgebases/mineru_parse')
        
        # 读取utils.py文件内容
        utils_file = '/Users/zxwei/zhishi/KnowFlow/knowflow/server/services/knowledgebases/mineru_parse/utils.py'
        
        with open(utils_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        checks = [
            ('parent_child策略支持', 'parent_child' in content),
            ('父子分块函数', 'split_markdown_to_chunks_parent_child' in content),
            ('Smart分块集成', 'SmartParentChildSplitter' in content),
            ('数据库保存功能', '_save_parent_child_chunks_to_db' in content)
        ]
        
        all_ok = True
        for check_name, check_result in checks:
            if check_result:
                print(f"  ✅ {check_name}: 已集成")
            else:
                print(f"  ❌ {check_name}: 缺失")
                all_ok = False
        
        return all_ok
        
    except Exception as e:
        print(f"❌ 分块器检查失败: {e}")
        return False


def check_frontend_integration():
    """检查前端界面集成"""
    
    print("\n🖥️ 检查前端界面...")
    
    try:
        # 检查前端分块配置组件
        frontend_file = '/Users/zxwei/zhishi/KnowFlow/web/src/components/chunking-config/index.tsx'
        
        with open(frontend_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        checks = [
            ('父子分块选项', "'parent_child'" in content),
            ('父分块配置', 'parent_config' in content),
            ('检索模式选择', 'retrieval_mode' in content),
            ('参数验证', 'parent_chunk_size' in content)
        ]
        
        all_ok = True
        for check_name, check_result in checks:
            if check_result:
                print(f"  ✅ {check_name}: 已集成")
            else:
                print(f"  ❌ {check_name}: 缺失")
                all_ok = False
        
        return all_ok
        
    except Exception as e:
        print(f"❌ 前端检查失败: {e}")
        return False


def check_core_files():
    """检查核心文件是否存在"""
    
    print("\n📁 检查核心文件...")
    
    files_to_check = [
        ('/Users/zxwei/zhishi/KnowFlow/api/db/parent_child_models.py', '数据库模型'),
        ('/Users/zxwei/zhishi/KnowFlow/rag/nlp/parent_child_splitter.py', '父子分块器'),
        ('/Users/zxwei/zhishi/KnowFlow/rag/nlp/ragflow_parent_retriever.py', '检索器'),
        ('/Users/zxwei/zhishi/KnowFlow/docs/parent_child_chunking_usage.md', '使用文档')
    ]
    
    all_ok = True
    for file_path, description in files_to_check:
        if os.path.exists(file_path):
            size = os.path.getsize(file_path)
            print(f"  ✅ {description}: 存在 ({size:,} 字节)")
        else:
            print(f"  ❌ {description}: 缺失")
            all_ok = False
    
    return all_ok


def main():
    """主验证函数"""
    
    print("=" * 60)
    print("🔍 RAGFlow 父子分块功能安装验证")
    print("=" * 60)
    
    # 各项检查
    db_ok = check_database_tables()
    chunk_ok = check_chunking_integration() 
    frontend_ok = check_frontend_integration()
    files_ok = check_core_files()
    
    print("\n" + "=" * 60)
    print("📊 验证结果汇总:")
    print("=" * 60)
    
    results = [
        ("数据库表", db_ok),
        ("分块器集成", chunk_ok), 
        ("前端界面", frontend_ok),
        ("核心文件", files_ok)
    ]
    
    all_passed = True
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {name}: {status}")
        if not result:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 所有检查通过！父子分块功能已正确安装")
        print("\n📋 使用步骤:")
        print("  1. 启动 KnowFlow 服务")
        print("  2. 创建或编辑知识库")
        print("  3. 在 MinerU 解析配置中选择'父子分块'")
        print("  4. 配置父子分块参数")
        print("  5. 上传文档进行解析")
        print("  6. 验证父子分块效果")
    else:
        print("⚠️ 部分检查失败，请检查上述问题")
    print("=" * 60)


if __name__ == "__main__":
    main()