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
RAGFlow 专用的父子文档检索器
集成 LangChain ParentDocumentRetriever 与 RAGFlow 现有架构
复用现有的 Elasticsearch、向量存储和数据库系统
"""

import logging
import json
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, asdict

try:
    from langchain.retrievers import ParentDocumentRetriever
    from langchain.vectorstores.base import VectorStore
    from langchain.storage import BaseStore
    from langchain.schema import Document
    from langchain.text_splitter import TextSplitter
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    print("Warning: LangChain not available. Using RAGFlow-native implementation.")

# RAGFlow 模块导入
from rag.nlp.search import Dealer, index_name
from rag.utils.doc_store_conn import DocStoreConnection
from .parent_child_splitter import SmartParentChildSplitter, ChunkInfo, ParentChildResult

logger = logging.getLogger('ragflow.parent_retriever')


@dataclass
class RetrievalResult:
    """检索结果数据类"""
    content: str
    metadata: Dict[str, Any]
    chunk_id: str
    chunk_type: str  # 'parent' or 'child'
    score: float = 0.0
    parent_id: Optional[str] = None
    children_ids: Optional[List[str]] = None


class RAGFlowDocumentStore(BaseStore):
    """RAGFlow 文档存储适配器，兼容 LangChain BaseStore"""
    
    def __init__(self):
        self.parent_chunks = {}
        
    def mget(self, keys: List[str]) -> List[Optional[Document]]:
        """批量获取文档"""
        try:
            from api.db.parent_child_models import ParentChunk
            
            docs = []
            for key in keys:
                try:
                    parent_chunk = ParentChunk.get_by_id(key)
                    if parent_chunk and parent_chunk.available_int:
                        doc = Document(
                            page_content=parent_chunk.content,
                            metadata=json.loads(parent_chunk.metadata or '{}')
                        )
                        docs.append(doc)
                    else:
                        docs.append(None)
                except:
                    docs.append(None)
            
            return docs
        except ImportError:
            # 使用内存存储作为回退
            return [self.parent_chunks.get(key) for key in keys]
    
    def mset(self, key_value_pairs: List[tuple]) -> None:
        """批量设置文档"""
        try:
            from api.db.parent_child_models import ParentChunk
            
            for key, document in key_value_pairs:
                if isinstance(document, Document):
                    # 尝试保存到数据库
                    try:
                        metadata = document.metadata or {}
                        parent_chunk = ParentChunk.create(
                            id=key,
                            doc_id=metadata.get('doc_id', ''),
                            kb_id=metadata.get('kb_id', ''),
                            content=document.page_content,
                            content_with_weight=document.page_content,
                            metadata=json.dumps(metadata),
                            token_count=metadata.get('token_count', 0),
                            char_count=len(document.page_content),
                            chunk_order=metadata.get('order', 0),
                            chunk_method='parent_smart'
                        )
                        logger.debug(f"Saved parent chunk to DB: {key}")
                    except Exception as e:
                        logger.warning(f"Failed to save parent chunk to DB: {e}")
                        # 回退到内存存储
                        self.parent_chunks[key] = document
                else:
                    # 回退到内存存储
                    self.parent_chunks[key] = document
        except ImportError:
            # 仅使用内存存储
            for key, document in key_value_pairs:
                self.parent_chunks[key] = document
    
    def mdelete(self, keys: List[str]) -> None:
        """批量删除文档"""
        try:
            from api.db.parent_child_models import ParentChunk
            
            for key in keys:
                try:
                    parent_chunk = ParentChunk.get_by_id(key)
                    if parent_chunk:
                        parent_chunk.available_int = 0
                        parent_chunk.save()
                except:
                    pass
                
                # 同时从内存中删除
                self.parent_chunks.pop(key, None)
        except ImportError:
            # 仅从内存中删除
            for key in keys:
                self.parent_chunks.pop(key, None)
    
    def yield_keys(self, prefix: Optional[str] = None):
        """生成键名"""
        for key in self.parent_chunks.keys():
            if prefix is None or key.startswith(prefix):
                yield key


class RAGFlowVectorStore(VectorStore):
    """RAGFlow 向量存储适配器，兼容 LangChain VectorStore"""
    
    def __init__(self, dealer: Dealer, kb_id: str, embedding_model=None):
        self.dealer = dealer
        self.kb_id = kb_id
        self.embedding_model = embedding_model
        self._child_to_parent_map = {}
        
    def add_documents(self, documents: List[Document], **kwargs) -> List[str]:
        """添加文档到向量存储"""
        doc_ids = []
        
        try:
            from api.db.parent_child_models import ChildChunk, ParentChildMapping
            
            for doc in documents:
                metadata = doc.metadata or {}
                chunk_id = metadata.get('chunk_id', f"child_{len(doc_ids):08d}")
                
                # 保存子分块到数据库
                try:
                    child_chunk = ChildChunk.create(
                        id=chunk_id,
                        parent_chunk_id=metadata.get('parent_id', ''),
                        doc_id=metadata.get('doc_id', ''),
                        kb_id=self.kb_id,
                        content=doc.page_content,
                        content_ltks=doc.page_content,
                        chunk_order_in_parent=metadata.get('parent_order', 0),
                        chunk_order_global=metadata.get('order', 0),
                        metadata=json.dumps(metadata),
                        token_count=metadata.get('token_count', 0),
                        char_count=len(doc.page_content),
                        available_int=1
                    )
                    
                    # 建立映射关系
                    if metadata.get('parent_id'):
                        self._child_to_parent_map[chunk_id] = metadata['parent_id']
                        ParentChildMapping.create(
                            child_chunk_id=chunk_id,
                            parent_chunk_id=metadata['parent_id'],
                            doc_id=metadata.get('doc_id', ''),
                            kb_id=self.kb_id,
                            relevance_score=100
                        )
                    
                    logger.debug(f"Saved child chunk to DB: {chunk_id}")
                except Exception as e:
                    logger.warning(f"Failed to save child chunk to DB: {e}")
                
                doc_ids.append(chunk_id)
        
        except ImportError:
            logger.warning("Database models not available, using memory storage")
            doc_ids = [f"child_{i:08d}" for i in range(len(documents))]
        
        return doc_ids
    
    def similarity_search(self, query: str, k: int = 4, **kwargs) -> List[Document]:
        """执行相似性搜索"""
        try:
            # 使用现有的 RAGFlow 搜索机制
            req = {
                'question': query,
                'topk': k * 2,  # 检索更多候选
                'size': k * 2,
                'similarity': kwargs.get('similarity', 0.1)
            }
            
            idx_names = index_name(self.kb_id)
            kb_ids = [self.kb_id]
            
            # 执行搜索
            search_result = self.dealer.search(
                req=req,
                idx_names=idx_names,
                kb_ids=kb_ids,
                emb_mdl=self.embedding_model,
                highlight=False
            )
            
            # 转换为 LangChain Document 格式
            documents = []
            for chunk_id in search_result.ids[:k]:
                try:
                    from api.db.parent_child_models import ChildChunk
                    child_chunk = ChildChunk.get_by_id(chunk_id)
                    
                    if child_chunk and child_chunk.available_int:
                        doc = Document(
                            page_content=child_chunk.content,
                            metadata={
                                'chunk_id': chunk_id,
                                'parent_id': child_chunk.parent_chunk_id,
                                'doc_id': child_chunk.doc_id,
                                'kb_id': child_chunk.kb_id,
                                **json.loads(child_chunk.metadata or '{}')
                            }
                        )
                        documents.append(doc)
                except Exception as e:
                    logger.warning(f"Failed to load child chunk {chunk_id}: {e}")
                    continue
            
            return documents
            
        except Exception as e:
            logger.error(f"Similarity search failed: {e}")
            return []
    
    def from_documents(cls, documents, embedding, **kwargs):
        """从文档创建向量存储"""
        pass  # 不需要实现，使用现有的添加方法
    
    def from_texts(cls, texts, embedding, metadatas=None, **kwargs):
        """从文本创建向量存储"""
        pass  # 不需要实现，使用现有的添加方法


class SmartParentChildTextSplitter(TextSplitter):
    """Smart 分块的 LangChain TextSplitter 适配器"""
    
    def __init__(self, splitter: SmartParentChildSplitter, chunk_type: str = 'child'):
        self.splitter = splitter
        self.chunk_type = chunk_type  # 'parent' 或 'child'
    
    def split_documents(self, documents: List[Document]) -> List[Document]:
        """分割文档"""
        split_docs = []
        
        for doc in documents:
            metadata = doc.metadata or {}
            doc_id = metadata.get('doc_id', 'unknown')
            kb_id = metadata.get('kb_id', 'unknown')
            
            # 使用 Smart 分块器分割
            result = self.splitter.split_text(
                text=doc.page_content,
                doc_id=doc_id,
                kb_id=kb_id,
                metadata=metadata
            )
            
            # 根据类型返回相应的分块
            if self.chunk_type == 'parent':
                chunks = result.parent_chunks
            else:
                chunks = result.child_chunks
            
            for chunk_info in chunks:
                split_doc = Document(
                    page_content=chunk_info.content,
                    metadata={
                        **metadata,
                        'chunk_id': chunk_info.id,
                        'order': chunk_info.order,
                        'token_count': chunk_info.token_count,
                        'char_count': chunk_info.char_count,
                        **chunk_info.metadata
                    }
                )
                split_docs.append(split_doc)
        
        return split_docs
    
    def split_text(self, text: str) -> List[str]:
        """分割文本"""
        # 简单实现，实际使用 split_documents
        result = self.splitter.split_text(
            text=text,
            doc_id='temp',
            kb_id='temp'
        )
        
        if self.chunk_type == 'parent':
            return [chunk.content for chunk in result.parent_chunks]
        else:
            return [chunk.content for chunk in result.child_chunks]


class RAGFlowParentDocumentRetriever:
    """RAGFlow 版本的父子文档检索器"""
    
    def __init__(self, 
                 dealer: Dealer,
                 kb_id: str,
                 embedding_model=None,
                 config: Optional[Dict[str, Any]] = None):
        """
        初始化检索器
        
        Args:
            dealer: RAGFlow 搜索处理器
            kb_id: 知识库ID
            embedding_model: 嵌入模型
            config: 父子分块配置
        """
        self.dealer = dealer
        self.kb_id = kb_id
        self.embedding_model = embedding_model
        self.config = config or {}
        
        # 初始化分割器
        self.splitter = SmartParentChildSplitter(
            parent_chunk_size=self.config.get('parent_chunk_size', 1024),
            child_chunk_size=self.config.get('child_chunk_size', 256),
            parent_overlap=self.config.get('parent_overlap', 100),
            child_overlap=self.config.get('child_overlap', 50)
        )
        
        # 初始化存储
        self.docstore = RAGFlowDocumentStore()
        self.vectorstore = RAGFlowVectorStore(dealer, kb_id, embedding_model)
        
        # LangChain 集成（如果可用）
        self.langchain_retriever = None
        if LANGCHAIN_AVAILABLE:
            try:
                child_splitter = SmartParentChildTextSplitter(self.splitter, 'child')
                parent_splitter = SmartParentChildTextSplitter(self.splitter, 'parent')
                
                self.langchain_retriever = ParentDocumentRetriever(
                    vectorstore=self.vectorstore,
                    docstore=self.docstore,
                    child_splitter=child_splitter,
                    parent_splitter=parent_splitter
                )
                logger.info("LangChain ParentDocumentRetriever initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize LangChain retriever: {e}")
                self.langchain_retriever = None
    
    def add_documents(self, 
                     documents: List[Document], 
                     **kwargs) -> ParentChildResult:
        """添加文档并建立父子关系"""
        
        if not documents:
            return ParentChildResult([], [], [], 0, 0)
        
        all_results = []
        
        for doc in documents:
            metadata = doc.metadata or {}
            doc_id = metadata.get('doc_id', f"doc_{len(all_results):08d}")
            
            # 执行父子分块
            result = self.splitter.split_text(
                text=doc.page_content,
                doc_id=doc_id,
                kb_id=self.kb_id,
                metadata=metadata
            )
            all_results.append(result)
            
            # 存储父分块
            parent_docs = []
            for parent_chunk in result.parent_chunks:
                parent_doc = Document(
                    page_content=parent_chunk.content,
                    metadata={
                        **metadata,
                        'chunk_id': parent_chunk.id,
                        'doc_id': doc_id,
                        'kb_id': self.kb_id,
                        'parent_id': parent_chunk.id,
                        **parent_chunk.metadata
                    }
                )
                parent_docs.append((parent_chunk.id, parent_doc))
            
            self.docstore.mset(parent_docs)
            
            # 存储子分块到向量存储
            child_docs = []
            for child_chunk in result.child_chunks:
                # 找到对应的父分块ID
                parent_id = None
                for rel in result.relationships:
                    if rel['child_chunk_id'] == child_chunk.id:
                        parent_id = rel['parent_chunk_id']
                        break
                
                child_doc = Document(
                    page_content=child_chunk.content,
                    metadata={
                        **metadata,
                        'chunk_id': child_chunk.id,
                        'parent_id': parent_id,
                        'doc_id': doc_id,
                        'kb_id': self.kb_id,
                        'order': child_chunk.order,
                        'token_count': child_chunk.token_count,
                        **child_chunk.metadata
                    }
                )
                child_docs.append(child_doc)
            
            if child_docs:
                self.vectorstore.add_documents(child_docs)
        
        # 合并所有结果
        combined_result = self._combine_results(all_results)
        
        logger.info(f"Added {combined_result.total_parents} parent chunks and "
                   f"{combined_result.total_children} child chunks for kb {self.kb_id}")
        
        return combined_result
    
    def retrieve(self, 
                query: str, 
                k: int = 4, 
                mode: str = 'parent',
                **kwargs) -> List[RetrievalResult]:
        """
        检索相关文档
        
        Args:
            query: 查询文本
            k: 返回结果数量
            mode: 检索模式 ('parent', 'child', 'hybrid')
            
        Returns:
            List[RetrievalResult]: 检索结果列表
        """
        
        if mode == 'child':
            return self._retrieve_child_only(query, k, **kwargs)
        elif mode == 'hybrid':
            return self._retrieve_hybrid(query, k, **kwargs)
        else:  # parent mode (default)
            return self._retrieve_parent(query, k, **kwargs)
    
    def _retrieve_parent(self, query: str, k: int, **kwargs) -> List[RetrievalResult]:
        """检索父分块（默认模式）"""
        
        # 优先使用 LangChain 检索器
        if self.langchain_retriever:
            try:
                langchain_docs = self.langchain_retriever.get_relevant_documents(query)
                
                results = []
                for doc in langchain_docs[:k]:
                    metadata = doc.metadata or {}
                    result = RetrievalResult(
                        content=doc.page_content,
                        metadata=metadata,
                        chunk_id=metadata.get('chunk_id', ''),
                        chunk_type='parent',
                        parent_id=metadata.get('chunk_id', ''),
                        children_ids=[]  # 可以从关系表中获取
                    )
                    results.append(result)
                
                return results
            except Exception as e:
                logger.warning(f"LangChain retrieval failed, using fallback: {e}")
        
        # 回退到 RAGFlow 原生检索
        return self._retrieve_parent_native(query, k, **kwargs)
    
    def _retrieve_parent_native(self, query: str, k: int, **kwargs) -> List[RetrievalResult]:
        """使用 RAGFlow 原生方法检索父分块"""
        
        # 1. 先检索相关的子分块
        child_docs = self.vectorstore.similarity_search(query, k=k*2)
        
        # 2. 获取对应的父分块
        parent_ids = []
        seen_parents = set()
        
        for child_doc in child_docs:
            parent_id = child_doc.metadata.get('parent_id')
            if parent_id and parent_id not in seen_parents:
                parent_ids.append(parent_id)
                seen_parents.add(parent_id)
                
                if len(parent_ids) >= k:
                    break
        
        # 3. 从文档存储中获取父分块
        parent_docs = self.docstore.mget(parent_ids)
        
        results = []
        for parent_doc in parent_docs:
            if parent_doc:
                metadata = parent_doc.metadata or {}
                result = RetrievalResult(
                    content=parent_doc.page_content,
                    metadata=metadata,
                    chunk_id=metadata.get('chunk_id', ''),
                    chunk_type='parent',
                    parent_id=metadata.get('chunk_id', ''),
                    children_ids=[]  # TODO: 从关系表获取
                )
                results.append(result)
        
        return results[:k]
    
    def _retrieve_child_only(self, query: str, k: int, **kwargs) -> List[RetrievalResult]:
        """仅检索子分块"""
        child_docs = self.vectorstore.similarity_search(query, k=k)
        
        results = []
        for child_doc in child_docs:
            metadata = child_doc.metadata or {}
            result = RetrievalResult(
                content=child_doc.page_content,
                metadata=metadata,
                chunk_id=metadata.get('chunk_id', ''),
                chunk_type='child',
                parent_id=metadata.get('parent_id', '')
            )
            results.append(result)
        
        return results
    
    def _retrieve_hybrid(self, query: str, k: int, **kwargs) -> List[RetrievalResult]:
        """混合检索：返回子分块+对应父分块"""
        child_results = self._retrieve_child_only(query, k)
        
        # 获取对应的父分块
        parent_ids = [r.parent_id for r in child_results if r.parent_id]
        parent_docs = self.docstore.mget(parent_ids)
        
        results = child_results.copy()
        
        for parent_doc in parent_docs:
            if parent_doc:
                metadata = parent_doc.metadata or {}
                result = RetrievalResult(
                    content=parent_doc.page_content,
                    metadata=metadata,
                    chunk_id=metadata.get('chunk_id', ''),
                    chunk_type='parent',
                    parent_id=metadata.get('chunk_id', '')
                )
                results.append(result)
        
        return results
    
    def _combine_results(self, results: List[ParentChildResult]) -> ParentChildResult:
        """合并多个分块结果"""
        all_parents = []
        all_children = []
        all_relationships = []
        
        for result in results:
            all_parents.extend(result.parent_chunks)
            all_children.extend(result.child_chunks)
            all_relationships.extend(result.relationships)
        
        return ParentChildResult(
            parent_chunks=all_parents,
            child_chunks=all_children,
            relationships=all_relationships,
            total_parents=len(all_parents),
            total_children=len(all_children)
        )