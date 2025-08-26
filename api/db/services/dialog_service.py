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
import binascii
import logging
import re
import time
from copy import deepcopy
from datetime import datetime
from functools import partial
from timeit import default_timer as timer

from langfuse import Langfuse
from peewee import fn

from agentic_reasoning import DeepResearcher
from api import settings
from api.db import LLMType, ParserType, StatusEnum
from api.db.db_models import DB, Dialog
from api.db.services.common_service import CommonService
from api.db.services.knowledgebase_service import KnowledgebaseService
from api.db.services.langfuse_service import TenantLangfuseService
from api.db.services.llm_service import LLMBundle, TenantLLMService

# 添加父子分块支持
try:
    from api.db.parent_child_models import ParentChildMapping
    PARENT_CHILD_AVAILABLE = True
except ImportError:
    PARENT_CHILD_AVAILABLE = False
from api.utils import current_timestamp, datetime_format
from rag.app.resume import forbidden_select_fields4resume
from rag.app.tag import label_question
from rag.nlp.search import index_name
from rag.prompts import chunks_format, citation_prompt, cross_languages, full_question, kb_prompt, keyword_extraction, message_fit_in
from rag.utils import num_tokens_from_string, rmSpace
from rag.utils.tavily_conn import Tavily


def check_kb_parent_child_enabled(kb_ids):
    """检查知识库中是否有使用父子分块策略的文档"""
    if not PARENT_CHILD_AVAILABLE:
        return False, []
    
    enabled_kbs = []
    try:
        from api.db.services.document_service import DocumentService
        
        for kb_id in kb_ids:
            # 查询该知识库下是否有使用parent_child策略的文档
            # 使用原始数据库查询代替DocumentService.get_by_kb_id
            from api.db.db_models import Document
            documents = Document.select().where(Document.kb_id == kb_id)
            
            for doc in documents:
                if doc.parser_config:
                    try:
                        import json
                        if isinstance(doc.parser_config, str):
                            parser_config = json.loads(doc.parser_config)
                        else:
                            parser_config = doc.parser_config
                        
                        chunking_config = parser_config.get('chunking_config', {})
                        strategy = chunking_config.get('strategy', 'smart')
                        
                        if strategy == 'parent_child':
                            enabled_kbs.append(kb_id)
                            break  # 该知识库有父子分块文档，跳出内层循环
                    except:
                        continue
    except:
        pass
    
    return len(enabled_kbs) > 0, enabled_kbs


