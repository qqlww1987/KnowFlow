#
#  Copyright 2025 The InfiniFlow Authors. All Rights Reserved.
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

"""
基于 Smart AST 分块策略的父子文档分割器
整合现有的智能分块能力，实现父子层级结构
"""

import hashlib
import json
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

# 导入现有的智能分块模块
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'knowflow', 'server', 'services', 'knowledgebases', 'mineru_parse'))

try:
    from utils import (
        split_markdown_to_chunks_smart,
        num_tokens_from_string,
        get_configured_chunk_method
    )
    SMART_CHUNKING_AVAILABLE = True
    print("[INFO] Successfully imported Smart chunking utilities.")
except ImportError:
    print("[WARNING] Could not import Smart chunking utilities. Using fallback methods.")
    SMART_CHUNKING_AVAILABLE = False
    
    # 使用tiktoken进行准确的token计算
    try:
        import tiktoken
        encoder = tiktoken.get_encoding("cl100k_base")
        
        def num_tokens_from_string(text):
            """使用tiktoken进行准确token计算"""
            return len(encoder.encode(text))
    except ImportError:
        def num_tokens_from_string(text):
            """简单token计数回退"""
            # 对中文文本的改进估算
            return len(text) // 2 if any('\u4e00' <= char <= '\u9fff' for char in text) else len(text.split())
    
    def split_markdown_to_chunks_smart(txt, chunk_token_num=256, min_chunk_tokens=10):
        """回退方法：简单按段落分割"""
        if not txt or not txt.strip():
            return []
        
        paragraphs = [p.strip() for p in txt.split('\n\n') if p.strip()]
        chunks = []
        current_chunk = []
        current_tokens = 0
        
        for para in paragraphs:
            para_tokens = num_tokens_from_string(para)
            if current_tokens + para_tokens > chunk_token_num and current_chunk:
                chunks.append('\n\n'.join(current_chunk))
                current_chunk = [para]
                current_tokens = para_tokens
            else:
                current_chunk.append(para)
                current_tokens += para_tokens
        
        if current_chunk:
            chunks.append('\n\n'.join(current_chunk))
        
        return chunks


@dataclass
class ChunkInfo:
    """分块信息数据类"""
    id: str
    content: str
    token_count: int
    char_count: int
    order: int
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class ParentChildResult:
    """父子分块结果"""
    parent_chunks: List[ChunkInfo]
    child_chunks: List[ChunkInfo]
    relationships: List[Dict[str, Any]]
    total_parents: int
    total_children: int


class SmartParentChildSplitter:
    """基于 Smart AST 分块的父子文档分割器"""
    
    def __init__(self, 
                 parent_chunk_size: int = 1024,
                 child_chunk_size: int = 256,
                 parent_overlap: int = 100,
                 child_overlap: int = 50,
                 min_child_size: int = 10,
                 parent_separator: str = r'\n\n',
                 child_separator: str = r'[。！？.!?]'):
        """
        初始化分割器
        
        Args:
            parent_chunk_size: 父分块大小（tokens）
            child_chunk_size: 子分块大小（tokens）
            parent_overlap: 父分块重叠（tokens）
            child_overlap: 子分块重叠（tokens）
            min_child_size: 最小子分块大小
            parent_separator: 父分块分隔符正则
            child_separator: 子分块分隔符正则
        """
        self.parent_chunk_size = parent_chunk_size
        self.child_chunk_size = child_chunk_size
        self.parent_overlap = parent_overlap
        self.child_overlap = child_overlap
        self.min_child_size = min_child_size
        self.parent_separator = parent_separator
        self.child_separator = child_separator
        
    def split_text(self, 
                   text: str, 
                   doc_id: str,
                   kb_id: str,
                   metadata: Optional[Dict[str, Any]] = None) -> ParentChildResult:
        """
        执行父子分块
        
        Args:
            text: 要分块的文本
            doc_id: 文档ID
            kb_id: 知识库ID
            metadata: 额外的元数据
            
        Returns:
            ParentChildResult: 父子分块结果
        """
        if not text or not text.strip():
            return ParentChildResult([], [], [], 0, 0)
        
        metadata = metadata or {}
        
        # 第一步：使用Smart分块获得基础分块
        base_chunks = split_markdown_to_chunks_smart(
            text, 
            chunk_token_num=self.child_chunk_size,
            min_chunk_tokens=self.min_child_size
        )
        
