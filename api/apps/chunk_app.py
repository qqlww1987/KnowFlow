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
import datetime
import json
import re

import xxhash
from flask import request
from flask_login import current_user, login_required

from api import settings
from api.db import LLMType, ParserType
from api.db.services.document_service import DocumentService
from api.db.services.knowledgebase_service import KnowledgebaseService
from api.db.services.llm_service import LLMBundle
from api.db.services.user_service import UserTenantService
from api.utils.api_utils import get_data_error_result, get_json_result, server_error_response, validate_request
from rag.app.qa import beAdoc, rmPrefix
from rag.app.tag import label_question
from rag.nlp import rag_tokenizer, search
from rag.prompts import cross_languages, keyword_extraction
from rag.settings import PAGERANK_FLD
from rag.utils import rmSpace


@manager.route('/list', methods=['POST'])  # noqa: F821
@login_required
@validate_request("doc_id")
def list_chunk():
    req = request.json
    doc_id = req["doc_id"]
    page = int(req.get("page", 1))
    size = int(req.get("size", 30))
    question = req.get("keywords", "")
    try:
        tenant_id = DocumentService.get_tenant_id(req["doc_id"])
        if not tenant_id:
            return get_data_error_result(message="Tenant not found!")
        e, doc = DocumentService.get_by_id(doc_id)
        if not e:
            return get_data_error_result(message="Document not found!")
        kb_ids = KnowledgebaseService.get_kb_ids(tenant_id)
        query = {
            "doc_ids": [doc_id], "page": page, "size": size, "question": question, "sort": True
        }
        if "available_int" in req:
            query["available_int"] = int(req["available_int"])
        sres = settings.retrievaler.search(query, search.index_name(tenant_id), kb_ids, highlight=True)
        res = {"total": sres.total, "chunks": [], "doc": doc.to_dict()}
        for id in sres.ids:
            d = {
                "chunk_id": id,
                "content_with_weight": rmSpace(sres.highlight[id]) if question and id in sres.highlight else sres.field[
                    id].get(
                    "content_with_weight", ""),
                "doc_id": sres.field[id]["doc_id"],
                "docnm_kwd": sres.field[id]["docnm_kwd"],
                "important_kwd": sres.field[id].get("important_kwd", []),
                "question_kwd": sres.field[id].get("question_kwd", []),
                "image_id": sres.field[id].get("img_id", ""),
                "available_int": int(sres.field[id].get("available_int", 1)),
                "positions": sres.field[id].get("position_int", []),
            }
            assert isinstance(d["positions"], list)
            assert len(d["positions"]) == 0 or (isinstance(d["positions"][0], list) and len(d["positions"][0]) == 5)
            res["chunks"].append(d)
        return get_json_result(data=res)
    except Exception as e:
        if str(e).find("not_found") > 0:
            return get_json_result(data=False, message='No chunk found!',
                                   code=settings.RetCode.DATA_ERROR)
        return server_error_response(e)


@manager.route('/get', methods=['GET'])  # noqa: F821
@login_required
def get():
    chunk_id = request.args["chunk_id"]
    try:
        tenants = UserTenantService.query(user_id=current_user.id)
        if not tenants:
            return get_data_error_result(message="Tenant not found!")
        for tenant in tenants:
            kb_ids = KnowledgebaseService.get_kb_ids(tenant.tenant_id)
            chunk = settings.docStoreConn.get(chunk_id, search.index_name(tenant.tenant_id), kb_ids)
            if chunk:
                break
        if chunk is None:
            return server_error_response(Exception("Chunk not found"))

        k = []
        for n in chunk.keys():
            if re.search(r"(_vec$|_sm_|_tks|_ltks)", n):
                k.append(n)
        for n in k:
            del chunk[n]

        return get_json_result(data=chunk)
    except Exception as e:
        if str(e).find("NotFoundError") >= 0:
            return get_json_result(data=False, message='Chunk not found!',
                                   code=settings.RetCode.DATA_ERROR)
        return server_error_response(e)


