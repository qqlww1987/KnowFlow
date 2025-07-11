from ragflow_sdk import RAGFlow
import os
import time
import shutil
import json
from dotenv import load_dotenv
from .minio_server import upload_directory_to_minio
from .mineru_test import update_markdown_image_urls
from .utils import split_markdown_to_chunks_configured, get_bbox_for_chunk, update_document_progress, should_cleanup_temp_files
from database import get_es_client, get_db_connection
import concurrent.futures
import threading
from datetime import datetime

# 性能优化配置参数
CHUNK_PROCESSING_CONFIG = {
    'max_concurrent_workers': 8,           # 最大并发线程数
    'es_bulk_batch_size': 100,           # ES批量操作批次大小
    'enable_concurrent_chunk_add': True,   # 是否启用并发添加chunks
    'chunk_add_timeout': 30,              # 单个chunk添加超时时间（秒）
    'es_bulk_timeout': 60,                # ES批量操作超时时间（秒）
    'enable_performance_stats': True,     # 是否启用性能统计
}

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

def get_ragflow_doc(doc_id, kb_id):
    """获取RAGFlow文档对象和dataset对象"""
    api_key, base_url = _validate_environment()
    rag_object = RAGFlow(api_key=api_key, base_url=base_url)
    datasets = rag_object.list_datasets(id=kb_id)
    if not datasets:
        raise Exception(f"未找到知识库 {kb_id}")
    dataset = datasets[0]
    docs = dataset.list_documents(id=doc_id)
    if not docs:
        raise Exception(f"未找到文档 {doc_id}")
    return docs[0], dataset  # 返回doc和dataset元组

