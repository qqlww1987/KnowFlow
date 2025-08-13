#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RBAC权限装饰器
提供函数和路由级别的权限验证装饰器
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from functools import wraps
from typing import Optional, Callable, Any, Union, List
from flask import request, jsonify, g
import logging
from models.rbac_models import ResourceType, PermissionType
from services.rbac.permission_service import permission_service
from database import get_db_connection

logger = logging.getLogger(__name__)

def extract_user_from_token() -> tuple[Optional[str], Optional[str]]:
    """
    从请求中提取用户ID和租户ID
    由于不需要登录，返回默认的用户身份
    
    Returns:
        tuple[Optional[str], Optional[str]]: (用户ID, 租户ID)
    """
    try:
        # 检查是否有Authorization header（为了兼容性）
        auth_header = request.headers.get('Authorization')
        logger.info(f"[AUTH] 收到请求，Authorization header: {auth_header[:50] if auth_header else 'None'}...")
        
        # 如果有Bearer token格式的header，尝试解析
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            logger.info(f"[AUTH] 提取到token: {token[:20]}...")
            
            # 尝试从api_token表查询
            try:
                db = get_db_connection()
                cursor = db.cursor()
                cursor.execute("SELECT tenant_id FROM api_token WHERE token = %s", (token,))
                result = cursor.fetchone()
                cursor.close()
                
                if result:
                    tenant_id = result[0]
                    logger.info(f"[AUTH] API Token验证成功，tenant_id: {tenant_id}")
                    return tenant_id, tenant_id
                else:
                    logger.info(f"[AUTH] Token在数据库中未找到，使用默认用户身份")
            except Exception as e:
                logger.warning(f"[AUTH] API Token查询失败: {e}，使用默认用户身份")
        
        # 返回默认的用户身份（不需要登录）
        default_user_id = "default_user"
        default_tenant_id = "default_tenant"
        logger.info(f"[AUTH] 使用默认用户身份 - user_id: {default_user_id}, tenant_id: {default_tenant_id}")
        return default_user_id, default_tenant_id
            
    except Exception as e:
        logger.error(f"[AUTH] 提取用户信息失败: {e}，使用默认用户身份")
        # 即使出错也返回默认身份，确保系统可用
        return "default_user", "default_tenant"

def get_tenant_id() -> Optional[str]:
    """
    获取租户ID（从extract_user_from_token中已经获取）
    
    Returns:
        Optional[str]: 租户ID
    """
    # 这个函数现在主要为了兼容性，实际的tenant_id在extract_user_from_token中获取
    return None

