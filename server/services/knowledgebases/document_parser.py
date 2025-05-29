import os
import tempfile
import shutil
import json
import mysql.connector
import traceback
import time 
from database import DB_CONFIG, get_minio_client


def _get_db_connection():
    """创建数据库连接"""
    return mysql.connector.connect(**DB_CONFIG)

def _update_document_progress(doc_id, progress=None, message=None, status=None, run=None, chunk_count=None, process_duration=None):
    """更新数据库中文档的进度和状态"""
    conn = None
    cursor = None
    try:
        conn = _get_db_connection()
        cursor = conn.cursor()
        updates = []
        params = []

        if progress is not None:
            updates.append("progress = %s")
            params.append(float(progress))
        if message is not None:
            updates.append("progress_msg = %s")
            params.append(message)
        if status is not None:
            updates.append("status = %s")
            params.append(status)
        if run is not None:
            updates.append("run = %s")
            params.append(run)
        if chunk_count is not None:
             updates.append("chunk_num = %s")
             params.append(chunk_count)
        if process_duration is not None:
            updates.append("process_duation = %s")
            params.append(process_duration)


        if not updates:
            return

        query = f"UPDATE document SET {', '.join(updates)} WHERE id = %s"
        params.append(doc_id)
        cursor.execute(query, params)
        conn.commit()
    except Exception as e:
        print(f"[Parser-ERROR] 更新文档 {doc_id} 进度失败: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()



def perform_parse(doc_id, doc_info, file_info, embedding_config):
    """
    执行文档解析的核心逻辑

    Args:
        doc_id (str): 文档ID.
        doc_info (dict): 包含文档信息的字典 (name, location, type, kb_id, parser_config, created_by).
        file_info (dict): 包含文件信息的字典 (parent_id/bucket_name).

    Returns:
        dict: 包含解析结果的字典 (success, chunk_count).
    """
    temp_pdf_path = None
    temp_image_dir = None
    start_time = time.time()

    
      # 默认值处理
    embedding_model_name = embedding_config.get("llm_name") if embedding_config and embedding_config.get("llm_name") else "bge-m3" # 默认模型
    # 对模型名称进行处理
    if embedding_model_name and '___' in embedding_model_name:
        embedding_model_name = embedding_model_name.split('___')[0]
    embedding_api_base = embedding_config.get("api_base") if embedding_config and embedding_config.get("api_base") else "http://localhost:8000" # 默认基础 URL
    embedding_api_key = embedding_config.get("api_key") if embedding_config else None # 可能为 None 或空字符串
    
    # 构建完整的 Embedding API URL
    embedding_url = None # 默认为 None
    if embedding_api_base:
        # 确保 embedding_api_base 包含协议头 (http:// 或 https://)
        if not embedding_api_base.startswith(('http://', 'https://')):
            embedding_api_base = 'http://' + embedding_api_base

        # --- URL 拼接优化 (处理 /v1) ---
        endpoint_segment = "embeddings"
        full_endpoint_path = "v1/embeddings"
        # 移除末尾斜杠以方便判断
        normalized_base_url = embedding_api_base.rstrip('/')

        if normalized_base_url.endswith('/v1'):
            # 如果 base_url 已经是 http://host/v1 形式
            embedding_url = normalized_base_url + '/' + endpoint_segment
        else:
            # 如果 base_url 是 http://host 或 http://host/api 等其他形式
            embedding_url = normalized_base_url + '/' + full_endpoint_path

    print(f"[Parser-INFO] 使用 Embedding 配置: URL='{embedding_url}', Model='{embedding_model_name}', Key={embedding_api_key}")
    
    try:
        kb_id = doc_info['kb_id']
        file_location = doc_info['location']
        # 打印 doc_info
        # 从文件路径中提取原始后缀名
        _, file_extension = os.path.splitext(file_location)
        file_type = doc_info['type'].lower()
        parser_config = json.loads(doc_info['parser_config']) if isinstance(doc_info['parser_config'], str) else doc_info['parser_config']
        bucket_name = file_info['parent_id'] # 文件存储的桶是 parent_id

        # 进度更新回调 (直接调用内部更新函数)
        def update_progress(prog=None, msg=None):
            _update_document_progress(doc_id, progress=prog, message=msg)
            print(f"[Parser-PROGRESS] Doc: {doc_id}, Progress: {prog}, Message: {msg}")


        minio_client = get_minio_client()
        # 从MinIO下载文件
        try:
            if minio_client.bucket_exists(bucket_name):
                print(f"[Parser-INFO] 从 MinIO 下载文件: {file_location}")
                response = minio_client.get_object(bucket_name, file_location)
                file_content = response.read()
                response.close()
        except Exception as e:
            print(f"[Parser-WARNING] MinIO 下载异常: {e}，尝试从 RAGFlow API获取文件")
            from .utils import get_doc_content     
            file_content = get_doc_content(kb_id, doc_id)

        if not file_content:
           raise ValueError(f"[Parser-ERROR] 无法获取文件内容: {file_location}")
        
        temp_dir = tempfile.gettempdir()
        temp_file_path = os.path.join(temp_dir, f"{doc_id}{file_extension}")
        print(f"[Parser-INFO] 临时文件路径: {temp_file_path}")
        with open(temp_file_path, 'wb') as f:
            f.write(file_content)

        # 初始化进度
        update_progress(0.2, "OCR开始")

        # 执行 OCR 进行文档解析
        from .mineru_parse.process_pdf import process_pdf_entry
        chunk_count = process_pdf_entry(doc_id, temp_file_path,kb_id, update_progress)

        return {"success": True, "chunk_count": chunk_count}
            
    except Exception as e:
        process_duration = time.time() - start_time
        # error_message = f"解析失败: {str(e)}"
        print(f"[Parser-ERROR] 文档 {doc_id} 解析失败: {e}")
        error_message = f"解析失败: {e}"
        traceback.print_exc() # 打印详细错误堆栈
        # 更新文档状态为失败
        _update_document_progress(doc_id, status='1', run='0', message=error_message, process_duration=process_duration) # status=1表示完成，run=0表示失败
        # 不抛出异常，让调用者知道任务已结束（但失败）
        return {"success": False, "error": error_message}

    finally:
        # 清理临时文件 - 根据环境变量控制
        cleanup_enabled = os.getenv('CLEANUP_TEMP_FILES', 'true').lower() in ('true', '1', 'yes', 'on')
        
        if cleanup_enabled:
            try:
                if temp_pdf_path and os.path.exists(temp_pdf_path):
                    os.remove(temp_pdf_path)
                    print(f"[Parser-INFO] 已清理临时PDF文件: {temp_pdf_path}")
                if temp_image_dir and os.path.exists(temp_image_dir):
                    shutil.rmtree(temp_image_dir, ignore_errors=True)
                    print(f"[Parser-INFO] 已清理临时图片目录: {temp_image_dir}")
            except Exception as clean_e:
                print(f"[Parser-WARNING] 清理临时文件失败: {clean_e}")
        else:
            print(f"[Parser-INFO] 环境变量 CLEANUP_TEMP_FILES 设置为 false，保留临时文件")
            if temp_pdf_path:
                print(f"[Parser-INFO] 保留临时PDF文件: {temp_pdf_path}")
            if temp_image_dir:
                print(f"[Parser-INFO] 保留临时图片目录: {temp_image_dir}")
