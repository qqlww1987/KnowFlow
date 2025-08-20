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

"""
KnowFlow 批量 Chunk 添加插件 (集成式实现)
提供 POST /datasets/{dataset_id}/documents/{document_id}/chunks/batch 接口
提供 GET /datasets/{dataset_id}/documents/{document_id}/parse/progress 接口
所有业务逻辑直接在此文件中实现，简化结构
"""

import datetime
import xxhash
import re
import sys
import traceback
from timeit import default_timer as timer
import time
import threading

from flask import request, Blueprint
from api.utils.api_utils import token_required, get_result, get_error_data_result
from api.db.services.knowledgebase_service import KnowledgebaseService
from api.db.services.document_service import DocumentService
from api.db import LLMType, ParserType
from api.db.services.llm_service import TenantLLMService
from rag.nlp import rag_tokenizer, search
from rag.app.qa import rmPrefix, beAdoc
from rag.prompts import keyword_extraction, question_proposal
from rag.app.tag import label_question
from rag.utils import rmSpace
from graphrag.utils import get_llm_cache, set_llm_cache, chat_limiter
from api import settings
import trio

# 创建 Blueprint manager
manager = Blueprint('batch_chunk', __name__)

# 全局进度状态存储 - 简化版本
# 结构: {document_id: {"progress": float, "message": str, "timestamp": float, "stage": str}}
_progress_states = {}
_progress_lock = threading.Lock()


def _update_progress_state(document_id, progress=None, message=None, stage=None):
    """更新文档的进度状态"""
    with _progress_lock:
        if document_id not in _progress_states:
            _progress_states[document_id] = {
                "progress": 0.0,
                "message": "",
                "timestamp": time.time(),
                "stage": "initializing"
            }
        
        state = _progress_states[document_id]
        if progress is not None:
            state["progress"] = float(progress)
        if message is not None:
            state["message"] = str(message)
        if stage is not None:
            state["stage"] = str(stage)
        state["timestamp"] = time.time()


def _get_progress_state(document_id):
    """获取文档的进度状态"""
    with _progress_lock:
        if document_id in _progress_states:
            return _progress_states[document_id].copy()
        else:
            return {
                "progress": 0.0,
                "message": "未开始",
                "timestamp": time.time(),
                "stage": "unknown"
            }


def _clear_progress_state(document_id):
    """清空指定文档的进度状态"""
    with _progress_lock:
        if document_id in _progress_states:
            del _progress_states[document_id]
            print(f"🧹 清空进度状态: {document_id}")


