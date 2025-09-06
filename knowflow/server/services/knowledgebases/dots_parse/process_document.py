#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DOTS OCR 文档处理入口

提供与现有document_parser.py兼容的接口，支持:
- PDF文档的DOTS OCR解析
- 图片文件的OCR处理
- 与RAGFlow系统的集成
"""

import os
import tempfile
import logging
from typing import Optional, Callable
from pathlib import Path
from io import BytesIO

from .dots_fastapi_adapter import get_global_adapter
from .dots_processor import process_dots_result
from .ragflow_integration import create_ragflow_resources

logger = logging.getLogger(__name__)

def _process_pdf_to_images(file_path: str, adapter, update_progress: Optional[Callable] = None) -> list:
    """
    将PDF转换为图像后处理（符合DOTS VLLM的处理方式）
    
    Args:
        file_path: PDF文件路径
        adapter: DOTS适配器实例 
        update_progress: 进度回调函数
    
    Returns:
        list: 解析结果列表
    """
    try:
        logger.info(f"将PDF转换为图像进行处理: {file_path}")
        
        # 方案1: 尝试使用pdf2image（推荐）
        try:
            from pdf2image import convert_from_path
            logger.info("使用pdf2image库转换PDF")
            
            # 转换PDF为PIL图像列表（200 DPI与DOTS官方一致）
            images = convert_from_path(file_path, dpi=200)
            
            document_results = []
            total_pages = len(images)
            
            for page_num, image in enumerate(images):
                if update_progress:
                    progress = 0.2 + (page_num / total_pages) * 0.6
                    update_progress(progress, f"处理第{page_num + 1}/{total_pages}页")
                
                # 转换PIL图像为字节
                img_buffer = BytesIO()
                image.save(img_buffer, format='PNG')
                img_bytes = img_buffer.getvalue()
                
                # 调用DOTS VLLM API解析
                page_result = adapter.parse_image(img_bytes)
                page_result['page_number'] = page_num + 1
                page_result['source_type'] = 'pdf_page'
                # 保存原始PIL图像用于后续图片裁剪
                page_result['page_image'] = image
                document_results.append(page_result)
                
                logger.info(f"完成第{page_num + 1}页解析")
            
            return document_results
            
        except ImportError:
            logger.warning("pdf2image未安装，尝试其他方法")
            
            # 方案2: 提供安装指引和临时处理方案
            error_msg = """
            PDF处理需要pdf2image库支持。请安装：
            pip install pdf2image
            
            另外，系统还需要poppler-utils：
            - Ubuntu/Debian: sudo apt-get install poppler-utils
            - macOS: brew install poppler
            - Windows: 下载并配置poppler
            """
            
            return [{
                'success': False,
                'error': error_msg.strip(),
                'suggestion': 'install_pdf2image'
            }]
            
    except Exception as e:
        logger.error(f"PDF转图像处理失败: {e}")
        return [{
            'success': False,
            'error': f'PDF转图像处理失败: {str(e)}'
        }]

def process_document_with_dots(doc_id: str, file_path: str, kb_id: str, 
                              update_progress: Optional[Callable] = None,
                              embedding_config: Optional[dict] = None,
                              parser_config: Optional[dict] = None) -> int:
    """使用DOTS OCR处理文档的主入口函数
    
    Args:
        doc_id: 文档ID
        file_path: 文件路径
        kb_id: 知识库ID  
        update_progress: 进度更新回调函数
        embedding_config: 嵌入模型配置
        parser_config: 解析器配置（包含分块策略设置）
        
    Returns:
        int: 生成的文档块数量
    """
    try:
        if update_progress:
            update_progress(0.1, "初始化DOTS OCR服务")
        
        # 1. 初始化DOTS适配器
        adapter = get_global_adapter()
        
        # 2. 测试连接
        connection_result = adapter.test_connection()
        if connection_result['status'] != 'success':
            error_msg = connection_result['message']
            logger.error(f"DOTS服务连接失败: {error_msg}")
            
            # 提供详细的故障排除信息  
            if "502" in error_msg or "Empty reply" in error_msg:
                detailed_msg = f"""DOTS服务连接失败: {error_msg}

诊断发现VLLM服务在服务器本地(localhost:30001)正常工作，但外部访问失败。

可能的原因和解决方案:
1. 网络配置问题
   - 服务器端: 确认VLLM启动时使用 --host 0.0.0.0 允许外部访问
   - 防火墙: 确认端口30001已开放外部访问
   - 当前配置: {adapter.base_url} (模型: {adapter.model_name})

2. VLLM启动命令应包含外部访问配置:
   vllm serve ${{MODEL_PATH}} \\
     --host 0.0.0.0 \\
     --port 30001 \\
     --served-model-name dotsocr-model \\
     --trust-remote-code

