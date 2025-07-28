#
#  Copyright 2024 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

import json
import logging
import os
import requests
from flask import request, Response
from flask_login import login_required, current_user

from api.utils import get_uuid, current_timestamp, get_base_config
from api.utils.api_utils import server_error_response, get_data_error_result, get_json_result, validate_request
from api import settings
from api.db.services.dialog_service import DialogService
from api.db.services.file_service import FileService

# 获取colpali服务配置
colpali_config = get_base_config('colpali', {})
colpali_host = colpali_config.get('host', 'localhost')
colpali_port = colpali_config.get('port', '8000')
colpali_api_key = colpali_config.get('api_key', '')
multimodal_enabled = colpali_config.get('multimodal_enabled', False)

# colpali服务的基础URL
COLPALI_BASE_URL = f"http://{colpali_host}:{colpali_port}"

@manager.route('/multimodal/enabled', methods=['GET'])  # noqa: F821
@login_required
def check_multimodal_enabled():
    """检查多模态功能是否启用"""
    try:
        # 检查配置是否启用多模态
        enabled = multimodal_enabled
        
        # 检查colpali服务是否可用
        if enabled:
            try:
                # 尝试连接colpali服务
                response = requests.get(f"{COLPALI_BASE_URL}/health", timeout=2)
                if response.status_code != 200:
                    enabled = False
                    logging.warning(f"Colpali服务不可用: {response.status_code}")
            except Exception as e:
                enabled = False
                logging.warning(f"连接Colpali服务失败: {str(e)}")
        
        return get_json_result(data={"enabled": enabled})
    except Exception as e:
        return server_error_response(e)

@manager.route('/multimodal/upload', methods=['POST'])  # noqa: F821
@login_required
def upload_multimodal_file():
    """上传多模态文件到colpali服务"""
    try:
        # 检查多模态功能是否启用
        if not multimodal_enabled:
            return get_data_error_result(message="多模态功能未启用")
        
        # 获取上传的文件
        if 'file' not in request.files:
            return get_data_error_result(message="未找到文件")
        
        file = request.files['file']
        conversation_id = request.form.get('conversation_id')
        
        if not file or not conversation_id:
            return get_data_error_result(message="缺少必要参数")
        
        # 保存文件到本地临时目录
        file_id = get_uuid()
        file_ext = os.path.splitext(file.filename)[1]
        temp_file_path = f"/tmp/{file_id}{file_ext}"
        file.save(temp_file_path)
        
        # 上传文件到colpali服务
        files = {'file': open(temp_file_path, 'rb')}
        data = {'conversation_id': conversation_id}
        headers = {}
        if colpali_api_key:
            headers['Authorization'] = f"Bearer {colpali_api_key}"
            
        response = requests.post(
            f"{COLPALI_BASE_URL}/api/v1/upload",
            files=files,
            data=data,
            headers=headers
        )
        
        # 删除临时文件
        os.remove(temp_file_path)
        
        if response.status_code != 200:
            return get_data_error_result(message=f"上传文件到colpali服务失败: {response.text}")
        
        # 保存文件记录到数据库
        file_data = {
            "id": file_id,
            "name": file.filename,
            "type": file.content_type,
            "size": os.path.getsize(temp_file_path),
            "conversation_id": conversation_id,
            "colpali_file_id": response.json().get('file_id'),
            "create_time": current_timestamp()
        }
        
        # 返回文件ID和colpali服务返回的信息
        return get_json_result(data={
            "file_id": file_id,
            "colpali_response": response.json()
        })
    except Exception as e:
        return server_error_response(e)

@manager.route('/multimodal/chat', methods=['POST'])  # noqa: F821
@login_required
@validate_request("conversation_id", "message")
def multimodal_chat():
    """发送多模态聊天消息到colpali服务"""
    try:
        # 检查多模态功能是否启用
        if not multimodal_enabled:
            return get_data_error_result(message="多模态功能未启用")
        
        req = request.json
        conversation_id = req.get("conversation_id")
        message = req.get("message")
        file_ids = req.get("file_ids", [])
        mode = req.get("mode", "multimodal")
        
        # 检查会话是否存在
        dialog = DialogService.get_dialog_by_conversation_id(conversation_id)
        if not dialog:
            return get_data_error_result(message="会话不存在")
        
        # 准备发送到colpali服务的数据
        chat_data = {
            "conversation_id": conversation_id,
            "message": message,
            "file_ids": file_ids,
            "mode": mode
        }
        
        headers = {"Content-Type": "application/json"}
        if colpali_api_key:
            headers['Authorization'] = f"Bearer {colpali_api_key}"
        
        # 发送请求到colpali服务
        response = requests.post(
            f"{COLPALI_BASE_URL}/api/v1/chat",
            json=chat_data,
            headers=headers
        )
        
        if response.status_code != 200:
            return get_data_error_result(message=f"发送消息到colpali服务失败: {response.text}")
        
        # 返回colpali服务的响应
        return get_json_result(data=response.json())
    except Exception as e:
        return server_error_response(e)