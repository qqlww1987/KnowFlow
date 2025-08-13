#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查用户角色分配情况
"""

import sys
import os
# 添加server目录到Python路径
# 从 scripts/role 向上两级到 knowflow，然后进入 server
script_dir = os.path.dirname(os.path.abspath(__file__))
knowflow_dir = os.path.dirname(os.path.dirname(script_dir))
server_dir = os.path.join(knowflow_dir, 'server')
sys.path.append(server_dir)

from database import get_db_connection

def check_user_roles():
    """检查用户角色分配情况"""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        print("=== 检查用户角色分配情况 ===")
        
        # 0. 先查看user表结构
        print("\n0. user表结构:")
        cursor.execute("DESCRIBE user")
        user_columns = cursor.fetchall()
        for col in user_columns:
            print(f"  {col[0]} - {col[1]} - {col[2]}")
        
        # 1. 检查所有用户（使用正确的字段名）
        print("\n1. 所有用户列表:")
        cursor.execute("SELECT id, nickname, email, status FROM user LIMIT 10")
        users = cursor.fetchall()
        for user in users:
            print(f"  用户ID: {user[0]}, 昵称: {user[1]}, 邮箱: {user[2]}, 状态: {user[3]}")
        
        # 2. 检查所有角色
        print("\n2. 所有角色列表:")
        cursor.execute("SELECT id, name, code, role_type FROM rbac_roles")
        roles = cursor.fetchall()
        for role in roles:
            print(f"  角色ID: {role[0]}, 名称: {role[1]}, 代码: {role[2]}, 类型: {role[3]}")
        
        # 3. 检查用户角色分配
        print("\n3. 用户角色分配情况:")
        cursor.execute("""
            SELECT u.id, u.nickname, r.name, r.code, ur.is_active
            FROM user u
            LEFT JOIN rbac_user_roles ur ON u.id = ur.user_id
            LEFT JOIN rbac_roles r ON ur.role_id = r.id
            ORDER BY u.id
        """)
        user_roles = cursor.fetchall()
        
        current_user = None
        for user_role in user_roles:
            user_id, nickname, role_name, role_code, is_active = user_role
            if current_user != user_id:
                print(f"\n  用户: {nickname} (ID: {user_id})")
                current_user = user_id
            
            if role_name:
                status = "激活" if is_active else "未激活"
                print(f"    - 角色: {role_name} ({role_code}) - {status}")
            else:
                print(f"    - 无角色分配")
        
        # 4. 特别检查admin用户的super_admin角色
        print("\n4. 检查admin用户的super_admin角色:")
        cursor.execute("""
            SELECT u.id, u.nickname, r.name, r.code, ur.is_active
            FROM user u
            JOIN rbac_user_roles ur ON u.id = ur.user_id
            JOIN rbac_roles r ON ur.role_id = r.id
            WHERE u.nickname = 'admin' AND r.code = 'super_admin'
        """)
        admin_super_role = cursor.fetchall()
        
        if admin_super_role:
            for role in admin_super_role:
                user_id, nickname, role_name, role_code, is_active = role
                status = "激活" if is_active else "未激活"
                print(f"  ✓ 找到admin用户的super_admin角色: {role_name} - {status}")
        else:
            print(f"  ✗ admin用户没有super_admin角色")
            
            # 检查admin用户是否存在
            cursor.execute("SELECT id, nickname FROM user WHERE nickname = 'admin'")
            admin_user = cursor.fetchone()
            if admin_user:
                print(f"  - admin用户存在，ID: {admin_user[0]}")
                
                # 检查super_admin角色是否存在
                cursor.execute("SELECT id, name, code FROM rbac_roles WHERE code = 'super_admin'")
                super_admin_role = cursor.fetchone()
                if super_admin_role:
                    print(f"  - super_admin角色存在，ID: {super_admin_role[0]}")
                    print(f"  - 建议执行: INSERT INTO rbac_user_roles (user_id, role_id, is_active) VALUES ('{admin_user[0]}', {super_admin_role[0]}, 1)")
                else:
                    print(f"  - super_admin角色不存在")
            else:
                print(f"  - admin用户不存在")
                
                # 查看所有用户，看看有没有类似admin的用户
                print(f"  - 查看所有用户:")
                cursor.execute("SELECT id, nickname, email FROM user")
                all_users = cursor.fetchall()
                for user in all_users:
                    print(f"    用户ID: {user[0]}, 昵称: {user[1]}, 邮箱: {user[2]}")
        
        cursor.close()
        db.close()
        
    except Exception as e:
        print(f"检查失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_user_roles()