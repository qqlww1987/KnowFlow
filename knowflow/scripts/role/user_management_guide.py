#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用户管理和角色授予操作指南
本脚本演示如何添加用户并授予角色权限
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
import hashlib
import uuid
from datetime import datetime
import requests
import json

def generate_user_id():
    """生成用户ID"""
    return str(uuid.uuid4()).replace('-', '')

def hash_password(password):
    """密码哈希"""
    return hashlib.md5(password.encode()).hexdigest()

def add_user_to_database(nickname, email, password=None):
    """
    直接在数据库中添加用户
    
    Args:
        nickname (str): 用户昵称
        email (str): 用户邮箱
        password (str): 用户密码（可选）
    
    Returns:
        str: 用户ID，如果失败返回None
    """
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        # 检查邮箱是否已存在
        cursor.execute("SELECT id FROM user WHERE email = %s", (email,))
        if cursor.fetchone():
            print(f"✗ 邮箱 {email} 已存在")
            return None
        
        # 生成用户ID和默认密码
        user_id = generate_user_id()
        if not password:
            password = "12345678"  # 默认密码
        
        # 插入用户记录
        cursor.execute("""
            INSERT INTO user (
                id, nickname, email, password, 
                create_time, create_date, update_time, update_date,
                status, is_superuser, login_channel, last_login_time,
                is_active, is_authenticated, is_anonymous
            ) VALUES (
                %s, %s, %s, %s,
                UNIX_TIMESTAMP(), CURDATE(), UNIX_TIMESTAMP(), CURDATE(),
                '1', 0, 'manual', NOW(),
                '1', '1', '0'
            )
        """, (user_id, nickname, email, hash_password(password)))
        
        db.commit()
        print(f"✓ 用户添加成功")
        print(f"  - 用户ID: {user_id}")
        print(f"  - 昵称: {nickname}")
        print(f"  - 邮箱: {email}")
        print(f"  - 默认密码: {password}")
        
        cursor.close()
        db.close()
        return user_id
        
    except Exception as e:
        print(f"添加用户失败: {e}")
        return None

def grant_role_to_user_db(user_id, role_code, granted_by=None):
    """
    直接在数据库中为用户授予角色
    
    Args:
        user_id (str): 用户ID
        role_code (str): 角色代码 (admin, editor, viewer, guest, super_admin)
        granted_by (str): 授权人ID（可选）
    
    Returns:
        bool: 是否成功
    """
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        # 获取角色ID
        cursor.execute("SELECT id, name FROM rbac_roles WHERE code = %s", (role_code,))
        role_result = cursor.fetchone()
        if not role_result:
            print(f"✗ 角色 {role_code} 不存在")
            return False
        
        role_id, role_name = role_result
        
        # 检查用户是否已有该角色
        cursor.execute("""
            SELECT id FROM rbac_user_roles 
            WHERE user_id = %s AND role_id = %s AND is_active = 1
        """, (user_id, role_id))
        
        if cursor.fetchone():
            print(f"✗ 用户已拥有角色 {role_name} ({role_code})")
            return False
        
        # 授予角色
        cursor.execute("""
            INSERT INTO rbac_user_roles (
                user_id, role_id, granted_by, is_active, created_at, updated_at
            ) VALUES (
                %s, %s, %s, 1, NOW(), NOW()
            )
        """, (user_id, role_id, granted_by))
        
        db.commit()
        print(f"✓ 成功为用户授予角色 {role_name} ({role_code})")
        
        cursor.close()
        db.close()
        return True
        
    except Exception as e:
        print(f"授予角色失败: {e}")
        return False

