from flask import request, jsonify
from utils import success_response, error_response
from services.files.document_service import DocumentService
from services.rbac.permission_decorator import require_permission
from models.rbac_models import ResourceType, PermissionType
from .. import documents_bp
import json

@documents_bp.route('/<doc_id>/chunking-config', methods=['GET'])
def get_document_chunking_config(doc_id):
    """获取文档分块配置"""
    try:
        # 从数据库获取文档信息
        document = DocumentService.get_by_id(doc_id)
        if not document:
            return error_response("文档不存在", code=404)
        
        # 解析parser_config中的chunking_config
        parser_config = {}
        if document.parser_config:
            if isinstance(document.parser_config, str):
                parser_config = json.loads(document.parser_config)
            else:
                parser_config = document.parser_config
        
        chunking_config = parser_config.get('chunking_config', {
            'strategy': 'smart',
            'chunk_token_num': 256,
            'min_chunk_tokens': 10
        })
        
        return success_response(data={'chunking_config': chunking_config})
        
    except Exception as e:
        return error_response(f"获取分块配置失败: {str(e)}", code=500)

@documents_bp.route('/<doc_id>/chunking-config', methods=['PUT'])
def update_document_chunking_config(doc_id):
    """更新文档分块配置"""
    try:
        data = request.get_json()
        if not data or 'chunking_config' not in data:
            return error_response("缺少分块配置数据", code=400)
        
        chunking_config = data['chunking_config']
        
        # 验证分块配置
        required_fields = ['strategy', 'chunk_token_num', 'min_chunk_tokens']
        for field in required_fields:
            if field not in chunking_config:
                return error_response(f"缺少必需字段: {field}", code=400)
        
        # 验证策略类型
        valid_strategies = ['basic', 'smart', 'advanced', 'strict_regex']
        if chunking_config['strategy'] not in valid_strategies:
            return error_response(f"无效的分块策略: {chunking_config['strategy']}", code=400)
        
        # 验证数值范围
        if not (50 <= chunking_config['chunk_token_num'] <= 2048):
            return error_response("chunk_token_num必须在50-2048之间", code=400)
        
        if not (10 <= chunking_config['min_chunk_tokens'] <= 500):
            return error_response("min_chunk_tokens必须在10-500之间", code=400)
        
        # 获取现有文档
        document = DocumentService.get_by_id(doc_id)
        if not document:
            return error_response("文档不存在", code=404)
        
        # 更新parser_config中的chunking_config
        current_parser_config = {}
        if document.parser_config:
            if isinstance(document.parser_config, str):
                current_parser_config = json.loads(document.parser_config)
            else:
                current_parser_config = document.parser_config
        
        current_parser_config['chunking_config'] = chunking_config
        
        # 更新文档
        update_data = {
            'parser_config': json.dumps(current_parser_config)
        }
        
        DocumentService.update(doc_id, update_data)
        
        return success_response(data={'message': '分块配置更新成功'})
        
    except Exception as e:
        return error_response(f"更新分块配置失败: {str(e)}", code=500)