def parent_child_retrieval(query, embd_mdl, tenant_ids, kb_ids, page, top_n, similarity_threshold, vector_similarity_weight, doc_ids=None, top=1024, aggs=False, rerank_mdl=None, rank_feature=None):
    """父子分块检索逻辑"""
    try:
        # 先进行标准检索获取子分块
        child_results = settings.retrievaler.retrieval(
            query, embd_mdl, tenant_ids, kb_ids, page, top_n,
            similarity_threshold, vector_similarity_weight,
            doc_ids=doc_ids, top=top, aggs=aggs, rerank_mdl=rerank_mdl,
            rank_feature=rank_feature
        )
        
        # 获取父分块内容
        parent_chunks = []
        processed_parents = set()  # 避免重复的父分块
        
        for chunk in child_results.get("chunks", []):
            # retrieval() returns chunks with key 'chunk_id' for the chunk identifier
            # and 'doc_id' for the document identifier. Fall back to alternative keys if present.
            child_chunk_id = chunk.get("chunk_id", chunk.get("id"))
            doc_id = chunk.get("doc_id", chunk.get("document_id"))
            logging.info("1-------------")
            if not child_chunk_id or not doc_id:
                continue
            
            # # 检查该文档是否启用了父子分块
            # try:
            #     from api.db.services.document_service import DocumentService
            #     document = DocumentService.get_by_id(doc_id)
            #     if not document or not document.parser_config:
            #         continue
                    
            #     import json
            #     if isinstance(document.parser_config, str):
            #         parser_config = json.loads(document.parser_config)
            #     else:
            #         parser_config = document.parser_config
                
            #     chunking_config = parser_config.get('chunking_config', {})
            #     strategy = chunking_config.get('strategy', 'smart')
                
            #     # 只对父子分块策略的文档进行父子检索
            #     if strategy != 'parent_child':
            #         continue
                
            #     # 检查retrieval_mode配置，只有parent模式才进行父子转换
            #     parent_config = chunking_config.get('parent_config', {})
            #     retrieval_mode = parent_config.get('retrieval_mode', 'parent')
                
            #     logging.info(f"Document {doc_id}: strategy={strategy}, retrieval_mode={retrieval_mode}")
                
            #     # 如果配置为child模式，保留子分块，不转换为父分块
            #     if retrieval_mode != 'parent':
            #         logging.info(f"Skipping parent-child conversion for doc {doc_id}: retrieval_mode={retrieval_mode}")
            #         continue
                    
            # except Exception as e:
            #     logging.warning(f"Failed to check document strategy for {doc_id}: {e}")
            #     continue
            
            # 查询父子关系映射
            try:
                mappings = ParentChildMapping.select().where(
                    ParentChildMapping.child_chunk_id == child_chunk_id
                ).limit(1)
                logging.info("2-------------")
                logging.info("child_chunk_id=%s, doc_id=%s", child_chunk_id, doc_id)
                count = ParentChildMapping.select().where(
                     ParentChildMapping.child_chunk_id == child_chunk_id
                ).count()
                logging.info("mapping_count=%s", count)
                
                for mapping in mappings:
                    parent_id = mapping.parent_chunk_id
                    if parent_id in processed_parents:
                        continue
                    processed_parents.add(parent_id)
                    logging.info("3-------------")
                    
                    # 获取正确的tenant_id
                    try:
                        from api.db.services.document_service import DocumentService
                        tenant_id = DocumentService.get_tenant_id(mapping.doc_id)
                        if not tenant_id:
                            logging.warning(f"Failed to get tenant_id for doc {mapping.doc_id}")
                            continue
                    except Exception as e:
                        logging.warning(f"Failed to get tenant_id for doc {mapping.doc_id}: {e}")
                        continue
                    
                    # 从单独的父分块ES索引中获取父分块内容
                    parent_index = f"{index_name(tenant_id)}_parent"
                    parent_chunk_data = settings.docStoreConn.get(
                        parent_id, 
                        parent_index, 
                        [mapping.kb_id]
                    )
                    
                    if parent_chunk_data:
                        logging.info(f"Successfully retrieved parent chunk {parent_id} from separate index {parent_index} for child {child_chunk_id}")
                        # 构建父分块数据结构，保持与标准检索结果兼容
                        parent_chunk = {
                            "id": parent_id,
                            "content_with_weight": parent_chunk_data.get("content_with_weight", ""),
                            "content_ltks": parent_chunk_data.get("content_ltks", ""),  # 添加缺失的字段
                            "doc_id": mapping.doc_id,
                            "docnm_kwd": parent_chunk_data.get("docnm_kwd", ""),
                            "kb_id": mapping.kb_id,
                            "similarity": chunk.get("similarity", 0.5),  # 继承子分块的相似度
                            "term_similarity": chunk.get("term_similarity", 0.5),
                            "vector": chunk.get("vector", []),
                            "positions": parent_chunk_data.get("positions", []),
                            "img_id": parent_chunk_data.get("img_id", ""),
                            "important_kwd": parent_chunk_data.get("important_kwd", []),
                            "question_kwd": parent_chunk_data.get("question_kwd", []),
                            "chunk_type": "parent"  # 标记为父分块
                        }
                        parent_chunks.append(parent_chunk)
                    else:
                        logging.warning(f"Failed to retrieve parent chunk data from ES: {parent_id}")
            
            except Exception as e:
                logging.warning(f"Failed to get parent chunk for child {child_chunk_id}: {e}")
                continue
        
        # 如果找到父分块，返回父分块结果；否则返回原始子分块结果
        if parent_chunks:
            logging.info(f"Parent-child retrieval: {len(parent_chunks)} parent chunks retrieved")
            # 保持原有的结果结构
            result = deepcopy(child_results)
            result["chunks"] = parent_chunks[:top_n]  # 限制返回数量
            return result
        else:
            logging.info("Parent-child retrieval: no parent chunks found, using child chunks")
            return child_results
            
    except Exception as e:
        logging.error(f"Parent-child retrieval failed: {e}")
        # 回退到标准检索
        return settings.retrievaler.retrieval(
            query, embd_mdl, tenant_ids, kb_ids, page, top_n,
            similarity_threshold, vector_similarity_weight,
            doc_ids=doc_ids, top=top, aggs=aggs, rerank_mdl=rerank_mdl,
            rank_feature=rank_feature
        )


