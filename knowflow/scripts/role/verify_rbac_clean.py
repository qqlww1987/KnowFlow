#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证RBAC数据库清空结果
"""

import sys
import os
import mysql.connector
from mysql.connector import Error

# 添加server目录到Python路径
script_dir = os.path.dirname(os.path.abspath(__file__))
knowflow_dir = os.path.dirname(os.path.dirname(script_dir))
server_dir = os.path.join(knowflow_dir, 'server')
sys.path.append(server_dir)

try:
    from database import get_db_connection
except ImportError:
    # 如果无法导入，使用默认配置
    def get_db_connection():
        """建立数据库连接"""
        try:
            connection = mysql.connector.connect(
                host='localhost',
                database='rag_flow',
                user='root',
                password='infini_rag_flow',
                port=5455
            )
            return connection
        except Error as e:
            print(f"数据库连接错误: {e}")
            return None

def verify_rbac_clean():
    """验证RBAC数据库清空结果"""
    connection = None
    cursor = None
    
    try:
        # 建立数据库连接
        connection = get_db_connection()
        if not connection:
            print("❌ 无法连接到数据库")
            return False
            
        cursor = connection.cursor()
        
        print("🔍 验证RBAC数据库清空结果")
        print("=" * 40)
        
        # 定义需要检查的RBAC表
        rbac_tables = [
            'rbac_roles',
            'rbac_permissions', 
            'rbac_user_roles',
            'rbac_role_permissions',
            'rbac_team_roles'
        ]
        
        # 检查每个表的记录数
        total_records = 0
        all_empty = True
        
        for table in rbac_tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                status = "✅ 空" if count == 0 else f"❌ {count} 条记录"
                print(f"  {table:<25} {status}")
                total_records += count
                if count > 0:
                    all_empty = False
            except Error as e:
                print(f"  {table:<25} ❌ 查询失败: {e}")
                all_empty = False
        
        print("=" * 40)
        print(f"总记录数: {total_records}")
        
        if all_empty:
            print("🎉 验证通过：所有RBAC表都已清空")
            return True
        else:
            print("⚠️  验证失败：仍有数据残留")
            return False
            
    except Error as e:
        print(f"❌ 验证过程中发生错误: {e}")
        return False
        
    finally:
        # 关闭数据库连接
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

if __name__ == '__main__':
    success = verify_rbac_clean()
    sys.exit(0 if success else 1)