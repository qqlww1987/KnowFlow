from flask import Blueprint, request, jsonify
# from flask_jwt_extended import jwt_required, get_jwt_identity
from services.rbac.permission_service import permission_service
from models.rbac_models import ResourceType, PermissionType
# from services.rbac.permission_decorator import admin_required
import logging

logger = logging.getLogger(__name__)

permission_bp = Blueprint('permission', __name__, url_prefix='/api/permissions')

@permission_bp.route('/check', methods=['POST'])
# @jwt_required()
def check_permission():
    """
    检查用户权限（增强版）
    """
    try:
        # current_user_id = get_jwt_identity()
        current_user_id = 'system'  # 临时使用系统用户
        data = request.get_json()
        
        resource_type = ResourceType(data.get('resource_type'))
        resource_id = data.get('resource_id')
        permission_type = PermissionType(data.get('permission_type'))
        tenant_id = data.get('tenant_id', 'default')
        use_cache = data.get('use_cache', True)
        
        result = permission_service.check_permission_enhanced(
            current_user_id, resource_type, resource_id, 
            permission_type, tenant_id, use_cache
        )
        
        return jsonify({
            'success': True,
            'data': {
                'has_permission': result.has_permission,
                'permission_level': result.permission_level.value if result.permission_level else None,
                'granted_by': result.granted_by,
                'reason': result.reason,
                'details': result.details
            }
        })
        
    except Exception as e:
        logger.error(f"Error checking permission: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'权限检查失败: {str(e)}'
        }), 500

@permission_bp.route('/user/<string:user_id>/effective', methods=['GET'])
# @jwt_required()
# @admin_required
def get_user_effective_permissions(user_id):
    """
    获取用户的有效权限
    """
    try:
        resource_type = ResourceType(request.args.get('resource_type'))
        resource_id = request.args.get('resource_id')
        tenant_id = request.args.get('tenant_id', 'default')
        
        permissions = permission_service.get_user_effective_permissions(
            user_id, resource_type, resource_id, tenant_id
        )
        
        # 转换为可序列化的格式
        serialized_permissions = {}
        for perm_name, result in permissions.items():
            serialized_permissions[perm_name] = {
                'has_permission': result.has_permission,
                'permission_level': result.permission_level.value if result.permission_level else None,
                'source': result.source,
                'direct_roles': [role.value for role in result.direct_roles],
                'team_roles': [role.value for role in result.team_roles],
                'effective_roles': [role.value for role in result.effective_roles],
                'reason': result.reason
            }
        
        return jsonify({
            'success': True,
            'data': serialized_permissions
        })
        
    except Exception as e:
        logger.error(f"Error getting user effective permissions: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取用户有效权限失败: {str(e)}'
        }), 500

@permission_bp.route('/compare', methods=['POST'])
# @jwt_required()
# @admin_required
def compare_user_permissions():
    """
    比较两个用户的权限
    """
    try:
        data = request.get_json()
        
        user1_id = data.get('user1_id')
        user2_id = data.get('user2_id')
        resource_type = ResourceType(data.get('resource_type'))
        resource_id = data.get('resource_id')
        tenant_id = data.get('tenant_id', 'default')
        
        comparison = permission_service.compare_user_permissions(
            user1_id, user2_id, resource_type, resource_id, tenant_id
        )
        
        return jsonify({
            'success': True,
            'data': comparison
        })
        
    except Exception as e:
        logger.error(f"Error comparing user permissions: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'比较用户权限失败: {str(e)}'
        }), 500

@permission_bp.route('/cache/invalidate/user/<string:user_id>', methods=['DELETE'])
# @jwt_required()
# @admin_required
def invalidate_user_cache(user_id):
    """
    使用户权限缓存失效
    """
    try:
        count = permission_service.invalidate_user_permissions(user_id)
        
        return jsonify({
            'success': True,
            'data': {
                'invalidated_count': count
            },
            'message': f'已使用户 {user_id} 的 {count} 个权限缓存失效'
        })
        
    except Exception as e:
        logger.error(f"Error invalidating user cache: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'使用户缓存失效失败: {str(e)}'
        }), 500

@permission_bp.route('/cache/invalidate/resource', methods=['DELETE'])
# @jwt_required()
# @admin_required
def invalidate_resource_cache():
    """
    使资源权限缓存失效
    """
    try:
        data = request.get_json()
        resource_type = ResourceType(data.get('resource_type'))
        resource_id = data.get('resource_id')
        
        count = permission_service.invalidate_resource_permissions(resource_type, resource_id)
        
        return jsonify({
            'success': True,
            'data': {
                'invalidated_count': count
            },
            'message': f'已使资源 {resource_type.value}:{resource_id} 的 {count} 个权限缓存失效'
        })
        
    except Exception as e:
        logger.error(f"Error invalidating resource cache: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'使资源缓存失效失败: {str(e)}'
        }), 500

@permission_bp.route('/cache/invalidate/team/<string:team_id>', methods=['DELETE'])
# @jwt_required()
# @admin_required
def invalidate_team_cache(team_id):
    """
    使团队权限缓存失效
    """
    try:
        count = permission_service.invalidate_team_permissions(team_id)
        
        return jsonify({
            'success': True,
            'data': {
                'invalidated_count': count
            },
            'message': f'已使团队 {team_id} 的 {count} 个权限缓存失效'
        })
        
    except Exception as e:
        logger.error(f"Error invalidating team cache: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'使团队缓存失效失败: {str(e)}'
        }), 500

@permission_bp.route('/cache/stats', methods=['GET'])
# @jwt_required()
# @admin_required
def get_cache_stats():
    """
    获取权限缓存统计信息
    """
    try:
        stats = permission_service.get_permission_cache_stats()
        
        return jsonify({
            'success': True,
            'data': stats
        })
        
    except Exception as e:
        logger.error(f"Error getting cache stats: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取缓存统计失败: {str(e)}'
        }), 500

@permission_bp.route('/cache/cleanup', methods=['POST'])
# @jwt_required()
# @admin_required
def cleanup_cache():
    """
    清理过期的权限缓存
    """
    try:
        count = permission_service.cleanup_permission_cache()
        
        return jsonify({
            'success': True,
            'data': {
                'cleaned_count': count
            },
            'message': f'已清理 {count} 个过期的权限缓存条目'
        })
        
    except Exception as e:
        logger.error(f"Error cleaning up cache: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'清理缓存失败: {str(e)}'
        }), 500