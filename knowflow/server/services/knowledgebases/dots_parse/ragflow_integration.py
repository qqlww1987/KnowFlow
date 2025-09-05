#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DOTS OCR 与 RAGFlow 集成模块

将DOTS OCR的解析结果集成到RAGFlow的存储和检索系统中，复用mineru的分块处理逻辑:
- 使用增强的batch API进行分块存储
- 复用mineru的ragflow_build模块
- 支持统一的数据格式和处理流程
"""

import os
import json
import uuid
import logging
import tempfile
from typing import Dict, List, Any, Optional, Callable
from pathlib import Path

# 复用mineru的相关模块
from ..mineru_parse.ragflow_build import get_ragflow_doc, add_chunks_with_enhanced_batch_api
from ..mineru_parse.utils import update_document_progress
try:
    from database import get_minio_client
except ImportError:
    # 如果直接导入失败，尝试相对导入
    from ....database import get_minio_client

logger = logging.getLogger(__name__)

class RAGFlowIntegration:
    """DOTS OCR 与 RAGFlow 的集成类，复用mineru的处理逻辑"""
    
    def __init__(self, kb_id: str, doc_id: str, embedding_config: Optional[Dict] = None):
        """初始化RAGFlow集成
        
        Args:
            kb_id: 知识库ID
            doc_id: 文档ID
            embedding_config: 嵌入模型配置
        """
        self.kb_id = kb_id
        self.doc_id = doc_id
        self.embedding_config = embedding_config or {}
        
        # 数据库和存储客户端
        self.minio_client = get_minio_client()
        
        # 获取RAGFlow文档对象（复用mineru逻辑）
        self.doc, self.dataset = get_ragflow_doc(doc_id, kb_id)
    
    def create_chunks_in_ragflow(self, chunks: List[Dict[str, Any]], 
                                update_progress: Optional[Callable] = None) -> int:
        """将DOTS解析的chunks存储到RAGFlow系统中（复用mineru的batch API）
        
        Args:
            chunks: DOTS处理器生成的分块列表
            update_progress: 进度更新回调函数
            
        Returns:
            int: 成功创建的块数量
        """
        if not chunks:
            logger.warning("没有文档块需要创建")
            return 0
        
        # 转换DOTS chunks为RAGFlow batch API格式
        batch_chunks = []
        for i, chunk_data in enumerate(chunks):
            content = chunk_data.get('content', '').strip()
            if not content:
                continue
                
            chunk_request = {
                "content": content,
                "important_keywords": [],  # 可以根据需要添加关键词提取
                "questions": []  # 可以根据需要添加问题生成
            }
            
            # 添加位置信息（完全复用Mineru的逻辑和格式）
            # 统一排序机制：固定page_num_int=1，top_int=原始索引（与Mineru保持一致）
            chunk_request["page_num_int"] = [1]  # 固定为1，保证所有chunks都在同一"页"
            chunk_request["top_int"] = i  # 使用分块索引保证顺序
            
            # 尝试获取精确位置信息（作为额外的位置数据，不影响排序）
            if chunk_data.get('positions'):
                # 使用从DOTS元素映射得到的精确坐标（Mineru格式）
                chunk_request["positions"] = chunk_data['positions']
                logger.debug(f"分块 {i}: 找到精确坐标 ({len(chunk_data['positions'])} 个位置) + 索引排序 (page=1, top={i})")
            else:
                logger.debug(f"分块 {i}: 使用索引排序 (page=1, top={i})")
            
            batch_chunks.append(chunk_request)
        
        if not batch_chunks:
            logger.warning("没有有效的chunks需要创建")
            return 0
        
        # 使用mineru的batch API（复用代码）
        chunk_contents = [chunk["content"] for chunk in batch_chunks]
        chunk_content_to_index = {content: i for i, content in enumerate(chunk_contents)}
        
        try:
            # 直接调用mineru的add_chunks_with_enhanced_batch_api
            chunk_count = add_chunks_with_enhanced_batch_api(
                self.doc, 
                chunk_contents, 
                None,  # 没有md_file_path，设为None
                chunk_content_to_index, 
                update_progress
            )
            
            logger.info(f"成功创建 {chunk_count} 个文档块")
            return chunk_count
            
        except Exception as e:
            logger.error(f"使用batch API创建chunks失败: {e}")
            raise
    
    def save_markdown_to_minio(self, markdown_content: str, 
                              bucket_name: Optional[str] = None) -> Optional[str]:
        """将Markdown内容保存到MinIO
        
        Args:
            markdown_content: Markdown内容
            bucket_name: 存储桶名称，默认使用知识库ID
            
        Returns:
            str: MinIO中的文件路径，失败时返回None
        """
        if not markdown_content:
            logger.warning("Markdown内容为空，跳过保存")
            return None
        
        try:
            bucket = bucket_name or self.kb_id
            
            # 确保bucket存在
            if not self.minio_client.bucket_exists(bucket):
                logger.warning(f"MinIO bucket {bucket} 不存在，跳过保存")
                return None
            
            # 生成文件路径
            file_name = f"{self.doc_id}_dots_output.md"
            file_path = f"dots_output/{file_name}"
            
            # 上传内容
            from io import BytesIO
            content_bytes = markdown_content.encode('utf-8')
            content_stream = BytesIO(content_bytes)
            
            self.minio_client.put_object(
                bucket,
                file_path,
                content_stream,
                length=len(content_bytes),
                content_type='text/markdown'
            )
            
            logger.info(f"Markdown内容已保存到 MinIO: {bucket}/{file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"保存Markdown到MinIO失败: {e}")
            return None
    
    def create_elasticsearch_entries(self, chunks: List[Dict[str, Any]]) -> bool:
        """创建Elasticsearch索引条目（由batch API自动处理）
        
        Args:
            chunks: 文档块列表
            
        Returns:
            bool: 是否成功
        """
        # batch API会自动处理Elasticsearch索引，无需单独处理
        logger.info("Elasticsearch索引由batch API自动处理")
        return True
    
    def process_and_store(self, processor_result: Dict[str, Any], 
                         update_progress: Optional[Callable] = None) -> Dict[str, Any]:
        """处理DOTS结果并存储到RAGFlow（复用mineru的处理逻辑）
        
        Args:
            processor_result: DOTS处理器的结果
            update_progress: 进度更新回调
            
        Returns:
            dict: 存储结果
        """
        try:
            if not processor_result.get('success', False):
                return {
                    'success': False,
                    'error': 'DOTS处理器结果无效',
                    'chunk_count': 0
                }
            
            chunks = processor_result.get('chunks', [])
            markdown_content = processor_result.get('markdown_content', '')
            
            if update_progress:
                update_progress(0.4, "开始保存解析结果")
            
            # 1. 使用batch API创建文档块（复用mineru逻辑）
            chunk_count = self.create_chunks_in_ragflow(chunks, update_progress)
            
            if update_progress:
                update_progress(0.8, "保存Markdown到存储")
            
            # 2. 保存Markdown到MinIO（可选）
            markdown_path = self.save_markdown_to_minio(markdown_content)
            
            # 3. Elasticsearch索引由batch API自动处理
            es_success = self.create_elasticsearch_entries(chunks)
            
            # 4. 更新文档进度（复用mineru的逻辑）
            if update_progress:
                update_progress(0.95, f"完成数据存储，成功处理 {chunk_count} 个chunks")
            
            # 使用mineru的进度更新函数
            update_document_progress(
                self.doc_id, 
                progress=1.0, 
                message=f"DOTS处理完成，共 {chunk_count} 个chunks",
                chunk_count=chunk_count
            )
            
            return {
                'success': True,
                'chunk_count': chunk_count,
                'markdown_saved': markdown_path is not None,
                'markdown_path': markdown_path,
                'elasticsearch_indexed': es_success,
                'elements_count': processor_result.get('elements_count', 0),
                'pages_count': processor_result.get('pages_count', 0)
            }
            
        except Exception as e:
            logger.error(f"处理和存储DOTS结果失败: {e}")
            # 更新错误状态
            update_document_progress(
                self.doc_id, 
                progress=1.0, 
                message=f"DOTS处理失败: {str(e)}",
                status="0"  # 标记为失败
            )
            return {
                'success': False,
                'error': f'存储失败: {str(e)}',
                'chunk_count': 0
            }

def create_ragflow_resources(doc_id: str, kb_id: str, 
                           processor_result: Dict[str, Any],
                           update_progress: Optional[Callable] = None,
                           embedding_config: Optional[Dict] = None) -> int:
    """创建RAGFlow资源的便捷函数（复用mineru设计模式）
    
    Args:
        doc_id: 文档ID
        kb_id: 知识库ID
        processor_result: DOTS处理器结果
        update_progress: 进度更新回调
        embedding_config: 嵌入模型配置
        
    Returns:
        int: 创建的文档块数量
    """
    try:
        integration = RAGFlowIntegration(kb_id, doc_id, embedding_config)
        result = integration.process_and_store(processor_result, update_progress)
        
        if result['success']:
            logger.info(f"DOTS RAGFlow资源创建成功: {result['chunk_count']} 个块")
            return result['chunk_count']
        else:
            logger.error(f"DOTS RAGFlow资源创建失败: {result.get('error', 'Unknown error')}")
            return 0
            
    except Exception as e:
        logger.error(f"创建DOTS RAGFlow资源异常: {e}")
        # 确保错误状态被记录
        try:
            update_document_progress(
                doc_id, 
                progress=1.0, 
                message=f"DOTS处理异常: {str(e)}",
                status="0"
            )
        except:
            pass
        return 0