class DialogService(CommonService):
    model = Dialog

    @classmethod
    def save(cls, **kwargs):
        """Save a new record to database.

        This method creates a new record in the database with the provided field values,
        forcing an insert operation rather than an update.

        Args:
            **kwargs: Record field values as keyword arguments.

        Returns:
            Model instance: The created record object.
        """
        sample_obj = cls.model(**kwargs).save(force_insert=True)
        return sample_obj

    @classmethod
    def update_many_by_id(cls, data_list):
        """Update multiple records by their IDs.

        This method updates multiple records in the database, identified by their IDs.
        It automatically updates the update_time and update_date fields for each record.

        Args:
            data_list (list): List of dictionaries containing record data to update.
                             Each dictionary must include an 'id' field.
        """
        with DB.atomic():
            for data in data_list:
                data["update_time"] = current_timestamp()
                data["update_date"] = datetime_format(datetime.now())
                cls.model.update(data).where(cls.model.id == data["id"]).execute()

    @classmethod
    @DB.connection_context()
    def get_list(cls, tenant_id, page_number, items_per_page, orderby, desc, id, name):
        chats = cls.model.select()
        if id:
            chats = chats.where(cls.model.id == id)
        if name:
            chats = chats.where(cls.model.name == name)
        chats = chats.where((cls.model.tenant_id == tenant_id) & (cls.model.status == StatusEnum.VALID.value))
        if desc:
            chats = chats.order_by(cls.model.getter_by(orderby).desc())
        else:
            chats = chats.order_by(cls.model.getter_by(orderby).asc())

        chats = chats.paginate(page_number, items_per_page)

        return list(chats.dicts())


    @classmethod
    @DB.connection_context()
    def get_by_tenant_ids(cls, joined_tenant_ids, user_id, page_number, items_per_page, orderby, desc, keywords, parser_id=None):
        from api.db.db_models import User

        fields = [
            cls.model.id,
            cls.model.tenant_id,
            cls.model.name,
            cls.model.description,
            cls.model.language,
            cls.model.llm_id,
            cls.model.llm_setting,
            cls.model.prompt_type,
            cls.model.prompt_config,
            cls.model.similarity_threshold,
            cls.model.vector_similarity_weight,
            cls.model.top_n,
            cls.model.top_k,
            cls.model.do_refer,
            cls.model.rerank_id,
            cls.model.kb_ids,
            cls.model.status,
            User.nickname,
            User.avatar.alias("tenant_avatar"),
            cls.model.update_time,
            cls.model.create_time,
        ]
        if keywords:
            dialogs = (
                cls.model.select(*fields)
                .join(User, on=(cls.model.tenant_id == User.id))
                .where(
                    (cls.model.tenant_id.in_(joined_tenant_ids) | (cls.model.tenant_id == user_id)) & (cls.model.status == StatusEnum.VALID.value),
                    (fn.LOWER(cls.model.name).contains(keywords.lower())),
                )
            )
        else:
            dialogs = (
                cls.model.select(*fields)
                .join(User, on=(cls.model.tenant_id == User.id))
                .where(
                    (cls.model.tenant_id.in_(joined_tenant_ids) | (cls.model.tenant_id == user_id)) & (cls.model.status == StatusEnum.VALID.value),
                )
            )
        if parser_id:
            dialogs = dialogs.where(cls.model.parser_id == parser_id)
        if desc:
            dialogs = dialogs.order_by(cls.model.getter_by(orderby).desc())
        else:
            dialogs = dialogs.order_by(cls.model.getter_by(orderby).asc())

        count = dialogs.count()

        if page_number and items_per_page:
            dialogs = dialogs.paginate(page_number, items_per_page)

        return list(dialogs.dicts()), count


def chat_solo(dialog, messages, stream=True):
    if TenantLLMService.llm_id2llm_type(dialog.llm_id) == "image2text":
        chat_mdl = LLMBundle(dialog.tenant_id, LLMType.IMAGE2TEXT, dialog.llm_id)
    else:
        chat_mdl = LLMBundle(dialog.tenant_id, LLMType.CHAT, dialog.llm_id)

    prompt_config = dialog.prompt_config
    tts_mdl = None
    if prompt_config.get("tts"):
        tts_mdl = LLMBundle(dialog.tenant_id, LLMType.TTS)
    msg = [{"role": m["role"], "content": re.sub(r"##\d+\$\$", "", m["content"])} for m in messages if m["role"] != "system"]
    if stream:
        last_ans = ""
        delta_ans = ""
        for ans in chat_mdl.chat_streamly(prompt_config.get("system", ""), msg, dialog.llm_setting):
            answer = ans
            delta_ans = ans[len(last_ans) :]
            if num_tokens_from_string(delta_ans) < 16:
                continue
            last_ans = answer
            yield {"answer": answer, "reference": {}, "audio_binary": tts(tts_mdl, delta_ans), "prompt": "", "created_at": time.time()}
            delta_ans = ""
        if delta_ans:
            yield {"answer": answer, "reference": {}, "audio_binary": tts(tts_mdl, delta_ans), "prompt": "", "created_at": time.time()}
    else:
        answer = chat_mdl.chat(prompt_config.get("system", ""), msg, dialog.llm_setting)
        user_content = msg[-1].get("content", "[content not available]")
        logging.debug("User: {}|Assistant: {}".format(user_content, answer))
        yield {"answer": answer, "reference": {}, "audio_binary": tts(tts_mdl, answer), "prompt": "", "created_at": time.time()}