@manager.route('/set', methods=['POST'])  # noqa: F821
@login_required
@validate_request("doc_id", "chunk_id", "content_with_weight")
def set():
    req = request.json
    d = {
        "id": req["chunk_id"],
        "content_with_weight": req["content_with_weight"]}
    d["content_ltks"] = rag_tokenizer.tokenize(req["content_with_weight"])
    d["content_sm_ltks"] = rag_tokenizer.fine_grained_tokenize(d["content_ltks"])
    if "important_kwd" in req:
        if not isinstance(req["important_kwd"], list):
            return get_data_error_result(message="`important_kwd` should be a list")
        d["important_kwd"] = req["important_kwd"]
        d["important_tks"] = rag_tokenizer.tokenize(" ".join(req["important_kwd"]))
    if "question_kwd" in req:
        if not isinstance(req["question_kwd"], list):
            return get_data_error_result(message="`question_kwd` should be a list")
        d["question_kwd"] = req["question_kwd"]
        d["question_tks"] = rag_tokenizer.tokenize("\n".join(req["question_kwd"]))
    if "tag_kwd" in req:
        d["tag_kwd"] = req["tag_kwd"]
    if "tag_feas" in req:
        d["tag_feas"] = req["tag_feas"]
    if "available_int" in req:
        d["available_int"] = req["available_int"]

    try:
        tenant_id = DocumentService.get_tenant_id(req["doc_id"])
        if not tenant_id:
            return get_data_error_result(message="Tenant not found!")

        embd_id = DocumentService.get_embd_id(req["doc_id"])
        embd_mdl = LLMBundle(tenant_id, LLMType.EMBEDDING, embd_id)

        e, doc = DocumentService.get_by_id(req["doc_id"])
        if not e:
            return get_data_error_result(message="Document not found!")

        if doc.parser_id == ParserType.QA:
            arr = [
                t for t in re.split(
                    r"[\n\t]",
                    req["content_with_weight"]) if len(t) > 1]
            q, a = rmPrefix(arr[0]), rmPrefix("\n".join(arr[1:]))
            d = beAdoc(d, q, a, not any(
                [rag_tokenizer.is_chinese(t) for t in q + a]))

        v, c = embd_mdl.encode([doc.name, req["content_with_weight"] if not d.get("question_kwd") else "\n".join(d["question_kwd"])])
        v = 0.1 * v[0] + 0.9 * v[1] if doc.parser_id != ParserType.QA else v[1]
        d["q_%d_vec" % len(v)] = v.tolist()
        settings.docStoreConn.update({"id": req["chunk_id"]}, d, search.index_name(tenant_id), doc.kb_id)
        return get_json_result(data=True)
    except Exception as e:
        return server_error_response(e)


@manager.route('/switch', methods=['POST'])  # noqa: F821
@login_required
@validate_request("chunk_ids", "available_int", "doc_id")
def switch():
    req = request.json
    try:
        e, doc = DocumentService.get_by_id(req["doc_id"])
        if not e:
            return get_data_error_result(message="Document not found!")
        for cid in req["chunk_ids"]:
            if not settings.docStoreConn.update({"id": cid},
                                                {"available_int": int(req["available_int"])},
                                                search.index_name(DocumentService.get_tenant_id(req["doc_id"])),
                                                doc.kb_id):
                return get_data_error_result(message="Index updating failure")
        return get_json_result(data=True)
    except Exception as e:
        return server_error_response(e)


@manager.route('/rm', methods=['POST'])  # noqa: F821
@login_required
@validate_request("chunk_ids", "doc_id")
def rm():
    from rag.utils.storage_factory import STORAGE_IMPL
    req = request.json
    try:
        e, doc = DocumentService.get_by_id(req["doc_id"])
        if not e:
            return get_data_error_result(message="Document not found!")
        if not settings.docStoreConn.delete({"id": req["chunk_ids"]},
                                            search.index_name(DocumentService.get_tenant_id(req["doc_id"])),
                                            doc.kb_id):
            return get_data_error_result(message="Chunk deleting failure")
        deleted_chunk_ids = req["chunk_ids"]
        chunk_number = len(deleted_chunk_ids)
        DocumentService.decrement_chunk_num(doc.id, doc.kb_id, 1, chunk_number, 0)
        for cid in deleted_chunk_ids:
            if STORAGE_IMPL.obj_exist(doc.kb_id, cid):
                STORAGE_IMPL.rm(doc.kb_id, cid)
        return get_json_result(data=True)
    except Exception as e:
        return server_error_response(e)


