#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
from .mineru_test import process_pdf_with_minerU
from .ragflow_build import create_ragflow_resources
# 聊天助手 Prompt 模板:
#   请参考{knowledge}内容回答用户问题。
#   如果知识库内容包含图片，请在回答中包含图片URL。
#   注意这个 html 格式的 URL 是来自知识库本身，URL 不能做任何改动。
#   示例如下：<img src="http://172.21.4.35:8000/images/filename.png" alt="图片" width="300">。
#   请确保回答简洁、专业，将图片自然地融入回答内容中。



def _safe_process_pdf(pdf_path, update_progress):
    """封装PDF处理，便于异常捕获和扩展"""
    return process_pdf_with_minerU(pdf_path, update_progress)

def _safe_create_ragflow(doc_id, kb_id, md_file_path, image_dir, update_progress):
    """封装RAGFlow资源创建，便于异常捕获和扩展"""
    return create_ragflow_resources(doc_id, kb_id, md_file_path, image_dir, update_progress)

def process_pdf_entry(doc_id, pdf_path, kb_id, update_progress):
    """
    供外部调用的PDF处理接口
    Args:
        doc_id (str): 文档ID
        pdf_path (str): PDF文件路径
        kb_id (str): 知识库ID
        update_progress (function): 进度回调
    Returns:
        dict: 处理结果
    """
    try:
        md_file_path = _safe_process_pdf(pdf_path, update_progress)
        images_dir = os.path.join(os.path.dirname(md_file_path), 'images')
        result = _safe_create_ragflow(doc_id, kb_id, md_file_path, images_dir, update_progress)
        return result
    except Exception as e:
        print(e)
        return 0