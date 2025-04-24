from ragflow_sdk import RAGFlow
import os
from dotenv import load_dotenv



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

def get_doc_content(dataset_id, doc_id):
    api_key, base_url = _validate_environment()
    rag_object = RAGFlow(api_key=api_key, base_url=base_url)
    datasets = rag_object.list_datasets(id=dataset_id)
    if not datasets:
        raise Exception(f"未找到指定 dataset_id: {dataset_id}")
    dataset = datasets[0]
    docs = dataset.list_documents(id=doc_id)
    if not docs:
        raise Exception(f"未找到指定 doc_id: {doc_id}")
    doc = docs[0]
    file_content = doc.download()
    print(f"下载文档成功: {file_content}")
    return file_content
  