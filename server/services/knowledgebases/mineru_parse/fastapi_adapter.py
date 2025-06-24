#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MinerU FastAPI 适配器

直接通过 FastAPI 接口处理文档，提供高性能的文档解析服务。
"""

import os
import requests
import json
from typing import Optional, Callable, Dict, Any
from loguru import logger


class MinerUFastAPIAdapter:
    """MinerU FastAPI 适配器"""
    
    def __init__(self, 
                 base_url: str = "http://localhost:8888",
                 backend: str = "pipeline",
                 timeout: int = 300):
        """
        初始化适配器
        
        Args:
            base_url: FastAPI 服务地址
            backend: 默认后端类型 (pipeline, vlm-transformers, vlm-sglang-engine, vlm-sglang-client)
            timeout: 请求超时时间（秒）
        """
        self.base_url = base_url.rstrip('/')
        self.backend = backend
        self.timeout = timeout
        self.session = requests.Session()
        
    def _check_server_health(self) -> bool:
        """检查 FastAPI 服务器是否可访问"""
        try:
            response = self.session.get(f"{self.base_url}/docs", timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"FastAPI 服务器不可访问: {e}")
            return False
    
    def _prepare_request_data(self, 
                             backend: str = None,
                             parse_method: str = "auto",
                             lang: str = "ch", 
                             formula_enable: bool = True,
                             table_enable: bool = True,
                             server_url: Optional[str] = None,
                             **kwargs) -> Dict[str, Any]:
        """准备请求数据"""
        backend = backend or self.backend
        
        data = {
            'backend': backend,
            'return_content_list': True,  # 总是返回内容列表
            'return_info': True,         # 默认返回解析信息（用于位置信息）
            'return_layout': False,      # 默认不返回布局
            'return_images': True,       # 获取原始图片数据
            'is_json_md_dump': False,    # 默认不保存文件到服务器
            'output_dir': 'output'  # 临时输出目录
        }
        
        # 添加特定后端参数
        if backend == 'vlm-sglang-client':
            if server_url:
                data['server_url'] = server_url
            else:
                logger.warning("vlm-sglang-client 后端需要 server_url 参数")
                
        elif backend == 'pipeline':
            data.update({
                'parse_method': parse_method,
                'lang': lang,
                'formula_enable': formula_enable,
                'table_enable': table_enable
            })
        
        # 合并额外参数，允许用户覆盖默认设置
        data.update(kwargs)
        return data
    
    def process_file(self,
                    file_path: str,
                    update_progress: Optional[Callable] = None,
                    backend: str = None,
                    **kwargs) -> Dict[str, Any]:
        """
        处理文件的主要接口
        
        Args:
            file_path: PDF文件路径
            update_progress: 进度回调函数
            backend: 指定后端类型
            **kwargs: 其他参数
            
        Returns:
            Dict: 处理结果
        """
        if update_progress:
            update_progress(0.1, "开始连接 FastAPI 服务")
            
        # 检查服务器健康状态
        if not self._check_server_health():
            raise Exception(f"FastAPI 服务器不可访问: {self.base_url}")
            
        if update_progress:
            update_progress(0.2, "准备文件上传")
            
        # 检查文件是否存在
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")
            
        # 准备请求数据
        data = self._prepare_request_data(backend=backend, **kwargs)
        
        if update_progress:
            update_progress(0.3, f"开始 {data['backend']} 后端处理")
            
        try:
            # 发送请求
            with open(file_path, 'rb') as f:
                files = {'file': f}
                response = self.session.post(
                    f"{self.base_url}/file_parse",
                    files=files,
                    data=data,
                    timeout=self.timeout
                )
                
            if response.status_code == 200:
                result = response.json()
                
                if update_progress:
                    update_progress(0.8, "FastAPI 处理完成")
                    
                # 添加处理信息
                result['_adapter_info'] = {
                    'backend_used': result.get('backend', data['backend']),
                    'file_processed': os.path.basename(file_path),
                    'adapter_version': '2.0.0',
                    'processing_mode': 'fastapi_only'
                }
                
                if update_progress:
                    update_progress(1.0, "处理完成")
                    
                return result
            else:
                error_msg = f"FastAPI 请求失败: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)
                
        except requests.exceptions.Timeout:
            error_msg = f"FastAPI 请求超时 ({self.timeout}秒)"
            logger.error(error_msg)
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"FastAPI 请求失败: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)


# 全局适配器实例
_global_adapter = None

def get_global_adapter() -> MinerUFastAPIAdapter:
    """获取全局适配器实例"""
    global _global_adapter
    if _global_adapter is None:
        fastapi_url = os.environ.get('MINERU_FASTAPI_URL', 'http://localhost:8888')
        backend = os.environ.get('MINERU_FASTAPI_BACKEND', 'pipeline')
        timeout = int(os.environ.get('MINERU_FASTAPI_TIMEOUT', '300'))
        
        _global_adapter = MinerUFastAPIAdapter(
            base_url=fastapi_url,
            backend=backend,
            timeout=timeout
        )
    return _global_adapter


def configure_adapter(base_url: str = None, 
                     backend: str = None, 
                     timeout: int = None):
    """配置全局适配器"""
    global _global_adapter
    
    current_url = os.environ.get('MINERU_FASTAPI_URL', 'http://localhost:8888')
    current_backend = os.environ.get('MINERU_FASTAPI_BACKEND', 'pipeline')
    current_timeout = int(os.environ.get('MINERU_FASTAPI_TIMEOUT', '300'))
    
    _global_adapter = MinerUFastAPIAdapter(
        base_url=base_url or current_url,
        backend=backend or current_backend,
        timeout=timeout or current_timeout
    )
    
    logger.info(f"FastAPI 适配器已配置: {_global_adapter.base_url}, 后端: {_global_adapter.backend}")


def test_adapter_connection(base_url: str = None) -> Dict[str, Any]:
    """测试适配器连接"""
    test_url = base_url or os.environ.get('MINERU_FASTAPI_URL', 'http://localhost:8888')
    
    try:
        response = requests.get(f"{test_url.rstrip('/')}/docs", timeout=10)
        if response.status_code == 200:
            return {
                'status': 'success',
                'url': test_url,
                'message': 'FastAPI 服务可访问'
            }
        else:
            return {
                'status': 'error',
                'url': test_url,
                'message': f'服务响应异常: {response.status_code}'
            }
    except Exception as e:
        return {
            'status': 'error',
            'url': test_url,
            'message': f'连接失败: {str(e)}'
        } 