3. 测试方法:
   在服务器上运行: curl http://localhost:30001/v1/models
   在外部运行: curl http://8.134.177.47:30001/v1/models"""
                raise Exception(detailed_msg)
            else:
                raise Exception(f"DOTS服务连接失败: {error_msg}")
        
        if update_progress:
            update_progress(0.2, "开始DOTS OCR解析")
        
        # 3. 根据文件类型选择处理方式
        file_ext = Path(file_path).suffix.lower()
        
        if file_ext == '.pdf':
            # PDF文档处理 - 转换为图像后处理（符合DOTS VLLM要求）
            logger.info(f"使用DOTS解析PDF文档: {file_path}")
            document_results = _process_pdf_to_images(file_path, adapter, update_progress)
        elif file_ext in ['.png', '.jpg', '.jpeg', '.bmp', '.tiff']:
            # 单个图片处理
            logger.info(f"使用DOTS解析图片文件: {file_path}")
            with open(file_path, 'rb') as f:
                image_bytes = f.read()
            
            # 加载PIL图像用于后续图片裁剪
            from PIL import Image
            page_image = Image.open(file_path)
            
            image_result = adapter.parse_image(image_bytes)
            image_result['page_image'] = page_image
            document_results = [image_result]  # 包装为列表
        else:
            raise ValueError(f"不支持的文件类型: {file_ext}")
        
        if update_progress:
            update_progress(0.4, "处理OCR解析结果")
        
        # 4. 处理DOTS解析结果（使用前端配置的分块策略）
        # 从parser_config中提取分块配置
        chunking_config = {}
        chunk_token_num = 256
        min_chunk_tokens = 10
        chunking_strategy = 'smart'
        
        if parser_config:
            # 优先使用parser_config中的chunking_config
            if 'chunking_config' in parser_config:
                chunking_config = parser_config['chunking_config']
                chunk_token_num = chunking_config.get('chunk_token_num', 256)
                min_chunk_tokens = chunking_config.get('min_chunk_tokens', 10)
                chunking_strategy = chunking_config.get('strategy', 'smart')
                logger.info(f"DOTS分块配置: strategy={chunking_strategy}, chunk_size={chunk_token_num}, min_size={min_chunk_tokens}")
            # 向后兼容：直接从parser_config中获取
            elif 'chunk_token_num' in parser_config:
                chunk_token_num = parser_config.get('chunk_token_num', 256)
                logger.info(f"使用parser_config中的chunk_token_num: {chunk_token_num}")
        
        # 创建临时目录用于图片处理
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            processor_result = process_dots_result(
                document_results,
                chunk_token_num=chunk_token_num,
                min_chunk_tokens=min_chunk_tokens,
                chunking_strategy=chunking_strategy,
                kb_id=kb_id,  # 传递知识库ID用于图片上传
                temp_dir=temp_dir,  # 传递临时目录用于图片处理
                chunking_config=chunking_config  # 传递完整分块配置
            )
        
        if not processor_result['success']:
            raise Exception("DOTS结果处理失败")
        
        if update_progress:
            update_progress(0.6, f"生成了 {processor_result['chunks'].__len__()} 个文档块")
        
        # 5. 创建RAGFlow资源
        chunk_count = create_ragflow_resources(
            doc_id=doc_id,
            kb_id=kb_id,
            processor_result=processor_result,
            update_progress=update_progress,
            embedding_config=embedding_config
        )
        
        if update_progress:
            update_progress(1.0, f"DOTS OCR解析完成，生成 {chunk_count} 个文档块")
        
        logger.info(f"DOTS文档处理完成: doc_id={doc_id}, chunks={chunk_count}")
        return chunk_count
        
    except Exception as e:
        logger.error(f"DOTS文档处理失败: doc_id={doc_id}, error={e}")
        if update_progress:
            update_progress(None, f"DOTS解析失败: {str(e)}")
        raise

def is_dots_supported_file(file_path: str) -> bool:
    """检查文件是否支持DOTS OCR处理
    
    Args:
        file_path: 文件路径
        
    Returns:
        bool: 是否支持
    """
    file_ext = Path(file_path).suffix.lower()
    supported_extensions = ['.pdf', '.png', '.jpg', '.jpeg', '.bmp', '.tiff']
    return file_ext in supported_extensions

def test_dots_service() -> dict:
    """测试DOTS服务状态
    
    Returns:
        dict: 测试结果
    """
    try:
        adapter = get_global_adapter()
        return adapter.test_connection()
    except Exception as e:
        return {
            'status': 'error',
            'message': f'测试DOTS服务异常: {str(e)}'
        }