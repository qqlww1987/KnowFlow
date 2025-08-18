#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试用户token和权限问题
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from itsdangerous.url_safe import URLSafeTimedSerializer as Serializer
import mysql.connector
from datetime import datetime

# 数据库配置（根据conf/service_conf.yaml）
DB_CONFIG = {
    'host': 'localhost',
    'port': 5455,  # 使用配置文件中的端口
    'user': 'root',
    'password': 'infini_rag_flow',  # 使用配置文件中的密码
    'database': 'rag_flow',  # 使用配置文件中的数据库名
    'charset': 'utf8mb4'
}

# JWT密钥（需要与系统配置一致）
# 根据settings.py的逻辑，如果没有配置secret_key，会使用当前日期
from datetime import date
SECRET_KEY = str(date.today())  # 默认使用当前日期作为密钥

def get_db_connection():
    """获取数据库连接"""
    return mysql.connector.connect(**DB_CONFIG)

def decode_jwt_token(token):
    """解码JWT token"""
    try:
        jwt = Serializer(secret_key=SECRET_KEY)
        access_token = str(jwt.loads(token))
        return access_token
    except Exception as e:
        print(f"JWT token解码失败: {e}")
        return None

def get_user_by_access_token(access_token):
    """根据access_token查询用户信息"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        query = """
        SELECT id, nickname, email, status, create_time, last_login_time, is_superuser, access_token
        FROM user 
        WHERE access_token = %s AND status = '1'
        """
        
        cursor.execute(query, (access_token,))
        user = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        return user
    except Exception as e:
        print(f"查询用户失败: {e}")
        return None

def get_user_rbac_roles(user_id):
    """获取用户的RBAC角色"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        query = """
        SELECT DISTINCT 
            ur.user_id,
            ur.resource_id,
            ur.resource_type,
            r.code as role_code,
            r.name as role_name,
            ur.granted_at,
            ur.is_active
        FROM rbac_user_roles ur
        JOIN rbac_roles r ON ur.role_id = r.id
        WHERE ur.user_id = %s AND ur.is_active = 1
        ORDER BY ur.granted_at DESC
        """
        
        cursor.execute(query, (user_id,))
        roles = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return roles
    except Exception as e:
        print(f"查询用户角色失败: {e}")
        return []

def get_user_kb_permissions(user_id):
    """获取用户的知识库权限"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # 查询用户直接拥有的知识库权限
        query = """
        SELECT DISTINCT 
            ur.user_id,
            ur.resource_id as kb_id,
            r.code as role_code,
            r.name as role_name,
            ur.granted_at,
            kb.name as kb_name,
            kb.tenant_id,
            kb.status as kb_status
        FROM rbac_user_roles ur
        JOIN rbac_roles r ON ur.role_id = r.id
        LEFT JOIN knowledgebase kb ON ur.resource_id = kb.id
        WHERE ur.user_id = %s 
            AND ur.is_active = 1
            AND ur.resource_type = 'knowledgebase'
        ORDER BY ur.granted_at DESC
        """
        
        cursor.execute(query, (user_id,))
        kb_permissions = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return kb_permissions
    except Exception as e:
        print(f"查询用户知识库权限失败: {e}")
        return []

