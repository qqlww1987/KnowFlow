from ragflow_sdk import RAGFlow
import os
import uuid
import base64
from datetime import datetime
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
        # 详细错误信息，用于调试
        raise Exception(f"无法获取或生成tenant {tenant_id} 的API key，请检查数据库连接和权限")
    
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

def _get_tenant_by_api_key(api_token):
    """根据API token获取tenant_id"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT tenant_id FROM api_token WHERE token = %s", (api_token,))
        result = cursor.fetchone()
        
        if result:
            tenant_id = result[0]
            print(f"[DEBUG] 根据API token获取到tenant_id: {tenant_id}")
            return tenant_id
        else:
            print(f"[DEBUG] API token在数据库中未找到: {api_token[:20]}...")
            return None
            
    except Exception as e:
        print(f"[ERROR] 根据API token查询tenant_id失败: {e}")
        return None
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def _get_tenant_api_key(tenant_id):
    """根据tenant_id获取API key，如果不存在则自动生成"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 首先尝试查询该tenant的API key
        cursor.execute("SELECT token FROM api_token WHERE tenant_id = %s LIMIT 1", (tenant_id,))
        result = cursor.fetchone()
        
        if result:
            api_key = result[0]
            print(f"[DEBUG] 获取到tenant {tenant_id} 的API key: {api_key[:10]}...")
            return api_key
        else:
            print(f"[WARN] 未找到tenant {tenant_id} 的API key，尝试自动生成...")
            # 关闭当前连接，因为_generate_api_token会创建新连接
            cursor.close()
            conn.close()
            
            # 自动生成API token
            api_key = _generate_api_token(tenant_id)
            if api_key:
                print(f"[INFO] 成功为tenant {tenant_id} 生成API key")
                return api_key
            else:
                print(f"[ERROR] 为tenant {tenant_id} 生成API key失败")
                return None
            
    except Exception as e:
        print(f"[ERROR] 获取tenant API key失败: {e}")
        return None
    finally:
        # 只有在连接仍然打开时才关闭
        try:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
        except:
            pass

def _generate_api_token(tenant_id):
    """为tenant生成API token"""
    print(f"[DEBUG] 开始为tenant {tenant_id} 生成API token...")
    
    # 生成与RAGFlow相同格式的token
    token_uuid = str(uuid.uuid4()).replace('-', '')
    base64_encoded = base64.b64encode(token_uuid.encode('utf-8')).decode('utf-8')
    api_token = f"ragflow-{base64_encoded[:32]}"
    
    print(f"[DEBUG] 生成的token: {api_token[:20]}...")
    
    try:
        conn = get_db_connection()
        print(f"[DEBUG] 数据库连接成功")
        cursor = conn.cursor()
        
        # 插入新的API token
        insert_query = """
        INSERT INTO api_token (tenant_id, token, create_time, create_date, source) 
        VALUES (%s, %s, %s, %s, %s)
        """
        current_time = datetime.now()
        values = (
            tenant_id, 
            api_token, 
            current_time.timestamp(), 
            current_time.strftime('%Y-%m-%d'), 
            'knowflow_auto'  # 限制在16字符以内
        )
        
        print(f"[DEBUG] 执行SQL插入: {insert_query}")
        print(f"[DEBUG] 参数: {values}")
        
        cursor.execute(insert_query, values)
        conn.commit()
        
        print(f"[INFO] 为tenant {tenant_id} 自动生成API key: {api_token[:20]}...")
        return api_token
        
    except Exception as e:
        print(f"[ERROR] 生成API token失败: {e}")
        print(f"[ERROR] 异常类型: {type(e)}")
        import traceback
        print(f"[ERROR] 完整异常信息: {traceback.format_exc()}")
        return None
    finally:
        try:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
            print(f"[DEBUG] 数据库连接已关闭")
        except Exception as e:
            print(f"[DEBUG] 关闭数据库连接时出错: {e}")

def _validate_base_url():
    """验证并获取base_url"""
    load_dotenv()
    base_url = os.getenv('RAGFLOW_BASE_URL')
    if not base_url:
        raise ValueError("错误：请在.env文件中设置RAGFLOW_BASE_URL或使用--server_ip参数指定。")
    return base_url
  