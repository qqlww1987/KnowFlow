#!/usr/bin/env python3
#
#  Copyright 2025 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

"""
父子分块数据库表初始化脚本
创建父子分块相关的数据库表和索引

注意：从 v2.1.0 开始，父子分块表已经集成到主数据库模型中（api/db/db_models.py），
会在系统启动时自动创建。此脚本保留用于：
1. 手动初始化（如果需要）
2. 独立验证和测试
3. 向后兼容性

大部分情况下，您不需要手动运行此脚本，因为表会在 ragflow_server.py 启动时自动创建。
"""

import sys
import os
import logging

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.db.db_models import DB
from api.db.parent_child_models import ParentChunk, ChildChunk, ParentChildMapping, ParentChildConfig

logger = logging.getLogger(__name__)


def init_parent_child_tables():
    """初始化父子分块相关表"""
    
    print("🚀 开始初始化父子分块数据库表...")
    
    try:
        # 连接数据库
        if not DB.is_connection_usable():
            DB.connect()
        
        # 创建表
        tables_to_create = [
            ParentChunk,
            ChildChunk,  
            ParentChildMapping,
            ParentChildConfig
        ]
        
        created_tables = []
        existing_tables = []
        
        for table_model in tables_to_create:
            table_name = table_model._meta.table_name
            
            if not table_model.table_exists():
                print(f"📋 创建表: {table_name}")
                table_model.create_table(safe=True)
                created_tables.append(table_name)
            else:
                print(f"✅ 表已存在: {table_name}")
                existing_tables.append(table_name)
        
        # 创建索引（如果需要额外索引）
        print("🔍 创建索引...")
        
        # 父分块索引
        try:
            # MySQL 不支持 CREATE INDEX IF NOT EXISTS，先检查后创建
            DB.execute_sql("""
                CREATE INDEX idx_parent_chunk_kb_doc 
                ON parent_chunk(kb_id, doc_id)
            """)
            print("✅ 父分块复合索引创建完成")
        except Exception as e:
            if "Duplicate key name" in str(e) or "already exists" in str(e):
                print("ℹ️ 父分块索引已存在")
            else:
                print(f"⚠️ 父分块索引创建失败: {e}")
        
        # 子分块索引
        try:
            DB.execute_sql("""
                CREATE INDEX idx_child_chunk_parent 
                ON child_chunk(parent_chunk_id, chunk_order_in_parent)
            """)
            print("✅ 子分块父关联索引创建完成")
        except Exception as e:
            if "Duplicate key name" in str(e) or "already exists" in str(e):
                print("ℹ️ 子分块索引已存在")
            else:
                print(f"⚠️ 子分块索引创建失败: {e}")
        
        # 映射关系索引
        try:
            DB.execute_sql("""
                CREATE INDEX idx_mapping_kb_doc 
                ON parent_child_mapping(kb_id, doc_id)
            """)
            print("✅ 映射关系索引创建完成")
        except Exception as e:
            if "Duplicate key name" in str(e) or "already exists" in str(e):
                print("ℹ️ 映射关系索引已存在")
            else:
                print(f"⚠️ 映射关系索引创建失败: {e}")
        
        print("\n📊 初始化结果:")
        print(f"  ✅ 新建表: {len(created_tables)} 个")
        if created_tables:
            for table in created_tables:
                print(f"    - {table}")
                
        print(f"  ℹ️ 已存在表: {len(existing_tables)} 个")
        if existing_tables:
            for table in existing_tables:
                print(f"    - {table}")
        
        print("\n🎉 父子分块数据库表初始化完成!")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if DB.is_connection_usable():
            DB.close()