def get_models(dialog):
    embd_mdl, chat_mdl, rerank_mdl, tts_mdl = None, None, None, None
    kbs = KnowledgebaseService.get_by_ids(dialog.kb_ids)
    embedding_list = list(set([kb.embd_id for kb in kbs]))
    if len(embedding_list) > 1:
        raise Exception("**ERROR**: Knowledge bases use different embedding models.")

    if embedding_list:
        embd_mdl = LLMBundle(dialog.tenant_id, LLMType.EMBEDDING, embedding_list[0])
        if not embd_mdl:
            raise LookupError("Embedding model(%s) not found" % embedding_list[0])

    if TenantLLMService.llm_id2llm_type(dialog.llm_id) == "image2text":
        chat_mdl = LLMBundle(dialog.tenant_id, LLMType.IMAGE2TEXT, dialog.llm_id)
    else:
        chat_mdl = LLMBundle(dialog.tenant_id, LLMType.CHAT, dialog.llm_id)

    if dialog.rerank_id:
        rerank_mdl = LLMBundle(dialog.tenant_id, LLMType.RERANK, dialog.rerank_id)

    if dialog.prompt_config.get("tts"):
        tts_mdl = LLMBundle(dialog.tenant_id, LLMType.TTS)
    return kbs, embd_mdl, rerank_mdl, chat_mdl, tts_mdl


def repair_bad_citation_formats(answer: str, kbinfos: dict, idx: set):
    max_index = len(kbinfos["chunks"])

    def safe_add(i):
        if 0 <= i < max_index:
            idx.add(i)
            return True
        return False

    def find_and_replace(pattern, group_index=1, repl=lambda i: f"##{i}$$", flags=0):
        nonlocal answer
        for match in re.finditer(pattern, answer, flags=flags):
            try:
                i = int(match.group(group_index))
                if safe_add(i):
                    answer = answer.replace(match.group(0), repl(i))
            except Exception:
                continue

    find_and_replace(r"\(\s*ID:\s*(\d+)\s*\)")  # (ID: 12)
    find_and_replace(r"\[\s*ID\s*[: ]*\s*(\d+)\s*\]")  # [ID: 12]
    find_and_replace(r"ID[: ]+(\d+)")  # ID: 12, ID 12
    find_and_replace(r"\$\$(\d+)\$\$")  # $$12$$
    find_and_replace(r"\$\[(\d+)\]\$")  # $[12]$
    find_and_replace(r"\$\$(\d+)\${2,}")  # $$12$$$$
    find_and_replace(r"\$(\d+)\$")  # $12$
    find_and_replace(r"(#{2,})(\d+)(\${2,})", group_index=2)  # 2+ # and 2+ $
    find_and_replace(r"(#{2,})(\d+)(#{1,})", group_index=2)  # 2+ # and 1+ #
    find_and_replace(r"##(\d+)#{2,}")  # ##12###
    find_and_replace(r"【(\d+)】")  # 【12】
    find_and_replace(r"ref\s*(\d+)", flags=re.IGNORECASE)  # ref12, ref 12, REF 12

    return answer, idx