def _process_single_batch(batch_chunks, batch_index, embd_mdl, doc, dataset_id, document_id, 
                         current_time, current_timestamp, tenant_id, DB_BULK_SIZE):
    """
    处理单个批次的chunks
    
    Args:
        batch_chunks: 当前批次的chunks数据 [(original_index, chunk_req), ...]
        batch_index: 批次起始索引
        embd_mdl: embedding模型实例
        doc: 文档对象
        dataset_id: 数据集ID
        document_id: 文档ID
        current_time: 当前时间字符串
        current_timestamp: 当前时间戳
        tenant_id: 租户ID
        DB_BULK_SIZE: 数据库批量插入大小
        
    Returns:
        tuple: (success: bool, result: dict)
               success=True时，result包含 {"processed_chunks": [], "cost": float}
               success=False时，result包含 {"error": str}
    """
    try:
        # 构建chunk文档数据
        processed_chunks = []
        embedding_texts = []
        batch_cost = 0
        
        # 简化排序机制：固定page_num_int=1，用top_int保证顺序
        for original_index, chunk_req in batch_chunks:
            content = chunk_req["content"]
            
            # 使用从 ragflow_build 传递过来的 top_int，如果没有则使用 original_index
            global_top_int = chunk_req.get("top_int", original_index)
            
            chunk_id = xxhash.xxh64((content + document_id + str(global_top_int)).encode("utf-8")).hexdigest()
            
            # 基础chunk数据结构
            d = {
                "id": chunk_id,
                "content_ltks": rag_tokenizer.tokenize(content),
                "content_with_weight": content,
                "content_sm_ltks": rag_tokenizer.fine_grained_tokenize(rag_tokenizer.tokenize(content)),
                "important_kwd": chunk_req.get("important_keywords", []),
                "important_tks": rag_tokenizer.tokenize(" ".join(chunk_req.get("important_keywords", []))),
                "question_kwd": [str(q).strip() for q in chunk_req.get("questions", []) if str(q).strip()],
                "question_tks": rag_tokenizer.tokenize("\n".join(chunk_req.get("questions", []))),
                "create_time": current_time,
                "create_timestamp_flt": current_timestamp,
                "kb_id": dataset_id,
                "docnm_kwd": doc.name,
                "doc_id": document_id,
                # 统一排序机制：固定page_num_int=1，top_int=原始索引
                "page_num_int": [1],  # 固定为1，保证所有chunks都在同一"页"
                "top_int": global_top_int  # 使用全局索引保证顺序
            }
            
            # 位置信息处理（作为额外信息，不影响排序）
            if "positions" in chunk_req:
                # 添加精确位置信息，但不覆盖page_num_int和top_int
                _add_positions_to_chunk_data(d, chunk_req["positions"])
                print(f"[_process_single_batch] global_idx={global_top_int}: 精确坐标 + 索引排序 (page={d['page_num_int'][0]}, top={global_top_int})")
            
            # 准备embedding文本
            text_for_embedding = content if not d["question_kwd"] else "\n".join(d["question_kwd"])
            embedding_texts.append([doc.name, text_for_embedding])
            processed_chunks.append(d)
            
            print(f"[_process_single_batch] chunk_idx={original_index}, content_len={len(chunk_req['content'])}, has_positions={'positions' in chunk_req}, top_int={d.get('top_int')}")
        
        # 批量执行embedding
        all_texts_for_embedding = []
        for doc_name, content_text in embedding_texts:
            all_texts_for_embedding.extend([doc_name, content_text])
        
        batch_vectors, batch_cost = embd_mdl.encode(all_texts_for_embedding)
        
        # 添加向量到chunks
        for i, d in enumerate(processed_chunks):
            doc_name_vector = batch_vectors[i * 2]
            content_vector = batch_vectors[i * 2 + 1]
            v = 0.1 * doc_name_vector + 0.9 * content_vector
            d["q_%d_vec" % len(v)] = v.tolist()
        
        # 分批插入数据库
        for b in range(0, len(processed_chunks), DB_BULK_SIZE):
            batch_for_db = processed_chunks[b:b + DB_BULK_SIZE]
            try:
                settings.docStoreConn.insert(batch_for_db, search.index_name(tenant_id), dataset_id)
            except Exception as db_error:
                print(f"[_process_single_batch] DB写入异常: {db_error}\n{traceback.format_exc()}")
                return False, {"error": f"Database insertion failed: {str(db_error)}"}
        
        return True, {"processed_chunks": processed_chunks, "cost": batch_cost}
        
    except Exception as e:
        print(f"[_process_single_batch] Batch处理异常: {e}\n{traceback.format_exc()}")
        return False, {"error": str(e)}