@manager.route('/create', methods=['POST'])  # noqa: F821
@login_required
@validate_request("doc_id", "content_with_weight")
def create():
    req = request.json
    chunck_id = xxhash.xxh64((req["content_with_weight"] + req["doc_id"]).encode("utf-8")).hexdigest()
    d = {"id": chunck_id, "content_ltks": rag_tokenizer.tokenize(req["content_with_weight"]),
         "content_with_weight": req["content_with_weight"]}
    d["content_sm_ltks"] = rag_tokenizer.fine_grained_tokenize(d["content_ltks"])
    d["important_kwd"] = req.get("important_kwd", [])
    if not isinstance(d["important_kwd"], list):
        return get_data_error_result(message="`important_kwd` is required to be a list")
    d["important_tks"] = rag_tokenizer.tokenize(" ".join(d["important_kwd"]))
    d["question_kwd"] = req.get("question_kwd", [])
    if not isinstance(d["question_kwd"], list):
        return get_data_error_result(message="`question_kwd` is required to be a list")
    d["question_tks"] = rag_tokenizer.tokenize("\n".join(d["question_kwd"]))
    d["create_time"] = str(datetime.datetime.now()).replace("T", " ")[:19]
    d["create_timestamp_flt"] = datetime.datetime.now().timestamp()
    if "tag_feas" in req:
        d["tag_feas"] = req["tag_feas"]
    if "tag_feas" in req:
        d["tag_feas"] = req["tag_feas"]

    try:
        e, doc = DocumentService.get_by_id(req["doc_id"])
        if not e:
            return get_data_error_result(message="Document not found!")
        d["kb_id"] = [doc.kb_id]
        d["docnm_kwd"] = doc.name
        d["title_tks"] = rag_tokenizer.tokenize(doc.name)
        d["doc_id"] = doc.id

        tenant_id = DocumentService.get_tenant_id(req["doc_id"])
        if not tenant_id:
            return get_data_error_result(message="Tenant not found!")

        e, kb = KnowledgebaseService.get_by_id(doc.kb_id)
        if not e:
            return get_data_error_result(message="Knowledgebase not found!")
        if kb.pagerank:
            d[PAGERANK_FLD] = kb.pagerank

        embd_id = DocumentService.get_embd_id(req["doc_id"])
        embd_mdl = LLMBundle(tenant_id, LLMType.EMBEDDING.value, embd_id)

        v, c = embd_mdl.encode([doc.name, req["content_with_weight"] if not d["question_kwd"] else "\n".join(d["question_kwd"])])
        v = 0.1 * v[0] + 0.9 * v[1]
        d["q_%d_vec" % len(v)] = v.tolist()
        settings.docStoreConn.insert([d], search.index_name(tenant_id), doc.kb_id)

        DocumentService.increment_chunk_num(
            doc.id, doc.kb_id, c, 1, 0)
        return get_json_result(data={"chunk_id": chunck_id})
    except Exception as e:
        return server_error_response(e)


