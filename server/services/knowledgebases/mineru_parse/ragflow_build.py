from ragflow_sdk import RAGFlow
import os
import time
import shutil
from dotenv import load_dotenv
from .minio_server import upload_directory_to_minio
from .mineru_test import update_markdown_image_urls
from .utils import split_markdown_to_chunks,get_bbox_for_chunk,update_document_progress
from database import get_es_client


def _validate_environment():
    """验证环境变量配置"""
    load_dotenv()
    api_key = os.getenv('RAGFLOW_API_KEY')
    base_url = os.getenv('RAGFLOW_SERVER_IP')
    if not api_key:
        raise ValueError("错误：请在.env文件中设置RAGFLOW_API_KEY或使用--api_key参数指定。")
    
    if not base_url:
        raise ValueError("错误：请在.env文件中设置RAGFLOW_SERVER_IP或使用--server_ip参数指定。")
    
    return api_key, base_url


def create_ragflow_resources(doc_id, kb_id, md_file_path, image_dir,update_progress):
    """使用增强文本创建RAGFlow知识库和聊天助手
    
    Args:
        md_file_path: md文件路径
        pdf_filename: PDF文件名
        image_dir: 图片目录
        api_key: RAGFlow API密钥
        base_url: RAGFlow基础URL
    
    Returns:
        tuple: (dataset, assistant) 知识库和助手对象
    """
    
    try:
        # 初始化RAGFlow客户端
        api_key,base_url = _validate_environment()
        rag_object = RAGFlow(api_key=api_key, base_url=base_url)
        datasets = rag_object.list_datasets(id = kb_id)
        if datasets and len(datasets) > 0:
            dataset = datasets[0] 
        # 上传图片到MinIO
        print(f"第4步：上传图片到MinIO...")
    
        update_progress(0.7, "上传图片到MinIO...")
        upload_directory_to_minio(kb_id, image_dir)

        # 解析文档
        enhanced_text = update_markdown_image_urls(md_file_path,kb_id)
        chunks = split_markdown_to_chunks(enhanced_text, chunk_token_num=128)

        docs = dataset.list_documents(id = doc_id)
        doc = docs[0]

        update_progress(0.8, "添加 chunk 到文档...")
        for chunk in chunks:
            if chunk and chunk.strip(): 
                print(f"添加 chunk: {chunk}")
                try:
                    doc.add_chunk(content=chunk)
                except Exception as e:
                    print(f"添加 chunk 失败: {e}")    

      
        es_client = get_es_client()        
        print(f"文档: id: {doc.id})"
        )
        chunk_count = 0 
        tenant_id = doc.created_by
        index_name = f"ragflow_{tenant_id}"
        # 添加坐标信息
        for chunk in doc.list_chunks(keywords=None, page=1, page_size=10000):
            position_int_temp = get_bbox_for_chunk(md_file_path, chunk.content)
            if position_int_temp is not None:
                doc_fields = {}
                try:
                    _add_positions(doc_fields, position_int_temp)
                    direct_update = {
                        "doc": {
                            "page_num_int": doc_fields.get("page_num_int"),
                            "position_int": doc_fields.get("position_int"),
                            "top_int": doc_fields.get("top_int"),
                        }
                    }
                    try:
                        es_client.update(index=index_name, id=chunk.id, body=direct_update, refresh=True)
                    except Exception as es_e:
                        print(f"ES更新异常: {es_e}")
                except Exception as e:
                    print(f"处理chunk位置异常: {e}")
            print(chunk)
            print("***************")
            chunk_count += 1 
        
        # 通知 RAGFlow 文档解析完成
        update_document_progress(doc.id, progress=1.0, message="解析完成", status='1', run='3', chunk_count=chunk_count, process_duration=None)
        
        # 清空临时文件
        shutil.rmtree(os.path.dirname(os.path.abspath(md_file_path)))

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