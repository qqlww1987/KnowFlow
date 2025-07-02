#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MinerU 工具函数模块

此模块包含文档处理相关的工具函数，主要用于支持 FastAPI 处理模式。
已移除旧版 MinerU 1.x 本地处理代码，统一使用 FastAPI 接口。
"""

import os
import re
from loguru import logger
from .minio_server import get_image_url


def update_markdown_image_urls(md_file_path, kb_id):
    """
    更新Markdown文件中的图片URL
    
    Args:
        md_file_path (str): Markdown文件路径
        kb_id (str): 知识库ID
        
    Returns:
        str: 更新后的Markdown内容
    """
    def _replace_img(match):
        img_url = os.path.basename(match.group(1))
        if not img_url.startswith(('http://', 'https://')):
            img_url = get_image_url(kb_id, img_url)
        return f'<img src="{img_url}" style="max-width: 300px;" alt="图片">'
    
    try:
        with open(md_file_path, 'r+', encoding='utf-8') as f:
            content = f.read()
            updated_content = re.sub(r'!\[\]\((.*?)\)', _replace_img, content)
            f.seek(0)
            f.write(updated_content)
            f.truncate()
        logger.info(f"已更新Markdown文件中的图片URL: {md_file_path}")
        return updated_content
    except Exception as e:
        logger.error(f"更新Markdown图片URL失败: {e}")
        raise


# 已弃用的函数警告
def process_pdf_with_minerU(*args, **kwargs):
    """
    已弃用函数
    
    注意：此函数已被移除，请使用 FastAPI 接口进行文档处理。
    建议使用：server.services.knowledgebases.mineru_parse.process_pdf.process_pdf_entry
    """
    raise DeprecationWarning(
        "process_pdf_with_minerU 函数已被弃用。"
        "请使用 FastAPI 模式进行文档处理。"
        "参考：server.services.knowledgebases.mineru_parse.process_pdf.process_pdf_entry"
    )


if __name__ == '__main__':
    # 测试用例
    logger.info("MinerU 工具函数模块加载成功")
    logger.info("注意：已移除旧版 MinerU 1.x 本地处理代码，统一使用 FastAPI 接口")