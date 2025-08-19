#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RBAC权限管理系统数据库迁移脚本
创建权限相关的数据表和初始数据
"""

import sys
import os
import argparse
import logging
from datetime import datetime
from typing import List, Dict, Any

# 添加server目录到Python路径
# 从 scripts/role 向上两级到 knowflow，然后进入 server
script_dir = os.path.dirname(os.path.abspath(__file__))
knowflow_dir = os.path.dirname(os.path.dirname(script_dir))
server_dir = os.path.join(knowflow_dir, 'server')
sys.path.append(server_dir)

from database import get_db_connection
from models.rbac_models import SYSTEM_ROLES, SYSTEM_PERMISSIONS, RoleType, PermissionType, ResourceType

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('rbac_migration.log')
    ]
)
logger = logging.getLogger(__name__)

class RBACMigration:
    """
    RBAC权限管理系统迁移类
    """
    
    def __init__(self):
        self.db = get_db_connection()
        self.db.autocommit = True  # 启用自动提交
        self.cursor = self.db.cursor()
    
    def migrate(self):
        """
        执行完整的RBAC系统迁移
        """
        try:
            logger.info("开始RBAC权限管理系统迁移...")
            
            # 1. 创建权限相关表
            self._create_tables()
            
            # 2. 插入系统权限
            self._insert_system_permissions()
            
            # 3. 插入系统角色
            self._insert_system_roles()
            
            # 4. 建立角色权限关联
            self._setup_role_permissions()
            
            # 5. 迁移现有用户数据
            self._migrate_existing_users()
            
            # 6. 设置知识库默认权限
            self._setup_knowledgebase_permissions()
            
            # 7. 验证迁移结果
            self._verify_migration()
            
            logger.info("RBAC权限管理系统迁移完成！")
            
        except Exception as e:
            logger.error(f"RBAC迁移失败: {e}")
            self.db.rollback()
            raise
    
    def _create_tables(self):
        """
        创建RBAC相关数据表
        """
        logger.info("创建RBAC数据表...")
        
        # RBAC权限表
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS rbac_permissions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL COMMENT '权限名称',
                code VARCHAR(50) NOT NULL UNIQUE COMMENT '权限代码',
                description TEXT COMMENT '权限描述',
                resource_type ENUM('knowledgebase', 'document', 'team', 'user', 'system') NOT NULL COMMENT '资源类型',
                permission_type ENUM('read', 'write', 'delete', 'admin', 'share', 'export') NOT NULL COMMENT '权限类型',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_resource_type (resource_type),
                INDEX idx_permission_type (permission_type),
                INDEX idx_code (code)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='RBAC权限表'
        """)
        
        # RBAC角色表
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS rbac_roles (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL COMMENT '角色名称',
                code VARCHAR(50) NOT NULL COMMENT '角色代码',
                description TEXT COMMENT '角色描述',
                role_type ENUM('super_admin', 'admin', 'editor', 'viewer', 'user', 'guest') NOT NULL COMMENT '角色类型',
                is_system BOOLEAN DEFAULT FALSE COMMENT '是否为系统角色',
                tenant_id VARCHAR(50) NULL COMMENT '租户ID',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uk_code_tenant (code, tenant_id),
                INDEX idx_role_type (role_type),
                INDEX idx_tenant_id (tenant_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='RBAC角色表'
        """)
        
        # RBAC用户角色关联表
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS rbac_user_roles (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id VARCHAR(50) NOT NULL COMMENT '用户ID',
                role_id INT NOT NULL COMMENT '角色ID',
                tenant_id VARCHAR(50) NULL COMMENT '租户ID',
                resource_type ENUM('knowledgebase', 'document', 'team', 'user', 'system') NULL COMMENT '资源类型',
                resource_id VARCHAR(50) NULL COMMENT '资源ID',
                granted_by VARCHAR(50) NULL COMMENT '授权人',
                granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '授权时间',
                expires_at TIMESTAMP NULL COMMENT '过期时间',
                is_active BOOLEAN DEFAULT TRUE COMMENT '是否有效',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (role_id) REFERENCES rbac_roles(id) ON DELETE CASCADE,
                INDEX idx_user_id (user_id),
                INDEX idx_role_id (role_id),
                INDEX idx_tenant_id (tenant_id),
                INDEX idx_resource (resource_type, resource_id),
                INDEX idx_active_expires (is_active, expires_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='RBAC用户角色关联表'
        """)
        
        # RBAC角色权限关联表
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS rbac_role_permissions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                role_id INT NOT NULL COMMENT '角色ID',
                permission_id INT NOT NULL COMMENT '权限ID',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (role_id) REFERENCES rbac_roles(id) ON DELETE CASCADE,
                FOREIGN KEY (permission_id) REFERENCES rbac_permissions(id) ON DELETE CASCADE,
                UNIQUE KEY uk_role_permission (role_id, permission_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='RBAC角色权限关联表'
        """)
        
        # RBAC资源权限表（用于直接授权）
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS rbac_resource_permissions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                resource_type ENUM('knowledgebase', 'document', 'team', 'user', 'system') NOT NULL COMMENT '资源类型',
                resource_id VARCHAR(50) NOT NULL COMMENT '资源ID',
                user_id VARCHAR(50) NOT NULL COMMENT '用户ID',
                permission_type ENUM('read', 'write', 'delete', 'admin', 'share', 'export') NOT NULL COMMENT '权限类型',
                granted_by VARCHAR(50) NULL COMMENT '授权人',
                granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '授权时间',
                expires_at TIMESTAMP NULL COMMENT '过期时间',
                is_active BOOLEAN DEFAULT TRUE COMMENT '是否有效',
                tenant_id VARCHAR(50) NULL COMMENT '租户ID',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_resource (resource_type, resource_id),
                INDEX idx_user_id (user_id),
                INDEX idx_permission_type (permission_type),
                INDEX idx_tenant_id (tenant_id),
                INDEX idx_active_expires (is_active, expires_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='RBAC资源权限表'
        """)
        
        self.db.commit()
        logger.info("RBAC数据表创建完成")
    
    def _insert_system_permissions(self):
        """
        插入系统权限
        """
        logger.info("插入系统权限...")
        
        for perm_code, perm_data in SYSTEM_PERMISSIONS.items():
            try:
                self.cursor.execute("""
                    INSERT IGNORE INTO rbac_permissions (name, code, description, resource_type, permission_type)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    perm_data['name'],
                    perm_data['code'],
                    perm_data.get('description', ''),
                    perm_data['resource_type'].value,
                    perm_data['permission_type'].value
                ))
                
                if self.cursor.rowcount > 0:
                    logger.info(f"插入权限: {perm_data['name']} ({perm_code})")
                    
            except Exception as e:
                logger.error(f"插入权限失败 {perm_code}: {e}")
        
        self.db.commit()
        logger.info("系统权限插入完成")
    
    def _insert_system_roles(self):
        """
        插入系统角色
        """
        logger.info("插入系统角色...")
        
        for role_type, role_data in SYSTEM_ROLES.items():
            try:
                self.cursor.execute("""
                    INSERT IGNORE INTO rbac_roles (name, code, description, role_type, is_system)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    role_data['name'],
                    role_type.value,
                    role_data['description'],
                    role_type.value,
                    True
                ))
                
                if self.cursor.rowcount > 0:
                    logger.info(f"插入角色: {role_data['name']} ({role_type.value})")
                    
            except Exception as e:
                logger.error(f"插入角色失败 {role_type.value}: {e}")
        
        self.db.commit()
        logger.info("系统角色插入完成")
    
    def _setup_role_permissions(self):
        """
        建立角色权限关联
        """
        logger.info("建立角色权限关联...")
        
        # 先获取所有角色和权限的映射
        self.cursor.execute("SELECT id, code FROM rbac_roles")
        roles_map = {code: role_id for role_id, code in self.cursor.fetchall()}
        
        self.cursor.execute("SELECT id, code FROM rbac_permissions")
        permissions_map = {code: perm_id for perm_id, code in self.cursor.fetchall()}
        
        for role_type, role_data in SYSTEM_ROLES.items():
            try:
                if role_type.value not in roles_map:
                    continue
                
                role_id = roles_map[role_type.value]
                permissions = role_data['permissions']
                
                for perm_type in permissions:
                    # 为每种资源类型创建权限关联
                    for resource_type in ResourceType:
                        # 构造权限代码
                        if resource_type == ResourceType.KNOWLEDGEBASE:
                            perm_code = f"kb_{perm_type.value}"
                        elif resource_type == ResourceType.DOCUMENT:
                            perm_code = f"doc_{perm_type.value}"
                        elif resource_type == ResourceType.TEAM:
                            perm_code = f"team_{perm_type.value}"
                        else:
                            continue
                        
                        if perm_code in permissions_map:
                            perm_id = permissions_map[perm_code]
                            
                            # 插入角色权限关联
                            self.cursor.execute("""
                                INSERT IGNORE INTO rbac_role_permissions (role_id, permission_id)
                                VALUES (%s, %s)
                            """, (role_id, perm_id))
                
                logger.info(f"角色 {role_type.value} 权限关联完成")
                
            except Exception as e:
                logger.error(f"建立角色权限关联失败 {role_type.value}: {e}")
        
        self.db.commit()
        logger.info("角色权限关联建立完成")
    
    def _migrate_existing_users(self):
        """
        迁移现有用户数据
        """
        logger.info("迁移现有用户数据...")
        
        try:
            # 获取所有用户租户关系
            self.cursor.execute("""
                SELECT user_id, tenant_id, role FROM user_tenant
            """)
            user_tenants = self.cursor.fetchall()
            
            # 获取角色映射
            self.cursor.execute("SELECT id, code FROM rbac_roles")
            roles_map = {code: role_id for role_id, code in self.cursor.fetchall()}
            
            migrated_count = 0
            for user_id, tenant_id, old_role in user_tenants:
                try:
                    # 映射旧角色到新角色
                    new_role_code = self._map_old_role_to_new(old_role)
                    if not new_role_code or new_role_code not in roles_map:
                        continue
                    
                    role_id = roles_map[new_role_code]
                    
                    # 插入用户角色关联
                    self.cursor.execute("""
                        INSERT IGNORE INTO rbac_user_roles 
                        (user_id, role_id, tenant_id, granted_by, granted_at, is_active)
                        VALUES (%s, %s, %s, 'system', NOW(), 1)
                    """, (user_id, role_id, tenant_id))
                    
                    migrated_count += 1
                    logger.info(f"迁移用户 {user_id} 角色: {old_role} -> {new_role_code}")
                    
                except Exception as e:
                    logger.error(f"迁移用户 {user_id} 失败: {e}")
            
            # 为admin_admin用户分配管理员角色（用于简化登录系统）
            try:
                admin_user_id = "admin_admin"
                admin_role_code = "admin"
                
                if admin_role_code in roles_map:
                    role_id = roles_map[admin_role_code]
                    
                    # 插入admin_admin用户角色关联
                    self.cursor.execute("""
                        INSERT IGNORE INTO rbac_user_roles 
                        (user_id, role_id, tenant_id, granted_by, granted_at, is_active)
                        VALUES (%s, %s, 'default', 'system', NOW(), 1)
                    """, (admin_user_id, role_id))
                    
                    logger.info(f"为用户 {admin_user_id} 分配管理员角色")
                    migrated_count += 1
                        
            except Exception as e:
                logger.error(f"为admin_admin用户分配角色失败: {e}")
            
            logger.info(f"用户数据迁移完成，共迁移 {migrated_count} 条记录")
            
        except Exception as e:
            logger.error(f"迁移现有用户数据失败: {e}")
    
    def _map_old_role_to_new(self, old_role: str) -> str:
        """
        映射旧角色到新角色
        
        Args:
            old_role: 旧角色名称
            
        Returns:
            str: 新角色代码
        """
        role_mapping = {
            'owner': 'admin',
            'admin': 'admin',
            'member': 'editor',
            'editor': 'editor',
            'viewer': 'viewer',
            'guest': 'guest'
        }
        
        return role_mapping.get(old_role.lower(), 'viewer')
    
    def _setup_knowledgebase_permissions(self):
        """
        设置知识库默认权限
        """
        logger.info("设置知识库默认权限...")
        
        try:
            # 检查knowledgebases表是否存在
            self.cursor.execute("""
                SELECT COUNT(*) FROM information_schema.tables 
                WHERE table_schema = DATABASE() AND table_name = 'knowledgebases'
            """)
            table_exists = self.cursor.fetchone()[0]
            
            if not table_exists:
                logger.info("knowledgebases表不存在，跳过默认权限设置")
                return
            
            # 获取所有知识库
            self.cursor.execute("""
                SELECT id, created_by, permission FROM knowledgebases
            """)
            knowledgebases = self.cursor.fetchall()
            
            permission_count = 0
            for kb_id, created_by, permission in knowledgebases:
                try:
                    # 为创建者设置管理员权限
                    if created_by:
                        # 获取admin角色ID
                        self.cursor.execute("SELECT id FROM rbac_roles WHERE code = 'admin'")
                        admin_role_result = self.cursor.fetchone()
                        if admin_role_result:
                            admin_role_id = admin_role_result[0]
                            
                            # 插入用户角色关联（知识库级别）
                            self.cursor.execute("""
                                INSERT IGNORE INTO rbac_user_roles 
                                (user_id, role_id, resource_type, resource_id, granted_by, granted_at, is_active)
                                VALUES (%s, %s, 'knowledgebase', %s, 'system', NOW(), 1)
                            """, (created_by, admin_role_id, kb_id))
                            
                            if self.cursor.rowcount > 0:
                                permission_count += 1
                                logger.info(f"为知识库 {kb_id} 创建者 {created_by} 设置管理员权限")
                    
                    # 根据知识库的permission字段设置默认权限
                    if permission and permission != 'me':
                        # 如果是公开或团队权限，可以在这里设置相应的默认权限
                        pass
                    
                except Exception as e:
                    logger.error(f"设置知识库 {kb_id} 权限失败: {e}")
            
            logger.info(f"知识库权限设置完成，共设置 {permission_count} 条权限")
            
        except Exception as e:
            logger.error(f"设置知识库默认权限失败: {e}")
    
    def _verify_migration(self):
        """
        验证迁移结果
        """
        logger.info("验证迁移结果...")
        
        try:
            # 统计各表记录数
            tables = ['rbac_permissions', 'rbac_roles', 'rbac_user_roles', 'rbac_role_permissions', 'rbac_resource_permissions']
            for table in tables:
                try:
                    self.cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = self.cursor.fetchone()[0]
                    logger.info(f"{table} 表记录数: {count}")
                except Exception as e:
                    logger.warning(f"统计表 {table} 记录数失败: {e}")
            
            # 验证系统角色
            try:
                self.cursor.execute("SELECT code, name FROM rbac_roles WHERE is_system = 1")
                system_roles = self.cursor.fetchall()
                logger.info(f"系统角色: {[f'{role[1]}({role[0]})' for role in system_roles]}")
            except Exception as e:
                logger.warning(f"验证系统角色失败: {e}")
            
            # 验证权限数量
            try:
                self.cursor.execute("""
                    SELECT resource_type, COUNT(*) as count 
                    FROM rbac_permissions 
                    GROUP BY resource_type
                """)
                perm_stats = self.cursor.fetchall()
                for resource_type, count in perm_stats:
                    logger.info(f"{resource_type} 权限数量: {count}")
            except Exception as e:
                logger.warning(f"验证权限数量失败: {e}")
            
            logger.info("迁移结果验证完成")
            
        except Exception as e:
            logger.error(f"验证迁移结果失败: {e}")
    
    def rollback(self):
        """
        回滚RBAC迁移
        """
        logger.info("开始回滚RBAC迁移...")
        
        try:
            # 删除RBAC相关表（按依赖关系逆序删除）
            tables = [
                'rbac_resource_permissions',
                'rbac_role_permissions', 
                'rbac_user_roles',
                'rbac_roles',
                'rbac_permissions'
            ]
            
            for table in tables:
                self.cursor.execute(f"DROP TABLE IF EXISTS {table}")
                logger.info(f"删除表: {table}")
            
            self.db.commit()
            logger.info("RBAC迁移回滚完成")
            
        except Exception as e:
            logger.error(f"回滚失败: {e}")
            self.db.rollback()
            raise
    
    def __del__(self):
        """
        析构函数，关闭数据库连接
        """
        if hasattr(self, 'db') and self.db:
            self.db.close()

def main():
    """
    主函数
    """
    parser = argparse.ArgumentParser(description='RBAC权限管理系统迁移工具')
    parser.add_argument('action', choices=['migrate', 'rollback'], help='执行的操作')
    parser.add_argument('--force', action='store_true', help='强制执行（跳过确认）')
    
    args = parser.parse_args()
    
    migration = RBACMigration()
    
    try:
        if args.action == 'migrate':
            if not args.force:
                confirm = input("确定要执行RBAC迁移吗？这将创建新的数据表和权限数据。(y/N): ")
                if confirm.lower() != 'y':
                    print("迁移已取消")
                    return
            
            migration.migrate()
            print("RBAC迁移完成！")
            
        elif args.action == 'rollback':
            if not args.force:
                confirm = input("确定要回滚RBAC迁移吗？这将删除所有RBAC相关的数据表。(y/N): ")
                if confirm.lower() != 'y':
                    print("回滚已取消")
                    return
            
            migration.rollback()
            print("RBAC回滚完成！")
            
    except Exception as e:
        logger.error(f"操作失败: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()