def require_permission(permission_code: str, 
                      resource_id_param: Optional[str] = None,
                      resource_type: Optional[ResourceType] = None,
                      permission_type: Optional[PermissionType] = None,
                      allow_owner: bool = True):
    """
    权限验证装饰器
    
    Args:
        permission_code: 权限代码（如 'kb_read', 'doc_write'）
        resource_id_param: 资源ID参数名（从请求参数中获取）
        resource_type: 资源类型（可选，会从permission_code推断）
        permission_type: 权限类型（可选，会从permission_code推断）
        allow_owner: 是否允许资源所有者访问
    
    Returns:
        装饰器函数
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                logger.info(f"[PERMISSION] 权限检查开始，路径: {request.path}, 方法: {request.method}")
                logger.info(f"[PERMISSION] 请求headers: {dict(request.headers)}")
                
                # 1. 提取用户ID
                user_id, tenant_id = extract_user_from_token()
                logger.info(f"[PERMISSION] 提取用户信息 - user_id: {user_id}, tenant_id: {tenant_id}")
                
                if not user_id:
                    logger.warning(f"[PERMISSION] 用户身份验证失败，返回401")
                    return jsonify({
                        'error': '未授权访问',
                        'message': '请先登录',
                        'code': 401
                    }), 401
                
                # 2. 获取租户ID
                # tenant_id = get_tenant_id() # 这个函数现在主要为了兼容性，实际的tenant_id在extract_user_from_token中获取
                
                # 3. 获取资源ID
                resource_id = ''
                if resource_id_param:
                    # 从路径参数获取
                    if resource_id_param in kwargs:
                        resource_id = kwargs[resource_id_param]
                    # 从查询参数获取
                    elif resource_id_param in request.args:
                        resource_id = request.args.get(resource_id_param)
                    # 从JSON body获取
                    elif request.is_json and resource_id_param in request.json:
                        resource_id = request.json.get(resource_id_param)
                
                # 4. 解析权限类型和资源类型
                if not resource_type or not permission_type:
                    parsed_resource_type, parsed_permission_type = _parse_permission_code(permission_code)
                    final_resource_type = resource_type or parsed_resource_type
                    final_permission_type = permission_type or parsed_permission_type
                else:
                    final_resource_type = resource_type
                    final_permission_type = permission_type
                
                if not final_resource_type or not final_permission_type:
                    return jsonify({
                        'error': '权限配置错误',
                        'message': f'无效的权限代码: {permission_code}',
                        'code': 500
                    }), 500
                
                # 5. 执行权限检查
                permission_check = permission_service.check_permission(
                    user_id=user_id,
                    resource_type=final_resource_type,
                    resource_id=resource_id,
                    permission_type=final_permission_type,
                    tenant_id=tenant_id
                )
                
                if not permission_check.has_permission:
                    return jsonify({
                        'error': '权限不足',
                        'message': f'您没有执行此操作的权限: {permission_check.reason}',
                        'code': 403,
                        'required_permission': permission_code,
                        'resource_id': resource_id
                    }), 403
                
                # 6. 将权限信息添加到g对象中，供后续使用
                g.current_user_id = user_id
                g.current_tenant_id = tenant_id
                g.permission_check = permission_check
                
                # 7. 执行原函数
                return func(*args, **kwargs)
                
            except Exception as e:
                logger.error(f"权限验证异常: {e}")
                return jsonify({
                    'error': '权限验证失败',
                    'message': '系统内部错误',
                    'code': 500
                }), 500
        
        return wrapper
    return decorator

def require_role(role_codes: Union[str, List[str]], 
                tenant_id_param: Optional[str] = None,
                resource_id_param: Optional[str] = None):
    """
    角色验证装饰器
    
    Args:
        role_codes: 需要的角色代码（字符串或列表）
        tenant_id_param: 租户ID参数名
        resource_id_param: 资源ID参数名
    
    Returns:
        装饰器函数
    """
    if isinstance(role_codes, str):
        role_codes = [role_codes]
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                # 1. 提取用户ID
                user_id, tenant_id = extract_user_from_token()
                if not user_id:
                    return jsonify({
                        'error': '未授权访问',
                        'message': '请先登录',
                        'code': 401
                    }), 401
                
                # 2. 获取租户ID
                # tenant_id = get_tenant_id() # 这个函数现在主要为了兼容性，实际的tenant_id在extract_user_from_token中获取
                if tenant_id_param and tenant_id_param in kwargs:
                    tenant_id = kwargs[tenant_id_param]
                
                # 3. 获取用户角色
                user_roles = permission_service.get_user_roles(user_id, tenant_id)
                user_role_codes = [role.code for role in user_roles]
                
                # 4. 检查是否有所需角色
                has_required_role = any(role_code in user_role_codes for role_code in role_codes)
                
                if not has_required_role:
                    return jsonify({
                        'error': '角色权限不足',
                        'message': f'需要以下角色之一: {", ".join(role_codes)}',
                        'code': 403,
                        'required_roles': role_codes,
                        'user_roles': user_role_codes
                    }), 403
                
                # 5. 将信息添加到g对象中
                g.current_user_id = user_id
                g.current_tenant_id = tenant_id
                g.user_roles = user_roles
                
                # 6. 执行原函数
                return func(*args, **kwargs)
                
            except Exception as e:
                logger.error(f"角色验证异常: {e}")
                return jsonify({
                    'error': '角色验证失败',
                    'message': '系统内部错误',
                    'code': 500
                }), 500
        
        return wrapper
    return decorator

def require_login(func: Callable) -> Callable:
    """
    登录验证装饰器
    
    Args:
        func: 被装饰的函数
    
    Returns:
        装饰器函数
    """
    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        try:
            user_id, tenant_id = extract_user_from_token()
            if not user_id:
                return jsonify({
                    'error': '未授权访问',
                    'message': '请先登录',
                    'code': 401
                }), 401
            
            # 将用户信息添加到g对象中
            g.current_user_id = user_id
            g.current_tenant_id = tenant_id
            
            return func(*args, **kwargs)
            
        except Exception as e:
            logger.error(f"登录验证异常: {e}")
            return jsonify({
                'error': '登录验证失败',
                'message': '系统内部错误',
                'code': 500
            }), 500
    
    return wrapper

def admin_required(func: Callable) -> Callable:
    """
    管理员权限装饰器
    
    Args:
        func: 被装饰的函数
    
    Returns:
        装饰器函数
    """
    return require_role(['admin', 'super_admin'])(func)

def super_admin_required(func: Callable) -> Callable:
    """
    超级管理员权限装饰器
    
    Args:
        func: 被装饰的函数
    
    Returns:
        装饰器函数
    """
    return require_role('super_admin')(func)

def _parse_permission_code(permission_code: str) -> tuple[Optional[ResourceType], Optional[PermissionType]]:
    """
    解析权限代码，提取资源类型和权限类型
    
    Args:
        permission_code: 权限代码（如 'kb_read', 'doc_write'）
    
    Returns:
        tuple: (资源类型, 权限类型)
    """
    try:
        if '_' not in permission_code:
            return None, None
        
        prefix, suffix = permission_code.split('_', 1)
        
        # 解析资源类型
        resource_type_map = {
            'kb': ResourceType.KNOWLEDGEBASE,
            'doc': ResourceType.DOCUMENT,
            'team': ResourceType.TEAM,
            'user': ResourceType.USER,
            'system': ResourceType.SYSTEM
        }
        
        resource_type = resource_type_map.get(prefix)
        
        # 解析权限类型
        try:
            permission_type = PermissionType(suffix)
        except ValueError:
            permission_type = None
        
        return resource_type, permission_type
        
    except Exception as e:
        logger.error(f"解析权限代码失败: {e}")
        return None, None

# 常用权限装饰器的快捷方式
kb_read_required = lambda resource_id_param='kb_id': require_permission('kb_read', resource_id_param)
kb_write_required = lambda resource_id_param='kb_id': require_permission('kb_write', resource_id_param)
kb_delete_required = lambda resource_id_param='kb_id': require_permission('kb_delete', resource_id_param)
kb_share_required = lambda resource_id_param='kb_id': require_permission('kb_share', resource_id_param)

doc_read_required = lambda resource_id_param='doc_id': require_permission('doc_read', resource_id_param)
doc_write_required = lambda resource_id_param='doc_id': require_permission('doc_write', resource_id_param)
doc_delete_required = lambda resource_id_param='doc_id': require_permission('doc_delete', resource_id_param)

team_read_required = lambda resource_id_param='team_id': require_permission('team_read', resource_id_param)
team_admin_required = lambda resource_id_param='team_id': require_permission('team_admin', resource_id_param)