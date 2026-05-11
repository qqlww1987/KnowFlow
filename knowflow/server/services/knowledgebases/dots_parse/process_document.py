#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DOTS OCR 文档处理入口

提供与现有document_parser.py兼容的接口，支持:
- PDF文档的DOTS OCR解析
- 图片文件的OCR处理  
- 非PDF文件的预处理转换（Office文档、图像、URL等）
- 与RAGFlow系统的集成
"""

import os
import tempfile
import logging
from typing import Optional, Callable, Tuple
from pathlib import Path
from io import BytesIO

from .dots_fastapi_adapter import get_global_adapter
from .dots_processor import process_dots_result
from .ragflow_integration import create_ragflow_resources
# 导入MinerU的文件转换器
from ..mineru_parse.file_converter import ensure_pdf, OFFICE_EXTENSIONS

logger = logging.getLogger(__name__)

def _ensure_pdf_for_dots(file_input: str, job_temp_dir: str, update_progress: Optional[Callable] = None) -> Tuple[Optional[str], Optional[str]]:
    """
    为DOTS处理确保输入文件为PDF格式
    
    Args:
        file_input: 输入文件路径或URL
        job_temp_dir: 临时目录
        update_progress: 进度回调函数
        
    Returns:
        tuple: (pdf_file_path, temp_file_to_cleanup)
            - pdf_file_path: 可用于处理的PDF文件路径，失败时为None
            - temp_file_to_cleanup: 需要清理的临时文件路径，无需清理时为None
    """
    logger.info(f"DOTS预处理: 确保文件为PDF格式 - {file_input}")
    
    if update_progress:
        update_progress(0.05, "检查文件格式...")
    
    # 获取文件扩展名
    file_ext = os.path.splitext(file_input)[1].lower()
    
    # 检查是否为支持的非PDF格式
    if file_ext not in ['.pdf'] and (file_input.startswith('http') or file_ext in OFFICE_EXTENSIONS or file_ext in {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff'}):
        logger.info(f"检测到非PDF文件，开始转换: {file_input} (扩展名: {file_ext})")
        
        if update_progress:
            update_progress(0.1, f"转换{file_ext}文件为PDF...")
        
        try:
            # 使用MinerU的转换器
            pdf_path, temp_path = ensure_pdf(file_input, job_temp_dir)
            
            if pdf_path:
                logger.info(f"文件转换成功: {file_input} -> {pdf_path}")
                if update_progress:
                    update_progress(0.2, "文件转换完成")
                return pdf_path, temp_path
            else:
                logger.error(f"文件转换失败: {file_input}")
                return None, None
                
        except Exception as e:
            logger.error(f"文件转换异常: {file_input}, 错误: {e}")
            return None, None
    
    elif file_ext == '.pdf':
        # 已经是PDF文件
        logger.info(f"输入文件已是PDF格式: {file_input}")
        if update_progress:
            update_progress(0.2, "PDF文件验证完成")
        
        if os.path.exists(file_input):
            return file_input, None
        else:
            logger.error(f"PDF文件不存在: {file_input}")
            return None, None
    
    else:
        # 不支持的文件类型
        logger.warning(f"不支持的文件类型: {file_input} (扩展名: {file_ext})")
        logger.info(f"DOTS支持的文件类型: PDF, 以及可转换的格式: {list(OFFICE_EXTENSIONS)} + 图像文件")
        return None, None

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
    
    支持的文件类型:
    - PDF文件 (直接处理)
    - Office文档 (.docx, .pptx, .xlsx等，通过Gotenberg转换为PDF)
    - 图像文件 (.jpg, .png等，通过Gotenberg转换为PDF)
    - URL网页 (通过Gotenberg转换为PDF)
    
    Args:
        doc_id: 文档ID
        file_path: 文件路径或URL
        kb_id: 知识库ID  
        update_progress: 进度更新回调函数
        embedding_config: 嵌入模型配置
        parser_config: 解析器配置（包含分块策略设置）
        
    Returns:
        int: 生成的文档块数量
    """
    temp_file_to_cleanup = None
    
    try:
        # 创建任务临时目录
        job_temp_dir = tempfile.mkdtemp(prefix=f"dots_job_{doc_id}_")
        logger.info(f"DOTS处理任务临时目录: {job_temp_dir}")
        
        if update_progress:
            update_progress(0.05, "准备处理文件...")
        
        # 1. 预处理: 确保输入文件为PDF格式
        processed_file_path, temp_file_to_cleanup = _ensure_pdf_for_dots(
            file_path, job_temp_dir, update_progress
        )
        
        if not processed_file_path:
            raise Exception(f"文件预处理失败，无法转换为PDF格式: {file_path}")
        
        logger.info(f"DOTS将处理文件: {processed_file_path} (原文件: {file_path})")
        
        if update_progress:
            update_progress(0.1, "初始化DOTS OCR服务")
        
        # 2. 初始化DOTS适配器
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
        
        # 3. 处理转换后的PDF文件（所有输入都已转换为PDF）
        # 注意：此时 processed_file_path 总是指向一个PDF文件
        logger.info(f"使用DOTS解析PDF文档: {processed_file_path}")
        document_results = _process_pdf_to_images(processed_file_path, adapter, update_progress)
        
        if update_progress:
            update_progress(0.4, "处理OCR解析结果")
        
        # 4. 处理DOTS解析结果（使用统一分块接口）
        # 从 parser_config 中提取分块配置
        chunking_config = None
        if parser_config:
            # 优先使用 parser_config 中的 chunking_config
            if 'chunking_config' in parser_config:
                chunking_config = parser_config['chunking_config']
                logger.info(f"DOTS分块配置: {chunking_config}")
            # 向后兼容：直接从 parser_config 中获取
            elif 'chunk_token_num' in parser_config:
                chunking_config = {
                    'strategy': 'smart',
                    'chunk_token_num': parser_config.get('chunk_token_num', 256),
                    'min_chunk_tokens': parser_config.get('min_chunk_tokens', 10)
                }
                logger.info(f"使用兼容配置: {chunking_config}")
        
        # 创建临时目录用于图片处理
        with tempfile.TemporaryDirectory() as temp_dir:
            processor_result = process_dots_result(
                document_results,
                kb_id=kb_id,
                temp_dir=temp_dir,
                chunking_config=chunking_config,
                doc_id=doc_id
            )
        
        if not processor_result['success']:
            raise Exception("DOTS结果处理失败")
        
        # 检查是否为父子分块并更新进度信息
        chunk_count = processor_result.get('total_chunks', len(processor_result.get('chunks', [])))
        is_parent_child = processor_result.get('is_parent_child', False)
        
        if update_progress:
            progress_msg = f"生成了 {chunk_count} 个文档块"
            if is_parent_child:
                total_parents = processor_result.get('total_parents', 0)
                total_children = processor_result.get('total_children', 0)
                progress_msg += f" (父块:{total_parents}, 子块:{total_children})"
            update_progress(0.6, progress_msg)
        
        # 5. 创建RAGFlow资源
        chunk_count = create_ragflow_resources(
            doc_id=doc_id,
            kb_id=kb_id,
            processor_result=processor_result,
            update_progress=update_progress,
            embedding_config=embedding_config
        )
        
        # 最终进度更新
        if update_progress:
            final_msg = f"DOTS OCR解析完成，生成 {chunk_count} 个文档块"
            if is_parent_child:
                final_msg += f" (父子分块模式)"
            update_progress(1.0, final_msg)
        
        logger.info(f"DOTS文档统一处理完成: doc_id={doc_id}, chunks={chunk_count}, "
                   f"strategy={processor_result.get('chunking_strategy', 'unknown')}, "
                   f"parent_child={is_parent_child}")
        return chunk_count
        
    except Exception as e:
        logger.error(f"DOTS文档统一处理失败: doc_id={doc_id}, error={e}")
        import traceback
        traceback.print_exc()
        if update_progress:
            update_progress(None, f"DOTS统一解析失败: {str(e)}")
        raise
    
    finally:
        # 清理临时文件
        if temp_file_to_cleanup and os.path.exists(temp_file_to_cleanup):
            try:
                os.remove(temp_file_to_cleanup)
                logger.info(f"已清理临时转换文件: {temp_file_to_cleanup}")
            except Exception as cleanup_error:
                logger.warning(f"清理临时文件失败: {temp_file_to_cleanup}, 错误: {cleanup_error}")
        
        # 清理任务临时目录
        try:
            if 'job_temp_dir' in locals() and os.path.exists(job_temp_dir):
                import shutil
                shutil.rmtree(job_temp_dir)
                logger.info(f"已清理任务临时目录: {job_temp_dir}")
        except Exception as cleanup_error:
            logger.warning(f"清理任务临时目录失败: {job_temp_dir}, 错误: {cleanup_error}")

def is_dots_supported_file(file_path: str) -> bool:
    """检查文件是否支持DOTS OCR处理
    
    支持的文件类型:
    - PDF文件 (直接处理)
    - Office文档 (.docx, .pptx, .xlsx等，通过Gotenberg转换)
    - 图像文件 (.jpg, .png等，通过Gotenberg转换)  
    - URL网页 (通过Gotenberg转换)
    
    Args:
        file_path: 文件路径或URL
        
    Returns:
        bool: 是否支持
    """
    # 检查URL
    if file_path.startswith('http://') or file_path.startswith('https://'):
        return True
    
    # 检查文件扩展名
    file_ext = Path(file_path).suffix.lower()
    
    # PDF文件直接支持
    if file_ext == '.pdf':
        return True
    
    # Office文档通过转换支持
    if file_ext in OFFICE_EXTENSIONS:
        return True
    
    # 图像文件通过转换支持
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
    if file_ext in image_extensions:
        return True
    
    return False

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