# 可以通过环境变量启用调试
        if os.environ.get("DEBUG_PARENT_CHILD", "").lower() == "true":
            print(f"📊 [DEBUG] Smart分块结果: {len(base_chunks)} 个基础分块")
            for i, chunk in enumerate(base_chunks):
                print(f"  基础分块{i+1}: {num_tokens_from_string(chunk)} tokens - {chunk[:50]}...")
        
        if not base_chunks:
            return ParentChildResult([], [], [], 0, 0)
        
        # 第二步：构建父子层级结构
        parent_chunks, child_chunks, relationships = self._build_parent_child_hierarchy(
            base_chunks, doc_id, kb_id, metadata
        )
        
        return ParentChildResult(
            parent_chunks=parent_chunks,
            child_chunks=child_chunks,
            relationships=relationships,
            total_parents=len(parent_chunks),
            total_children=len(child_chunks)
        )
    
    def _build_parent_child_hierarchy(self, 
                                     base_chunks: List[str], 
                                     doc_id: str, 
                                     kb_id: str, 
                                     metadata: Dict[str, Any]) -> Tuple[List[ChunkInfo], List[ChunkInfo], List[Dict[str, Any]]]:
        """构建父子分块层级结构"""
        
        parent_chunks = []
        child_chunks = []
        relationships = []
        
        # 直接使用Smart分块的结果作为子分块，避免重复处理
        child_order_global = 0
        current_parent_content = []
        current_parent_tokens = 0
        current_child_ids = []
        parent_order = 0
        
        for base_chunk in base_chunks:
            chunk_tokens = num_tokens_from_string(base_chunk)
            
            # 检查是否需要创建新的父分块
            if (current_parent_tokens + chunk_tokens > self.parent_chunk_size 
                and current_parent_content):
                
                # 完成当前父分块
                parent_chunk = self._create_parent_chunk(
                    current_parent_content, parent_order, doc_id, kb_id, metadata
                )
                parent_chunks.append(parent_chunk)
                
                # 建立关系映射
                for child_id in current_child_ids:
                    relationships.append({
                        'child_chunk_id': child_id,
                        'parent_chunk_id': parent_chunk.id,
                        'doc_id': doc_id,
                        'kb_id': kb_id,
                        'relevance_score': 100
                    })
                
                # 重置状态开始新的父分块
                current_parent_content = []
                current_parent_tokens = 0
                current_child_ids = []
                parent_order += 1
            
            # 创建子分块（直接使用Smart分块结果）
            child_chunk = self._create_child_chunk(
                base_chunk, child_order_global, len(current_child_ids), 
                doc_id, kb_id, metadata
            )
            child_chunks.append(child_chunk)
            current_child_ids.append(child_chunk.id)
            
            # 添加到当前父分块
            current_parent_content.append(base_chunk)
            current_parent_tokens += chunk_tokens
            child_order_global += 1
        
        # 处理最后一个父分块
        if current_parent_content:
            parent_chunk = self._create_parent_chunk(
                current_parent_content, parent_order, doc_id, kb_id, metadata
            )
            parent_chunks.append(parent_chunk)
            
            # 建立关系映射
            for child_id in current_child_ids:
                relationships.append({
                    'child_chunk_id': child_id,
                    'parent_chunk_id': parent_chunk.id,
                    'doc_id': doc_id,
                    'kb_id': kb_id,
                    'relevance_score': 100
                })
        
        return parent_chunks, child_chunks, relationships
    
    def _create_parent_chunk(self, 
                           content_parts: List[str], 
                           order: int, 
                           doc_id: str, 
                           kb_id: str, 
                           metadata: Dict[str, Any]) -> ChunkInfo:
        """创建父分块"""
        
        # 合并内容
        content = "\n\n".join(content_parts).strip()
        
        # 生成ID
        chunk_id = self._generate_chunk_id(doc_id, "parent", order, content)
        
        # 计算统计信息
        token_count = num_tokens_from_string(content)
        char_count = len(content)
        
        # 增强元数据
        chunk_metadata = {
            **metadata,
            'chunk_type': 'parent',
            'contains_children': len(content_parts),
            'chunk_method': 'parent_smart'
        }
        
        return ChunkInfo(
            id=chunk_id,
            content=content,
            token_count=token_count,
            char_count=char_count,
            order=order,
            metadata=chunk_metadata
        )
    
    def _create_child_chunk(self, 
                          content: str, 
                          global_order: int, 
                          parent_order: int,
                          doc_id: str, 
                          kb_id: str, 
                          metadata: Dict[str, Any]) -> ChunkInfo:
        """创建子分块"""
        
        # 生成ID
        chunk_id = self._generate_chunk_id(doc_id, "child", global_order, content)
        
        # 计算统计信息
        token_count = num_tokens_from_string(content)
        char_count = len(content)
        
        # 增强元数据
        chunk_metadata = {
            **metadata,
            'chunk_type': 'child',
            'parent_order': parent_order,
            'chunk_method': 'child_smart'
        }
        
        return ChunkInfo(
            id=chunk_id,
            content=content,
            token_count=token_count,
            char_count=char_count,
            order=global_order,
            metadata=chunk_metadata
        )
    
    def _generate_chunk_id(self, doc_id: str, chunk_type: str, order: int, content: str) -> str:
        """生成分块ID"""
        content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()[:8]
        return f"{doc_id}_{chunk_type}_{order:04d}_{content_hash}"
    
    def _further_split_child(self, content: str) -> List[str]:
        """进一步分割子分块（如果需要）"""
        if num_tokens_from_string(content) <= self.child_chunk_size:
            return [content]
        
        # 首先尝试按段落分割
        paragraphs = content.split('\n\n')
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
        
        chunks = []
        current_chunk_parts = []
        current_tokens = 0
        
        for paragraph in paragraphs:
            paragraph_tokens = num_tokens_from_string(paragraph)
            
            # 如果单个段落就超出了限制，需要进一步分割
            if paragraph_tokens > self.child_chunk_size:
                # 先添加当前积累的部分（如果有）
                if current_chunk_parts:
                    chunks.append('\n\n'.join(current_chunk_parts).strip())
                    current_chunk_parts = []
                    current_tokens = 0
                
                # 对超长段落按句子分割
                sentences = re.split(r'[。！？.!?]+', paragraph)
                sentences = [s.strip() for s in sentences if s.strip()]
                
                sentence_chunk_parts = []
                sentence_tokens = 0
                
                for sentence in sentences:
                    sentence_token_count = num_tokens_from_string(sentence)
                    
                    if (sentence_tokens + sentence_token_count > self.child_chunk_size 
                        and sentence_chunk_parts):
                        chunks.append('。'.join(sentence_chunk_parts) + '。')
                        sentence_chunk_parts = [sentence]
                        sentence_tokens = sentence_token_count
                    else:
                        sentence_chunk_parts.append(sentence)
                        sentence_tokens += sentence_token_count
                
                if sentence_chunk_parts:
                    chunks.append('。'.join(sentence_chunk_parts) + '。')
                    
            else:
                # 检查是否可以添加到当前分块
                if (current_tokens + paragraph_tokens > self.child_chunk_size 
                    and current_chunk_parts):
                    chunks.append('\n\n'.join(current_chunk_parts).strip())
                    current_chunk_parts = [paragraph]
                    current_tokens = paragraph_tokens
                else:
                    current_chunk_parts.append(paragraph)
                    current_tokens += paragraph_tokens
        
        # 添加最后的分块
        if current_chunk_parts:
            chunks.append('\n\n'.join(current_chunk_parts).strip())
        
        # 确保返回的分块都不为空
        return [chunk for chunk in chunks if chunk.strip()]


