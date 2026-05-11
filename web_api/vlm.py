import json
import os
import requests
from urllib.parse import urlparse
from base64 import b64encode
from glob import glob
from typing import Tuple, Union, Optional
import gc
import copy

import uvicorn
from fastapi import FastAPI, UploadFile
from fastapi.responses import JSONResponse
from loguru import logger

from mineru.data.data_reader_writer import FileBasedDataWriter
from mineru.data.data_reader_writer.s3 import S3DataReader, S3DataWriter
from mineru.utils.config_reader import get_bucket_name, get_s3_config
from fastapi import Form
from mineru.cli.common import convert_pdf_bytes_to_bytes_by_pypdfium2
from mineru.backend.pipeline.pipeline_analyze import doc_analyze as pipeline_doc_analyze
from mineru.backend.pipeline.model_json_to_middle_json import result_to_middle_json as pipeline_result_to_middle_json
from mineru.backend.pipeline.pipeline_middle_json_mkcontent import union_make as pipeline_union_make
from mineru.backend.vlm.vlm_analyze import doc_analyze as vlm_doc_analyze
from mineru.backend.vlm.vlm_middle_json_mkcontent import union_make as vlm_union_make
from mineru.utils.enum_class import MakeMode
from mineru.utils.draw_bbox import draw_layout_bbox, draw_span_bbox
from mineru.utils.language import remove_invalid_surrogates
pdf_extensions = [".pdf"]
def process_file_vlm(
    file_bytes: bytes,
    file_extension: str,
    image_writer: Union[S3DataWriter, FileBasedDataWriter],
    backend: str = "transformers",
    server_url: Optional[str] = None,
):
    """VLM 模式处理函数"""
    logger.info(f"Starting VLM processing with backend: {backend}")
    if server_url:
        logger.info(f"Using server URL: {server_url}")
    
    processed_bytes = file_bytes
    if file_extension in pdf_extensions:
        processed_bytes = convert_pdf_bytes_to_bytes_by_pypdfium2(file_bytes, 0, None)
        logger.info("PDF converted to bytes for VLM processing")
    
    # 使用 VLM 后端进行解析
    logger.info(f"Calling vlm_doc_analyze with backend={backend}, server_url={server_url}")
    middle_json, infer_result = vlm_doc_analyze(
        processed_bytes, 
        image_writer=image_writer, 
        backend=backend, 
        server_url=server_url
    )
    logger.info("VLM document analysis completed successfully")
    
    pdf_info = middle_json["pdf_info"]
    
    # 生成 markdown 和内容列表
    logger.info("Generating markdown and content list from VLM results")
    md_content = vlm_union_make(pdf_info, MakeMode.MM_MD, "images")
    content_list = vlm_union_make(pdf_info, MakeMode.CONTENT_LIST, "images")
    logger.info("Markdown and content list generation completed")
    
    # 构造类似于 pipeline 的 model_json 格式
    model_json = {
        "model_output": infer_result,
        "backend": backend
    }
    
    logger.info(f"VLM processing completed successfully with backend: {backend}")
    return model_json, middle_json, content_list, md_content, processed_bytes, pdf_info