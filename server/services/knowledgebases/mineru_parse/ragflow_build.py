from ragflow_sdk import RAGFlow
import os
import time
import shutil
from dotenv import load_dotenv
from .minio_server import upload_directory_to_minio
from .mineru_test import update_markdown_image_urls
from .utils import split_markdown_to_chunks_configured, get_bbox_for_chunk, update_document_progress
from database import get_es_client

def _validate_environment():
    """验证环境变量配置"""
    load_dotenv()
    api_key = os.getenv('RAGFLOW_API_KEY')
    base_url = os.getenv('RAGFLOW_BASE_URL')
    if not api_key:
        raise ValueError("错误：请在.env文件中设置RAGFLOW_API_KEY或使用--api_key参数指定。")
    if not base_url:
        raise ValueError("错误：请在.env文件中设置RAGFLOW_BASE_URL或使用--server_ip参数指定。")
    return api_key, base_url

def _upload_images(kb_id, image_dir, update_progress):
    update_progress(0.7, "上传图片到MinIO...")
    print(f"第4步：上传图片到MinIO...")
    upload_directory_to_minio(kb_id, image_dir)

def _add_chunks_to_doc(doc, chunks, update_progress):
    update_progress(0.8, "添加 chunk 到文档...")
    print(f"总共接收到 {len(chunks)} 个 chunks 准备添加。")
    for i, chunk in enumerate(chunks):
        chunk_preview = chunk.strip()[:50].replace('\n', ' ')
        print(f"准备添加 Chunk {i}: \"{chunk_preview}...\"")
        if chunk and chunk.strip():
            try:
                doc.add_chunk(content=chunk)
            except Exception as e:
                print(f"添加 chunk 失败: {e}")

def _update_chunks_position(doc, md_file_path, chunk_content_to_index):
    es_client = get_es_client()
    print(f"文档: id: {doc.id})")
    chunk_count = 0
    tenant_id = doc.created_by
    index_name = f"ragflow_{tenant_id}"
    for chunk in doc.list_chunks(keywords=None, page=1, page_size=10000):
        original_index = chunk_content_to_index.get(chunk.content)
        if original_index is None:
            print(f"警告: 无法为块 id={chunk.id} 的内容找到原始索引，将跳过此块。")
            continue
        
        direct_update = {
            "doc": {
                "top_int": original_index
            }
        }
        
        # 尝试获取位置信息，如果成功则添加到更新中
        try:
            position_int_temp = get_bbox_for_chunk(md_file_path, chunk.content)
            if position_int_temp is not None:
                doc_fields = {}
                _add_positions(doc_fields, position_int_temp)
                direct_update["doc"]["position_int"] = doc_fields.get("position_int")
        except Exception as e:
            print(f"获取chunk位置异常: {e}")
        
        # 执行ES更新
        try:
            es_client.update(index=index_name, id=chunk.id, body=direct_update, refresh=True)
            chunk_count += 1
        except Exception as es_e:
            print(f"ES更新异常: {es_e}")
        
    return chunk_count

def _cleanup_temp_files(md_file_path):
    """清理临时文件"""
    # 检查环境变量是否允许删除临时文件
    cleanup_enabled = os.getenv('CLEANUP_TEMP_FILES', 'true').lower() in ('true', '1', 'yes', 'on')
    
    if not cleanup_enabled:
        print(f"[INFO] 环境变量 CLEANUP_TEMP_FILES 设置为 false，保留临时文件: {os.path.dirname(os.path.abspath(md_file_path))}")
        return
    
    try:
        temp_dir = os.path.dirname(os.path.abspath(md_file_path))
        shutil.rmtree(temp_dir)
        print(f"[INFO] 已清理临时文件目录: {temp_dir}")
    except Exception as e:
        print(f"[WARNING] 清理临时文件异常: {e}")

def create_ragflow_resources(doc_id, kb_id, md_file_path, image_dir, update_progress):
    """
    使用增强文本创建RAGFlow知识库和聊天助手
    """
    try:
        api_key, base_url = _validate_environment()
        rag_object = RAGFlow(api_key=api_key, base_url=base_url)
        datasets = rag_object.list_datasets(id=kb_id)
        if not datasets:
            raise Exception("未找到对应的知识库")
        dataset = datasets[0]

        _upload_images(kb_id, image_dir, update_progress)

        enhanced_text = update_markdown_image_urls(md_file_path, kb_id)
        chunks = split_markdown_to_chunks_configured(enhanced_text, chunk_token_num=256)
        chunk_content_to_index = {chunk: i for i, chunk in enumerate(chunks)}

        docs = dataset.list_documents(id=doc_id)
        if not docs:
            raise Exception("未找到对应的文档")
        doc = docs[0]

        _add_chunks_to_doc(doc, chunks, update_progress)
        chunk_count = _update_chunks_position(doc, md_file_path, chunk_content_to_index)

        update_document_progress(doc.id, progress=1.0, message="解析完成", status='1', run='3', chunk_count=chunk_count, process_duration=None)

        # 根据环境变量决定是否清理临时文件
        _cleanup_temp_files(md_file_path)

        return chunk_count

    except Exception as e:
        print(f"create_ragflow_resources 处理出错: {str(e)}")
        import traceback
        traceback.print_exc()
        raise

def _add_positions(d, poss):
    try:
        if not poss:
            return
        page_num_int = []
        position_int = []
        top_int = []
        for pn, left, right, top, bottom in poss:
            page_num_int.append(int(pn + 1))
            top_int.append(int(top))
            position_int.append((int(pn + 1), int(left), int(right), int(top), int(bottom)))
        d["page_num_int"] = page_num_int
        d["position_int"] = position_int
        d["top_int"] = top_int
    except Exception as e:
        print(f"add_positions异常: {e}")