class ParentChildConfigManager:
    """父子分块配置管理器"""
    
    def __init__(self):
        self.default_config = {
            'parent_chunk_size': 1024,
            'child_chunk_size': 256,
            'parent_overlap': 100,
            'child_overlap': 50,
            'min_child_size': 10,
            'parent_separator': r'\n\n',
            'child_separator': r'[。！？.!?]',
            'retrieval_mode': 'parent',
            'top_k_children': 10,
            'top_k_parents': 4
        }
    
    def get_config(self, kb_id: str) -> Dict[str, Any]:
        """获取知识库的父子分块配置"""
        try:
            from api.db.parent_child_models import ParentChildConfig
            config = ParentChildConfig.get_by_id(kb_id)
            
            return {
                'parent_chunk_size': config.parent_chunk_size,
                'child_chunk_size': config.child_chunk_size,
                'parent_overlap': config.parent_chunk_overlap,
                'child_overlap': config.child_chunk_overlap,
                'parent_separator': config.parent_separator,
                'child_separator': config.child_separator,
                'retrieval_mode': config.retrieval_mode,
                'top_k_children': config.top_k_children,
                'top_k_parents': config.top_k_parents,
                'enabled': config.enabled,
                **json.loads(config.config_json or '{}')
            }
        except:
            # 返回默认配置
            return self.default_config.copy()
    
    def create_splitter(self, kb_id: str) -> SmartParentChildSplitter:
        """根据配置创建分割器"""
        config = self.get_config(kb_id)
        
        return SmartParentChildSplitter(
            parent_chunk_size=config['parent_chunk_size'],
            child_chunk_size=config['child_chunk_size'],
            parent_overlap=config['parent_overlap'],
            child_overlap=config['child_overlap'],
            min_child_size=config.get('min_child_size', 10),
            parent_separator=config['parent_separator'],
            child_separator=config['child_separator']
        )