def get_all_knowledgebases():
    """获取所有知识库"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        query = """
        SELECT k.id, k.name, k.tenant_id, k.permission, k.create_time, k.created_by,
               u.nickname as owner_name, u.email as owner_email
        FROM knowledgebase k
        LEFT JOIN user u ON k.tenant_id = u.id
        WHERE k.status = 1
        ORDER BY k.create_time DESC
        """
        cursor.execute(query)
        kbs = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return kbs
    except Exception as e:
        print(f"查询知识库失败: {e}")
        return []

def get_user_tenants(user_id):
    """获取用户的租户关联"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        query = """
        SELECT ut.tenant_id, ut.role, t.nickname as tenant_name
        FROM user_tenant ut
        LEFT JOIN user t ON ut.tenant_id = t.id
        WHERE ut.user_id = %s
        """
        cursor.execute(query, (user_id,))
        tenants = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return tenants
    except Exception as e:
        print(f"查询用户租户关联失败: {e}")
        return []

def debug_user_token(jwt_token):
    """调试用户token和权限"""
    print("=== 用户Token调试 ===")
    print(f"JWT Token: {jwt_token[:50]}...")
    
    # 1. 解码JWT token
    access_token = decode_jwt_token(jwt_token)
    if not access_token:
        print("❌ JWT token解码失败")
        return
    
    print(f"Access Token: {access_token}")
    
    # 2. 查询用户信息
    user = get_user_by_access_token(access_token)
    if not user:
        print("❌ 未找到对应的用户")
        return
    
    print(f"\n=== 用户信息 ===")
    print(f"用户ID: {user['id']}")
    print(f"昵称: {user['nickname']}")
    print(f"邮箱: {user['email']}")
    print(f"状态: {'正常' if user['status'] == '1' else '禁用'}")
    print(f"超级用户: {'是' if user['is_superuser'] else '否'}")
    
    user_id = user['id']
    
    # 3. 查询用户RBAC角色
    roles = get_user_rbac_roles(user_id)
    print(f"\n=== RBAC角色 ({len(roles)}个) ===")
    if roles:
        for role in roles:
            print(f"- 角色: {role['role_name']} ({role['role_code']})")
            print(f"  资源: {role['resource_type']}:{role['resource_id']}")
            print(f"  授权时间: {role['granted_at']}")
            print(f"  状态: {'活跃' if role['is_active'] else '禁用'}")
            print()
    else:
        print("❌ 用户没有任何RBAC角色")
    
    # 4. 查询用户租户关联
    user_tenants = get_user_tenants(user_id)
    print(f"\n=== 用户租户关联 ({len(user_tenants)}个) ===")
    if user_tenants:
        for tenant in user_tenants:
            print(f"- 租户ID: {tenant['tenant_id']}")
            print(f"  租户名称: {tenant['tenant_name']}")
            print(f"  角色: {tenant['role']}")
            print()
    else:
        print("❌ 用户没有任何租户关联")
    
    # 5. 查询用户知识库权限
    kb_permissions = get_user_kb_permissions(user_id)
    print(f"=== 知识库权限 ({len(kb_permissions)}个) ===")
    if kb_permissions:
        for perm in kb_permissions:
            print(f"- 知识库: {perm['kb_name']} (ID: {perm['kb_id']})")
            print(f"  角色: {perm['role_name']} ({perm['role_code']})")
            print(f"  租户: {perm['tenant_id']}")
            print(f"  状态: {perm['kb_status']}")
            print(f"  授权时间: {perm['granted_at']}")
            print()
    else:
        print("❌ 用户没有任何知识库权限")
    
    # 6. 显示所有知识库
    all_kbs = get_all_knowledgebases()
    print(f"=== 系统中所有知识库 ({len(all_kbs)}个) ===")
    for kb in all_kbs:
        print(f"- {kb['name']} (ID: {kb['id']})")
        print(f"  租户: {kb['tenant_id']}")
        print(f"  拥有者: {kb['owner_name']} ({kb['owner_email']})")
        print(f"  权限模式: {kb['permission']}")
        print(f"  创建时间: {kb['create_time']}")
        print()
    
    # 7. 分析问题
    print("=== 问题分析 ===")
    if not roles:
        print("❌ 问题1: 用户没有任何RBAC角色，无法访问知识库")
    
    if not kb_permissions:
        print("❌ 问题2: 用户没有任何知识库的直接权限")
    
    # 检查是否有系统级角色
    system_roles = [r for r in roles if not r['resource_id'] or r['resource_id'] == 'system']
    if system_roles:
        print(f"✅ 用户有系统级角色: {[r['role_code'] for r in system_roles]}")
    else:
        print("❌ 问题3: 用户没有系统级角色")
    
    # 检查租户权限 - 通过租户关联表
    if user_tenants:
        tenant_ids = [t['tenant_id'] for t in user_tenants]
        tenant_kbs = [kb for kb in all_kbs if kb['tenant_id'] in tenant_ids]
        if tenant_kbs:
            print(f"✅ 用户通过租户关联可访问 {len(tenant_kbs)} 个知识库")
            for kb in tenant_kbs:
                print(f"  - {kb['name']} (租户: {kb['tenant_id']})")
        else:
            print("❌ 问题4: 用户关联的租户没有拥有任何知识库")
    else:
        # 检查用户ID是否直接作为租户ID
        user_tenant_id = user['id']
        tenant_kbs = [kb for kb in all_kbs if kb['tenant_id'] == user_tenant_id]
        if tenant_kbs:
            print(f"✅ 用户作为租户拥有 {len(tenant_kbs)} 个知识库")
        else:
            print("❌ 问题5: 用户没有租户关联，且用户ID不匹配任何知识库的租户ID")

if __name__ == "__main__":
    # 用户提供的JWT token
    jwt_token = "Ijc1NTllODI4N2JlZTExZjA5YjU0NjZmYzUxYWM1OGRmIg.aKKwZg.SyqDxxRx2pkz0yBvFb712u6E_hA"
    
    debug_user_token(jwt_token)