from ragflow_sdk import RAGFlow
import os
import time
import shutil
import json
from dotenv import load_dotenv
from .minio_server import upload_directory_to_minio
from .mineru_test import update_markdown_image_urls
from .utils import split_markdown_to_chunks_configured, get_bbox_for_chunk, update_document_progress, should_cleanup_temp_files
from database import get_db_connection
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

def add_chunks_with_positions(doc, chunks, md_file_path, chunk_content_to_index, update_progress, config=None):
    """
    合并版 add_chunks_to_doc + _update_chunks_position
    直接调用 batch_add_chunk 接口，一步完成chunk添加和位置信息设置
    """
    start_time = time.time()
    
    # 合并配置参数
    effective_config = CHUNK_PROCESSING_CONFIG.copy()
    if config:
        effective_config.update(config)
    
    print(f"🚀 合并批量添加: 总共接收到 {len(chunks)} 个 chunks 准备批量添加（包含位置信息）")
    
    if not chunks:
        print("⚠️ 没有chunks需要添加")
        update_progress(0.8, "没有chunks需要添加")
        return 0
    
    # 初始进度更新
    update_progress(0.8, "开始批量添加chunks到文档（包含位置信息）...")
    
    try:
        # 准备批量数据，包含位置信息
        batch_chunks = []
        for i, chunk in enumerate(chunks):
            if chunk and chunk.strip():
                chunk_data = {
                    "content": chunk.strip(),
                    "important_keywords": [],  # 可以根据需要添加关键词提取
                    "questions": []  # 可以根据需要添加问题生成
                }
                
                # 获取位置信息
                try:
                    position_int_temp = get_bbox_for_chunk(md_file_path, chunk.strip())
                    if position_int_temp is not None:
                        # 有完整位置信息，使用positions参数
                        chunk_data["positions"] = position_int_temp
                        print(f"🔧 chunk {i}: 获取到完整位置信息: {len(position_int_temp)} 个位置")
                    else:
                        # 没有完整位置信息，使用top_int参数
                        original_index = chunk_content_to_index.get(chunk.strip())
                        if original_index is not None:
                            chunk_data["top_int"] = original_index
                            print(f"🔧 chunk {i}: 使用top_int: {original_index}")
                        else:
                            print(f"⚠️ chunk {i}: 无法获取位置信息")
                except Exception as pos_e:
                    print(f"⚠️ chunk {i}: 获取位置信息失败: {pos_e}")
                    # 即使位置信息获取失败，也继续添加chunk
                
                batch_chunks.append(chunk_data)
        
        if not batch_chunks:
            print("⚠️ 过滤后没有有效的chunks")
            update_progress(0.95, "没有有效的chunks")
            return 0
        
        print(f"📦 准备批量添加 {len(batch_chunks)} 个有效chunks（包含位置信息）")
        
        # 统计位置信息类型
        chunks_with_positions = [c for c in batch_chunks if "positions" in c]
        chunks_with_top_int = [c for c in batch_chunks if "top_int" in c]
        chunks_without_position = len(batch_chunks) - len(chunks_with_positions) - len(chunks_with_top_int)
        
        print(f"📍 位置信息统计:")
        print(f"   - 完整位置信息: {len(chunks_with_positions)} chunks")
        print(f"   - 单独top_int: {len(chunks_with_top_int)} chunks")
        print(f"   - 无位置信息: {chunks_without_position} chunks")
        
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
                        print(f"   💰 嵌入成本: {stats.get('embedding_cost', 0)}")
                    
                    # 检查返回的chunks是否包含位置信息
                    returned_chunks = data.get("chunks", [])
                    if returned_chunks:
                        chunks_with_pos = [c for c in returned_chunks if c.get('positions') or c.get('top_positions')]
                        print(f"   📍 位置信息: {len(chunks_with_pos)}/{len(returned_chunks)} chunks包含位置")
                
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
        
        print(f"📊 合并批量添加完成:")
        print(f"   ✅ 成功: {total_added}/{len(batch_chunks)} chunks")
        print(f"   ❌ 失败: {total_failed} chunks") 
        print(f"   📈 成功率: {success_rate:.1f}%")
        print(f"   📍 位置信息: {len(chunks_with_positions)} 完整位置, {len(chunks_with_top_int)} top_int")
        
        # 最终进度更新
        if total_failed == 0:
            update_progress(0.95, f"批量添加完成: 成功 {total_added}/{len(batch_chunks)} chunks（包含位置信息）")
        else:
            update_progress(0.95, f"批量添加完成: 成功 {total_added}, 失败 {total_failed} chunks")
        
        # 记录性能统计
        end_time = time.time()
        processing_time = end_time - start_time
        additional_info = f"合并模式, 批次数: {batch_count}, 成功率: {success_rate:.1f}%, 位置信息: {len(chunks_with_positions)}+{len(chunks_with_top_int)}"
        _log_performance_stats("合并批量添加Chunks", start_time, end_time, len(batch_chunks), additional_info)
        
        return total_added
        
    except Exception as e:
        print(f"❌ 合并批量添加过程中出现异常: {e}")
        update_progress(0.95, f"批量添加异常: {str(e)}")
        
        # 记录异常统计
        end_time = time.time()
        _log_performance_stats("合并批量添加Chunks(异常)", start_time, end_time, len(chunks), f"异常: {str(e)}")
        
        return 0

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

        chunk_count = add_chunks_with_positions(doc, chunks, md_file_path, chunk_content_to_index, update_progress)
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
