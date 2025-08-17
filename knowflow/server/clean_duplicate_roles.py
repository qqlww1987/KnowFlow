#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import mysql.connector
from mysql.connector import Error
import os
from datetime import datetime

def get_db_connection():
    """获取数据库连接"""
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

def check_duplicate_roles():
    """检查重复的角色数据"""
    connection = get_db_connection()
    if not connection:
        return
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        # 检查rbac_user_roles表中的重复数据
        print("=== 检查rbac_user_roles表中的重复数据 ===")
        cursor.execute("""
            SELECT user_id, role_id, resource_type, resource_id, tenant_id, COUNT(*) as count
            FROM rbac_user_roles 
            GROUP BY user_id, role_id, resource_type, resource_id, tenant_id
            HAVING COUNT(*) > 1
            ORDER BY count DESC
        """)
        
        user_role_duplicates = cursor.fetchall()
        if user_role_duplicates:
            print(f"发现 {len(user_role_duplicates)} 组重复的用户角色数据:")
            for dup in user_role_duplicates:
                print(f"  用户ID: {dup['user_id']}, 角色ID: {dup['role_id']}, 资源类型: {dup['resource_type']}, 资源ID: {dup['resource_id']}, 租户ID: {dup['tenant_id']}, 重复次数: {dup['count']}")
        else:
            print("未发现重复的用户角色数据")
        
        # 检查rbac_team_roles表中的重复数据
        print("\n=== 检查rbac_team_roles表中的重复数据 ===")
        cursor.execute("""
            SELECT team_id, role_code, resource_type, resource_id, tenant_id, COUNT(*) as count
            FROM rbac_team_roles 
            GROUP BY team_id, role_code, resource_type, resource_id, tenant_id
            HAVING COUNT(*) > 1
            ORDER BY count DESC
        """)
        
        team_role_duplicates = cursor.fetchall()
        if team_role_duplicates:
            print(f"发现 {len(team_role_duplicates)} 组重复的团队角色数据:")
            for dup in team_role_duplicates:
                print(f"  团队ID: {dup['team_id']}, 角色: {dup['role_code']}, 资源类型: {dup['resource_type']}, 资源ID: {dup['resource_id']}, 租户ID: {dup['tenant_id']}, 重复次数: {dup['count']}")
        else:
            print("未发现重复的团队角色数据")
        
        # 检查user_tenant表中的重复数据
        print("\n=== 检查user_tenant表中的重复数据 ===")
        cursor.execute("""
            SELECT user_id, tenant_id, role, COUNT(*) as count
            FROM user_tenant 
            GROUP BY user_id, tenant_id, role
            HAVING COUNT(*) > 1
            ORDER BY count DESC
        """)
        
        user_tenant_duplicates = cursor.fetchall()
        if user_tenant_duplicates:
            print(f"发现 {len(user_tenant_duplicates)} 组重复的用户租户数据:")
            for dup in user_tenant_duplicates:
                print(f"  用户ID: {dup['user_id']}, 租户ID: {dup['tenant_id']}, 角色: {dup['role']}, 重复次数: {dup['count']}")
        else:
            print("未发现重复的用户租户数据")
        
        return user_role_duplicates, team_role_duplicates, user_tenant_duplicates
        
    except Error as e:
        print(f"查询错误: {e}")
        return [], [], []
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def clean_duplicate_roles():
    """清理重复的角色数据"""
    connection = get_db_connection()
    if not connection:
        return
    
    try:
        cursor = connection.cursor()
        
        print("\n=== 开始清理重复数据 ===")
        
        # 清理rbac_user_roles表中的重复数据，保留最新的记录
        print("清理rbac_user_roles表中的重复数据...")
        cursor.execute("""
            DELETE ur1 FROM rbac_user_roles ur1
            INNER JOIN rbac_user_roles ur2 
            WHERE ur1.id < ur2.id 
            AND ur1.user_id = ur2.user_id 
            AND ur1.role_id = ur2.role_id 
            AND ur1.resource_type = ur2.resource_type 
            AND ur1.resource_id = ur2.resource_id 
            AND ur1.tenant_id = ur2.tenant_id
        """)
        user_role_deleted = cursor.rowcount
        print(f"删除了 {user_role_deleted} 条重复的用户角色记录")
        
        # 清理rbac_team_roles表中的重复数据，保留最新的记录
        print("清理rbac_team_roles表中的重复数据...")
        cursor.execute("""
            DELETE tr1 FROM rbac_team_roles tr1
            INNER JOIN rbac_team_roles tr2 
            WHERE tr1.id < tr2.id 
            AND tr1.team_id = tr2.team_id 
            AND tr1.role_code = tr2.role_code 
            AND tr1.resource_type = tr2.resource_type 
            AND tr1.resource_id = tr2.resource_id 
            AND tr1.tenant_id = tr2.tenant_id
        """)
        team_role_deleted = cursor.rowcount
        print(f"删除了 {team_role_deleted} 条重复的团队角色记录")
        
        # 清理user_tenant表中的重复数据，保留最新的记录
        print("清理user_tenant表中的重复数据...")
        cursor.execute("""
            DELETE ut1 FROM user_tenant ut1
            INNER JOIN user_tenant ut2 
            WHERE ut1.id < ut2.id 
            AND ut1.user_id = ut2.user_id 
            AND ut1.tenant_id = ut2.tenant_id 
            AND ut1.role = ut2.role
        """)
        user_tenant_deleted = cursor.rowcount
        print(f"删除了 {user_tenant_deleted} 条重复的用户租户记录")
        
        # 提交事务
        connection.commit()
        
        total_deleted = user_role_deleted + team_role_deleted + user_tenant_deleted
        print(f"\n总共删除了 {total_deleted} 条重复记录")
        
        if total_deleted > 0:
            print("数据清理完成！")
        else:
            print("没有发现需要清理的重复数据")
        
    except Error as e:
        print(f"清理数据时发生错误: {e}")
        connection.rollback()
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def main():
    print("🧹 开始检查和清理数据库中的重复角色数据")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    # 首先检查重复数据
    user_role_dups, team_role_dups, user_tenant_dups = check_duplicate_roles()
    
    # 如果发现重复数据，询问是否清理
    total_dups = len(user_role_dups) + len(team_role_dups) + len(user_tenant_dups)
    
    if total_dups > 0:
        print(f"\n发现总共 {total_dups} 组重复数据")
        response = input("是否要清理这些重复数据？(y/N): ")
        if response.lower() in ['y', 'yes', '是']:
            clean_duplicate_roles()
            print("\n重新检查清理结果...")
            check_duplicate_roles()
        else:
            print("取消清理操作")
    else:
        print("\n✅ 数据库中没有发现重复的角色数据")

if __name__ == "__main__":
    main()