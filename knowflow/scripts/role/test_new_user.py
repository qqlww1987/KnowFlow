#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试新创建用户的登录和权限功能
"""

import requests
import json

def test_new_user_login():
    """
    测试新用户登录和权限功能
    """
    print("=== 测试新用户登录和权限功能 ===")
    
    # 1. 测试登录
    print("\n1. 测试用户登录...")
    login_url = "http://127.0.0.1:5000/api/v1/auth/login"
    login_data = {
        "username": "测试用户",  # 使用昵称登录
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
            print(f"✗ 登录失败: {response.status_code} - {response.text}")
            return
    except Exception as e:
        print(f"✗ 登录失败: {e}")
        return
    
    # 2. 测试获取用户角色
    print("\n2. 测试获取用户角色...")
    headers = {"Authorization": f"Bearer {token}"}
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
    
    # 3. 测试获取用户权限
    print("\n3. 测试获取用户权限...")
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
    
    # 4. 测试权限检查
    print("\n4. 测试权限检查...")
    check_url = "http://127.0.0.1:5000/api/v1/rbac/permissions/simple-check"
    check_data = {
        "permission_code": "kb_read",
        "resource_id": "test_kb_001"
    }
    
    try:
        response = requests.post(check_url, headers=headers, json=check_data)
        if response.status_code == 200:
            check_result = response.json()
            has_permission = check_result.get('has_permission', False)
            permission_code = check_result.get('permission_code', '')
            resource_id = check_result.get('resource_id', '')
            
            print(f"✓ 权限检查结果: {has_permission}")
            print(f"✓ 权限代码: {permission_code}")
            print(f"✓ 资源ID: {resource_id}")
        else:
            print(f"✗ 权限检查失败: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"✗ 权限检查失败: {e}")
    
    print("\n=== 新用户测试完成 ===")

if __name__ == "__main__":
    test_new_user_login()