def chat(dialog, messages, stream=True, **kwargs):
    assert messages[-1]["role"] == "user", "The last content of this conversation is not from user."
    if not dialog.kb_ids and not dialog.prompt_config.get("tavily_api_key"):
        for ans in chat_solo(dialog, messages, stream):
            yield ans
        return

    chat_start_ts = timer()

    if TenantLLMService.llm_id2llm_type(dialog.llm_id) == "image2text":
        llm_model_config = TenantLLMService.get_model_config(dialog.tenant_id, LLMType.IMAGE2TEXT, dialog.llm_id)
    else:
        llm_model_config = TenantLLMService.get_model_config(dialog.tenant_id, LLMType.CHAT, dialog.llm_id)

    max_tokens = llm_model_config.get("max_tokens", 8192)

    check_llm_ts = timer()

    langfuse_tracer = None
    trace_context = {}
    langfuse_keys = TenantLangfuseService.filter_by_tenant(tenant_id=dialog.tenant_id)
    if langfuse_keys:
        langfuse = Langfuse(public_key=langfuse_keys.public_key, secret_key=langfuse_keys.secret_key, host=langfuse_keys.host)
        if langfuse.auth_check():
            langfuse_tracer = langfuse
            trace_id = langfuse_tracer.create_trace_id()
            trace_context = {"trace_id": trace_id}

    check_langfuse_tracer_ts = timer()
    kbs, embd_mdl, rerank_mdl, chat_mdl, tts_mdl = get_models(dialog)
    toolcall_session, tools = kwargs.get("toolcall_session"), kwargs.get("tools")
    if toolcall_session and tools:
        chat_mdl.bind_tools(toolcall_session, tools)
    bind_models_ts = timer()

    retriever = settings.retrievaler
    questions = [m["content"] for m in messages if m["role"] == "user"][-3:]
    attachments = kwargs["doc_ids"].split(",") if "doc_ids" in kwargs else None
    if "doc_ids" in messages[-1]:
        attachments = messages[-1]["doc_ids"]
    prompt_config = dialog.prompt_config
    field_map = KnowledgebaseService.get_field_map(dialog.kb_ids)
    # try to use sql if field mapping is good to go
    if field_map:
        logging.debug("Use SQL to retrieval:{}".format(questions[-1]))
        ans = use_sql(questions[-1], field_map, dialog.tenant_id, chat_mdl, prompt_config.get("quote", True))
        if ans:
            yield ans
            return

    for p in prompt_config["parameters"]:
        if p["key"] == "knowledge":
            continue
        if p["key"] not in kwargs and not p["optional"]:
            raise KeyError("Miss parameter: " + p["key"])
        if p["key"] not in kwargs:
            prompt_config["system"] = prompt_config["system"].replace("{%s}" % p["key"], " ")

    if len(questions) > 1 and prompt_config.get("refine_multiturn"):
        questions = [full_question(dialog.tenant_id, dialog.llm_id, messages)]
    else:
        questions = questions[-1:]

    if prompt_config.get("cross_languages"):
        questions = [cross_languages(dialog.tenant_id, dialog.llm_id, questions[0], prompt_config["cross_languages"])]

    if prompt_config.get("keyword", False):
        questions[-1] += keyword_extraction(chat_mdl, questions[-1])

    refine_question_ts = timer()

    thought = ""
    kbinfos = {"total": 0, "chunks": [], "doc_aggs": []}

    if "knowledge" not in [p["key"] for p in prompt_config["parameters"]]:
        knowledges = []
    else:
        tenant_ids = list(set([kb.tenant_id for kb in kbs]))
        knowledges = []
        if prompt_config.get("reasoning", False):
            reasoner = DeepResearcher(
                chat_mdl,
                prompt_config,
                partial(retriever.retrieval, embd_mdl=embd_mdl, tenant_ids=tenant_ids, kb_ids=dialog.kb_ids, page=1, page_size=dialog.top_n, similarity_threshold=0.2, vector_similarity_weight=0.3),
            )

            for think in reasoner.thinking(kbinfos, " ".join(questions)):
                if isinstance(think, str):
                    thought = think
                    knowledges = [t for t in think.split("\n") if t]
                elif stream:
                    yield think
        else:
            if embd_mdl:
                # 检查是否启用父子分块检索
                parent_child_enabled, enabled_kb_ids = check_kb_parent_child_enabled(dialog.kb_ids)
                
                if parent_child_enabled:
                    logging.info(f"Using parent-child retrieval for KBs: {enabled_kb_ids}")
                    kbinfos = parent_child_retrieval(
                        " ".join(questions),
                        embd_mdl,
                        tenant_ids,
                        dialog.kb_ids,
                        1,
                        dialog.top_n,
                        dialog.similarity_threshold,
                        dialog.vector_similarity_weight,
                        doc_ids=attachments,
                        top=dialog.top_k,
                        aggs=False,
                        rerank_mdl=rerank_mdl,
                        rank_feature=label_question(" ".join(questions), kbs),
                    )
                else:
                    kbinfos = retriever.retrieval(
                        " ".join(questions),
                        embd_mdl,
                        tenant_ids,
                        dialog.kb_ids,
                        1,
                        dialog.top_n,
                        dialog.similarity_threshold,
                        dialog.vector_similarity_weight,
                        doc_ids=attachments,
                        top=dialog.top_k,
                        aggs=False,
                        rerank_mdl=rerank_mdl,
                        rank_feature=label_question(" ".join(questions), kbs),
                    )
            if prompt_config.get("tavily_api_key"):
                tav = Tavily(prompt_config["tavily_api_key"])
                tav_res = tav.retrieve_chunks(" ".join(questions))
                kbinfos["chunks"].extend(tav_res["chunks"])
                kbinfos["doc_aggs"].extend(tav_res["doc_aggs"])
            if prompt_config.get("use_kg"):
                ck = settings.kg_retrievaler.retrieval(" ".join(questions), tenant_ids, dialog.kb_ids, embd_mdl, LLMBundle(dialog.tenant_id, LLMType.CHAT))
                if ck["content_with_weight"]:
                    kbinfos["chunks"].insert(0, ck)

            knowledges = kb_prompt(kbinfos, max_tokens)

    logging.debug("{}->{}".format(" ".join(questions), "\n->".join(knowledges)))

    retrieval_ts = timer()
    if not knowledges and prompt_config.get("empty_response"):
        empty_res = prompt_config["empty_response"]
        yield {"answer": empty_res, "reference": kbinfos, "prompt": "\n\n### Query:\n%s" % " ".join(questions), "audio_binary": tts(tts_mdl, empty_res)}
        return {"answer": prompt_config["empty_response"], "reference": kbinfos}

    kwargs["knowledge"] = "\n------\n" + "\n\n------\n\n".join(knowledges)
    gen_conf = dialog.llm_setting

    msg = [{"role": "system", "content": prompt_config["system"].format(**kwargs)}]
    prompt4citation = ""
    if knowledges and (prompt_config.get("quote", True) and kwargs.get("quote", True)):
        prompt4citation = citation_prompt()
    msg.extend([{"role": m["role"], "content": re.sub(r"##\d+\$\$", "", m["content"])} for m in messages if m["role"] != "system"])
    used_token_count, msg = message_fit_in(msg, int(max_tokens * 0.95))
    assert len(msg) >= 2, f"message_fit_in has bug: {msg}"
    prompt = msg[0]["content"]

    if "max_tokens" in gen_conf:
        gen_conf["max_tokens"] = min(gen_conf["max_tokens"], max_tokens - used_token_count)

    def decorate_answer(answer):
        nonlocal embd_mdl, prompt_config, knowledges, kwargs, kbinfos, prompt, retrieval_ts, questions, langfuse_tracer

        refs = []
        ans = answer.split("</think>")
        think = ""
        if len(ans) == 2:
            think = ans[0] + "</think>"
            answer = ans[1]

        if knowledges and (prompt_config.get("quote", True) and kwargs.get("quote", True)):
            idx = set([])
            if embd_mdl and not re.search(r"\[ID:([0-9]+)\]", answer):
                answer, idx = retriever.insert_citations(
                    answer,
                    [ck["content_ltks"] for ck in kbinfos["chunks"]],
                    [ck["vector"] for ck in kbinfos["chunks"]],
                    embd_mdl,
                    tkweight=1 - dialog.vector_similarity_weight,
                    vtweight=dialog.vector_similarity_weight,
                )
            else:
                for match in re.finditer(r"\[ID:([0-9]+)\]", answer):
                    i = int(match.group(1))
                    if i < len(kbinfos["chunks"]):
                        idx.add(i)

            answer, idx = repair_bad_citation_formats(answer, kbinfos, idx)

            idx = set([kbinfos["chunks"][int(i)]["doc_id"] for i in idx])
            recall_docs = [d for d in kbinfos["doc_aggs"] if d["doc_id"] in idx]
            if not recall_docs:
                recall_docs = kbinfos["doc_aggs"]
            kbinfos["doc_aggs"] = recall_docs

            refs = deepcopy(kbinfos)
            for c in refs["chunks"]:
                if c.get("vector"):
                    del c["vector"]

        if answer.lower().find("invalid key") >= 0 or answer.lower().find("invalid api") >= 0:
            answer += " Please set LLM API-Key in 'User Setting -> Model providers -> API-Key'"
        finish_chat_ts = timer()

        total_time_cost = (finish_chat_ts - chat_start_ts) * 1000
        check_llm_time_cost = (check_llm_ts - chat_start_ts) * 1000
        check_langfuse_tracer_cost = (check_langfuse_tracer_ts - check_llm_ts) * 1000
        bind_embedding_time_cost = (bind_models_ts - check_langfuse_tracer_ts) * 1000
        refine_question_time_cost = (refine_question_ts - bind_models_ts) * 1000
        retrieval_time_cost = (retrieval_ts - refine_question_ts) * 1000
        generate_result_time_cost = (finish_chat_ts - retrieval_ts) * 1000

        tk_num = num_tokens_from_string(think + answer)
        prompt += "\n\n### Query:\n%s" % " ".join(questions)
        prompt = (
            f"{prompt}\n\n"
            "## Time elapsed:\n"
            f"  - Total: {total_time_cost:.1f}ms\n"
            f"  - Check LLM: {check_llm_time_cost:.1f}ms\n"
            f"  - Check Langfuse tracer: {check_langfuse_tracer_cost:.1f}ms\n"
            f"  - Bind models: {bind_embedding_time_cost:.1f}ms\n"
            f"  - Query refinement(LLM): {refine_question_time_cost:.1f}ms\n"
            f"  - Retrieval: {retrieval_time_cost:.1f}ms\n"
            f"  - Generate answer: {generate_result_time_cost:.1f}ms\n\n"
            "## Token usage:\n"
            f"  - Generated tokens(approximately): {tk_num}\n"
            f"  - Token speed: {int(tk_num / (generate_result_time_cost / 1000.0))}/s"
        )

        # Add a condition check to call the end method only if langfuse_tracer exists
        if langfuse_tracer and "langfuse_generation" in locals():
            langfuse_output = "\n" + re.sub(r"^.*?(### Query:.*)", r"\1", prompt, flags=re.DOTALL)
            langfuse_output = {"time_elapsed:": re.sub(r"\n", "  \n", langfuse_output), "created_at": time.time()}
            langfuse_generation.update(output=langfuse_output)
            langfuse_generation.end()

        return {"answer": think + answer, "reference": refs, "prompt": re.sub(r"\n", "  \n", prompt), "created_at": time.time()}

    if langfuse_tracer:
        langfuse_generation = langfuse_tracer.start_generation(
            trace_context=trace_context, name="chat", model=llm_model_config["llm_name"], input={"prompt": prompt, "prompt4citation": prompt4citation, "messages": msg}
        )

    if stream:
        last_ans = ""
        answer = ""
        for ans in chat_mdl.chat_streamly(prompt + prompt4citation, msg[1:], gen_conf):
            if thought:
                ans = re.sub(r"^.*</think>", "", ans, flags=re.DOTALL)
            answer = ans
            delta_ans = ans[len(last_ans) :]
            if num_tokens_from_string(delta_ans) < 16:
                continue
            last_ans = answer
            yield {"answer": thought + answer, "reference": {}, "audio_binary": tts(tts_mdl, delta_ans)}
        delta_ans = answer[len(last_ans) :]
        if delta_ans:
            yield {"answer": thought + answer, "reference": {}, "audio_binary": tts(tts_mdl, delta_ans)}
        yield decorate_answer(thought + answer)
    else:
        answer = chat_mdl.chat(prompt + prompt4citation, msg[1:], gen_conf)
        user_content = msg[-1].get("content", "[content not available]")
        logging.debug("User: {}|Assistant: {}".format(user_content, answer))
        res = decorate_answer(answer)
        res["audio_binary"] = tts(tts_mdl, answer)
        yield res


