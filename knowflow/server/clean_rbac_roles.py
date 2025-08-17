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

def clean_duplicate_rbac_roles():
    """清理rbac_roles表中的重复数据，保留最新的记录"""
    connection = get_db_connection()
    if not connection:
        return
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        print("=== 开始清理rbac_roles表中的重复数据 ===")
        
        # 查找所有重复的角色（按code分组）
        cursor.execute("""
            SELECT code, COUNT(*) as count
            FROM rbac_roles 
            GROUP BY code
            HAVING COUNT(*) > 1
            ORDER BY code
        """)
        
        duplicate_codes = cursor.fetchall()
        if not duplicate_codes:
            print("未发现重复的角色数据")
            return
        
        print(f"发现 {len(duplicate_codes)} 个重复的角色代码")
        
        total_deleted = 0
        
        for dup in duplicate_codes:
            code = dup['code']
            print(f"\n处理角色代码: {code}")
            
            # 查找该代码的所有记录，按创建时间排序（最新的在前）
            cursor.execute("""
                SELECT id, name, created_at
                FROM rbac_roles 
                WHERE code = %s
                ORDER BY created_at DESC
            """, (code,))
            
            records = cursor.fetchall()
            if len(records) <= 1:
                continue
            
            # 保留第一条（最新的），删除其他的
            keep_record = records[0]
            delete_records = records[1:]
            
            print(f"  保留记录: ID={keep_record['id']}, 名称={keep_record['name']}, 创建时间={keep_record['created_at']}")
            
            for record in delete_records:
                print(f"  删除记录: ID={record['id']}, 名称={record['name']}, 创建时间={record['created_at']}")
                
                # 删除记录
                cursor.execute("DELETE FROM rbac_roles WHERE id = %s", (record['id'],))
                total_deleted += 1
        
        # 提交事务
        connection.commit()
        print(f"\n✅ 清理完成，共删除 {total_deleted} 条重复记录")
        
        # 验证清理结果
        print("\n=== 验证清理结果 ===")
        cursor.execute("""
            SELECT code, COUNT(*) as count
            FROM rbac_roles 
            GROUP BY code
            HAVING COUNT(*) > 1
        """)
        
        remaining_duplicates = cursor.fetchall()
        if remaining_duplicates:
            print(f"⚠️  仍有 {len(remaining_duplicates)} 个重复的角色代码")
            for dup in remaining_duplicates:
                print(f"  角色代码: {dup['code']}, 重复次数: {dup['count']}")
        else:
            print("✅ 所有重复数据已清理完成")
        
        # 显示最终的角色列表
        print("\n=== 最终角色列表 ===")
        cursor.execute("SELECT id, code, name, role_type, created_at FROM rbac_roles ORDER BY code")
        final_roles = cursor.fetchall()
        print(f"当前共有 {len(final_roles)} 个角色:")
        for role in final_roles:
            print(f"  ID: {role['id']}, 代码: {role['code']}, 名称: {role['name']}, 类型: {role['role_type']}")
        
    except Error as e:
        print(f"清理过程中出错: {e}")
        connection.rollback()
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def backup_rbac_roles():
    """备份rbac_roles表数据"""
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        # 创建备份表
        backup_table_name = f"rbac_roles_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        cursor.execute(f"CREATE TABLE {backup_table_name} AS SELECT * FROM rbac_roles")
        
        cursor.execute(f"SELECT COUNT(*) as count FROM {backup_table_name}")
        count = cursor.fetchone()['count']
        
        print(f"✅ 已创建备份表 {backup_table_name}，备份了 {count} 条记录")
        return True
        
    except Error as e:
        print(f"备份失败: {e}")
        return False
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

if __name__ == "__main__":
    print("🧹 开始清理rbac_roles表中的重复数据")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    # 先备份数据
    print("1. 备份原始数据...")
    if backup_rbac_roles():
        print("\n2. 开始清理重复数据...")
        clean_duplicate_rbac_roles()
    else:
        print("❌ 备份失败，取消清理操作")
    
    print("\n🎉 操作完成")