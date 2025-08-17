#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import mysql.connector
from mysql.connector import Error
from datetime import datetime

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

def check_rbac_roles_duplicates():
    """检查rbac_roles表中的重复数据"""
    connection = get_db_connection()
    if not connection:
        return
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        print("=== 检查rbac_roles表结构 ===")
        cursor.execute("DESCRIBE rbac_roles")
        columns = cursor.fetchall()
        print("表结构:")
        for col in columns:
            print(f"  字段: {col['Field']}, 类型: {col['Type']}, 允许NULL: {col['Null']}, 默认值: {col['Default']}")
        
        print("\n=== 查看所有角色数据 ===")
        cursor.execute("SELECT * FROM rbac_roles ORDER BY code, name")
        all_roles = cursor.fetchall()
        print(f"总共有 {len(all_roles)} 条角色记录:")
        for role in all_roles:
            print(f"  ID: {role['id']}, 代码: {role['code']}, 名称: {role['name']}, 类型: {role['role_type']}, 租户: {role['tenant_id']}")
        
        print("\n=== 检查按code分组的重复数据 ===")
        cursor.execute("""
            SELECT code, COUNT(*) as count
            FROM rbac_roles 
            GROUP BY code
            HAVING COUNT(*) > 1
            ORDER BY count DESC
        """)
        
        code_duplicates = cursor.fetchall()
        if code_duplicates:
            print(f"发现 {len(code_duplicates)} 个重复的角色代码:")
            for dup in code_duplicates:
                print(f"  角色代码: {dup['code']}, 重复次数: {dup['count']}")
                
                # 查看具体的重复记录
                cursor.execute("SELECT * FROM rbac_roles WHERE code = %s ORDER BY created_at", (dup['code'],))
                duplicate_records = cursor.fetchall()
                for i, record in enumerate(duplicate_records):
                    print(f"    记录{i+1}: ID={record['id']}, 名称={record['name']}, 租户={record['tenant_id']}, 创建时间={record['created_at']}")
        else:
            print("未发现按code分组的重复数据")
        
        print("\n=== 检查按name分组的重复数据 ===")
        cursor.execute("""
            SELECT name, COUNT(*) as count
            FROM rbac_roles 
            GROUP BY name
            HAVING COUNT(*) > 1
            ORDER BY count DESC
        """)
        
        name_duplicates = cursor.fetchall()
        if name_duplicates:
            print(f"发现 {len(name_duplicates)} 个重复的角色名称:")
            for dup in name_duplicates:
                print(f"  角色名称: {dup['name']}, 重复次数: {dup['count']}")
                
                # 查看具体的重复记录
                cursor.execute("SELECT * FROM rbac_roles WHERE name = %s ORDER BY created_at", (dup['name'],))
                duplicate_records = cursor.fetchall()
                for i, record in enumerate(duplicate_records):
                    print(f"    记录{i+1}: ID={record['id']}, 代码={record['code']}, 租户={record['tenant_id']}, 创建时间={record['created_at']}")
        else:
            print("未发现按name分组的重复数据")
        
        print("\n=== 检查完全重复的记录 ===")
        cursor.execute("""
            SELECT code, name, role_type, tenant_id, COUNT(*) as count
            FROM rbac_roles 
            GROUP BY code, name, role_type, tenant_id
            HAVING COUNT(*) > 1
            ORDER BY count DESC
        """)
        
        full_duplicates = cursor.fetchall()
        if full_duplicates:
            print(f"发现 {len(full_duplicates)} 组完全重复的记录:")
            for dup in full_duplicates:
                print(f"  代码: {dup['code']}, 名称: {dup['name']}, 类型: {dup['role_type']}, 租户: {dup['tenant_id']}, 重复次数: {dup['count']}")
        else:
            print("未发现完全重复的记录")
        
    except Error as e:
        print(f"查询错误: {e}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

if __name__ == "__main__":
    print("🔍 开始检查rbac_roles表中的重复数据")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    check_rbac_roles_duplicates()
    
    print("\n✅ 检查完成")