def use_sql(question, field_map, tenant_id, chat_mdl, quota=True):
    sys_prompt = "You are a Database Administrator. You need to check the fields of the following tables based on the user's list of questions and write the SQL corresponding to the last question."
    user_prompt = """
Table name: {};
Table of database fields are as follows:
{}

Question are as follows:
{}
Please write the SQL, only SQL, without any other explanations or text.
""".format(index_name(tenant_id), "\n".join([f"{k}: {v}" for k, v in field_map.items()]), question)
    tried_times = 0

    def get_table():
        nonlocal sys_prompt, user_prompt, question, tried_times
        sql = chat_mdl.chat(sys_prompt, [{"role": "user", "content": user_prompt}], {"temperature": 0.06})
        sql = re.sub(r"^.*</think>", "", sql, flags=re.DOTALL)
        logging.debug(f"{question} ==> {user_prompt} get SQL: {sql}")
        sql = re.sub(r"[\r\n]+", " ", sql.lower())
        sql = re.sub(r".*select ", "select ", sql.lower())
        sql = re.sub(r" +", " ", sql)
        sql = re.sub(r"([;；]|```).*", "", sql)
        if sql[: len("select ")] != "select ":
            return None, None
        if not re.search(r"((sum|avg|max|min)\(|group by )", sql.lower()):
            if sql[: len("select *")] != "select *":
                sql = "select doc_id,docnm_kwd," + sql[6:]
            else:
                flds = []
                for k in field_map.keys():
                    if k in forbidden_select_fields4resume:
                        continue
                    if len(flds) > 11:
                        break
                    flds.append(k)
                sql = "select doc_id,docnm_kwd," + ",".join(flds) + sql[8:]

        logging.debug(f"{question} get SQL(refined): {sql}")
        tried_times += 1
        return settings.retrievaler.sql_retrieval(sql, format="json"), sql

    tbl, sql = get_table()
    if tbl is None:
        return None
    if tbl.get("error") and tried_times <= 2:
        user_prompt = """
        Table name: {};
        Table of database fields are as follows:
        {}

        Question are as follows:
        {}
        Please write the SQL, only SQL, without any other explanations or text.


        The SQL error you provided last time is as follows:
        {}

        Error issued by database as follows:
        {}

        Please correct the error and write SQL again, only SQL, without any other explanations or text.
        """.format(index_name(tenant_id), "\n".join([f"{k}: {v}" for k, v in field_map.items()]), question, sql, tbl["error"])
        tbl, sql = get_table()
        logging.debug("TRY it again: {}".format(sql))

    logging.debug("GET table: {}".format(tbl))
    if tbl.get("error") or len(tbl["rows"]) == 0:
        return None

    docid_idx = set([ii for ii, c in enumerate(tbl["columns"]) if c["name"] == "doc_id"])
    doc_name_idx = set([ii for ii, c in enumerate(tbl["columns"]) if c["name"] == "docnm_kwd"])
    column_idx = [ii for ii in range(len(tbl["columns"])) if ii not in (docid_idx | doc_name_idx)]

    # compose Markdown table
    columns = (
        "|" + "|".join([re.sub(r"(/.*|（[^（）]+）)", "", field_map.get(tbl["columns"][i]["name"], tbl["columns"][i]["name"])) for i in column_idx]) + ("|Source|" if docid_idx and docid_idx else "|")
    )

    line = "|" + "|".join(["------" for _ in range(len(column_idx))]) + ("|------|" if docid_idx and docid_idx else "")

    rows = ["|" + "|".join([rmSpace(str(r[i])) for i in column_idx]).replace("None", " ") + "|" for r in tbl["rows"]]
    rows = [r for r in rows if re.sub(r"[ |]+", "", r)]
    if quota:
        rows = "\n".join([r + f" ##{ii}$$ |" for ii, r in enumerate(rows)])
    else:
        rows = "\n".join([r + f" ##{ii}$$ |" for ii, r in enumerate(rows)])
    rows = re.sub(r"T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+Z)?\|", "|", rows)

    if not docid_idx or not doc_name_idx:
        logging.warning("SQL missing field: " + sql)
        return {"answer": "\n".join([columns, line, rows]), "reference": {"chunks": [], "doc_aggs": []}, "prompt": sys_prompt}

    docid_idx = list(docid_idx)[0]
    doc_name_idx = list(doc_name_idx)[0]
    doc_aggs = {}
    for r in tbl["rows"]:
        if r[docid_idx] not in doc_aggs:
            doc_aggs[r[docid_idx]] = {"doc_name": r[doc_name_idx], "count": 0}
        doc_aggs[r[docid_idx]]["count"] += 1
    return {
        "answer": "\n".join([columns, line, rows]),
        "reference": {
            "chunks": [{"doc_id": r[docid_idx], "docnm_kwd": r[doc_name_idx]} for r in tbl["rows"]],
            "doc_aggs": [{"doc_id": did, "doc_name": d["doc_name"], "count": d["count"]} for did, d in doc_aggs.items()],
        },
        "prompt": sys_prompt,
    }


