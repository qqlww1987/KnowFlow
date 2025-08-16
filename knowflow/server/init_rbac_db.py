#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RBAC数据库初始化脚本
创建RBAC相关的数据库表结构
"""

import sqlite3
import os
import sys
from datetime import datetime

def init_rbac_tables():
    """初始化RBAC数据库表"""
    db_path = 'knowflow.db'
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("开始创建RBAC数据库表...")
        
        # 1. 创建角色表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rbac_roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(100) NOT NULL,
                code VARCHAR(50) NOT NULL UNIQUE,
                description TEXT,
                role_type VARCHAR(50) NOT NULL,
                is_system BOOLEAN DEFAULT 0,
                tenant_id VARCHAR(32) DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✓ 创建角色表 rbac_roles")
        
        # 2. 创建权限表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rbac_permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(100) NOT NULL,
                code VARCHAR(50) NOT NULL UNIQUE,
                description TEXT,
                resource_type VARCHAR(50) NOT NULL,
                permission_type VARCHAR(50) NOT NULL,
                is_system BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✓ 创建权限表 rbac_permissions")
        
        # 3. 创建用户角色关联表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rbac_user_roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id VARCHAR(32) NOT NULL,
                role_id INTEGER NOT NULL,
                resource_type VARCHAR(50) DEFAULT NULL,
                resource_id VARCHAR(32) DEFAULT NULL,
                granted_by VARCHAR(32) DEFAULT NULL,
                granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP DEFAULT NULL,
                is_active BOOLEAN DEFAULT 1,
                tenant_id VARCHAR(32) NOT NULL DEFAULT 'default',
                FOREIGN KEY (role_id) REFERENCES rbac_roles(id)
            )
        """)
        print("✓ 创建用户角色关联表 rbac_user_roles")
        
        # 4. 创建角色权限关联表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rbac_role_permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role_id INTEGER NOT NULL,
                permission_id INTEGER NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (role_id) REFERENCES rbac_roles(id),
                FOREIGN KEY (permission_id) REFERENCES rbac_permissions(id)
            )
        """)
        print("✓ 创建角色权限关联表 rbac_role_permissions")
        
        # 5. 创建团队角色表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rbac_team_roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id VARCHAR(32) NOT NULL,
                role_code VARCHAR(50) NOT NULL,
                resource_type VARCHAR(50) DEFAULT NULL,
                resource_id VARCHAR(32) DEFAULT NULL,
                tenant_id VARCHAR(32) NOT NULL DEFAULT 'default',
                granted_by VARCHAR(32) DEFAULT NULL,
                granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP DEFAULT NULL,
                is_active BOOLEAN DEFAULT 1
            )
        """)
        print("✓ 创建团队角色表 rbac_team_roles")
        
        # 6. 插入系统角色
        roles = [
            ('超级管理员', 'super_admin', '拥有系统所有权限', 'super_admin', 1),
            ('管理员', 'admin', '拥有租户内所有权限', 'admin', 1),
            ('编辑者', 'editor', '可以读取、编辑和分享资源', 'editor', 1),
            ('查看者', 'viewer', '只能查看资源', 'viewer', 1),
            ('用户', 'user', '基础用户权限', 'user', 1),
            ('访客', 'guest', '访客权限，只能查看公开资源', 'guest', 1)
        ]
        
        for name, code, desc, role_type, is_system in roles:
            cursor.execute("""
                INSERT OR IGNORE INTO rbac_roles (name, code, description, role_type, is_system)
                VALUES (?, ?, ?, ?, ?)
            """, (name, code, desc, role_type, is_system))
        
        print("✓ 插入系统角色数据")
        
        # 7. 插入系统权限
        permissions = [
            ('查看知识库', 'kb_read', '查看知识库权限', 'knowledgebase', 'read', 1),
            ('编辑知识库', 'kb_write', '编辑知识库权限', 'knowledgebase', 'write', 1),
            ('删除知识库', 'kb_delete', '删除知识库权限', 'knowledgebase', 'delete', 1),
            ('管理知识库', 'kb_admin', '管理知识库权限', 'knowledgebase', 'admin', 1),
            ('分享知识库', 'kb_share', '分享知识库权限', 'knowledgebase', 'share', 1),
            ('查看文档', 'doc_read', '查看文档权限', 'document', 'read', 1),
            ('编辑文档', 'doc_write', '编辑文档权限', 'document', 'write', 1),
            ('删除文档', 'doc_delete', '删除文档权限', 'document', 'delete', 1),
            ('查看团队', 'team_read', '查看团队权限', 'team', 'read', 1),
            ('管理团队', 'team_admin', '管理团队权限', 'team', 'admin', 1)
        ]
        
        for name, code, desc, resource_type, permission_type, is_system in permissions:
            cursor.execute("""
                INSERT OR IGNORE INTO rbac_permissions (name, code, description, resource_type, permission_type, is_system)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (name, code, desc, resource_type, permission_type, is_system))
        
        print("✓ 插入系统权限数据")
        
        conn.commit()
        print("\n🎉 RBAC数据库初始化完成！")
        
        # 显示创建的表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'rbac_%'")
        tables = cursor.fetchall()
        print(f"\n创建的表: {[table[0] for table in tables]}")
        
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

if __name__ == '__main__':
    init_rbac_tables()