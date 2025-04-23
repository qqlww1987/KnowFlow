from ragflow_sdk import RAGFlow
import os
import time
import shutil


def _create_dataset(rag_object):
    """创建知识库
    
    Args:
        rag_object: RAGFlow客户端实例
        dataset_name: 知识库名称
    
    Returns:
        dataset: 创建的知识库对象
    """
    try:
        datasets = rag_object.list_datasets(name="图文知识库")
        if datasets and len(datasets) > 0:
            print("[INFO] 已存在知识库 '图文知识库'，直接复用。")
            return datasets[0]
    except Exception as e:
        print(f"[WARN] 查询知识库异常，尝试新建: {e}")

    return rag_object.create_dataset(
        name="图文知识库",
        description="包含图片的PDF增强文档",
        embedding_model="BAAI/bge-m3",
        chunk_method="naive"
    )

def _create_chat(rag_object, dataset):
    """创建聊天助手

    Args:
        rag_object: RAGFlow客户端实例
        assistant_name: 助手名称
        dataset: 知识库对象

    Returns:
        assistant: 创建的助手对象
    """
    try:
        chats = rag_object.list_chats(name="图文聊天助手")
        if chats and len(chats) > 0:
            print("[INFO] 已存在助手 '图文聊天助手'，直接复用。")
            return chats[0]
    except Exception as e:
        print(f"[WARN] 查询助手异常，尝试新建: {e}")
    
    assistant = rag_object.create_chat(
        name='图文聊天助手',
        dataset_ids=[dataset.id],
    )

    prompt_template = """
        请参考{knowledge}内容回答用户问题。
        如果知识库内容包含图片，请在回答中包含图片URL。
        注意这个 html 格式的 URL 是来自知识库本身，URL 不能做任何改动。
        示例如下：<img src="http://172.21.4.35:8000/images/filename.png" alt="图片" width="300">。
        请确保回答简洁、专业，将图片自然地融入回答内容中。
        """
        
    return assistant.update({
        "prompt": {
            "prompt": prompt_template,
            "show_quote": True,
            "top_n": 8
        }
    })



def _wait_for_parsing(dataset, doc_ids, max_wait_time=300):
    """等待文档解析完成
    
    Args:
        dataset: 知识库对象
        doc_ids: 文档ID列表
        max_wait_time: 最大等待时间（秒）
    
    Returns:
        bool: 是否全部解析完成
    """
    all_done = False
    start_time = time.time()
    
    while not all_done and (time.time() - start_time) < max_wait_time:
        all_done = True
        for doc_id in doc_ids:
            docs = dataset.list_documents(id=doc_id)
            if docs and docs[0].run != "DONE":
                all_done = False
                break
        
        if not all_done:
            print("文档仍在解析中，等待10秒...")
            time.sleep(10)
    
    return all_done

def create_ragflow_resources(md_file_path, pdf_filename, image_dir, api_key, base_url):
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
        rag_object = RAGFlow(api_key=api_key, base_url=base_url)
        
        # 创建知识库
        print(f"第2步：创建RAGFlow知识库")
        dataset = _create_dataset(rag_object)

        # 处理和上传文档
        print(f"第3步：处理文档内容...")
        with open(pdf_filename, "rb") as f:
            pdf_blob = f.read()
        doc_name = os.path.basename(pdf_filename)
        dataset.upload_documents([{
            "display_name": doc_name,
            "blob": pdf_blob
        }])

        # 上传图片到MinIO
        print(f"第4步：上传图片到MinIO...")
        from minio_server import upload_directory_to_minio
        upload_directory_to_minio(dataset.id, image_dir)

        # 解析文档
        print(f"第5步：开始解析文档...")
        from mineru_test import update_markdown_image_urls
        enhanced_text = update_markdown_image_urls(md_file_path, dataset.id)
        from utils import split_markdown_to_chunks,get_bbox_for_chunk,update_document_progress
        chunks = split_markdown_to_chunks(enhanced_text, chunk_token_num=128)
        docs = dataset.list_documents()
        doc = docs[0]
        for chunk in chunks:
            if chunk and chunk.strip(): 
                doc.add_chunk(content=chunk)              

        print(f"遍历每个文档，打印其 chunk ...")
        from database import get_es_client
        es_client = get_es_client()
        
        print(f"文档: id: {doc.id})")
        chunk_count = 0 
        tenant_id = doc.created_by
        index_name = f"ragflow_{tenant_id}"
        # 添加坐标信息
        for chunk in doc.list_chunks(keywords=None, page=1, page_size=10000):
            position_int_temp = get_bbox_for_chunk(md_file_path, chunk.content)
            if position_int_temp is not None:
                doc_fields = {}
                try:
                    add_positions(doc_fields, position_int_temp)
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
        
        # 创建助手
        print(f"第6步：创建聊天助手...")
        assistant = _create_chat(rag_object, dataset)

        return dataset, assistant
        
    except Exception as e:
        print(f"创建RAGFlow资源时出错: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


def add_positions(d, poss):
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