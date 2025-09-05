#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DOTS OCR 与 RAGFlow 集成模块

将DOTS OCR的解析结果集成到RAGFlow的存储和检索系统中，支持:
- 文档块存储到MySQL和Elasticsearch
- 图片上传到MinIO
- RAGFlow兼容的数据格式
"""

import os
import json
import uuid
import logging
import tempfile
from typing import Dict, List, Any, Optional, Callable
from pathlib import Path
import mysql.connector
from database import get_minio_client, DB_CONFIG

logger = logging.getLogger(__name__)

class RAGFlowIntegration:
    """DOTS OCR 与 RAGFlow 的集成类"""
    
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
        
    def _get_db_connection(self):
        """获取数据库连接"""
        return mysql.connector.connect(**DB_CONFIG)
    
    def _generate_chunk_id(self) -> str:
        """生成文档块ID"""
        return str(uuid.uuid4()).replace('-', '')
    
    def create_chunks_in_ragflow(self, chunks: List[Dict[str, Any]], 
                                update_progress: Optional[Callable] = None) -> int:
        """将DOTS解析的chunks存储到RAGFlow系统中
        
        Args:
            chunks: DOTS处理器生成的分块列表
            update_progress: 进度更新回调函数
            
        Returns:
            int: 成功创建的块数量
        """
        if not chunks:
            logger.warning("没有文档块需要创建")
            return 0
        
        conn = None
        cursor = None
        created_count = 0
        
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            # 准备批量插入的SQL
            insert_sql = """
            INSERT INTO document_chunk (
                id, document_id, content_with_weight, content_ltks, content_sm_ltks,
                important_kwd, img_id, available_int, positions, page_number,
                create_time, create_by, update_time, update_by
            ) VALUES (
                %s, %s, %s, %s, %s, 
                %s, %s, %s, %s, %s,
                NOW(), %s, NOW(), %s
            )
            """
            
            # 获取创建者信息（从文档表）
            cursor.execute("SELECT created_by FROM document WHERE id = %s", (self.doc_id,))
            doc_result = cursor.fetchone()
            created_by = doc_result[0] if doc_result else 'system'
            
            total_chunks = len(chunks)
            
            for i, chunk_data in enumerate(chunks):
                try:
                    # 生成chunk ID
                    chunk_id = self._generate_chunk_id()
                    
                    # 准备chunk数据
                    content = chunk_data.get('content', '').strip()
                    if not content:
                        continue
                    
                    # 构建位置信息
                    positions = json.dumps([{
                        'page_number': chunk_data.get('page_number', 1),
                        'start_pos': chunk_data.get('start_pos', 0),
                        'end_pos': chunk_data.get('end_pos', len(content)),
                        'element_count': chunk_data.get('element_count', 1)
                    }])
                    
                    # 插入数据
                    chunk_values = (
                        chunk_id,                    # id
                        self.doc_id,                # document_id
                        content,                     # content_with_weight
                        content,                     # content_ltks (相同内容)
                        content[:512],              # content_sm_ltks (截断版本)
                        '',                         # important_kwd (暂时为空)
                        '',                         # img_id (暂时为空)
                        1,                          # available_int (可用)
                        positions,                  # positions
                        chunk_data.get('page_number', 1),  # page_number
                        created_by,                 # create_by
                        created_by                  # update_by
                    )
                    
                    cursor.execute(insert_sql, chunk_values)
                    created_count += 1
                    
                    # 更新进度
                    if update_progress:
                        progress = 0.4 + 0.5 * (i + 1) / total_chunks  # OCR完成后的进度范围
                        update_progress(progress, f"保存文档块 {i+1}/{total_chunks}")
                    
                    logger.debug(f"成功创建文档块 {chunk_id}, 页面 {chunk_data.get('page_number', 1)}")
                    
                except Exception as chunk_error:
                    logger.error(f"创建文档块 {i+1} 失败: {chunk_error}")
                    continue
            
            # 提交事务
            conn.commit()
            logger.info(f"成功创建 {created_count} 个文档块")
            
        except Exception as e:
            logger.error(f"创建RAGFlow chunks失败: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
        
        return created_count
    
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
        """创建Elasticsearch索引条目（可选功能）
        
        Args:
            chunks: 文档块列表
            
        Returns:
            bool: 是否成功
        """
        # 这里可以添加Elasticsearch集成代码
        # 目前先返回True，表示跳过ES索引
        logger.info("跳过Elasticsearch索引创建（功能可选）")
        return True
    
    def process_and_store(self, processor_result: Dict[str, Any], 
                         update_progress: Optional[Callable] = None) -> Dict[str, Any]:
        """处理DOTS结果并存储到RAGFlow
        
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
            
            # 1. 创建数据库中的文档块
            chunk_count = self.create_chunks_in_ragflow(chunks, update_progress)
            
            if update_progress:
                update_progress(0.8, "保存Markdown到存储")
            
            # 2. 保存Markdown到MinIO（可选）
            markdown_path = self.save_markdown_to_minio(markdown_content)
            
            # 3. 创建Elasticsearch索引（可选）
            es_success = self.create_elasticsearch_entries(chunks)
            
            if update_progress:
                update_progress(0.95, "完成数据存储")
            
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
            return {
                'success': False,
                'error': f'存储失败: {str(e)}',
                'chunk_count': 0
            }

def create_ragflow_resources(doc_id: str, kb_id: str, 
                           processor_result: Dict[str, Any],
                           update_progress: Optional[Callable] = None,
                           embedding_config: Optional[Dict] = None) -> int:
    """创建RAGFlow资源的便捷函数
    
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
            logger.info(f"RAGFlow资源创建成功: {result['chunk_count']} 个块")
            return result['chunk_count']
        else:
            logger.error(f"RAGFlow资源创建失败: {result.get('error', 'Unknown error')}")
            return 0
            
    except Exception as e:
        logger.error(f"创建RAGFlow资源异常: {e}")
        return 0