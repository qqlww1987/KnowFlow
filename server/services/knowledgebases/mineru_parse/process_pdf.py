#!/usr/bin/env python
# -*- coding: utf-8 -*-
from .mineru_test import process_pdf_with_minerU
from .ragflow_build import create_ragflow_resources


# 聊天助手 Pmrot 模板
#   请参考{knowledge}内容回答用户问题。
# 如果知识库内容包含图片，请在回答中包含图片URL。
#   注意这个 html 格式的 URL 是来自知识库本身，URL 不能做任何改动。
#   示例如下：<img src="http://172.21.4.35:8000/images/filename.png" alt="图片" width="300">。
#   请确保回答简洁、专业，将图片自然地融入回答内容中。

def process_pdf_entry(doc_id, pdf_path, kb_id,update_progress):
    """
    供外部调用的PDF处理接口
    Args:
        pdf_path (str): PDF文件路径
        kb_id (str): 知识库ID
        tenant_id (str): 租户ID
        api_key (str): RAGFlow API密钥（可选）
        server_ip (str): RAGFlow服务器IP（可选）
        skip_ragflow (bool): 是否跳过RAGFlow
    Returns:
        dict: 处理结果
    """
    try:
        md_file_path = process_pdf_with_minerU(pdf_path,update_progress)
        return create_ragflow_resources(doc_id,  kb_id, md_file_path, 'output/images',update_progress)
    except Exception as e:
        print(e)
        return 0