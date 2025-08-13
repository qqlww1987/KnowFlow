#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RBAC权限管理服务
提供权限检查、角色管理、用户权限查询等功能
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import logging
from database import get_db_connection
from models.rbac_models import (
    Permission, Role, UserRole, RolePermission,
    PermissionCheck, PermissionType, ResourceType, RoleType,
    SYSTEM_ROLES, SYSTEM_PERMISSIONS
)

logger = logging.getLogger(__name__)

class PermissionService:
    """权限管理服务类"""
    
    def __init__(self):
        pass
    
    def _get_db_connection(self):
        """获取数据库连接"""
        return get_db_connection()
    
    def check_permission(self, user_id: str, resource_type: ResourceType, 
                        resource_id: str, permission_type: PermissionType,
                        tenant_id: Optional[str] = None) -> PermissionCheck:
        """
        检查用户是否有指定资源的权限
        
        Args:
            user_id: 用户ID
            resource_type: 资源类型
            resource_id: 资源ID
            permission_type: 权限类型
            tenant_id: 租户ID
            
        Returns:
            PermissionCheck: 权限检查结果
        """
        try:
            # 1. 检查超级管理员权限
            if self._is_super_admin(user_id):
                return PermissionCheck(
                    has_permission=True,
                    user_id=user_id,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    permission_type=permission_type,
                    granted_roles=["super_admin"],
                    reason="超级管理员权限"
                )
            
            # 2. 检查直接资源权限
            direct_permission = self._check_direct_permission(
                user_id, resource_type, resource_id, permission_type, tenant_id
            )
            if direct_permission:
                return PermissionCheck(
                    has_permission=True,
                    user_id=user_id,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    permission_type=permission_type,
                    granted_roles=["direct"],
                    reason="直接权限授权"
                )
            
            # 3. 检查角色权限
            role_permission = self._check_role_permission(
                user_id, resource_type, resource_id, permission_type, tenant_id
            )
            if role_permission[0]:
                return PermissionCheck(
                    has_permission=True,
                    user_id=user_id,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    permission_type=permission_type,
                    granted_roles=role_permission[1],
                    reason="角色权限授权"
                )
            
            # 4. 检查资源所有者权限
            if self._is_resource_owner(user_id, resource_type, resource_id):
                return PermissionCheck(
                    has_permission=True,
                    user_id=user_id,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    permission_type=permission_type,
                    granted_roles=["owner"],
                    reason="资源所有者权限"
                )
            
            return PermissionCheck(
                has_permission=False,
                user_id=user_id,
                resource_type=resource_type,
                resource_id=resource_id,
                permission_type=permission_type,
                reason="无相关权限"
            )
            
        except Exception as e:
            logger.error(f"权限检查失败: {e}")
            return PermissionCheck(
                has_permission=False,
                user_id=user_id,
                resource_type=resource_type,
                resource_id=resource_id,
                permission_type=permission_type,
                reason=f"权限检查异常: {str(e)}"
            )
    
    def _is_super_admin(self, user_id: str) -> bool:
        """检查是否为超级管理员"""
        try:
            db = self._get_db_connection()
            cursor = db.cursor()
            
            # 1. 首先检查用户表中的 is_superuser 字段
            cursor.execute("""
                SELECT is_superuser FROM user WHERE id = %s
            """, (user_id,))
            user_result = cursor.fetchone()
            if user_result and user_result[0] == 1:
                return True
            
            # 2. 然后检查RBAC角色表中的 super_admin 角色
            cursor.execute("""
                SELECT COUNT(*) FROM rbac_user_roles ur
                JOIN rbac_roles r ON ur.role_id = r.id
                WHERE ur.user_id = %s AND r.code = 'super_admin' AND ur.is_active = 1
            """, (user_id,))
            return cursor.fetchone()[0] > 0
            
        except Exception as e:
            logger.error(f"检查超级管理员权限失败: {e}")
            return False
    
    def _check_direct_permission(self, user_id: str, resource_type: ResourceType,
                               resource_id: str, permission_type: PermissionType,
                               tenant_id: Optional[str] = None) -> bool:
        """检查直接权限"""
        try:
            db = self._get_db_connection()
            cursor = db.cursor()
            sql = """
                SELECT COUNT(*) FROM rbac_resource_permissions
                WHERE user_id = %s AND resource_type = %s AND resource_id = %s
                AND permission_type = %s AND is_active = 1
                AND (expires_at IS NULL OR expires_at > NOW())
            """
            params = [user_id, resource_type.value, resource_id, permission_type.value]
            
            if tenant_id:
                sql += " AND tenant_id = %s"
                params.append(tenant_id)
            
            cursor.execute(sql, params)
            return cursor.fetchone()[0] > 0
        except Exception as e:
            logger.error(f"检查直接权限失败: {e}")
            return False
    
    def _check_role_permission(self, user_id: str, resource_type: ResourceType,
                             resource_id: str, permission_type: PermissionType,
                             tenant_id: Optional[str] = None) -> Tuple[bool, List[str]]:
        """检查角色权限"""
        try:
            db = self._get_db_connection()
            cursor = db.cursor()
            sql = """
                SELECT DISTINCT r.code, r.name FROM rbac_user_roles ur
                JOIN rbac_roles r ON ur.role_id = r.id
                JOIN rbac_role_permissions rp ON r.id = rp.role_id
                JOIN rbac_permissions p ON rp.permission_id = p.id
                WHERE ur.user_id = %s AND ur.is_active = 1
                AND p.resource_type = %s AND p.permission_type = %s
                AND (ur.expires_at IS NULL OR ur.expires_at > NOW())
                AND (ur.resource_id IS NULL OR ur.resource_id = %s)
            """
            params = [user_id, resource_type.value, permission_type.value, resource_id]
            
            if tenant_id:
                sql += " AND ur.tenant_id = %s"
                params.append(tenant_id)
            
            cursor.execute(sql, params)
            roles = cursor.fetchall()
            
            if roles:
                role_names = [role[1] for role in roles]
                return True, role_names
            return False, []
        except Exception as e:
            logger.error(f"检查角色权限失败: {e}")
            return False, []
    
    def _is_resource_owner(self, user_id: str, resource_type: ResourceType, resource_id: str) -> bool:
        """检查是否为资源所有者"""
        try:
            db = self._get_db_connection()
            cursor = db.cursor()
            
            if resource_type == ResourceType.KNOWLEDGEBASE:
                # 检查knowledgebase表是否存在
                cursor.execute("""
                    SELECT COUNT(*) FROM information_schema.tables 
                    WHERE table_schema = DATABASE() AND table_name = 'knowledgebase'
                """)
                table_exists = cursor.fetchone()[0]
                
                if not table_exists:
                    logger.warning("knowledgebase表不存在，跳过资源所有者检查")
                    return False
                
                cursor.execute("""
                    SELECT COUNT(*) FROM knowledgebase
                    WHERE id = %s AND created_by = %s
                """, (resource_id, user_id))
                return cursor.fetchone()[0] > 0
            elif resource_type == ResourceType.TEAM:
                cursor.execute("""
                    SELECT COUNT(*) FROM user_tenant
                    WHERE tenant_id = %s AND user_id = %s AND role = 'owner'
                """, (resource_id, user_id))
                return cursor.fetchone()[0] > 0
            
            return False
        except Exception as e:
            logger.error(f"检查资源所有者失败: {e}")
            return False
        finally:
            if 'cursor' in locals():
                cursor.close()
    
    def grant_role_to_user(self, user_id: str, role_code: str, 
                          granted_by: str, tenant_id: Optional[str] = None,
                          resource_type: Optional[ResourceType] = None,
                          resource_id: Optional[str] = None,
                          expires_at: Optional[datetime] = None) -> bool:
        """
        为用户授予角色
        
        Args:
            user_id: 用户ID
            role_code: 角色代码
            granted_by: 授权人
            tenant_id: 租户ID
            resource_type: 资源类型（可选，用于资源级权限）
            resource_id: 资源ID（可选，用于资源级权限）
            expires_at: 过期时间（可选）
            
        Returns:
            bool: 是否成功
        """
        cursor = None
        db = None
        try:
            db = self._get_db_connection()
            cursor = db.cursor()
            
            # 获取角色ID
            cursor.execute("SELECT id FROM rbac_roles WHERE code = %s", (role_code,))
            role_result = cursor.fetchone()
            if not role_result:
                logger.error(f"角色不存在: {role_code}")
                return False
            
            role_id = role_result[0]
            
            # 检查是否已存在相同的角色授权
            check_sql = """
                SELECT id FROM rbac_user_roles
                WHERE user_id = %s AND role_id = %s
            """
            check_params = [user_id, role_id]
            
            if tenant_id:
                check_sql += " AND tenant_id = %s"
                check_params.append(tenant_id)
            if resource_type:
                check_sql += " AND resource_type = %s"
                check_params.append(resource_type.value)
            if resource_id:
                check_sql += " AND resource_id = %s"
                check_params.append(resource_id)
            
            cursor.execute(check_sql, check_params)
            existing = cursor.fetchone()
            
            if existing:
                # 更新现有记录
                update_sql = """
                    UPDATE rbac_user_roles SET
                    is_active = 1, granted_by = %s, granted_at = NOW(),
                    expires_at = %s, updated_at = NOW()
                    WHERE id = %s
                """
                cursor.execute(update_sql, (granted_by, expires_at, existing[0]))
            else:
                # 插入新记录
                insert_sql = """
                    INSERT INTO rbac_user_roles
                    (user_id, role_id, tenant_id, resource_type, resource_id,
                     granted_by, granted_at, expires_at, is_active, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s, 1, NOW())
                """
                cursor.execute(insert_sql, (
                    user_id, role_id, tenant_id,
                    resource_type.value if resource_type else None,
                    resource_id, granted_by, expires_at
                ))
            
            logger.info(f"成功为用户 {user_id} 授予角色 {role_code}")
            return True
            
        except Exception as e:
            logger.error(f"授予角色失败: {e}")
            return False
        finally:
            if cursor:
                cursor.close()
    
    def revoke_role_from_user(self, user_id: str, role_code: str,
                             tenant_id: Optional[str] = None,
                             resource_id: Optional[str] = None) -> bool:
        """
        撤销用户角色
        
        Args:
            user_id: 用户ID
            role_code: 角色代码
            tenant_id: 租户ID
            resource_id: 资源ID
            
        Returns:
            bool: 是否成功
        """
        try:
            db = self._get_db_connection()
            cursor = db.cursor()
            
            sql = """
                UPDATE rbac_user_roles ur
                JOIN rbac_roles r ON ur.role_id = r.id
                SET ur.is_active = 0, ur.updated_at = NOW()
                WHERE ur.user_id = %s AND r.code = %s
            """
            params = [user_id, role_code]
            
            if tenant_id:
                sql += " AND ur.tenant_id = %s"
                params.append(tenant_id)
            if resource_id:
                sql += " AND ur.resource_id = %s"
                params.append(resource_id)
            
            cursor.execute(sql, params)
            db.commit()
            
            logger.info(f"成功撤销用户 {user_id} 的角色 {role_code}")
            return True
            
        except Exception as e:
            if db:
                db.rollback()
            logger.error(f"撤销角色失败: {e}")
            return False
    
    def get_user_roles(self, user_id: str, tenant_id: Optional[str] = None) -> List[Role]:
        """
        获取用户的所有角色
        
        Args:
            user_id: 用户ID
            tenant_id: 租户ID
            
        Returns:
            List[Role]: 角色列表
        """
        try:
            db = self._get_db_connection()
            cursor = db.cursor()
            
            sql = """
                SELECT DISTINCT r.id, r.name, r.code, r.description, r.role_type,
                       r.is_system, r.tenant_id, r.created_at, r.updated_at
                FROM rbac_user_roles ur
                JOIN rbac_roles r ON ur.role_id = r.id
                WHERE ur.user_id = %s AND ur.is_active = 1
                AND (ur.expires_at IS NULL OR ur.expires_at > NOW())
            """
            params = [user_id]
            
            if tenant_id:
                sql += " AND ur.tenant_id = %s"
                params.append(tenant_id)
            
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            
            roles = []
            for row in rows:
                role = Role(
                    id=row[0],
                    name=row[1],
                    code=row[2],
                    description=row[3],
                    role_type=RoleType(row[4]),
                    is_system=bool(row[5]),
                    tenant_id=row[6],
                    created_at=row[7],
                    updated_at=row[8]
                )
                roles.append(role)
            
            return roles
            
        except Exception as e:
            logger.error(f"获取用户角色失败: {e}")
            return []
    
    def get_user_permissions(self, user_id: str, resource_type: Optional[ResourceType] = None,
                           tenant_id: Optional[str] = None) -> List[Permission]:
        """
        获取用户的所有权限
        
        Args:
            user_id: 用户ID
            resource_type: 资源类型过滤
            tenant_id: 租户ID
            
        Returns:
            List[Permission]: 权限列表
        """
        try:
            db = self._get_db_connection()
            cursor = db.cursor()
            
            sql = """
                SELECT DISTINCT p.id, p.name, p.code, p.description,
                       p.resource_type, p.permission_type, p.created_at, p.updated_at
                FROM rbac_user_roles ur
                JOIN rbac_roles r ON ur.role_id = r.id
                JOIN rbac_role_permissions rp ON r.id = rp.role_id
                JOIN rbac_permissions p ON rp.permission_id = p.id
                WHERE ur.user_id = %s AND ur.is_active = 1
                AND (ur.expires_at IS NULL OR ur.expires_at > NOW())
            """
            params = [user_id]
            
            if resource_type:
                sql += " AND p.resource_type = %s"
                params.append(resource_type.value)
            
            if tenant_id:
                sql += " AND ur.tenant_id = %s"
                params.append(tenant_id)
            
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            
            permissions = []
            for row in rows:
                permission = Permission(
                    id=row[0],
                    name=row[1],
                    code=row[2],
                    description=row[3],
                    resource_type=ResourceType(row[4]),
                    permission_type=PermissionType(row[5]),
                    created_at=row[6],
                    updated_at=row[7]
                )
                permissions.append(permission)
            
            return permissions
            
        except Exception as e:
            logger.error(f"获取用户权限失败: {e}")
            return []
    
    def has_permission(self, user_id: str, permission_code: str,
                      resource_id: Optional[str] = None,
                      tenant_id: Optional[str] = None) -> bool:
        """
        简化的权限检查方法
        
        Args:
            user_id: 用户ID
            permission_code: 权限代码
            resource_id: 资源ID
            tenant_id: 租户ID
            
        Returns:
            bool: 是否有权限
        """
        try:
            # 从权限代码解析资源类型和权限类型
            if permission_code.startswith('kb_'):
                resource_type = ResourceType.KNOWLEDGEBASE
                perm_type = permission_code.replace('kb_', '')
            elif permission_code.startswith('doc_'):
                resource_type = ResourceType.DOCUMENT
                perm_type = permission_code.replace('doc_', '')
            elif permission_code.startswith('team_'):
                resource_type = ResourceType.TEAM
                perm_type = permission_code.replace('team_', '')
            else:
                return False
            
            try:
                permission_type = PermissionType(perm_type)
            except ValueError:
                return False
            
            result = self.check_permission(
                user_id=user_id,
                resource_type=resource_type,
                resource_id=resource_id or '',
                permission_type=permission_type,
                tenant_id=tenant_id
            )
            
            return result.has_permission
            
        except Exception as e:
            logger.error(f"权限检查失败: {e}")
            return False

# 全局权限服务实例
permission_service = PermissionService()