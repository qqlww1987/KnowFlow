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
所有业务逻辑直接在此文件中实现，简化结构
"""

import datetime
import xxhash
import re
import sys
import traceback

from flask import request, Blueprint
from api.utils.api_utils import token_required, get_result, get_error_data_result
from api.db.services.knowledgebase_service import KnowledgebaseService
from api.db.services.document_service import DocumentService
from api.db import LLMType, ParserType
from api.db.services.llm_service import TenantLLMService
from rag.nlp import rag_tokenizer, search
from rag.app.qa import rmPrefix, beAdoc
from rag.prompts import keyword_extraction
from rag.app.tag import label_question
from rag.utils import rmSpace
from api import settings

# 创建 Blueprint manager
manager = Blueprint('batch_chunk', __name__)


def _add_positions_to_chunk_data(d, positions):
    """
    Add position information to chunk data based on RAGFlow's _add_positions logic.
    Args:
        d: chunk data dictionary
        positions: list of [page_num, left, right, top, bottom] tuples
    """
    if not positions:
        return
    
    page_num_int = []
    position_int = []
    top_int = []
    
    for pos in positions:
        if len(pos) != 5:
            continue  # Skip invalid positions
            
        pn, left, right, top, bottom = pos
        # 按照原始RAGFlow逻辑，page_num需要+1
        page_num_int.append(int(pn + 1))
        top_int.append(int(top))
        # 使用元组格式，与原始RAGFlow保持一致
        position_int.append((int(pn + 1), int(left), int(right), int(top), int(bottom)))
    
    if page_num_int:  # Only add if we have valid positions
        d["page_num_int"] = page_num_int
        d["position_int"] = position_int
        d["top_int"] = top_int


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
        return get_error_data_result(message=f"Validation errors: {error_msg}")
    
    # ===== 4. 初始化 embedding 模型 =====
    try:
        embd_id = DocumentService.get_embd_id(document_id)
        embd_mdl = TenantLLMService.model_instance(tenant_id, LLMType.EMBEDDING.value, embd_id)
    except Exception as e:
        return get_error_data_result(message=f"Failed to initialize embedding model: {str(e)}")
    
    # ===== 5. 批量处理 =====
    all_processed_chunks = []
    total_cost = 0
    processing_errors = []
    current_time = str(datetime.datetime.now()).replace("T", " ")[:19]
    current_timestamp = datetime.datetime.now().timestamp()
    
    print(f"[batch_add_chunk] 请求: dataset_id={dataset_id}, document_id={document_id}, chunks={len(chunks_data)}")
    
    for batch_start in range(0, len(validated_chunks), batch_size):
        batch_end = min(batch_start + batch_size, len(validated_chunks))
        batch_chunks = validated_chunks[batch_start:batch_end]
        
        print(f"[batch_add_chunk] 处理batch: {batch_start}~{min(batch_start+batch_size, len(validated_chunks))}")
        
        try:
            # 构建chunk文档数据
            processed_chunks = []
            embedding_texts = []
            
            for original_index, chunk_req in batch_chunks:
                content = chunk_req["content"]
                chunk_id = xxhash.xxh64((content + document_id + str(original_index)).encode("utf-8")).hexdigest()
                
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
                    "doc_id": document_id
                }
                
                # 位置信息处理
                if "positions" in chunk_req:
                    _add_positions_to_chunk_data(d, chunk_req["positions"])
                
                # 准备embedding文本
                text_for_embedding = content if not d["question_kwd"] else "\n".join(d["question_kwd"])
                embedding_texts.append([doc.name, text_for_embedding])
                processed_chunks.append(d)
                
                print(f"[batch_add_chunk] chunk_idx={original_index}, content_len={len(chunk_req['content'])}, positions={chunk_req.get('positions')}, top_int={chunk_req.get('top_int')}")
            
            # 批量执行embedding
            all_texts_for_embedding = []
            for doc_name, content_text in embedding_texts:
                all_texts_for_embedding.extend([doc_name, content_text])
            
            batch_vectors, batch_cost = embd_mdl.encode(all_texts_for_embedding)
            total_cost += batch_cost
            
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
                    print(f"[batch_add_chunk] DB写入异常: {db_error}\n{traceback.format_exc()}")
                    raise db_error
            
            all_processed_chunks.extend(processed_chunks)
            
        except Exception as e:
            error_msg = f"Batch {batch_start//batch_size + 1} failed: {str(e)}"
            processing_errors.append(error_msg)
            print(f"[batch_add_chunk] embedding异常: {e}\n{traceback.format_exc()}")
            continue
    
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
    
    # ===== 8. 构建返回结果 =====
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
        }
    }
    
    # 返回结果
    if processing_errors:
        return get_result(
            data=result_data,
            message=f"Partial success: {total_added} chunks added, {total_failed} failed. Check processing_stats for details."
        )
    else:
        return get_result(data=result_data)

# 设置页面名称 (可选，用于自定义 URL 前缀)
page_name = "batch_chunk"