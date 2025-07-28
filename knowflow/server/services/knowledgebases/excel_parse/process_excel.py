import time
import logging
from .excel_service import chunk_excel_for_knowledge_base
from ..mineru_parse.ragflow_build import get_ragflow_doc, add_chunks_with_positions

logger = logging.getLogger(__name__)

def process_excel_entry(doc_id, file_content, kb_id, parser_config, doc_info, update_progress):
    """
    处理Excel文件的入口函数
    
    Args:
        doc_id (str): 文档ID.
        file_content (bytes): 文件内容.
        kb_id (str): 知识库ID.
        parser_config (dict): 解析配置.
        doc_info (dict): 文档信息.
        update_progress (function): 更新进度的回调函数.

    Returns:
        int: 生成的块数量.
    """
    update_progress(0.3, "开始处理表格文件")
    logger.info(f"检测到表格文件，使用增强分块策略 for doc: {doc_id}")

    # 调用表格分块服务
    result = chunk_excel_for_knowledge_base(
        file_input=file_content,
        kb_config=parser_config,
        filename=doc_info.get('name')
    )
    
    chunks = result.get('chunks', [])
    chunk_count = 0
    
    # 使用 add_chunks_to_doc 批量保存分块
    if chunks:
        # 获取 RAGFlow 文档对象
        doc, dataset = get_ragflow_doc(doc_id, kb_id)
        
        # Excel 分块没有位置信息，md_file_path 设为 None，chunk_content_to_index 用索引映射
        chunk_content_to_index = {chunk: i for i, chunk in enumerate(chunks)}
        chunk_count = add_chunks_with_positions(doc, chunks, None, chunk_content_to_index, update_progress)
        
        # 注意: Excel 分块目前没有位置信息，所以不需要调用 _update_chunks_position

    logger.info(f"表格文件处理完成 for doc: {doc_id}, 生成 {chunk_count} 个块")
    return chunk_count 