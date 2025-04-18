from ragflow_sdk import RAGFlow
from ragflow_sdk.modules.chat import Chat
import os
import time
import sys

def _create_dataset(rag_object, dataset_name):
    """创建知识库
    
    Args:
        rag_object: RAGFlow客户端实例
        dataset_name: 知识库名称
    
    Returns:
        dataset: 创建的知识库对象
    """
    return rag_object.create_dataset(
        name=dataset_name,
        description="包含图片的PDF增强文档",
        embedding_model="BAAI/bge-m3",
        chunk_method="naive"
    )

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
        dataset_name = f"{os.path.splitext(os.path.basename(pdf_filename))[0][:4]}_知识库"
        dataset = _create_dataset(rag_object, dataset_name)

        # 处理和上传文档
        print(f"第3步：处理文档内容...")
        from mineru_test import update_markdown_image_urls
        enhanced_text = update_markdown_image_urls(md_file_path, dataset.id)
        
        doc_name = os.path.splitext(os.path.basename(pdf_filename))[0] + ".md"
        dataset.upload_documents([{
            "display_name": doc_name,
            "blob": enhanced_text.encode('utf-8')
        }])

        # 上传图片到MinIO
        print(f"第4步：上传图片到MinIO...")
        from minio_server import upload_directory_to_minio
        upload_directory_to_minio(dataset.id, image_dir)
        
        # 解析文档
        print(f"第5步：开始解析文档...")
        docs = dataset.list_documents()
        doc_ids = [doc.id for doc in docs]
        dataset.async_parse_documents(doc_ids)
        
        # 等待解析完成
        if _wait_for_parsing(dataset, doc_ids):
            print("文档解析完成！")
        else:
            print("文档解析超时，部分文档可能仍在处理中")
        
        # 创建助手
        print(f"第6步：创建聊天助手...")
        assistant_name = f"{os.path.splitext(os.path.basename(pdf_filename))[0][:4]}_助手"
        assistant = rag_object.create_chat(
            name=assistant_name,
            dataset_ids=[dataset.id]
        )
        
        # 设置助手提示词
        prompt_template = """
        请参考{knowledge}内容回答用户问题。
        如果知识库内容包含图片，请在回答中包含图片URL。
        注意这个 html 格式的 URL 是来自知识库本身，URL 不能做任何改动。
        示例如下：<img src="http://172.21.4.35:8000/images/filename.png" alt="图片" width="300">。
        请确保回答简洁、专业，将图片自然地融入回答内容中。
        """
        
        assistant.update({
            "prompt": {
                "prompt": prompt_template,
                "show_quote": True,
                "top_n": 8
            }
        })
        
        return dataset, assistant
        
    except Exception as e:
        print(f"创建RAGFlow资源时出错: {str(e)}")
        import traceback
        traceback.print_exc()
        raise