def grant_role_via_api(user_id, role_code, token):
    """
    通过API为用户授予角色
    
    Args:
        user_id (str): 用户ID
        role_code (str): 角色代码
        token (str): 认证令牌
    
    Returns:
        bool: 是否成功
    """
    try:
        url = f"http://127.0.0.1:5000/api/v1/rbac/users/{user_id}/roles"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        data = {
            "role_code": role_code
        }
        
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✓ API授予角色成功: {result.get('message')}")
            return True
        else:
            print(f"✗ API授予角色失败: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"API授予角色失败: {e}")
        return False

def list_available_roles():
    """
    列出所有可用角色
    """
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        cursor.execute("""
            SELECT id, name, code, description, role_type 
            FROM rbac_roles 
            ORDER BY id
        """)
        
        roles = cursor.fetchall()
        print("\n=== 可用角色列表 ===")
        for role in roles:
            role_id, name, code, description, role_type = role
            print(f"  - {name} ({code}): {description or '无描述'}")
        
        cursor.close()
        db.close()
        
    except Exception as e:
        print(f"获取角色列表失败: {e}")

def get_user_roles(user_id):
    """
    获取用户的所有角色
    
    Args:
        user_id (str): 用户ID
    """
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        cursor.execute("""
            SELECT u.nickname, r.name, r.code, ur.is_active, ur.created_at
            FROM user u
            JOIN rbac_user_roles ur ON u.id = ur.user_id
            JOIN rbac_roles r ON ur.role_id = r.id
            WHERE u.id = %s
            ORDER BY ur.created_at DESC
        """, (user_id,))
        
        roles = cursor.fetchall()
        
        if roles:
            nickname = roles[0][0]
            print(f"\n=== 用户 {nickname} 的角色 ===")
            for role in roles:
                _, role_name, role_code, is_active, created_at = role
                status = "激活" if is_active else "未激活"
                print(f"  - {role_name} ({role_code}) - {status} - 授予时间: {created_at}")
        else:
            print(f"\n用户 {user_id} 没有任何角色")
        
        cursor.close()
        db.close()
        
    except Exception as e:
        print(f"获取用户角色失败: {e}")

def list_all_users():
    """
    查询所有用户列表，包含用户名、邮箱、角色、权限等信息
    """
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        # 获取所有用户基本信息
        cursor.execute("""
            SELECT id, nickname, email, status, create_time, last_login_time
            FROM user 
            ORDER BY create_time DESC
        """)
        
        users = cursor.fetchall()
        
        if not users:
            print("\n=== 用户列表 ===")
            print("暂无用户")
            return
        
        print("\n=== 用户列表 ===")
        print(f"{'序号':<4} {'用户名':<15} {'邮箱':<25} {'状态':<6} {'角色':<30} {'权限数量':<8} {'创建时间':<20}")
        print("-" * 120)
        
        for idx, user in enumerate(users, 1):
            user_id, nickname, email, status, create_time, last_login_time = user
            
            # 获取用户角色
            cursor.execute("""
                SELECT r.name, r.code
                FROM rbac_user_roles ur
                JOIN rbac_roles r ON ur.role_id = r.id
                WHERE ur.user_id = %s AND ur.is_active = 1
                ORDER BY r.name
            """, (user_id,))
            
            user_roles = cursor.fetchall()
            roles_str = ", ".join([f"{role[0]}({role[1]})" for role in user_roles]) if user_roles else "无角色"
            
            # 获取用户权限数量
            cursor.execute("""
                SELECT COUNT(DISTINCT p.id)
                FROM rbac_user_roles ur
                JOIN rbac_role_permissions rp ON ur.role_id = rp.role_id
                JOIN rbac_permissions p ON rp.permission_id = p.id
                WHERE ur.user_id = %s AND ur.is_active = 1
            """, (user_id,))
            
            permission_count = cursor.fetchone()[0] or 0
            
            # 格式化时间
            if create_time:
                try:
                    # 如果create_time是毫秒时间戳，需要除以1000
                    if create_time > 1e10:  # 毫秒时间戳
                        create_time = create_time / 1000
                    create_time_str = datetime.fromtimestamp(create_time).strftime('%Y-%m-%d %H:%M')
                except (ValueError, OSError):
                    create_time_str = "时间格式错误"
            else:
                create_time_str = "未知"
            
            status_str = "正常" if status == '1' else "禁用"
            
            # 截断过长的角色字符串
            if len(roles_str) > 28:
                roles_str = roles_str[:25] + "..."
            
            print(f"{idx:<4} {nickname:<15} {email:<25} {status_str:<6} {roles_str:<30} {permission_count:<8} {create_time_str:<20}")
        
        print(f"\n共 {len(users)} 个用户")
        
        cursor.close()
        db.close()
        
    except Exception as e:
        print(f"获取用户列表失败: {e}")

def show_user_detail(user_identifier):
    """
    显示用户详细信息，包括所有角色和权限
    
    Args:
        user_identifier (str): 用户ID、用户名或邮箱
    """
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        # 获取用户基本信息，支持通过ID、昵称或邮箱查询
        cursor.execute("""
            SELECT id, nickname, email, status, create_time, last_login_time, is_superuser
            FROM user 
            WHERE id = %s OR nickname = %s OR email = %s
        """, (user_identifier, user_identifier, user_identifier))
        
        user = cursor.fetchone()
        if not user:
            print(f"用户 {user_identifier} 不存在")
            return
        
        user_id, nickname, email, status, create_time, last_login_time, is_superuser = user
        
        print(f"\n=== 用户详细信息 ===")
        print(f"用户ID: {user_id}")
        print(f"昵称: {nickname}")
        print(f"邮箱: {email}")
        print(f"状态: {'正常' if status == '1' else '禁用'}")
        print(f"超级用户: {'是' if is_superuser else '否'}")
        
        if create_time:
            try:
                # 如果create_time是毫秒时间戳，需要除以1000
                if create_time > 1e10:  # 毫秒时间戳
                    create_time = create_time / 1000
                create_time_str = datetime.fromtimestamp(create_time).strftime('%Y-%m-%d %H:%M:%S')
                print(f"创建时间: {create_time_str}")
            except (ValueError, OSError):
                print(f"创建时间: 时间格式错误")
        
        if last_login_time:
            print(f"最后登录: {last_login_time}")
        
        # 获取用户角色
        cursor.execute("""
            SELECT r.name, r.code, r.description, ur.is_active, ur.created_at
            FROM rbac_user_roles ur
            JOIN rbac_roles r ON ur.role_id = r.id
            WHERE ur.user_id = %s
            ORDER BY ur.created_at DESC
        """, (user_id,))
        
        roles = cursor.fetchall()
        
        print(f"\n=== 用户角色 ({len(roles)}) ===")
        if roles:
            for role in roles:
                role_name, role_code, description, is_active, created_at = role
                status_str = "激活" if is_active else "未激活"
                print(f"  - {role_name} ({role_code}) - {status_str}")
                if description:
                    print(f"    描述: {description}")
                print(f"    授予时间: {created_at}")
        else:
            print("  无角色")
        
        # 获取用户权限
        cursor.execute("""
            SELECT DISTINCT p.name, p.code, p.description, p.permission_type
            FROM rbac_user_roles ur
            JOIN rbac_role_permissions rp ON ur.role_id = rp.role_id
            JOIN rbac_permissions p ON rp.permission_id = p.id
            WHERE ur.user_id = %s AND ur.is_active = 1
            ORDER BY p.permission_type, p.name
        """, (user_id,))
        
        permissions = cursor.fetchall()
        
        print(f"\n=== 用户权限 ({len(permissions)}) ===")
        if permissions:
            current_type = None
            for permission in permissions:
                perm_name, perm_code, description, perm_type = permission
                if perm_type != current_type:
                    current_type = perm_type
                    print(f"\n  [{perm_type}]")
                print(f"    - {perm_name} ({perm_code})")
                if description:
                    print(f"      描述: {description}")
        else:
            print("  无权限")
        
        cursor.close()
        db.close()
        
    except Exception as e:
        print(f"获取用户详细信息失败: {e}")

def demo_add_user_and_grant_roles():
    """
    演示添加用户并授予角色的完整流程
    """
    print("=== 用户管理和角色授予演示 ===")
    
    # 1. 列出可用角色
    list_available_roles()
    
    # 2. 添加新用户
    print("\n=== 添加新用户 ===")
    nickname = "测试用户"
    email = "test@example.com"
    password = "test123456"
    
    user_id = add_user_to_database(nickname, email, password)
    if not user_id:
        print("用户添加失败，演示结束")
        return
    
    # 3. 为用户授予角色
    print("\n=== 授予角色 ===")
    
    # 授予编辑者角色
    success1 = grant_role_to_user_db(user_id, "editor")
    
    # 授予查看者角色
    success2 = grant_role_to_user_db(user_id, "viewer")
    
    # 4. 查看用户角色
    get_user_roles(user_id)
    
    print("\n=== 演示完成 ===")
    print(f"新用户信息:")
    print(f"  - 用户ID: {user_id}")
    print(f"  - 昵称: {nickname}")
    print(f"  - 邮箱: {email}")
    print(f"  - 密码: {password}")
    print(f"\n可以使用以下信息登录系统测试权限功能")

def interactive_user_management():
    """
    交互式用户管理
    """
    print("=== 交互式用户管理 ===")
    print("1. 添加用户")
    print("2. 授予角色")
    print("3. 查看用户角色")
    print("4. 查看可用角色")
    print("5. 查看所有用户列表")
    print("6. 查看用户详细信息")
    print("7. 演示完整流程")
    
    choice = input("\n请选择操作 (1-7): ").strip()
    
    if choice == "1":
        nickname = input("请输入用户昵称: ").strip()
        email = input("请输入用户邮箱: ").strip()
        password = input("请输入用户密码 (留空使用默认密码12345678): ").strip()
        if not password:
            password = None
        
        user_id = add_user_to_database(nickname, email, password)
        if user_id:
            print(f"\n用户添加成功，用户ID: {user_id}")
    
    elif choice == "2":
        user_id = input("请输入用户ID: ").strip()
        role_code = input("请输入角色代码 (admin/editor/viewer/guest/super_admin): ").strip()
        
        success = grant_role_to_user_db(user_id, role_code)
        if success:
            print("\n角色授予成功")
    
    elif choice == "3":
        user_id = input("请输入用户ID: ").strip()
        get_user_roles(user_id)
    
    elif choice == "4":
        list_available_roles()
    
    elif choice == "5":
        list_all_users()
    
    elif choice == "6":
        user_identifier = input("请输入用户名、用户ID或邮箱: ").strip()
        show_user_detail(user_identifier)
    
    elif choice == "7":
        demo_add_user_and_grant_roles()
    
    else:
        print("无效选择")

if __name__ == "__main__":
    # 可以选择运行演示或交互式管理
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "demo":
        demo_add_user_and_grant_roles()
    else:
        interactive_user_management()