def tts(tts_mdl, text):
    if not tts_mdl or not text:
        return
    bin = b""
    for chunk in tts_mdl.tts(text):
        bin += chunk
    return binascii.hexlify(bin).decode("utf-8")


def ask(question, kb_ids, tenant_id, chat_llm_name=None):
    kbs = KnowledgebaseService.get_by_ids(kb_ids)
    embedding_list = list(set([kb.embd_id for kb in kbs]))

    is_knowledge_graph = all([kb.parser_id == ParserType.KG for kb in kbs])
    retriever = settings.retrievaler if not is_knowledge_graph else settings.kg_retrievaler

    embd_mdl = LLMBundle(tenant_id, LLMType.EMBEDDING, embedding_list[0])
    chat_mdl = LLMBundle(tenant_id, LLMType.CHAT, chat_llm_name)
    max_tokens = chat_mdl.max_length
    tenant_ids = list(set([kb.tenant_id for kb in kbs]))
    kbinfos = retriever.retrieval(question, embd_mdl, tenant_ids, kb_ids, 1, 12, 0.1, 0.3, aggs=False, rank_feature=label_question(question, kbs))
    knowledges = kb_prompt(kbinfos, max_tokens)
    prompt = """
    Role: You're a smart assistant. Your name is Miss R.
    Task: Summarize the information from knowledge bases and answer user's question.
    Requirements and restriction:
      - DO NOT make things up, especially for numbers.
      - If the information from knowledge is irrelevant with user's question, JUST SAY: Sorry, no relevant information provided.
      - Answer with markdown format text.
      - Answer in language of user's question.
      - DO NOT make things up, especially for numbers.

    ### Information from knowledge bases
    %s

    The above is information from knowledge bases.

    """ % "\n".join(knowledges)
    msg = [{"role": "user", "content": question}]

    def decorate_answer(answer):
        nonlocal knowledges, kbinfos, prompt
        answer, idx = retriever.insert_citations(answer, [ck["content_ltks"] for ck in kbinfos["chunks"]], [ck["vector"] for ck in kbinfos["chunks"]], embd_mdl, tkweight=0.7, vtweight=0.3)
        idx = set([kbinfos["chunks"][int(i)]["doc_id"] for i in idx])
        recall_docs = [d for d in kbinfos["doc_aggs"] if d["doc_id"] in idx]
        if not recall_docs:
            recall_docs = kbinfos["doc_aggs"]
        kbinfos["doc_aggs"] = recall_docs
        refs = deepcopy(kbinfos)
        for c in refs["chunks"]:
            if c.get("vector"):
                del c["vector"]

        if answer.lower().find("invalid key") >= 0 or answer.lower().find("invalid api") >= 0:
            answer += " Please set LLM API-Key in 'User Setting -> Model Providers -> API-Key'"
        refs["chunks"] = chunks_format(refs)
        return {"answer": answer, "reference": refs}

    answer = ""
    for ans in chat_mdl.chat_streamly(prompt, msg, {"temperature": 0.1}):
        answer = ans
        yield {"answer": answer, "reference": {}}
    yield decorate_answer(answer)
