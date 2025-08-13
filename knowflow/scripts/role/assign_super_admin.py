#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
为用户分配super_admin角色
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

def assign_super_admin_role():
    """为tom用户分配super_admin角色"""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        print("=== 为用户分配super_admin角色 ===")
        
        # 1. 获取tom用户ID
        cursor.execute("SELECT id, nickname FROM user WHERE nickname = 'tom'")
        user = cursor.fetchone()
        if not user:
            print("✗ 找不到tom用户")
            return
        
        user_id = user[0]
        print(f"✓ 找到用户: {user[1]} (ID: {user_id})")
        
        # 2. 获取super_admin角色ID
        cursor.execute("SELECT id, name, code FROM rbac_roles WHERE code = 'super_admin' LIMIT 1")
        role = cursor.fetchone()
        if not role:
            print("✗ 找不到super_admin角色")
            return
        
        role_id = role[0]
        print(f"✓ 找到角色: {role[1]} (ID: {role_id})")
        
        # 3. 检查是否已经分配了该角色
        cursor.execute("""
            SELECT id FROM rbac_user_roles 
            WHERE user_id = %s AND role_id = %s
        """, (user_id, role_id))
        existing = cursor.fetchone()
        
        if existing:
            print(f"✓ 用户已经有super_admin角色，更新为激活状态")
            cursor.execute("""
                UPDATE rbac_user_roles 
                SET is_active = 1, updated_at = NOW()
                WHERE user_id = %s AND role_id = %s
            """, (user_id, role_id))
        else:
            print(f"✓ 为用户分配super_admin角色")
            cursor.execute("""
                INSERT INTO rbac_user_roles (user_id, role_id, is_active, created_at, updated_at)
                VALUES (%s, %s, 1, NOW(), NOW())
            """, (user_id, role_id))
        
        db.commit()
        print(f"✓ 角色分配成功")
        
        # 4. 验证分配结果
        cursor.execute("""
            SELECT u.nickname, r.name, r.code, ur.is_active
            FROM user u
            JOIN rbac_user_roles ur ON u.id = ur.user_id
            JOIN rbac_roles r ON ur.role_id = r.id
            WHERE u.id = %s AND r.code = 'super_admin'
        """, (user_id,))
        result = cursor.fetchone()
        
        if result:
            nickname, role_name, role_code, is_active = result
            status = "激活" if is_active else "未激活"
            print(f"✓ 验证成功: {nickname} 拥有 {role_name} ({role_code}) 角色 - {status}")
        else:
            print(f"✗ 验证失败: 角色分配可能未成功")
        
        cursor.close()
        db.close()
        
    except Exception as e:
        print(f"分配失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    assign_super_admin_role()