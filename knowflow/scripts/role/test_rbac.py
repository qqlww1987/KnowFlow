#!/usr/bin/env python3

import sys
import os
import requests
import json

# 添加server目录到Python路径
# 从 scripts/role 向上两级到 knowflow，然后进入 server
script_dir = os.path.dirname(os.path.abspath(__file__))
knowflow_dir = os.path.dirname(os.path.dirname(script_dir))
server_dir = os.path.join(knowflow_dir, 'server')
sys.path.append(server_dir)

from services.rbac.permission_service import permission_service
from models.rbac_models import ResourceType, PermissionType

def test_rbac_system():
    """测试RBAC权限管理系统"""
    print("=== RBAC权限管理系统测试 ===")
    
    # 测试1: 登录获取token
    print("\n1. 测试登录功能...")
    login_url = "http://127.0.0.1:5000/api/v1/auth/login"
    login_data = {
        "username": "tom",
        "password": "12345678"
    }
    
    try:
        response = requests.post(login_url, json=login_data)
        if response.status_code == 200:
            result = response.json()
            if result.get('code') == 0:
                token = result['data']['token']
                user_id = result['data']['user_id']
                print(f"✓ 登录成功，获取到token: {token[:20]}...")
                print(f"✓ 用户ID: {user_id}")
            else:
                print(f"✗ 登录失败: {result.get('message')}")
                return
        else:
            print(f"✗ 登录请求失败: {response.status_code}")
            return
    except Exception as e:
        print(f"✗ 登录测试失败: {e}")
        return
    
    # 测试2: 健康检查
    print("\n2. 测试健康检查...")
    health_url = "http://127.0.0.1:5000/api/v1/health"
    try:
        response = requests.get(health_url)
        if response.status_code == 200:
            health_data = response.json()
            print(f"✓ 服务状态: {health_data.get('status')}")
            print(f"✓ RBAC启用状态: {health_data.get('rbac_enabled')}")
        else:
            print(f"✗ 健康检查失败: {response.status_code}")
    except Exception as e:
        print(f"✗ 健康检查失败: {e}")
    
    # 测试3: RBAC API测试
    print("\n3. 测试RBAC API...")
    headers = {"Authorization": f"Bearer {token}"}
    
    # 测试获取当前用户角色
    roles_url = "http://127.0.0.1:5000/api/v1/rbac/my/roles"
    try:
        response = requests.get(roles_url, headers=headers)
        if response.status_code == 200:
            roles_data = response.json()
            print(f"✓ 获取用户角色成功: {len(roles_data.get('roles', []))} 个角色")
            for role in roles_data.get('roles', []):
                print(f"  - {role.get('name')} ({role.get('code')})")
        else:
            print(f"✗ 获取用户角色失败: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"✗ 获取用户角色失败: {e}")
    
    # 测试获取当前用户权限
    permissions_url = "http://127.0.0.1:5000/api/v1/rbac/my/permissions"
    try:
        response = requests.get(permissions_url, headers=headers)
        if response.status_code == 200:
            permissions_data = response.json()
            print(f"✓ 获取用户权限成功: {len(permissions_data.get('permissions', []))} 个权限")
            for perm in permissions_data.get('permissions', [])[:5]:  # 只显示前5个
                print(f"  - {perm.get('name')} ({perm.get('code')})")
        else:
            print(f"✗ 获取用户权限失败: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"✗ 获取用户权限失败: {e}")
    
    # 测试4: 权限检查
    print("\n4. 测试权限检查功能...")
    try:
        # 测试超级管理员权限
        has_permission = permission_service.check_permission(
            user_id=user_id,
            resource_type=ResourceType.KNOWLEDGEBASE,
            resource_id="test_kb_001",
            permission_type=PermissionType.ADMIN
        )
        print(f"✓ 权限检查结果: {has_permission.has_permission}")
        print(f"✓ 授权角色: {has_permission.granted_roles}")
        print(f"✓ 授权原因: {has_permission.reason}")
    except Exception as e:
        print(f"✗ 权限检查失败: {e}")
    
    # 测试5: 角色授予
    print("\n5. 测试角色授予功能...")
    try:
        success = permission_service.grant_role_to_user(
            user_id="test_user_001",
            role_code="editor",
            granted_by=user_id
        )
        if success:
            print("✓ 角色授予成功")
        else:
            print("✗ 角色授予失败")
    except Exception as e:
        print(f"✗ 角色授予失败: {e}")
    
    print("\n=== RBAC测试完成 ===")

if __name__ == "__main__":
    test_rbac_system()