def _get_document_chunking_config(doc_id):
    """从数据库获取文档的分块配置"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT parser_config FROM document WHERE id = %s", (doc_id,))
        result = cursor.fetchone()
        
        if result and result[0]:
            parser_config = json.loads(result[0])
            chunking_config = parser_config.get('chunking_config')
            if chunking_config:
                print(f"🔧 [DEBUG] 从数据库获取到分块配置: {chunking_config}")
                return chunking_config
        
        print(f"📄 [DEBUG] 文档 {doc_id} 没有自定义分块配置，使用默认配置")
        return None
        
    except Exception as e:
        print(f"⚠️ [WARNING] 获取文档分块配置失败: {e}")
        return None
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def _log_performance_stats(operation_name, start_time, end_time, item_count, additional_info=None):
    """记录性能统计信息"""
    if not CHUNK_PROCESSING_CONFIG.get('enable_performance_stats', True):
        return
        
    duration = end_time - start_time
    throughput = item_count / duration if duration > 0 else 0
    
    stats_msg = f"[性能统计] {operation_name}: "
    stats_msg += f"耗时 {duration:.2f}s, "
    stats_msg += f"处理 {item_count} 项, "
    stats_msg += f"吞吐量 {throughput:.2f} 项/秒"
    
    if additional_info:
        stats_msg += f", {additional_info}"
    
    print(stats_msg)
    
    # 如果耗时过长，记录警告
    if duration > 60:  # 超过1分钟
        print(f"[性能警告] {operation_name} 处理时间过长: {duration:.2f}s")

def add_chunks_to_doc(doc, chunks, update_progress, config=None):
    """
    优化版 add_chunks_to_doc - 直接调用批量接口
    """
    start_time = time.time()
    
    # 合并配置参数
    effective_config = CHUNK_PROCESSING_CONFIG.copy()
    if config:
        effective_config.update(config)
    
    print(f"🚀 批量添加: 总共接收到 {len(chunks)} 个 chunks 准备批量添加")
    
    if not chunks:
        print("⚠️ 没有chunks需要添加")
        update_progress(0.95, "没有chunks需要添加")
        return 0
    
    # 初始进度更新
    update_progress(0.8, "开始批量添加chunks到文档...")
    
    try:
        # 准备批量数据
        batch_chunks = []
        for i, chunk in enumerate(chunks):
            if chunk and chunk.strip():
                batch_chunks.append({
                    "content": chunk.strip(),
                    "important_keywords": [],  # 可以根据需要添加关键词提取
                    "questions": []  # 可以根据需要添加问题生成
                })
        
        if not batch_chunks:
            print("⚠️ 过滤后没有有效的chunks")
            update_progress(0.95, "没有有效的chunks")
            return 0
        
        print(f"📦 准备批量添加 {len(batch_chunks)} 个有效chunks")
        
        # 配置批量大小 - 根据chunk数量动态调整
        if len(batch_chunks) <= 10:
            batch_size = 5
        elif len(batch_chunks) <= 50:
            batch_size = 10
        else:
            batch_size = 20
        
        # 分批处理，避免单次请求过大
        total_added = 0
        total_failed = 0
        batch_count = (len(batch_chunks) + batch_size - 1) // batch_size
        
        for batch_idx in range(0, len(batch_chunks), batch_size):
            batch_end = min(batch_idx + batch_size, len(batch_chunks))
            current_batch = batch_chunks[batch_idx:batch_end]
            
            current_batch_num = batch_idx // batch_size + 1
            print(f"🔄 处理批次 {current_batch_num}/{batch_count} ({len(current_batch)} chunks)")
            
            try:
                # 直接调用批量接口
                response = doc.rag.post(
                    f'/datasets/{doc.dataset_id}/documents/{doc.id}/chunks/batch',
                    {
                        "chunks": current_batch,
                        "batch_size": min(batch_size, len(current_batch))
                    }
                )
                
                result = response.json()
                
                if result.get("code") == 0:
                    # 批量添加成功
                    data = result.get("data", {})
                    added = data.get("total_added", 0)
                    failed = data.get("total_failed", 0)
                    
                    total_added += added
                    total_failed += failed
                    
                    # 更新进度
                    progress = 0.8 + (batch_end / len(batch_chunks)) * 0.15  # 0.8-0.95范围
                    update_progress(progress, f"批量添加进度: {batch_end}/{len(batch_chunks)} chunks")
                    
                    print(f"✅ 批次 {current_batch_num} 成功: +{added} chunks (失败: {failed})")
                    
                    # 显示处理统计
                    stats = data.get("processing_stats", {})
                    if stats:
                        print(f"   📊 分片处理: {stats.get('batches_processed', 0)} 个分片")
                        print(f"   ⏱️  处理时间: {stats.get('processing_time', 0):.2f}s")
                
                else:
                    # 批量添加失败
                    error_msg = result.get("message", "Unknown error")
                    print(f"❌ 批次 {current_batch_num} 失败: {error_msg}")
                    total_failed += len(current_batch)
                    
                    # 更新进度
                    progress = 0.8 + (batch_end / len(batch_chunks)) * 0.15
                    update_progress(progress, f"批量添加进度: {batch_end}/{len(batch_chunks)} chunks (部分失败)")
                
            except Exception as e:
                print(f"❌ 批次 {current_batch_num} 网络请求异常: {e}")
                total_failed += len(current_batch)
                
                # 更新进度
                progress = 0.8 + (batch_end / len(batch_chunks)) * 0.15
                update_progress(progress, f"批量添加进度: {batch_end}/{len(batch_chunks)} chunks (网络异常)")
        
        # 最终统计
        success_rate = (total_added / len(batch_chunks) * 100) if len(batch_chunks) > 0 else 0
        
        print(f"📊 批量添加完成:")
        print(f"   ✅ 成功: {total_added}/{len(batch_chunks)} chunks")
        print(f"   ❌ 失败: {total_failed} chunks") 
        print(f"   📈 成功率: {success_rate:.1f}%")
        
        # 最终进度更新
        if total_failed == 0:
            update_progress(0.95, f"批量添加完成: 成功 {total_added}/{len(batch_chunks)} chunks")
        else:
            update_progress(0.95, f"批量添加完成: 成功 {total_added}, 失败 {total_failed} chunks")
        
        # 记录性能统计
        end_time = time.time()
        processing_time = end_time - start_time
        additional_info = f"批量模式, 批次数: {batch_count}, 成功率: {success_rate:.1f}%, 性能提升: ~{len(batch_chunks)}x"
        _log_performance_stats("批量添加Chunks", start_time, end_time, len(batch_chunks), additional_info)
        
        return total_added
        
    except Exception as e:
        print(f"❌ 批量添加过程中出现异常: {e}")
        update_progress(0.95, f"批量添加异常: {str(e)}")
        
        # 记录异常统计
        end_time = time.time()
        _log_performance_stats("批量添加Chunks(异常)", start_time, end_time, len(chunks), f"异常: {str(e)}")
        
        return 0

def _update_chunks_position(doc, md_file_path, chunk_content_to_index, dataset, config=None, update_progress=None):
    start_time = time.time()
    
    # 合并配置参数
    effective_config = CHUNK_PROCESSING_CONFIG.copy()
    if config:
        effective_config.update(config)
        
    es_client = get_es_client()
    print(f"文档: id: {doc.id})")
    chunk_count = 0
    
    # 🔧 直接使用传入的dataset对象获取tenant_id，避免重复API调用
    tenant_id = dataset.tenant_id
    print(f"[DEBUG] 🔧 使用复用的dataset对象获取tenant_id:")
    print(f"  - doc.dataset_id: {doc.dataset_id}")
    print(f"  - doc.created_by: {doc.created_by}")
    print(f"  - dataset.tenant_id: {tenant_id}")
    
    index_name = f"ragflow_{tenant_id}"
    print(f"  - ✅ 正确的ES索引名: {index_name}")
    
    # 收集所有批量更新操作
    bulk_operations = []
    batch_size = effective_config['es_bulk_batch_size']
    processed_count = 0
    batch_count = 0
    
    try:
        # 获取总chunk数量用于进度计算
        all_chunks = list(doc.list_chunks(keywords=None, page=1, page_size=10000))
        total_chunks = len(all_chunks)
        print(f"准备更新 {total_chunks} 个chunks的位置信息...")
        
        if update_progress:
            update_progress(0.96, "开始更新chunk位置信息...")
        
        position_fetch_time = 0
        
        for chunk in all_chunks:
            try:
                original_index = chunk_content_to_index.get(chunk.content)
                if original_index is None:
                    print(f"警告: 无法为块 id={chunk.id} 的内容找到原始索引，将跳过此块。")
                    processed_count += 1
                    continue
                
                # 构建更新操作 - 使用正确的ES bulk格式
                doc_update = {
                    "top_int": original_index
                }
                
                # 尝试获取位置信息，如果成功则添加到更新中
                position_start = time.time()
                try:
                    position_int_temp = get_bbox_for_chunk(md_file_path, chunk.content)
                    if position_int_temp is not None:
                        doc_fields = {}
                        _add_positions(doc_fields, position_int_temp)
                        doc_update["position_int"] = doc_fields.get("position_int")
                except Exception as e:
                    print(f"获取chunk位置异常: {e}")
                position_fetch_time += time.time() - position_start
                
                # ES bulk格式：action行 + document行
                bulk_operations.extend([
                    {"update": {"_index": index_name, "_id": chunk.id}},
                    {"doc": doc_update}
                ])
                chunk_count += 1
                processed_count += 1
                
                # 分批处理，避免单次请求过大
                if len(bulk_operations) >= batch_size:
                    try:
                        batch_start = time.time()
                        _execute_bulk_update(es_client, bulk_operations, effective_config)
                        batch_duration = time.time() - batch_start
                        batch_count += 1
                        
                        print(f"[批次 {batch_count}] 更新 {len(bulk_operations)} 个chunks, 耗时 {batch_duration:.2f}s")
                        bulk_operations = []
                        
                        # 更新进度
                        if update_progress:
                            progress = 0.96 + (processed_count / total_chunks) * 0.03  # 0.96-0.99范围
                            update_progress(progress, f"更新位置进度: {processed_count}/{total_chunks}")
                    except Exception as batch_e:
                        print(f"[异常处理] 批次更新失败: {batch_e}")
                        # 批次失败时，清空当前批次继续处理
                        bulk_operations = []
                        
            except Exception as chunk_e:
                print(f"[异常处理] 处理chunk {chunk.id} 失败: {chunk_e}")
                processed_count += 1
                continue
        
        # 处理剩余的操作
        if bulk_operations:
            try:
                batch_start = time.time()
                _execute_bulk_update(es_client, bulk_operations, effective_config)
                batch_duration = time.time() - batch_start
                batch_count += 1
                print(f"[最终批次 {batch_count}] 更新 {len(bulk_operations)} 个chunks, 耗时 {batch_duration:.2f}s")
            except Exception as final_batch_e:
                print(f"[异常处理] 最终批次更新失败: {final_batch_e}")
        
    except Exception as overall_e:
        print(f"[异常处理] 位置更新整体处理出现异常: {overall_e}")
        
    finally:
        # 确保进度更新到0.99，无论是否发生异常
        if update_progress:
            update_progress(0.99, f"位置更新完成: {chunk_count} 个chunks")
        
        end_time = time.time()
        
        # 记录性能统计
        additional_info = f"批次数: {batch_count}, 批次大小: {batch_size}, 位置获取耗时: {position_fetch_time:.2f}s"
        _log_performance_stats("更新Chunk位置", start_time, end_time, chunk_count, additional_info)
        
        print(f"位置更新完成: {chunk_count} 个chunks")
    
    return chunk_count

def _execute_bulk_update(es_client, bulk_operations, config):
    """执行ES批量更新的辅助函数"""
    if not bulk_operations:
        return
        
    operation_start = time.time()
    
    try:
        print(f"开始批量更新 {len(bulk_operations)} 个chunks...")
        response = es_client.bulk(
            body=bulk_operations, 
            refresh=True,
            timeout=f"{config['es_bulk_timeout']}s"
        )
        
        operation_duration = time.time() - operation_start
        
        # 检查批量操作结果
        if response.get('errors'):
            failed_count = 0
            for item in response.get('items', []):
                if 'update' in item and item['update'].get('status') >= 400:
                    print(f"ES批量更新失败 - ID: {item['update'].get('_id')}, Error: {item['update'].get('error')}")
                    failed_count += 1
            
            if failed_count > 0:
                print(f"批量更新完成，但有 {failed_count} 个操作失败, 耗时 {operation_duration:.2f}s")
            else:
                print(f"批量更新成功完成 {len(bulk_operations) // 2} 个chunks, 耗时 {operation_duration:.2f}s")
        else:
            throughput = (len(bulk_operations) // 2) / operation_duration if operation_duration > 0 else 0
            print(f"批量更新成功完成 {len(bulk_operations) // 2} 个chunks, 耗时 {operation_duration:.2f}s, 吞吐量 {throughput:.1f} chunks/秒")
            
    except Exception as es_e:
        operation_duration = time.time() - operation_start
        print(f"ES批量更新异常: {es_e}, 耗时 {operation_duration:.2f}s")
        # 如果批量更新失败，回退到单个更新模式
        print("回退到单个更新模式...")
        fallback_start = time.time()
        success_count = 0
        
        # 处理新的两行格式：每两个元素构成一个操作
        for i in range(0, len(bulk_operations), 2):
            if i + 1 < len(bulk_operations):
                try:
                    action = bulk_operations[i]
                    doc_data = bulk_operations[i + 1]
                    
                    if "update" in action:
                        es_client.update(
                            index=action["update"]["_index"], 
                            id=action["update"]["_id"], 
                            body=doc_data, 
                            refresh=True
                        )
                        success_count += 1
                except Exception as single_e:
                    print(f"单个更新也失败 - ID: {action.get('update', {}).get('_id', 'unknown')}, Error: {single_e}")
        
        fallback_duration = time.time() - fallback_start
        expected_operations = len(bulk_operations) // 2
        print(f"回退模式完成: 成功 {success_count}/{expected_operations} 个chunks, 耗时 {fallback_duration:.2f}s")

def _cleanup_temp_files(md_file_path):
    """清理临时文件"""
    if not should_cleanup_temp_files():
        print(f"[INFO] 配置为保留临时文件，路径: {os.path.dirname(os.path.abspath(md_file_path))}")
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
        doc, dataset = get_ragflow_doc(doc_id, kb_id)

        _upload_images(kb_id, image_dir, update_progress)

        # 获取文档的分块配置
        chunking_config = _get_document_chunking_config(doc_id)
        
        enhanced_text = update_markdown_image_urls(md_file_path, kb_id)
        
        # 传递分块配置给分块函数
        if chunking_config:
            chunks = split_markdown_to_chunks_configured(
                enhanced_text, 
                chunk_token_num=chunking_config.get('chunk_token_num', 256),
                min_chunk_tokens=chunking_config.get('min_chunk_tokens', 10),
                chunking_config=chunking_config
            )
        else:
            chunks = split_markdown_to_chunks_configured(enhanced_text, chunk_token_num=256)
        
        chunk_content_to_index = {chunk: i for i, chunk in enumerate(chunks)}

        add_chunks_to_doc(doc, chunks, update_progress)
        chunk_count = _update_chunks_position(doc, md_file_path, chunk_content_to_index, dataset, update_progress=update_progress)
        # 根据环境变量决定是否清理临时文件
        _cleanup_temp_files(md_file_path)

        # 确保进度更新到100%
        update_progress(1.0, f"处理完成！成功处理 {chunk_count} 个chunks")
        print(f"✅ 所有处理步骤完成，共处理 {chunk_count} 个chunks")

        return chunk_count

    except Exception as e:
        print(f"create_ragflow_resources 处理出错: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # 即使发生异常，也要确保进度更新到100%，避免前端界面卡住
        try:
            update_progress(1.0, f"处理过程中发生异常: {str(e)}")
            print(f"❌ 处理过程中发生异常，但进度已更新完成")
        except Exception as progress_e:
            print(f"[异常处理] 更新进度时也发生异常: {progress_e}")
        
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