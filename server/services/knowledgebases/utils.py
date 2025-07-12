from ragflow_sdk import RAGFlow
import os
from dotenv import load_dotenv
from database import get_db_connection

def get_doc_content(dataset_id, doc_id):
    # 首先获取知识库的tenant_id
    tenant_id = _get_kb_tenant_id(dataset_id)
    if not tenant_id:
        raise Exception(f"无法获取知识库 {dataset_id} 的tenant_id")
    
    # 根据tenant_id获取对应的API key
    api_key = _get_tenant_api_key(tenant_id)
    if not api_key:
        raise Exception(f"无法获取tenant {tenant_id} 的API key")
    
    base_url = _validate_base_url()
    rag_object = RAGFlow(api_key=api_key, base_url=base_url)
    datasets = rag_object.list_datasets(id=dataset_id)
    if not datasets:
        raise Exception(f"未找到指定 dataset_id: {dataset_id}")
    dataset = datasets[0]
    docs = dataset.list_documents(id=doc_id)
    if not docs:
        raise Exception(f"未找到指定 doc_id: {doc_id}")
    doc = docs[0]
    return doc.download()

def _get_kb_tenant_id(kb_id):
    """根据知识库ID获取tenant_id"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT tenant_id FROM knowledgebase WHERE id = %s", (kb_id,))
        result = cursor.fetchone()
        
        if result:
            tenant_id = result[0]
            print(f"[DEBUG] 知识库 {kb_id} 的 tenant_id: {tenant_id}")
            return tenant_id
        else:
            print(f"[ERROR] 未找到知识库 {kb_id} 的tenant_id")
            return None
            
    except Exception as e:
        print(f"[ERROR] 获取知识库tenant_id失败: {e}")
        return None
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def _get_tenant_api_key(tenant_id):
    """根据tenant_id获取API key"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 查询该tenant的任意一个API key
        cursor.execute("SELECT token FROM api_token WHERE tenant_id = %s LIMIT 1", (tenant_id,))
        result = cursor.fetchone()
        
        if result:
            api_key = result[0]
            print(f"[DEBUG] 获取到tenant {tenant_id} 的API key: {api_key[:10]}...")
            return api_key
        else:
            print(f"[ERROR] 未找到tenant {tenant_id} 的API key")
            return None
            
    except Exception as e:
        print(f"[ERROR] 获取tenant API key失败: {e}")
        return None
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def _validate_base_url():
    """验证并获取base_url"""
    load_dotenv()
    base_url = os.getenv('RAGFLOW_BASE_URL')
    if not base_url:
        raise ValueError("错误：请在.env文件中设置RAGFLOW_BASE_URL或使用--server_ip参数指定。")
    return base_url
  