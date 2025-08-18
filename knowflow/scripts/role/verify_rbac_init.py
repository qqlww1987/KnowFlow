#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证RBAC数据库初始化结果
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

def verify_rbac_init():
    """验证RBAC数据库初始化结果"""
    connection = None
    cursor = None
    
    try:
        # 建立数据库连接
        connection = get_db_connection()
        if not connection:
            print("❌ 无法连接到数据库")
            return False
            
        cursor = connection.cursor()
        
        print("🔍 验证RBAC数据库初始化结果")
        print("=" * 50)
        
        # 检查角色表
        print("\n📋 角色表 (rbac_roles):")
        cursor.execute("SELECT code, name, role_type FROM rbac_roles ORDER BY id")
        roles = cursor.fetchall()
        for code, name, role_type in roles:
            print(f"  ✓ {code:<15} {name:<12} ({role_type})")
        print(f"  总计: {len(roles)} 个角色")
        
        # 检查权限表
        print("\n🔐 权限表 (rbac_permissions):")
        cursor.execute("SELECT code, name, resource_type, permission_type FROM rbac_permissions ORDER BY resource_type, permission_type")
        permissions = cursor.fetchall()
        current_resource = None
        for code, name, resource_type, permission_type in permissions:
            if resource_type != current_resource:
                print(f"\n  [{resource_type}]")
                current_resource = resource_type
            print(f"    ✓ {code:<15} {name:<12} ({permission_type})")
        print(f"\n  总计: {len(permissions)} 个权限")
        
        # 检查用户角色关联
        print("\n👥 用户角色关联 (rbac_user_roles):")
        cursor.execute("""
            SELECT ur.user_id, r.code, ur.resource_type, ur.resource_id, ur.tenant_id
            FROM rbac_user_roles ur
            JOIN rbac_roles r ON ur.role_id = r.id
            ORDER BY ur.user_id, r.code
        """)
        user_roles = cursor.fetchall()
        current_user = None
        for user_id, role_code, resource_type, resource_id, tenant_id in user_roles:
            if user_id != current_user:
                print(f"\n  用户: {user_id}")
                current_user = user_id
            resource_info = f" (资源: {resource_type}:{resource_id})" if resource_type else ""
            print(f"    ✓ {role_code}{resource_info} [租户: {tenant_id}]")
        print(f"\n  总计: {len(user_roles)} 个用户角色关联")
        
        # 检查角色权限关联
        print("\n🔗 角色权限关联 (rbac_role_permissions):")
        cursor.execute("""
            SELECT r.code as role_code, p.code as perm_code, p.resource_type
            FROM rbac_role_permissions rp
            JOIN rbac_roles r ON rp.role_id = r.id
            JOIN rbac_permissions p ON rp.permission_id = p.id
            ORDER BY r.code, p.resource_type, p.permission_type
        """)
        role_permissions = cursor.fetchall()
        current_role = None
        for role_code, perm_code, resource_type in role_permissions:
            if role_code != current_role:
                print(f"\n  角色: {role_code}")
                current_role = role_code
            print(f"    ✓ {perm_code} ({resource_type})")
        print(f"\n  总计: {len(role_permissions)} 个角色权限关联")
        
        # 统计信息
        print("\n" + "=" * 50)
        print("📊 初始化统计:")
        print(f"  角色数量: {len(roles)}")
        print(f"  权限数量: {len(permissions)}")
        print(f"  用户角色关联: {len(user_roles)}")
        print(f"  角色权限关联: {len(role_permissions)}")
        
        # 验证必要的系统角色是否存在
        required_roles = ['super_admin', 'admin', 'editor', 'viewer', 'user', 'guest']
        existing_roles = [role[0] for role in roles]
        missing_roles = [role for role in required_roles if role not in existing_roles]
        
        if missing_roles:
            print(f"\n⚠️  缺少系统角色: {missing_roles}")
            return False
        else:
            print("\n✅ 所有必要的系统角色都已创建")
        
        # 验证必要的权限是否存在
        required_permissions = ['kb_read', 'kb_write', 'kb_admin', 'doc_read', 'doc_write']
        existing_permissions = [perm[0] for perm in permissions]
        missing_permissions = [perm for perm in required_permissions if perm not in existing_permissions]
        
        if missing_permissions:
            print(f"⚠️  缺少系统权限: {missing_permissions}")
            return False
        else:
            print("✅ 所有必要的系统权限都已创建")
        
        print("\n🎉 RBAC数据库初始化验证通过！")
        return True
            
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
    success = verify_rbac_init()
    sys.exit(0 if success else 1)