@manager.route('/retrieval_test', methods=['POST'])  # noqa: F821
@login_required
@validate_request("kb_id", "question")
def retrieval_test():
    req = request.json
    page = int(req.get("page", 1))
    size = int(req.get("size", 30))
    question = req["question"]
    kb_ids = req["kb_id"]
    if isinstance(kb_ids, str):
        kb_ids = [kb_ids]
    doc_ids = req.get("doc_ids", [])
    similarity_threshold = float(req.get("similarity_threshold", 0.0))
    vector_similarity_weight = float(req.get("vector_similarity_weight", 0.3))
    use_kg = req.get("use_kg", False)
    top = int(req.get("top_k", 1024))
    langs = req.get("cross_languages", [])
    tenant_ids = []

    try:
        tenants = UserTenantService.query(user_id=current_user.id)
        for kb_id in kb_ids:
            for tenant in tenants:
                if KnowledgebaseService.query(
                        tenant_id=tenant.tenant_id, id=kb_id):
                    tenant_ids.append(tenant.tenant_id)
                    break
            else:
                return get_json_result(
                    data=False, message='Only owner of knowledgebase authorized for this operation.',
                    code=settings.RetCode.OPERATING_ERROR)

        e, kb = KnowledgebaseService.get_by_id(kb_ids[0])
        if not e:
            return get_data_error_result(message="Knowledgebase not found!")

        if langs:
            question = cross_languages(kb.tenant_id, None, question, langs)

        embd_mdl = LLMBundle(kb.tenant_id, LLMType.EMBEDDING.value, llm_name=kb.embd_id)

        rerank_mdl = None
        if req.get("rerank_id"):
            rerank_mdl = LLMBundle(kb.tenant_id, LLMType.RERANK.value, llm_name=req["rerank_id"])

        if req.get("keyword", False):
            chat_mdl = LLMBundle(kb.tenant_id, LLMType.CHAT)
            question += keyword_extraction(chat_mdl, question)

        labels = label_question(question, [kb])
        ranks = settings.retrievaler.retrieval(question, embd_mdl, tenant_ids, kb_ids, page, size,
                               similarity_threshold, vector_similarity_weight, top,
                               doc_ids, rerank_mdl=rerank_mdl, highlight=req.get("highlight"),
                               rank_feature=labels
                               )
        if use_kg:
            ck = settings.kg_retrievaler.retrieval(question,
                                                   tenant_ids,
                                                   kb_ids,
                                                   embd_mdl,
                                                   LLMBundle(kb.tenant_id, LLMType.CHAT))
            if ck["content_with_weight"]:
                ranks["chunks"].insert(0, ck)

        for c in ranks["chunks"]:
            c.pop("vector", None)
        ranks["labels"] = labels

        return get_json_result(data=ranks)
    except Exception as e:
        if str(e).find("not_found") > 0:
            return get_json_result(data=False, message='No chunk found! Check the chunk status please!',
                                   code=settings.RetCode.DATA_ERROR)
        return server_error_response(e)


@manager.route('/knowledge_graph', methods=['GET'])  # noqa: F821
@login_required
def knowledge_graph():
    doc_id = request.args["doc_id"]
    tenant_id = DocumentService.get_tenant_id(doc_id)
    kb_ids = KnowledgebaseService.get_kb_ids(tenant_id)
    req = {
        "doc_ids": [doc_id],
        "knowledge_graph_kwd": ["graph", "mind_map"]
    }
    sres = settings.retrievaler.search(req, search.index_name(tenant_id), kb_ids)
    obj = {"graph": {}, "mind_map": {}}
    for id in sres.ids[:2]:
        ty = sres.field[id]["knowledge_graph_kwd"]
        try:
            content_json = json.loads(sres.field[id]["content_with_weight"])
        except Exception:
            continue

        if ty == 'mind_map':
            node_dict = {}

            def repeat_deal(content_json, node_dict):
                if 'id' in content_json:
                    if content_json['id'] in node_dict:
                        node_name = content_json['id']
                        content_json['id'] += f"({node_dict[content_json['id']]})"
                        node_dict[node_name] += 1
                    else:
                        node_dict[content_json['id']] = 1
                if 'children' in content_json and content_json['children']:
                    for item in content_json['children']:
                        repeat_deal(item, node_dict)

            repeat_deal(content_json, node_dict)

        obj[ty] = content_json

    return get_json_result(data=obj)