def _process_auto_keywords_questions(all_processed_chunks, document_id, chat_model, 
                                    auto_keywords, auto_questions, tenant_id, dataset_id):
    """
    处理自动关键词和问题生成
    
    Returns:
        bool: 是否成功完成处理
    """
    try:
        # 创建异步处理函数
        async def process_batch_keywords_and_questions():
            # 关键词提取处理
            keywords_processed = 0
            
            if auto_keywords > 0:
                st = timer()
                
                async def doc_keyword_extraction(chat_mdl, d, topn):
                    nonlocal keywords_processed
                    try:
                        content = d.get('content_with_weight', '').strip()
                        if not content or len(content) < 10:  # 跳过太短的内容
                            return
                        
                        # 检查缓存
                        cached = get_llm_cache(chat_mdl.llm_name, content, "keywords", {"topn": topn})
                        if not cached:
                            async with chat_limiter:
                                # 在线程中运行同步函数
                                cached = await trio.to_thread.run_sync(
                                    lambda: keyword_extraction(chat_mdl, content, topn)
                                )
                            # 只缓存有效结果
                            if cached and cached.strip():
                                set_llm_cache(chat_mdl.llm_name, content, cached, "keywords", {"topn": topn})
                        
                        if cached and cached.strip():
                            d["important_kwd"] = cached.split(",")
                            d["important_tks"] = rag_tokenizer.tokenize(" ".join(d["important_kwd"]))
                            keywords_processed += 1
                            
                            # 更新数据库中的关键词
                            settings.docStoreConn.update(
                                {"id": d["id"]}, 
                                {"important_kwd": d["important_kwd"], "important_tks": d["important_tks"]},
                                search.index_name(tenant_id), dataset_id
                            )
                    except Exception as e:
                        print(f"Keywords extraction error: {str(e)[:100]}")
                
                async with trio.open_nursery() as nursery:
                    for d in all_processed_chunks:
                        nursery.start_soon(doc_keyword_extraction, chat_model, d, auto_keywords)
                
                print(f"[Keywords] 全量关键词生成完成: {keywords_processed}/{len(all_processed_chunks)}, 耗时 {timer() - st:.2f}s")
                
                # 更新关键词生成完成进度
                if keywords_processed > 0:
                    _update_progress_state(document_id, progress=0.7, 
                                         message=f"关键词生成完成: {keywords_processed}/{len(all_processed_chunks)} 个文本块", 
                                         stage="keywords_completed")
            
            # 问题生成处理
            questions_processed = 0
            
            if auto_questions > 0:
                st = timer()
                
                async def doc_question_proposal(chat_mdl, d, topn):
                    nonlocal questions_processed
                    try:
                        content = d.get('content_with_weight', '').strip()
                        if not content or len(content) < 10:  # 跳过太短的内容
                            return
                        
                        # 检查缓存
                        cached = get_llm_cache(chat_mdl.llm_name, content, "question", {"topn": topn})
                        if not cached:
                            async with chat_limiter:
                                # 在线程中运行同步函数
                                cached = await trio.to_thread.run_sync(
                                    lambda: question_proposal(chat_mdl, content, topn)
                                )
                            # 只缓存有效结果
                            if cached and cached.strip():
                                set_llm_cache(chat_mdl.llm_name, content, cached, "question", {"topn": topn})
                        
                        if cached and cached.strip():
                            d["question_kwd"] = cached.split("\n")
                            d["question_tks"] = rag_tokenizer.tokenize("\n".join(d["question_kwd"]))
                            questions_processed += 1
                            
                            # 更新数据库中的问题
                            settings.docStoreConn.update(
                                {"id": d["id"]}, 
                                {"question_kwd": d["question_kwd"], "question_tks": d["question_tks"]},
                                search.index_name(tenant_id), dataset_id
                            )
                    except Exception as e:
                        print(f"Questions generation error: {str(e)[:100]}")
                
                async with trio.open_nursery() as nursery:
                    for d in all_processed_chunks:
                        nursery.start_soon(doc_question_proposal, chat_model, d, auto_questions)
                
                print(f"[Questions] 全量问题生成完成: {questions_processed}/{len(all_processed_chunks)}, 耗时 {timer() - st:.2f}s")
                
                # 更新问题生成完成进度
                if questions_processed > 0:
                    _update_progress_state(document_id, progress=0.8, 
                                         message=f"问题生成完成: {questions_processed}/{len(all_processed_chunks)} 个文本块", 
                                         stage="questions_completed")
            
            return keywords_processed, questions_processed
        
        # 运行异步处理
        keywords_processed, questions_processed = trio.run(process_batch_keywords_and_questions)
        return True
        
    except Exception as e:
        print(f"[_process_auto_keywords_questions] 处理异常: {e}")
        return False


def _process_graphrag(document_id, tenant_id, dataset_id, graphrag_config):
    """
    处理GraphRAG知识图谱构建
    
    Returns:
        bool: 是否成功完成处理
    """
    try:
        # 获取租户和模型信息
        from api.db.services.user_service import TenantService
        from api.db.services.llm_service import LLMBundle
        _, tenant = TenantService.get_by_id(tenant_id)
        chat_model = LLMBundle(tenant_id, LLMType.CHAT, tenant.llm_id)
        
        # 获取知识库信息
        kb_exists, kb = KnowledgebaseService.get_by_id(dataset_id)
        if not kb_exists or not kb:
            raise RuntimeError(f"Knowledge base {dataset_id} not found")
        embedding_model = LLMBundle(tenant_id, LLMType.EMBEDDING, kb.embd_id)
        
        # 构建GraphRAG处理参数
        row = {
            'tenant_id': tenant_id,
            'kb_id': dataset_id,
            'doc_id': document_id,
            'kb_parser_config': {
                'graphrag': {
                    'method': graphrag_config.get('method', 'light'),
                    'entity_types': graphrag_config.get('entity_types', 
                        ['organization', 'person', 'geo', 'event', 'category']),
                    'use_graphrag': True
                }
            }
        }
        
        # 进度回调函数
        def progress_callback(progress=None, msg=""):
            print(f"[GraphRAG Progress] {document_id}: {msg}")
            if msg:
                # 将GraphRAG的进度信息更新到状态中
                _update_progress_state(document_id, progress=0.9, 
                                     message=f"知识图谱构建: {msg}", 
                                     stage="graphrag_processing")
        
        # 创建一个包装函数来传递参数
        async def run_graphrag():
            from graphrag.general import index
            return await index.run_graphrag(
                row=row,
                language=graphrag_config.get('language', 'Chinese'),
                with_resolution=graphrag_config.get('resolution', False),
                with_community=graphrag_config.get('community', False),
                chat_model=chat_model,
                embedding_model=embedding_model,
                callback=progress_callback
            )
        
        # 调用GraphRAG抽取
        result = trio.run(run_graphrag)
        
        # 更新知识图谱完成进度
        _update_progress_state(document_id, progress=0.95, 
                             message="知识图谱构建完成", 
                             stage="graphrag_completed")
        return True
        
    except Exception as e:
        print(f"[_process_graphrag] 处理异常: {e}")
        return False


