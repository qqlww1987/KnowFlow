#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
权限计算服务
实现用户个人权限与团队权限的合并计算逻辑
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging
from database import get_db_connection
from models.rbac_models import (
    PermissionType, ResourceType, RoleType,
    PermissionCheck, UserRole, TeamRole
)

logger = logging.getLogger(__name__)

class PermissionLevel(Enum):
    """权限级别枚举"""
    NONE = 0
    READ = 1
    WRITE = 2
    ADMIN = 3

@dataclass
class UserPermissionContext:
    """用户权限上下文"""
    user_id: str
    direct_roles: List[UserRole]  # 用户直接角色
    team_roles: List[TeamRole]    # 团队继承角色
    resource_ownership: Dict[str, bool]  # 资源所有权
    is_super_admin: bool = False

@dataclass
class PermissionResult:
    """权限计算结果"""
    has_permission: bool
    permission_level: PermissionLevel
    granted_by: List[str]  # 权限来源
    reason: str
    details: Dict[str, any] = None

class PermissionCalculator:
    """权限计算器"""
    
    def __init__(self):
        self.permission_hierarchy = {
            PermissionType.READ: PermissionLevel.READ,
            PermissionType.WRITE: PermissionLevel.WRITE,
            PermissionType.ADMIN: PermissionLevel.ADMIN,
            PermissionType.DELETE: PermissionLevel.ADMIN,
            PermissionType.SHARE: PermissionLevel.WRITE,
            PermissionType.EXPORT: PermissionLevel.READ,
        }
        
        self.role_permissions = {
            'viewer': [PermissionType.READ],
            'editor': [PermissionType.READ, PermissionType.WRITE, PermissionType.SHARE],
            'admin': [PermissionType.READ, PermissionType.WRITE, PermissionType.ADMIN, 
                        PermissionType.DELETE, PermissionType.SHARE],
            'super_admin': [p for p in PermissionType],  # 超级管理员拥有所有权限
            'user': [PermissionType.READ],
            'guest': [PermissionType.READ],
        }
    
    def calculate_user_permission(self, user_id: str, resource_type: ResourceType, 
                                resource_id: str, permission_type: PermissionType,
                                tenant_id: str = "default") -> PermissionResult:
        """
        计算用户对特定资源的权限
        
        Args:
            user_id: 用户ID
            resource_type: 资源类型
            resource_id: 资源ID
            permission_type: 权限类型
            tenant_id: 租户ID
            
        Returns:
            PermissionResult: 权限计算结果
        """
        try:
            # 1. 获取用户权限上下文
            context = self._get_user_permission_context(user_id, resource_type, resource_id, tenant_id)
            
            # 2. 超级管理员检查
            if context.is_super_admin:
                return PermissionResult(
                    has_permission=True,
                    permission_level=PermissionLevel.ADMIN,
                    granted_by=["super_admin"],
                    reason="超级管理员权限"
                )
            
            # 3. 资源所有者检查
            if context.resource_ownership.get(resource_id, False):
                return PermissionResult(
                    has_permission=True,
                    permission_level=PermissionLevel.ADMIN,
                    granted_by=["owner"],
                    reason="资源所有者权限"
                )
            
            # 4. 计算合并权限
            merged_permissions = self._merge_permissions(context, resource_type, resource_id)
            
            # 5. 检查是否有所需权限
            required_level = self.permission_hierarchy.get(permission_type, PermissionLevel.NONE)
            user_level = merged_permissions.get(permission_type, PermissionLevel.NONE)
            
            has_permission = user_level.value >= required_level.value
            
            # 6. 构建权限来源信息
            granted_by = self._get_permission_sources(context, permission_type, resource_type, resource_id)
            
            return PermissionResult(
                has_permission=has_permission,
                permission_level=user_level,
                granted_by=granted_by,
                reason=f"权限级别: {user_level.name}, 需要: {required_level.name}",
                details={
                    "direct_roles": len(context.direct_roles),
                    "team_roles": len(context.team_roles),
                    "merged_permissions": {k.name: v.name for k, v in merged_permissions.items()}
                }
            )
            
        except Exception as e:
            logger.error(f"权限计算失败: {e}")
            return PermissionResult(
                has_permission=False,
                permission_level=PermissionLevel.NONE,
                granted_by=[],
                reason=f"权限计算异常: {str(e)}"
            )
    
    def _get_user_permission_context(self, user_id: str, resource_type: ResourceType, 
                                   resource_id: str, tenant_id: str) -> UserPermissionContext:
        """获取用户权限上下文"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            # 1. 检查超级管理员 - 基于角色分配判断
            is_super_admin = False
            
            # 2. 获取用户直接角色
            cursor.execute("""
                SELECT ur.*, r.code as role_code, r.name as role_name
                FROM rbac_user_roles ur
                JOIN rbac_roles r ON ur.role_id = r.id
                WHERE ur.user_id = %s AND ur.is_active = 1
                AND (ur.expires_at IS NULL OR ur.expires_at > NOW())
                AND (ur.resource_id IS NULL OR ur.resource_id = %s)
                AND ur.tenant_id = %s
            """, (user_id, resource_id, tenant_id))
            direct_roles_data = cursor.fetchall()
            
            # 3. 获取团队角色
            cursor.execute("""
                SELECT tr.*, ut.tenant_id as user_team_id
                FROM rbac_team_roles tr
                JOIN user_tenant ut ON tr.team_id = ut.tenant_id
                WHERE ut.user_id = %s AND ut.status = 1 AND tr.is_active = 1
                AND (tr.expires_at IS NULL OR tr.expires_at > NOW())
                AND (tr.resource_id IS NULL OR tr.resource_id = %s)
                AND tr.tenant_id = %s
            """, (user_id, resource_id, tenant_id))
            team_roles_data = cursor.fetchall()
            
            # 4. 检查资源所有权
            resource_ownership = {}
            if resource_type == ResourceType.KNOWLEDGEBASE:
                cursor.execute("""
                    SELECT created_by FROM knowledgebase WHERE id = %s
                """, (resource_id,))
                kb_result = cursor.fetchone()
                resource_ownership[resource_id] = (kb_result and kb_result['created_by'] == user_id)
            
            # 5. 构建上下文对象
            direct_roles = []
            for role_data in direct_roles_data:
                direct_roles.append(UserRole(
                    id=role_data['id'],
                    user_id=role_data['user_id'],
                    role_id=role_data['role_id'],
                    role_code=role_data['role_code'],
                    resource_type=ResourceType(role_data['resource_type']) if role_data['resource_type'] else None,
                    resource_id=role_data['resource_id'],
                    tenant_id=role_data['tenant_id'],
                    granted_by=role_data['granted_by'],
                    granted_at=role_data['granted_at'].isoformat() if role_data['granted_at'] else None,
                    expires_at=role_data['expires_at'].isoformat() if role_data['expires_at'] else None,
                    is_active=bool(role_data['is_active'])
                ))
            
            team_roles = []
            for role_data in team_roles_data:
                team_roles.append(TeamRole(
                    id=role_data['id'],
                    team_id=role_data['team_id'],
                    role_code=role_data['role_code'],
                    resource_type=ResourceType(role_data['resource_type']) if role_data['resource_type'] else None,
                    resource_id=role_data['resource_id'],
                    tenant_id=role_data['tenant_id'],
                    granted_by=role_data['granted_by'],
                    granted_at=role_data['granted_at'].isoformat() if role_data['granted_at'] else None,
                    expires_at=role_data['expires_at'].isoformat() if role_data['expires_at'] else None,
                    is_active=bool(role_data['is_active'])
                ))
            
            return UserPermissionContext(
                user_id=user_id,
                direct_roles=direct_roles,
                team_roles=team_roles,
                resource_ownership=resource_ownership,
                is_super_admin=is_super_admin
            )
            
        except Exception as e:
            logger.error(f"获取用户权限上下文失败: {e}")
            return UserPermissionContext(
                user_id=user_id,
                direct_roles=[],
                team_roles=[],
                resource_ownership={},
                is_super_admin=False
            )
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def _merge_permissions(self, context: UserPermissionContext, 
                         resource_type: ResourceType, resource_id: str) -> Dict[PermissionType, PermissionLevel]:
        """合并用户直接权限和团队权限"""
        merged_permissions = {}
        
        # 1. 处理用户直接角色权限
        for role in context.direct_roles:
            # 系统级别角色（super_admin, admin）对所有资源类型有效
            is_system_role = role.role_code in ['super_admin', 'admin'] and role.resource_type == ResourceType.SYSTEM
            is_resource_match = role.resource_type == resource_type and (role.resource_id is None or role.resource_id == resource_id)
            
            if is_system_role or is_resource_match:
                role_permissions = self.role_permissions.get(role.role_code, [])
                for perm_type in role_permissions:
                    current_level = merged_permissions.get(perm_type, PermissionLevel.NONE)
                    role_level = self.permission_hierarchy.get(perm_type, PermissionLevel.NONE)
                    # 取最高权限级别
                    merged_permissions[perm_type] = max(current_level, role_level, key=lambda x: x.value)
        
        # 2. 处理团队角色权限
        for role in context.team_roles:
            if role.resource_type == resource_type and (role.resource_id is None or role.resource_id == resource_id):
                role_permissions = self.role_permissions.get(role.role_code, [])
                for perm_type in role_permissions:
                    current_level = merged_permissions.get(perm_type, PermissionLevel.NONE)
                    role_level = self.permission_hierarchy.get(perm_type, PermissionLevel.NONE)
                    # 取最高权限级别（用户直接权限优先级更高，但这里是取最大值）
                    merged_permissions[perm_type] = max(current_level, role_level, key=lambda x: x.value)
        
        return merged_permissions
    
    def _get_permission_sources(self, context: UserPermissionContext, 
                              permission_type: PermissionType,
                              resource_type: ResourceType, resource_id: str) -> List[str]:
        """获取权限来源信息"""
        sources = []
        
        # 检查用户直接角色
        for role in context.direct_roles:
            if (role.resource_type == resource_type and 
                (role.resource_id is None or role.resource_id == resource_id)):
                role_permissions = self.role_permissions.get(role.role_code, [])
                if permission_type in role_permissions:
                    sources.append(f"直接角色: {role.role_code}")
        
        # 检查团队角色
        for role in context.team_roles:
            if (role.resource_type == resource_type and 
                (role.resource_id is None or role.resource_id == resource_id)):
                role_permissions = self.role_permissions.get(role.role_code, [])
                if permission_type in role_permissions:
                    sources.append(f"团队角色: {role.role_code} (团队: {role.team_id})")
        
        return sources
    
    def get_user_effective_permissions(self, user_id: str, resource_type: ResourceType, 
                                     resource_id: str, tenant_id: str = "default") -> Dict[str, PermissionResult]:
        """获取用户对特定资源的所有有效权限"""
        permissions = {}
        
        # 检查所有权限类型
        for perm_type in PermissionType:
            if perm_type.name.startswith('kb_'):  # 只检查知识库相关权限
                result = self.calculate_user_permission(
                    user_id, resource_type, resource_id, perm_type, tenant_id
                )
                permissions[perm_type.name] = result
        
        return permissions
    
    def compare_user_permissions(self, user1_id: str, user2_id: str, 
                               resource_type: ResourceType, resource_id: str,
                               tenant_id: str = "default") -> Dict[str, any]:
        """比较两个用户的权限差异"""
        user1_perms = self.get_user_effective_permissions(user1_id, resource_type, resource_id, tenant_id)
        user2_perms = self.get_user_effective_permissions(user2_id, resource_type, resource_id, tenant_id)
        
        comparison = {
            "user1_id": user1_id,
            "user2_id": user2_id,
            "resource_type": resource_type.name,
            "resource_id": resource_id,
            "differences": [],
            "common_permissions": [],
            "user1_only": [],
            "user2_only": []
        }
        
        all_perms = set(user1_perms.keys()) | set(user2_perms.keys())
        
        for perm_name in all_perms:
            user1_result = user1_perms.get(perm_name)
            user2_result = user2_perms.get(perm_name)
            
            if user1_result and user2_result:
                if user1_result.has_permission and user2_result.has_permission:
                    comparison["common_permissions"].append(perm_name)
                elif user1_result.has_permission != user2_result.has_permission:
                    comparison["differences"].append({
                        "permission": perm_name,
                        "user1_has": user1_result.has_permission,
                        "user2_has": user2_result.has_permission
                    })
            elif user1_result and user1_result.has_permission:
                comparison["user1_only"].append(perm_name)
            elif user2_result and user2_result.has_permission:
                comparison["user2_only"].append(perm_name)
        
        return comparison

# 全局权限计算器实例
permission_calculator = PermissionCalculator()