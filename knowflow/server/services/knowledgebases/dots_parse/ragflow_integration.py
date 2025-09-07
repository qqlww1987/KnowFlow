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
    
    def create_chunks_in_ragflow_unified(self, processor_result: Dict[str, Any], 
                                        update_progress: Optional[Callable] = None) -> int:
        """统一的RAGFlow集成 - 完全复用MinerU的batch API和父子分块处理
        
        Args:
            processor_result: DOTS统一处理器的结果
            update_progress: 进度更新回调函数
            
        Returns:
            int: 成功创建的块数量
        """
        chunks = processor_result.get('chunks', [])
        if not chunks:
            logger.warning("没有文档块需要创建")
            return 0
        
        # 1. 检查是否为父子分块
        is_parent_child = processor_result.get('is_parent_child', False)
        
        if is_parent_child:
            # 父子分块流程 - 复用MinerU的parent_child_data格式
            return self._handle_parent_child_chunks(processor_result, update_progress)
        else:
            # 普通分块流程 - 复用MinerU的标准batch API
            return self._handle_standard_chunks(processor_result, update_progress)
    
    def _handle_parent_child_chunks(self, processor_result: Dict, update_progress: Callable) -> int:
        """处理父子分块 - 完全复用MinerU逻辑"""
        
        # 构造MinerU格式的parent_child_data
        parent_child_data = {
            'doc_id': self.doc_id,
            'kb_id': self.kb_id,
            'parent_chunks': processor_result.get('parent_chunks', []),
            'child_chunks': processor_result.get('child_chunks', []),
            'relationships': processor_result.get('relationships', [])
        }
        
        # 提取子分块内容和坐标信息（用于向量化）
        child_chunks_data = parent_child_data['child_chunks']
        chunks_content = []
        chunks_with_positions = []  # 保存带坐标信息的分块
        
        for i, chunk_info in enumerate(child_chunks_data):
            if hasattr(chunk_info, 'content'):
                # 如果是ChunkInfo对象
                content = chunk_info.content
            elif isinstance(chunk_info, dict):
                # 如果是字典格式
                content = chunk_info.get('content', '')
            else:
                content = str(chunk_info)
            
            chunks_content.append(content)
            
            # 构造带坐标信息的分块数据
            chunk_with_coords = {
                "content": content,
                "important_keywords": [],
                "questions": []
            }
            
            # 添加位置信息
            chunk_with_coords["page_num_int"] = [1]  # 固定为1的排序
            chunk_with_coords["top_int"] = i  # 使用索引排序
            
            # 检查是否有精确坐标信息
            if isinstance(chunk_info, dict) and chunk_info.get('positions'):
                chunk_with_coords["positions"] = chunk_info['positions']
                logger.debug(f"父子分块 {i}: 找到精确坐标 ({len(chunk_info['positions'])} 个位置)")
            elif isinstance(chunk_info, dict) and chunk_info.get('has_coordinates'):
                # 如果有has_coordinates标记但没有positions，记录警告
                logger.warning(f"父子分块 {i}: has_coordinates=True 但找不到positions")
            
            chunks_with_positions.append(chunk_with_coords)
        
        chunk_content_to_index = {chunk: i for i, chunk in enumerate(chunks_content)}
        
        coords_count = sum(1 for c in chunks_with_positions if 'positions' in c)
        logger.info(f"DOTS父子分块坐标检查: {coords_count}/{len(chunks_with_positions)} 个子块有精确坐标")
        
        logger.info(f"DOTS父子分块处理: {len(parent_child_data.get('parent_chunks', []))}父块, "
                   f"{len(child_chunks_data)}子块, {len(parent_child_data.get('relationships', []))}映射关系")
        
        # 直接调用MinerU的增强batch API
        from ..mineru_parse.ragflow_build import add_chunks_with_enhanced_batch_api
        
        # 传递带坐标信息的分块数据给batch API
        return self._call_enhanced_batch_api_with_coordinates(
            chunks_with_positions,
            parent_child_data,
            update_progress
        )
    
    def _call_enhanced_batch_api_with_coordinates(self, chunks_with_positions: List[Dict], 
                                                 parent_child_data: Dict, 
                                                 update_progress: Callable) -> int:
        """调用增强batch API，确保坐标信息被正确传递"""
        try:
            # 导入MinerU的增强batch API
            from ..mineru_parse.ragflow_build import add_chunks_with_enhanced_batch_api
            
            # 准备子分块内容和索引映射
            child_chunks_content = []
            chunk_content_to_index = {}
            chunks_with_coords = []
            
            for i, chunk_info in enumerate(chunks_with_positions):
                content = chunk_info.get('content', '').strip()
                if content:
                    child_chunks_content.append(content)
                    chunk_content_to_index[content] = i
                    
                    # 构建包含坐标的分块数据
                    chunk_with_coords = {
                        'content': content,
                        'index': i
                    }
                    
                    # 如果有坐标信息，添加到分块数据中
                    if chunk_info.get('positions'):
                        chunk_with_coords['positions'] = chunk_info['positions']
                        logger.debug(f"子分块{i}包含坐标: {len(chunk_info['positions'])}个位置")
                    
                    chunks_with_coords.append(chunk_with_coords)
            
            logger.info(f"调用增强batch API: {len(child_chunks_content)}个子分块内容，"
                       f"{len(chunks_with_coords)}个包含坐标信息的分块")
            
            # 在parent_child_data中添加坐标信息
            enhanced_parent_child_data = parent_child_data.copy()
            enhanced_parent_child_data['chunks_with_coords'] = chunks_with_coords
            
            # 调用MinerU的增强batch API，传递完整的坐标信息
            return add_chunks_with_enhanced_batch_api(
                doc=self.doc,
                chunks=child_chunks_content,
                md_file_path=None,  # DOTS不需要md文件路径
                chunk_content_to_index=chunk_content_to_index,
                update_progress=update_progress,
                parent_child_data=enhanced_parent_child_data,  # 传递增强的父子数据（包含坐标）
                chunks_with_coordinates=chunks_with_coords  # 传递DOTS坐标信息
            )
            
        except Exception as e:
            logger.error(f"调用增强batch API失败: {e}")
            raise
    
    def _handle_standard_chunks(self, processor_result: Dict, update_progress: Callable) -> int:
        """处理标准分块 - 复用MinerU的batch API，包含坐标信息"""
        
        chunks = processor_result.get('chunks', [])
        
        # 提取分块内容和坐标信息
        chunks_content = []
        chunks_with_coordinates = []
        
        for chunk in chunks:
            content = chunk.get('content', '').strip()
            if content:
                chunks_content.append(content)
                
                # 构建包含坐标信息的分块数据
                chunk_with_coord = {
                    'content': content
                }
                
                # 检查是否有坐标信息
                if chunk.get('positions'):
                    chunk_with_coord['positions'] = chunk['positions']
                    logger.debug(f"标准分块包含坐标: {len(chunk['positions'])}个位置")
                
                chunks_with_coordinates.append(chunk_with_coord)
        
        if not chunks_content:
            logger.warning("没有有效的标准分块内容")
            return 0
        
        chunk_content_to_index = {chunk: i for i, chunk in enumerate(chunks_content)}
        coords_count = sum(1 for c in chunks_with_coordinates if c.get('positions'))
        
        logger.info(f"DOTS标准分块处理: {len(chunks_content)}个分块，其中{coords_count}个有坐标信息")
        
        # 调用MinerU的增强batch API，传递坐标信息
        from ..mineru_parse.ragflow_build import add_chunks_with_enhanced_batch_api
        
        return add_chunks_with_enhanced_batch_api(
            doc=self.doc,
            chunks=chunks_content,
            md_file_path=None,  # DOTS不需要md文件
            chunk_content_to_index=chunk_content_to_index,
            update_progress=update_progress,
            parent_child_data=None,  # 标准分块不传递父子数据
            chunks_with_coordinates=chunks_with_coordinates  # 传递DOTS坐标信息
        )
    
    def create_chunks_in_ragflow(self, chunks: List[Dict[str, Any]], 
                                update_progress: Optional[Callable] = None) -> int:
        """原有方法（向后兼容）——将DOTS解析的chunks存储到RAGFlow系统中（复用mineru的batch API）
        
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
            # 使用DOTS专用的batch API调用，直接传递包含坐标信息的batch_chunks
            chunk_count = self._add_dots_chunks_with_batch_api(
                batch_chunks, 
                update_progress
            )
            
            logger.info(f"成功创建 {chunk_count} 个文档块")
            return chunk_count
            
        except Exception as e:
            logger.error(f"使用batch API创建chunks失败: {e}")
            raise
    
    def _add_dots_chunks_with_batch_api(self, batch_chunks: List[Dict[str, Any]], 
                                       update_progress: Optional[Callable] = None) -> int:
        """使用batch API添加DOTS chunks，保持坐标信息
        
        Args:
            batch_chunks: 包含坐标信息的batch数据
            update_progress: 进度更新回调
            
        Returns:
            int: 成功添加的分块数量
        """
        if not batch_chunks:
            if update_progress:
                update_progress(0.8, "没有chunks需要添加")
            return 0
        
        if update_progress:
            update_progress(0.8, f"开始批量添加{len(batch_chunks)}个DOTS chunks...")
        
        try:
            import requests
            import json
            
            # 获取API基本信息（复用mineru的方式）
            base_url = self.doc.rag.api_url
            headers = self.doc.rag.authorization_header
            
            # 构建请求数据
            request_data = {
                "chunks": batch_chunks,
                "batch_size": 20
            }
            
            # 调用增强的batch接口
            api_url = f"{base_url}/datasets/{self.doc.dataset_id}/documents/{self.doc.id}/chunks/batch"
            logger.info(f"🔗 发送DOTS batch请求到: {api_url}")
            logger.debug(f"📦 发送 {len(batch_chunks)} 个chunks，其中 {sum(1 for c in batch_chunks if c.get('positions'))} 个有坐标信息")
            
            response = requests.post(api_url, json=request_data, headers=headers)
            
            logger.info(f"📥 DOTS batch接口响应状态码: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    if result.get("code") == 0:
                        # 批量添加成功
                        data = result.get("data", {})
                        added = data.get("total_added", 0)
                        failed = data.get("total_failed", 0)
                        
                        logger.info(f"✅ DOTS batch接口处理完成: 成功 {added} 个，失败 {failed} 个")
                        
                        # 统计坐标信息
                        coords_count = sum(1 for chunk in batch_chunks if chunk.get('positions'))
                        logger.info(f"📍 包含坐标信息的分块: {coords_count}/{len(batch_chunks)}")
                        
                        if update_progress:
                            update_progress(0.95, f"DOTS batch处理完成: 成功 {added}/{len(batch_chunks)} chunks")
                        return added
                    else:
                        # 批量添加失败
                        error_msg = result.get("message", "Unknown error")
                        logger.error(f"❌ DOTS batch接口失败: {error_msg}")
                        if update_progress:
                            update_progress(0.95, f"DOTS batch处理失败: {error_msg}")
                        return 0
                except json.JSONDecodeError:
                    logger.error(f"❌ DOTS batch接口响应解析失败")
                    if update_progress:
                        update_progress(0.95, "响应解析失败")
                    return 0
            else:
                logger.error(f"❌ DOTS batch接口HTTP错误: {response.status_code}")
                logger.error(f"响应内容: {response.text[:500]}")
                if update_progress:
                    update_progress(0.95, f"HTTP错误: {response.status_code}")
                return 0
                
        except Exception as e:
            if update_progress:
                update_progress(0.95, f"DOTS batch处理异常: {str(e)}")
            logger.error(f"❌ DOTS batch处理异常: {e}")
            import traceback
            traceback.print_exc()
            return 0
    
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
        """处理DOTS结果并存储到RAGFlow（使用统一分块接口）
        
        Args:
            processor_result: DOTS统一处理器的结果
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
            is_parent_child = processor_result.get('is_parent_child', False)
            
            if update_progress:
                progress_msg = f"开始保存DOTS解析结果 ({'Parent-Child' if is_parent_child else 'Standard'} 模式)"
                update_progress(0.4, progress_msg)
            
            # 1. 使用统一的batch API创建文档块（完全复用MinerU逻辑）
            chunk_count = self.create_chunks_in_ragflow_unified(processor_result, update_progress)
            
            # 2. 保存Markdown到MinIO（可选）
            if update_progress:
                update_progress(0.8, "保存Markdown到存储")
            
            markdown_path = self.save_markdown_to_minio(markdown_content)
            
            # 3. Elasticsearch索引由batch API自动处理
            es_success = self.create_elasticsearch_entries(chunks)
            
            # 4. 更新文档进度（复用MinerU的逻辑）
            progress_msg = f"完成DOTS数据存储，成功处理 {chunk_count} 个chunks"
            if is_parent_child:
                total_parents = processor_result.get('total_parents', 0)
                total_children = processor_result.get('total_children', 0)
                progress_msg += f" (父块:{total_parents}, 子块:{total_children})"
            
            if update_progress:
                update_progress(0.95, progress_msg)
            
            # 使用MinerU的进度更新函数
            update_document_progress(
                self.doc_id, 
                progress=1.0, 
                message=f"DOTS统一处理完成，共 {chunk_count} 个chunks" + 
                        (f" (父子分块)" if is_parent_child else ""),
                chunk_count=chunk_count
            )
            
            # 构建返回结果，包含统一分块的所有信息
            result = {
                'success': True,
                'chunk_count': chunk_count,
                'markdown_saved': markdown_path is not None,
                'markdown_path': markdown_path,
                'elasticsearch_indexed': es_success,
                'elements_count': processor_result.get('elements_count', 0),
                'pages_count': processor_result.get('pages_count', 0),
                'chunking_strategy': processor_result.get('chunking_strategy', 'unknown'),
                'coordinate_source': processor_result.get('coordinate_source', 'dots'),
                'has_coordinates': processor_result.get('has_coordinates', False)
            }
            
            # 如果是父子分块，添加父子分块结果
            if is_parent_child:
                result.update({
                    'is_parent_child': True,
                    'total_parents': processor_result.get('total_parents', 0),
                    'total_children': processor_result.get('total_children', 0),
                    'parent_child_relationships': len(processor_result.get('relationships', []))
                })
            
            return result
            
        except Exception as e:
            logger.error(f"处理和存储DOTS结果失败: {e}")
            import traceback
            traceback.print_exc()
            
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
                'chunk_count': 0,
                'is_parent_child': processor_result.get('is_parent_child', False)
            }

def create_ragflow_resources(doc_id: str, kb_id: str, 
                           processor_result: Dict[str, Any],
                           update_progress: Optional[Callable] = None,
                           embedding_config: Optional[Dict] = None) -> int:
    """创建RAGFlow资源的便捷函数（使用统一RAGFlow集成，完全复用MinerU逻辑）
    
    Args:
        doc_id: 文档ID
        kb_id: 知识库ID
        processor_result: DOTS统一处理器结果
        update_progress: 进度更新回调
        embedding_config: 嵌入模型配置
        
    Returns:
        int: 创建的文档块数量
    """
    try:
        integration = RAGFlowIntegration(kb_id, doc_id, embedding_config)
        result = integration.process_and_store(processor_result, update_progress)
        
        if result['success']:
            is_parent_child = result.get('is_parent_child', False)
            chunk_info = f"{result['chunk_count']} 个块"
            if is_parent_child:
                chunk_info += f" (父块:{result.get('total_parents', 0)}, 子块:{result.get('total_children', 0)})"
            
            logger.info(f"DOTS统一RAGFlow资源创建成功: {chunk_info}")
            return result['chunk_count']
        else:
            logger.error(f"DOTS统一RAGFlow资源创建失败: {result.get('error', 'Unknown error')}")
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