@manager.route('/parent_child_split', methods=['POST'])  # noqa: F821
def parent_child_split():
    """
    父子分块API端点 - 供外部服务调用
    不需要登录认证，供knowflow服务使用
    """
    try:
        import traceback
        
        # 解析请求参数
        req = request.get_json()
        if not req:
            return get_json_result(data=None, message="Request body is required", code=400)
        
        # 必需参数
        text = req.get('text', '').strip()
        doc_id = req.get('doc_id', 'unknown')
        kb_id = req.get('kb_id', 'unknown')
        
        if not text:
            return get_json_result(data=None, message="Text is required", code=400)
        
        # 可选参数
        chunk_token_num = req.get('chunk_token_num', 256)
        min_chunk_tokens = req.get('min_chunk_tokens', 10)
        parent_config = req.get('parent_config', {})
        metadata = req.get('metadata', {})
        
        # 使用tiktoken进行准确的token计算
        import tiktoken
        encoder = tiktoken.get_encoding("cl100k_base")
        
        def accurate_token_count(text):
            return len(encoder.encode(text))
        
        # 通过HTTP调用KnowFlow服务获取智能分块
        def get_smart_chunks_from_knowflow(text, chunk_token_num=128, min_chunk_tokens=10):
            """通过HTTP API调用KnowFlow的智能分块服务"""
            try:
                import requests
                import os
                
                knowflow_api_url = os.getenv('KNOWFLOW_API_URL', 'http://localhost:5000')
                api_endpoint = f"{knowflow_api_url}/api/smart_chunk"
                
                request_data = {
                    'text': text,
                    'chunk_token_num': chunk_token_num,
                    'min_chunk_tokens': min_chunk_tokens,
                    'method': 'smart'
                }
                
                response = requests.post(
                    api_endpoint,
                    json=request_data,
                    headers={'Content-Type': 'application/json'},
                    timeout=60
                )
                
                if response.status_code == 200:
                    result_data = response.json()
                    if result_data.get('code') == 0:
                        return result_data.get('data', {}).get('chunks', [])
                    else:
                        raise Exception(f"KnowFlow API Error: {result_data.get('message', 'Unknown error')}")
                else:
                    raise Exception(f"HTTP Error: {response.status_code}")
                    
            except Exception:
                try:
                    from rag.nlp import naive
                    return naive.split_by_sentences(text, chunk_token_num)
                except:
                    return [text]
        
        # 获取智能分块结果
        child_chunks_content = get_smart_chunks_from_knowflow(
            text, 
            chunk_token_num=chunk_token_num, 
            min_chunk_tokens=min_chunk_tokens
        )
        
        # 构建子分块对象
        import hashlib
        
        class SimpleChunkInfo:
            def __init__(self, id, content, token_count, char_count, order, metadata=None):
                self.id = id
                self.content = content
                self.token_count = token_count
                self.char_count = char_count
                self.order = order
                self.metadata = metadata or {}
        
        child_chunks = []
        for i, content in enumerate(child_chunks_content):
            chunk_id = f"{doc_id}_child_{i:04d}_{hashlib.md5(content.encode('utf-8')).hexdigest()[:8]}"
            child_chunks.append(SimpleChunkInfo(
                id=chunk_id,
                content=content,
                token_count=accurate_token_count(content),
                char_count=len(content),
                order=i,
                metadata={'chunk_type': 'child', 'chunk_method': 'child_smart'}
            ))
        
        # 构建父分块
        parent_chunks = []
        relationships = []
        current_parent_content = []
        current_parent_tokens = 0
        current_child_ids = []
        parent_order = 0
        parent_chunk_size = parent_config.get('parent_chunk_size', 1024)
        
        for child_chunk in child_chunks:
            # 检查是否需要创建新的父分块
            if (current_parent_tokens + child_chunk.token_count > parent_chunk_size 
                and current_parent_content):
                
                # 创建父分块
                parent_content = "\n\n".join(current_parent_content).strip()
                parent_id = f"{doc_id}_parent_{parent_order:04d}_{hashlib.md5(parent_content.encode('utf-8')).hexdigest()[:8]}"
                
                parent_chunk = SimpleChunkInfo(
                    id=parent_id,
                    content=parent_content,
                    token_count=accurate_token_count(parent_content),
                    char_count=len(parent_content),
                    order=parent_order,
                    metadata={'chunk_type': 'parent', 'chunk_method': 'parent_smart', 'contains_children': len(current_child_ids)}
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
            
            # 添加到当前父分块
            current_parent_content.append(child_chunk.content)
            current_parent_tokens += child_chunk.token_count
            current_child_ids.append(child_chunk.id)
        
        # 处理最后一个父分块
        if current_parent_content:
            parent_content = "\n\n".join(current_parent_content).strip()
            parent_id = f"{doc_id}_parent_{parent_order:04d}_{hashlib.md5(parent_content.encode('utf-8')).hexdigest()[:8]}"
            
            parent_chunk = SimpleChunkInfo(
                id=parent_id,
                content=parent_content,
                token_count=accurate_token_count(parent_content),
                char_count=len(parent_content),
                order=parent_order,
                metadata={'chunk_type': 'parent', 'chunk_method': 'parent_smart', 'contains_children': len(current_child_ids)}
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
        
        # 构建结果对象
        class SimpleParentChildResult:
            def __init__(self, parent_chunks, child_chunks, relationships, total_parents, total_children):
                self.parent_chunks = parent_chunks
                self.child_chunks = child_chunks
                self.relationships = relationships
                self.total_parents = total_parents
                self.total_children = total_children
        
        result = SimpleParentChildResult(
            parent_chunks=parent_chunks,
            child_chunks=child_chunks,
            relationships=relationships,
            total_parents=len(parent_chunks),
            total_children=len(child_chunks)
        )
        
        
        # 根据检索模式决定返回内容
        retrieval_mode = parent_config.get('retrieval_mode', 'parent')
        
        if retrieval_mode == 'child':
            chunks_content = [chunk.content for chunk in result.child_chunks]
        elif retrieval_mode == 'hybrid':
            chunks_content = [chunk.content for chunk in result.parent_chunks]
        else:
            chunks_content = [chunk.content for chunk in result.parent_chunks]
        
        vector_storage_chunks = [chunk.content for chunk in result.child_chunks]
        
        # 构建详细结果信息
        detailed_result = {
            'parent_chunks': [
                {
                    'id': chunk.id,
                    'content': chunk.content,
                    'order': chunk.order,
                    'token_count': accurate_token_count(chunk.content),
                    'char_count': len(chunk.content),
                    'metadata': chunk.metadata
                }
                for chunk in result.parent_chunks
            ],
            'child_chunks': [
                {
                    'id': chunk.id,
                    'content': chunk.content,
                    'order': chunk.order,
                    'token_count': accurate_token_count(chunk.content),
                    'char_count': len(chunk.content),
                    'metadata': chunk.metadata
                }
                for chunk in result.child_chunks
            ],
            'relationships': result.relationships,
            'total_parents': result.total_parents,
            'total_children': result.total_children,
            'config_used': {
                'parent_chunk_size': parent_config.get('parent_chunk_size', 1024),
                'child_chunk_size': chunk_token_num,
                'retrieval_mode': parent_config.get('retrieval_mode', 'parent')
            }
        }
        
        return get_json_result(data={
            'chunks': chunks_content,
            'vector_chunks': vector_storage_chunks,
            'detailed_result': detailed_result,
            'mode_info': {
                'retrieval_mode': retrieval_mode,
                'returned_content_type': 'child' if retrieval_mode == 'child' else 'parent',
                'vector_storage_type': 'child'
            }
        }, message="Parent-child chunking completed successfully")
        
    except Exception as e:
        return get_json_result(
            data=None,
            message=f"Parent-child chunking failed: {str(e)}", 
            code=500
        )


@manager.route('/parent_child_health', methods=['GET'])  # noqa: F821
def parent_child_health():
    """健康检查端点"""
    try:
        return get_json_result(
            data={'status': 'healthy', 'version': '2.1.0'},
            message="Parent-child service is healthy"
        )
    except Exception as e:
        return get_json_result(
            data={'status': 'unhealthy', 'error': str(e)},
            message="Parent-child service is unhealthy",
            code=500
        )