def _get_progress_stats():
    """获取进度状态统计信息（用于监控）"""
    with _progress_lock:
        total_states = len(_progress_states)
        completed_states = sum(1 for state in _progress_states.values() 
                             if state.get("stage", "") in ["completed", "completed_with_errors"])
        active_states = total_states - completed_states
        
        return {
            "total_states": total_states,
            "active_states": active_states, 
            "completed_states": completed_states
        }


@manager.route(  # noqa: F821
    "/datasets/<dataset_id>/documents/<document_id>/parse/progress", methods=["GET"]
)
@token_required
def get_parse_progress(tenant_id, dataset_id, document_id):
    """
    获取文档解析进度
    ---
    tags:
      - Parse Progress
    security:
      - ApiKeyAuth: []
    parameters:
      - in: path
        name: dataset_id
        type: string
        required: true
        description: ID of the dataset.
      - in: path
        name: document_id
        type: string
        required: true
        description: ID of the document.
    responses:
      200:
        description: Progress information retrieved successfully.
        schema:
          type: object
          properties:
            progress:
              type: number
              description: Progress value (0.0 to 1.0).
            message:
              type: string
              description: Current progress message.
            stage:
              type: string
              description: Current processing stage.
            timestamp:
              type: number
              description: Last update timestamp.
    """
    # 基础权限验证
    if not KnowledgebaseService.accessible(kb_id=dataset_id, user_id=tenant_id):
        return get_error_data_result(message=f"You don't own the dataset {dataset_id}.")
    
    doc = DocumentService.query(id=document_id, kb_id=dataset_id)
    if not doc:
        return get_error_data_result(message=f"You don't own the document {document_id}.")
    
    # 获取进度状态
    progress_state = _get_progress_state(document_id)
    
    return get_result(data=progress_state)


@manager.route(  # noqa: F821
    "/progress/stats", methods=["GET"]
)
@token_required
def get_progress_stats(tenant_id):
    """
    获取进度状态统计信息（监控接口）
    ---
    tags:
      - Progress Stats
    security:
      - ApiKeyAuth: []
    responses:
      200:
        description: Progress statistics retrieved successfully.
        schema:
          type: object
          properties:
            total_states:
              type: integer
              description: Total number of progress states in memory.
            active_states:
              type: integer
              description: Number of active (non-completed) states.
            completed_states:
              type: integer
              description: Number of completed states awaiting cleanup.
    """
    stats = _get_progress_stats()
    return get_result(data=stats)


def _add_positions_to_chunk_data(d, positions):
    """
    简化版本：仅添加position_int信息，不覆盖page_num_int和top_int排序字段
    Args:
        d: chunk data dictionary
        positions: list of [page_num, left, right, top, bottom] tuples
    """
    if not positions:
        return
    
    position_int = []
    
    for pos in positions:
        if len(pos) != 5:
            continue  # Skip invalid positions
            
        pn, left, right, top, bottom = pos
        # 使用元组格式，与原始RAGFlow保持一致
        position_int.append((int(pn + 1), int(left), int(right), int(top), int(bottom)))
    
    if position_int:  # Only add if we have valid positions
        # 仅添加精确位置信息，不修改排序字段
        d["position_int"] = position_int