def create_sample_config():
    """创建示例配置"""
    
    print("\n🔧 创建示例配置...")
    
    try:
        if not DB.is_connection_usable():
            DB.connect()
        
        # 创建默认配置（用于测试）
        sample_kb_id = "sample_kb_001"
        
        # 检查是否已存在
        try:
            existing_config = ParentChildConfig.get_by_id(sample_kb_id)
            print(f"ℹ️ 示例配置已存在: {sample_kb_id}")
            return True
        except ParentChildConfig.DoesNotExist:
            pass
        
        # 创建示例配置
        ParentChildConfig.create(
            kb_id=sample_kb_id,
            parent_chunk_size=1024,
            parent_chunk_overlap=100,
            parent_separator=r'\n\n',
            child_chunk_size=256,
            child_chunk_overlap=50,
            child_separator=r'[。！？.!?]',
            retrieval_mode='parent',
            top_k_children=10,
            top_k_parents=4,
            enabled=True,
            config_json='{"description": "示例配置，用于测试父子分块功能"}'
        )
        
        print(f"✅ 示例配置创建成功: {sample_kb_id}")
        return True
        
    except Exception as e:
        print(f"❌ 示例配置创建失败: {e}")
        return False
    finally:
        if DB.is_connection_usable():
            DB.close()


def verify_installation():
    """验证安装是否成功"""
    
    print("\n🔍 验证安装...")
    
    try:
        if not DB.is_connection_usable():
            DB.connect()
        
        # 检查表是否存在且可用
        tables_to_check = [
            (ParentChunk, "parent_chunk"),
            (ChildChunk, "child_chunk"),
            (ParentChildMapping, "parent_child_mapping"),
            (ParentChildConfig, "parent_child_config")
        ]
        
        all_good = True
        
        for model_class, table_name in tables_to_check:
            try:
                # 尝试查询表结构
                count = model_class.select().count()
                print(f"✅ 表 {table_name}: 正常 ({count} 条记录)")
            except Exception as e:
                print(f"❌ 表 {table_name}: 异常 - {e}")
                all_good = False
        
        # 测试简单的CRUD操作
        try:
            # 测试配置表
            test_kb_id = "test_verification"
            
            # 创建
            config = ParentChildConfig.create(
                kb_id=test_kb_id,
                parent_chunk_size=512,
                child_chunk_size=128,
                enabled=True
            )
            
            # 读取
            retrieved_config = ParentChildConfig.get_by_id(test_kb_id)
            
            # 更新
            retrieved_config.enabled = False
            retrieved_config.save()
            
            # 删除
            retrieved_config.delete_instance()
            
            print("✅ CRUD操作测试: 通过")
            
        except Exception as e:
            print(f"❌ CRUD操作测试: 失败 - {e}")
            all_good = False
        
        if all_good:
            print("\n🎉 验证通过！父子分块功能已准备就绪")
        else:
            print("\n⚠️ 验证发现问题，请检查上述错误")
            
        return all_good
        
    except Exception as e:
        print(f"❌ 验证过程失败: {e}")
        return False
    finally:
        if DB.is_connection_usable():
            DB.close()


def main():
    """主函数"""
    
    print("=" * 60)
    print("🔧 RAGFlow 父子分块数据库初始化工具")
    print("=" * 60)
    
    # 检查数据库连接
    try:
        if not DB.is_connection_usable():
            DB.connect()
        print("✅ 数据库连接正常")
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        sys.exit(1)
    finally:
        if DB.is_connection_usable():
            DB.close()
    
    # 执行初始化
    success = init_parent_child_tables()
    if not success:
        print("❌ 表初始化失败")
        sys.exit(1)
    
    # 创建示例配置
    create_sample_config()
    
    # 验证安装
    if verify_installation():
        print("\n✅ 所有步骤完成，父子分块功能已成功安装！")
        
        print("\n📖 使用说明:")
        print("  1. 在知识库设置中启用父子分块模式")
        print("  2. 配置父子分块参数")
        print("  3. 重新解析文档以生成父子分块")
        print("  4. 使用父子检索API进行检索")
        
        print("\n🔗 相关文件:")
        print("  - API接口: /api/apps/chunk_app.py (集成父子分块端点)")
        print("  - 前端组件: /web/src/components/parent-child-config.tsx")
        print("  - 分块器: /rag/nlp/parent_child_splitter.py")
        print("  - 检索器: /rag/nlp/ragflow_parent_retriever.py")
    else:
        print("\n❌ 安装验证失败，请检查错误信息")
        sys.exit(1)


if __name__ == "__main__":
    main()