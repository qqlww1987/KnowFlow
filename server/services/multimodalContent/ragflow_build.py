from ragflow_sdk import RAGFlow
from ragflow_sdk.modules.chat import Chat
import os
import time
import sys

def create_ragflow_resources(enhanced_text, pdf_filename, api_key, base_url="http://localhost", server_ip=None):

    """
    使用增强文本创建RAGFlow知识库和聊天助手
    
    参数:
    - enhanced_text: 包含图片URL的增强文本
    - pdf_filename: PDF文件名
    - api_key: RAGFlow API密钥
    - base_url: RAGFlow基础URL，默认为http://localhost
    - server_ip: 图片服务器IP地址（必须提供）
    """
    print(f"创建RAGFlow资源，使用文本长度: {len(enhanced_text)} 字符")
    
    # 检查是否提供了server_ip
    if server_ip is None:
        raise ValueError("必须提供图片服务器IP地址(server_ip)。请在.env文件中设置RAGFLOW_SERVER_IP或通过--server_ip参数指定。")
    
    print(f"使用图片服务器IP: {server_ip}")
    
    try:
        # 初始化RAGFlow客户端
        rag_object = RAGFlow(api_key=api_key, base_url=base_url)
        
        # 创建数据集名称
        dataset_name = f"{os.path.splitext(os.path.basename(pdf_filename))[0]}_知识库"
        
        print(f"使用默认分块方法创建数据集: {dataset_name}")
        # 使用默认的naive分块方法
        dataset = rag_object.create_dataset(
            name=dataset_name,
            description="包含图片的PDF增强文档",
            embedding_model="BAAI/bge-m3",
            chunk_method="naive"  # 使用默认分块方法
        )
        
        # 准备文档显示名称和文本内容
        doc_name = os.path.basename(pdf_filename)
        if not doc_name.endswith(".txt"):
            doc_name = os.path.splitext(doc_name)[0] + ".txt"
        
        # 直接将文本内容上传（无需再处理PDF）
        print(f"上传增强文本作为纯文本文档: {doc_name}")
        encoded_text = enhanced_text.encode('utf-8')
        
        # 上传增强文档
        dataset.upload_documents([{
            "display_name": doc_name,
            "blob": encoded_text
        }])
        
        # 解析文档
        docs = dataset.list_documents()
        doc_ids = [doc.id for doc in docs]
        print(f"开始解析文档，ID: {doc_ids}")
        dataset.async_parse_documents(doc_ids)
        
        print(f"文档上传成功，正在解析...")
        
        # 等待文档解析完成
        all_done = False
        max_wait_time = 300  # 最长等待5分钟
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
        
        if all_done:
            print("文档解析完成！")
        else:
            print(f"等待超时（{max_wait_time}秒），部分文档可能仍在解析中")
        
        # 创建聊天助手
        # 助手名称
        assistant_name = f"{os.path.splitext(os.path.basename(pdf_filename))[0]}_助手"
        print(f"创建聊天助手: {assistant_name}")
        
        # 创建聊天助手，使用默认配置
        assistant = rag_object.create_chat(
            name=assistant_name,
            dataset_ids=[dataset.id]
        )
        
        # 如果需要更新助手的提示词，可以在创建后更新
        prompt_template = f"""
        请参考知识库内容回答用户问题。
        需要展示知识库中和回答最相关的一张图片URL。注意这个 html 格式的 URL 是来自知识库本身，URL 不能做任何改动。
        示例如下：<img src="http://172.21.4.35:8000/images/filename.png" alt="维修图片" width="300">。
        请确保回答简洁、专业，将图片自然地融入回答内容中。
        """
        
        # 更新助手配置
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
        # 显示更详细的错误信息
        import traceback
        traceback.print_exc()
        raise
    
# 移除旧的process_pdf_with_images函数，因为我们现在使用分离的处理流程