@manager.route(  # noqa: F821
    "/datasets/<dataset_id>/documents/<document_id>/chunks/batch", methods=["POST"]
)
@token_required
def batch_add_chunk(tenant_id, dataset_id, document_id):
    """
    Add multiple chunks to a document in batch.
    ---
    tags:
      - Chunks
    security:
      - ApiKeyAuth: []
    parameters:
      - in: path
        name: dataset_id
        type: string
        required: true
        description: ID of the dataset.
      - in: path
        name: document_id
        type: string
        required: true
        description: ID of the document.
      - in: body
        name: body
        description: Batch chunk data.
        required: true
        schema:
          type: object
          properties:
            chunks:
              type: array
              items:
                type: object
                properties:
                  content:
                    type: string
                    required: true
                    description: Content of the chunk.
                  important_keywords:
                    type: array
                    items:
                      type: string
                    description: Important keywords.
                  questions:
                    type: array
                    items:
                      type: string
                    description: Questions related to the chunk.
                  positions:
                    type: array
                    items:
                      type: array
                      items:
                        type: integer
                      minItems: 5
                      maxItems: 5
                    description: Position information as list of [page_num, left, right, top, bottom].
              required: true
              description: Array of chunks to add.
            batch_size:
              type: integer
              description: Size of each processing batch (default 10, max 50).
            max_retries:
              type: integer
              description: Maximum number of retries for failed batches (default 3, max 5).
            retry_delay:
              type: number
              description: Delay in seconds between retries (default 2.0, max 10.0).
      - in: header
        name: Authorization
        type: string
        required: true
        description: Bearer token for authentication.
    responses:
      200:
        description: Chunks added successfully.
        schema:
          type: object
          properties:
            chunks:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: string
                    description: Chunk ID.
                  content:
                    type: string
                    description: Chunk content.
                  document_id:
                    type: string
                    description: ID of the document.
                  important_keywords:
                    type: array
                    items:
                      type: string
                    description: Important keywords.
                  positions:
                    type: array
                    items:
                      type: array
                      items:
                        type: integer
                    description: Position information.
            total_added:
              type: integer
              description: Total number of chunks successfully added.
            total_failed:
              type: integer
              description: Total number of chunks that failed to add.
    """
    # 配置参数
    MAX_CHUNKS_PER_REQUEST = 100
    DEFAULT_BATCH_SIZE = 10
    MAX_BATCH_SIZE = 50
    MAX_CONTENT_LENGTH = 10000
    DB_BULK_SIZE = 10
    
    try:
        # ===== 1. 权限和基础验证 =====
        if not KnowledgebaseService.accessible(kb_id=dataset_id, user_id=tenant_id):
            return get_error_data_result(message=f"You don't own the dataset {dataset_id}.")
        
        doc = DocumentService.query(id=document_id, kb_id=dataset_id)
        if not doc:
            return get_error_data_result(message=f"You don't own the document {document_id}.")
        doc = doc[0]
        
        # ===== 2. 请求数据解析和验证 =====
        req = request.json
        chunks_data = req.get("chunks", [])
        batch_size = min(req.get("batch_size", DEFAULT_BATCH_SIZE), MAX_BATCH_SIZE)
        
        # 重试机制配置（可通过请求参数调整）
        MAX_RETRIES = min(req.get("max_retries", 3), 5)  # 限制最大重试次数为5
        RETRY_DELAY = min(req.get("retry_delay", 2.0), 10.0)  # 限制最大延迟为10秒
        
        # 基础数据验证
        if not chunks_data or not isinstance(chunks_data, list):
            return get_error_data_result(message="`chunks` is required and must be a list")
        
        if len(chunks_data) == 0:
            return get_error_data_result(message="No chunks provided")
        
        if len(chunks_data) > MAX_CHUNKS_PER_REQUEST:
            return get_error_data_result(
                message=f"Too many chunks. Maximum allowed: {MAX_CHUNKS_PER_REQUEST}, received: {len(chunks_data)}"
            )
        
        # ===== 3. 数据验证 =====
        validated_chunks = []
        validation_errors = []
        
        for i, chunk_req in enumerate(chunks_data):
            # 内容验证
            content = str(chunk_req.get("content", "")).strip()
            if not content:
                validation_errors.append(f"Chunk {i}: content is required")
                continue
                
            if len(content) > MAX_CONTENT_LENGTH:
                validation_errors.append(f"Chunk {i}: content too long ({len(content)} chars, max {MAX_CONTENT_LENGTH})")
                continue
            
            # 关键词和问题验证    
            if "important_keywords" in chunk_req and not isinstance(chunk_req["important_keywords"], list):
                validation_errors.append(f"Chunk {i}: important_keywords must be a list")
                continue
                    
            if "questions" in chunk_req and not isinstance(chunk_req["questions"], list):
                validation_errors.append(f"Chunk {i}: questions must be a list")
                continue
            
            # 位置信息验证
            if "positions" in chunk_req:
                positions = chunk_req["positions"]
                if not isinstance(positions, list):
                    validation_errors.append(f"Chunk {i}: positions must be a list")
                    continue
                
                for j, pos in enumerate(positions):
                    if not isinstance(pos, list) or len(pos) != 5:
                        validation_errors.append(f"Chunk {i}: positions[{j}] must be a list of 5 integers [page_num, left, right, top, bottom]")
                        break
                    
                    try:
                        [int(x) for x in pos]
                    except (ValueError, TypeError):
                        validation_errors.append(f"Chunk {i}: positions[{j}] must contain only integers")
                        break
                
                if validation_errors and validation_errors[-1].startswith(f"Chunk {i}:"):
                    continue
            
            validated_chunks.append((i, chunk_req))
        
        # 验证错误处理
        if validation_errors:
            error_msg = "; ".join(validation_errors[:10])
            if len(validation_errors) > 10:
                error_msg += f" ... and {len(validation_errors)-10} more errors"
            # 标记为验证失败状态
            _update_progress_state(document_id, progress=-1, message=f"数据验证失败: {error_msg}", stage="validation_failed")
            return get_error_data_result(message=f"Validation errors: {error_msg}")
        
        # ===== 4. 初始化 embedding 模型 =====
        try:
            embd_id = DocumentService.get_embd_id(document_id)
            embd_mdl = TenantLLMService.model_instance(tenant_id, LLMType.EMBEDDING.value, embd_id)
        except Exception as e:
            # 标记为初始化失败状态
            _update_progress_state(document_id, progress=-1, message=f"模型初始化失败: {str(e)}", stage="initialization_failed")
            return get_error_data_result(message=f"Failed to initialize embedding model: {str(e)}")
        
        # ===== 5. 批量处理（带重试机制） =====
        all_processed_chunks = []
        total_cost = 0
        processing_errors = []
        current_time = str(datetime.datetime.now()).replace("T", " ")[:19]
        current_timestamp = datetime.datetime.now().timestamp()
        
        # 重试配置（已从请求参数中获取）
        
        print(f"[batch_add_chunk] 请求: dataset_id={dataset_id}, document_id={document_id}, chunks={len(chunks_data)}")
        
        # 初始化进度状态
        _update_progress_state(document_id, progress=0.1, message="开始批量处理文本块...", stage="initializing")
        
        # 失败批次跟踪（保持顺序）
        failed_batches = []  # 存储 (batch_index, batch_chunks, retry_count) 
        
        # 第一轮处理：按顺序处理所有批次
        for batch_index in range(0, len(validated_chunks), batch_size):
            batch_end = min(batch_index + batch_size, len(validated_chunks))
            batch_chunks = validated_chunks[batch_index:batch_end]
            
            print(f"[batch_add_chunk] 处理batch: {batch_index}~{batch_end}")
            
            # 更新分块处理进度
            chunk_progress = 0.1 + (batch_index / len(validated_chunks)) * 0.35  # 0.1-0.45 用于第一轮处理
            _update_progress_state(document_id, progress=chunk_progress, 
                                 message=f"处理文本块 {batch_index+1}-{batch_end}/{len(validated_chunks)}", 
                                 stage="chunking")
            
            success, batch_result = _process_single_batch(
                batch_chunks, batch_index, embd_mdl, doc, dataset_id, document_id, 
                current_time, current_timestamp, tenant_id, DB_BULK_SIZE
            )
            
            if success:
                all_processed_chunks.extend(batch_result["processed_chunks"])
                total_cost += batch_result["cost"]
            else:
                # 记录失败的批次，稍后重试
                failed_batches.append((batch_index, batch_chunks, 0))
                processing_errors.append(f"Batch {batch_index//batch_size + 1} failed: {batch_result.get('error', 'Unknown error')}")
                print(f"[batch_add_chunk] Batch {batch_index//batch_size + 1} 失败，加入重试队列: {batch_result.get('error', 'Unknown error')}")
        
        # 重试失败的批次（保持原始顺序）
        if failed_batches:
            print(f"[batch_add_chunk] 开始重试 {len(failed_batches)} 个失败的批次...")
            _update_progress_state(document_id, progress=0.5, 
                                 message=f"开始重试 {len(failed_batches)} 个失败批次...", 
                                 stage="retrying")
            
            # 按批次索引排序，确保按原始顺序重试
            failed_batches.sort(key=lambda x: x[0])
            
            retry_round = 1
            while failed_batches and retry_round <= MAX_RETRIES:
                print(f"[batch_add_chunk] 重试轮次 {retry_round}/{MAX_RETRIES}")
                
                remaining_failed = []
                for batch_index, batch_chunks, prev_retry_count in failed_batches:
                    batch_num = batch_index // batch_size + 1
                    
                    # 更新重试进度
                    retry_progress = 0.5 + (retry_round - 1) * 0.15  # 0.5-0.95 用于重试
                    _update_progress_state(document_id, progress=retry_progress,
                                         message=f"重试批次 {batch_num} (第{retry_round}次重试)", 
                                         stage="retrying")
                    
                    # 重试前等待
                    time.sleep(RETRY_DELAY)
                    
                    success, batch_result = _process_single_batch(
                        batch_chunks, batch_index, embd_mdl, doc, dataset_id, document_id, 
                        current_time, current_timestamp, tenant_id, DB_BULK_SIZE
                    )
                    
                    if success:
                        print(f"[batch_add_chunk] Batch {batch_num} 重试成功！")
                        all_processed_chunks.extend(batch_result["processed_chunks"])
                        total_cost += batch_result["cost"]
                    else:
                        print(f"[batch_add_chunk] Batch {batch_num} 重试失败 (第{retry_round}次): {batch_result.get('error', 'Unknown error')}")
                        remaining_failed.append((batch_index, batch_chunks, retry_round))
                
                failed_batches = remaining_failed
                retry_round += 1
        
        # 对成功处理的chunks按原始顺序排序
        # 使用 top_int 字段进行排序，确保最终顺序正确
        all_processed_chunks.sort(key=lambda x: x.get('top_int', 0))
        
        if failed_batches:
            final_failed_count = sum(len(batch[1]) for batch in failed_batches)
            print(f"[batch_add_chunk] 最终仍有 {len(failed_batches)} 个批次失败，共 {final_failed_count} 个chunks")
            
            for batch_index, batch_chunks, _ in failed_batches:
                batch_num = batch_index // batch_size + 1 
                processing_errors.append(f"Batch {batch_num} failed after {MAX_RETRIES} retries ({len(batch_chunks)} chunks)")
        
        # ===== 6. 处理自动关键词和问题生成 =====
        if all_processed_chunks:
            try:
                # 检查是否启用自动关键词/问题
                exists, doc_for_auto_gen = DocumentService.get_by_id(document_id)
                if exists and doc_for_auto_gen and doc_for_auto_gen.parser_config:
                    import json
                    if isinstance(doc_for_auto_gen.parser_config, str):
                        parser_config = json.loads(doc_for_auto_gen.parser_config)
                    else:
                        parser_config = doc_for_auto_gen.parser_config
                    
                    auto_keywords = parser_config.get('auto_keywords', 0)
                    auto_questions = parser_config.get('auto_questions', 0)
                    
                    if auto_keywords > 0 or auto_questions > 0:
                        print(f"[Keywords/Questions] 全量处理 - keywords: {auto_keywords}, questions: {auto_questions}, chunks: {len(all_processed_chunks)}")
                        
                        # 更新进度：开始关键词和问题生成
                        _update_progress_state(document_id, progress=0.6, 
                                             message="开始生成自动关键词和问题...", 
                                             stage="keywords_questions")
                        
                        # 获取租户信息和LLM模型
                        from api.db.services.user_service import TenantService
                        from api.db.services.llm_service import LLMBundle
                        _, tenant = TenantService.get_by_id(tenant_id)
                        chat_model = LLMBundle(tenant_id, LLMType.CHAT, tenant.llm_id)
                        
                        # 批量处理自动关键词和问题生成
                        success = _process_auto_keywords_questions(
                            all_processed_chunks, document_id, chat_model, 
                            auto_keywords, auto_questions, tenant_id, dataset_id
                        )
                        
                        if success:
                            print(f"[Keywords/Questions] 全量处理完成")
                        else:
                            print(f"[Keywords/Questions] 全量处理失败，但继续执行主流程")
                            
            except Exception as auto_gen_e:
                print(f"[Keywords/Questions] 全量处理异常: {auto_gen_e}")
                # 继续处理，不因为自动生成失败而中断主流程
        
        # ===== 7. 处理GraphRAG =====
        if all_processed_chunks:
            try:
                # 检查是否启用GraphRAG
                exists, doc_for_graphrag = DocumentService.get_by_id(document_id)
                if exists and doc_for_graphrag and doc_for_graphrag.parser_config:
                    import json
                    if isinstance(doc_for_graphrag.parser_config, str):
                        parser_config = json.loads(doc_for_graphrag.parser_config)
                    else:
                        parser_config = doc_for_graphrag.parser_config
                    
                    graphrag_config = parser_config.get('graphrag', {})
                    if graphrag_config.get('use_graphrag', False):
                        print(f"[GraphRAG] 全量处理 - 开始为文档 {document_id} 抽取知识图谱，chunks: {len(all_processed_chunks)}")
                        
                        # 更新进度：开始知识图谱构建
                        _update_progress_state(document_id, progress=0.85, 
                                             message="开始构建知识图谱...", 
                                             stage="graphrag_processing")
                        
                        success = _process_graphrag(
                            document_id, tenant_id, dataset_id, graphrag_config
                        )
                        
                        if success:
                            print(f"[GraphRAG] 全量处理完成 - 文档 {document_id} 知识图谱抽取成功")
                        else:
                            print(f"[GraphRAG] 全量处理失败，但继续执行主流程")
                            
            except Exception as graphrag_e:
                print(f"[GraphRAG] 全量处理异常 {document_id}: {graphrag_e}")
                # GraphRAG失败不影响主流程，继续处理
        
        # ===== 6. 更新文档统计 =====
        if all_processed_chunks:
            try:
                DocumentService.increment_chunk_num(doc.id, doc.kb_id, total_cost, len(all_processed_chunks), 0)
            except Exception as e:
                print(f"Warning: Failed to update document count: {e}")
        
        # ===== 7. 格式化响应数据 =====
        key_mapping = {
            "id": "id",
            "content_with_weight": "content",
            "doc_id": "document_id",
            "important_kwd": "important_keywords",
            "question_kwd": "questions",
            "kb_id": "dataset_id",
            "create_timestamp_flt": "create_timestamp",
            "create_time": "create_time",
            "position_int": "positions",
            "image_id": "image_id",
            "available_int": "available",
        }

        renamed_chunks = []
        for d in all_processed_chunks:
            renamed_chunk = {}
            for key, value in d.items():
                if key in key_mapping:
                    new_key = key_mapping[key]
                    # 将position_int的元组格式转换为列表格式
                    if key == "position_int" and isinstance(value, list):
                        renamed_chunk[new_key] = [list(pos) if isinstance(pos, tuple) else pos for pos in value]
                    else:
                        renamed_chunk[new_key] = value
            
            # 确保每个chunk都有positions字段
            if "positions" not in renamed_chunk:
                renamed_chunk["positions"] = []
            
            renamed_chunks.append(renamed_chunk)
        
        # ===== 7. 初始化GraphRAG结果 =====
        # 注意：实际的GraphRAG处理已在批处理中完成
        graphrag_result = {
            'status': 'success',
            'doc_id': document_id,
            'message': '知识图谱抽取已在批处理中完成'
        }
        
        # ===== 8. 初始化自动关键词和问题生成结果 =====
        keywords_result = {
            'status': 'success',
            'processed_chunks': 0,
            'message': '关键词生成已在批处理中完成'
        }
        
        questions_result = {
            'status': 'success',
            'processed_chunks': 0,
            'message': '问题生成已在批处理中完成'
        }
        
        # ===== 9. 构建返回结果 =====
        total_requested = len(chunks_data)
        total_added = len(renamed_chunks)
        total_failed = total_requested - total_added
        
        result_data = {
            "chunks": renamed_chunks,
            "total_added": total_added,
            "total_failed": total_failed,
            "processing_stats": {
                "total_requested": total_requested,
                "batch_size_used": batch_size,
                "batches_processed": (len(validated_chunks) - 1) // batch_size + 1,
                "embedding_cost": total_cost,
                "processing_errors": processing_errors if processing_errors else None
            },
            "graphrag_result": graphrag_result,  # GraphRAG处理结果
            "keywords_result": keywords_result,  # 关键词提取结果
            "questions_result": questions_result  # 关键问题生成结果
        }
        
        # 更新最终完成状态
        if total_failed == 0:
            _update_progress_state(document_id, progress=1.0, 
                                 message=f"处理完成！成功添加 {total_added} 个文本块", 
                                 stage="completed")
        else:
            _update_progress_state(document_id, progress=1.0, 
                                 message=f"处理完成！成功 {total_added} 个，失败 {total_failed} 个", 
                                 stage="completed_with_errors")
        
        # 返回结果
        if processing_errors:
            return get_result(
                data=result_data,
                message=f"Partial success: {total_added} chunks added, {total_failed} failed. Check processing_stats for details."
            )
        else:
            return get_result(data=result_data)
            
    except Exception as e:
        # 处理意外异常
        _update_progress_state(document_id, progress=-1, message=f"处理失败: {str(e)}", stage="failed")
        return get_error_data_result(message=f"Batch processing failed: {str(e)}")
    
    finally:
        # 请求结束后直接清空进度状态
        _clear_progress_state(document_id)

# 设置页面名称 (可选，用于自定义 URL 前缀)
page_name = "batch_chunk"