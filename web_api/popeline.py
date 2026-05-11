import json
import os
import re
from typing import Any, Dict, List, Tuple, Union, Optional
import gc
import copy

import requests
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

from md_split import split_markdown_chunk
from md_utitls import create_child_chunks, num_tokens_from_string
pdf_extensions = [".pdf"]
def process_file_pipeline(
    file_bytes: bytes,
    file_extension: str,
    image_writer: Union[S3DataWriter, FileBasedDataWriter],
    parse_method: str = "auto",
    lang: str = "ch",
    formula_enable: bool = True,
    table_enable: bool = True,
):
    """Pipeline 模式处理函数"""
    processed_bytes = file_bytes
    if file_extension in pdf_extensions:
        processed_bytes = convert_pdf_bytes_to_bytes_by_pypdfium2(file_bytes, 0, None)
    
    infer_results, all_image_lists, all_pdf_docs, lang_list, ocr_enabled_list = pipeline_doc_analyze(
        [processed_bytes], [lang], parse_method, formula_enable, table_enable
    )
    
    model_list = infer_results[0]
    images_list = all_image_lists[0]
    pdf_doc = all_pdf_docs[0]
    _lang = lang_list[0]
    _ocr_enable = ocr_enabled_list[0]

    # 优化深拷贝方式，避免JSON序列化的内存浪费
    model_json = copy.deepcopy(model_list)
    
    middle_json = pipeline_result_to_middle_json(model_list, images_list, pdf_doc, image_writer, _lang, _ocr_enable, formula_enable)
    
    md_content = pipeline_union_make(middle_json["pdf_info"], MakeMode.MM_MD, "images")
    content_list = pipeline_union_make(middle_json["pdf_info"], MakeMode.CONTENT_LIST, "images")
    
    return model_json, middle_json, content_list, md_content, processed_bytes, middle_json["pdf_info"]

def replace_image_links(content, image_map,api_base_url):
    def replacer(match):
        full_path = match.group(1)
        image_hash = match.group(2)
        
        if image_hash in image_map:
            upload_file_id = image_map[image_hash]
            return f"![image]({api_base_url}/files/{upload_file_id}/file-preview)"
            # return f"![image](https://ai.toone.com.cn/files/{upload_file_id}/file-preview)"
        return match.group(0)  # 如果找不到映射，保持原样
    pattern = r'!\[.*?\]\((images/([a-f0-9]+)\.(?:jpg|jpeg|png|gif|bmp|webp))\)'
    return re.sub(pattern, replacer, content)
def upload_images_and_create_mapping_api(
    image_dir: str,
    # api_key: str='app-zLh7zvRCvSQGmSQZjAqDiAiO',
    # api_url: str = 'http://10.1.30.45/v1/files/upload',
    
    api_key: str='app-HtvkyxXhZE80LINDhCkFdysL',
    api_url: str = 'http://dify-dev.v.vtoone.com/v1/files/upload',
    user_id: str = 'abc-123'
) -> Dict[str, str]:
    """
    通过API上传图片并创建映射关系
    
    Returns:
        Dict[图片hash, 上传后的文件ID]
    """
    image_hash_to_id_map = {}
    
    if not os.path.exists(image_dir):
        print(f"图片目录不存在: {image_dir}")
        return image_hash_to_id_map
    
    image_extensions = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}
    
    for filename in os.listdir(image_dir):
        file_path = os.path.join(image_dir, filename)
        
        if os.path.isfile(file_path):
            _, ext = os.path.splitext(filename.lower())
            
            if ext in image_extensions:
                # 确定MIME类型
                mime_type = {
                    '.png': 'image/png',
                    '.jpg': 'image/jpeg',
                    '.jpeg': 'image/jpeg',
                    '.webp': 'image/webp',
                    '.gif': 'image/gif'
                }.get(ext, 'application/octet-stream')
                
                # 准备请求
                headers = {
                    'Authorization': f'Bearer {api_key}'
                }
                
                with open(file_path, 'rb') as f:
                    files = {
                        'file': (filename, f, mime_type)
                    }
                    data = {
                        'user': user_id
                    }
                    
                    try:
                        response = requests.post(api_url, headers=headers, files=files, data=data)
                        response.raise_for_status()
                        result = response.json()
                        
                        # 提取上传后的文件ID（根据实际API响应结构调整）
                        image_hash = os.path.splitext(filename)[0]
                        # 假设API返回的JSON中有'id'字段，根据实际情况调整
                        if 'id' in result:
                            image_hash_to_id_map[image_hash] = result['id']
                        else:
                            # 如果没有id字段，使用完整响应或其他标识
                            image_hash_to_id_map[image_hash] = str(result)
                        
                        print(f"成功上传: {filename}")
                        
                    except Exception as e:
                        print(f"上传失败 {filename}: {e}")
                        continue
    
    return image_hash_to_id_map
# 修改你的update_markdown_image_urls函数
def update_markdown_image_urls_with_api(md_file_path, image_dir, api_key,api_base_url, user_id='abc-123'):
    
    try:
        api_upload_url = f"{api_base_url}/v1/files/upload"
        api_key = 'app-CseOPlx0Qj1q0mto2SG1h6Dz'
        # 通过API上传图片并创建映射
        image_hash_to_id_map = upload_images_and_create_mapping_api(
           image_dir= image_dir, api_key=api_key, user_id=user_id, api_url=api_upload_url
        )
        
        with open(md_file_path, 'r+', encoding='utf-8') as f:
            content = f.read()
            result = replace_image_links(content, image_hash_to_id_map,api_base_url)
            f.seek(0)
            f.write(result)
            f.truncate()
        print(f"已更新Markdown文件中的图片URL: {md_file_path}")
        return result
    except Exception as e:
        print(f"更新Markdown图片URL失败: {e}")
        raise
# 创建文件
def create_document_file_mineru(base_url: str, api_key: str, dataset_id: str,file_path:str) -> Optional[str]:
        # base_url = dify_config.DIFY_SERVICE_API_URL # 替换为你的实际 API 地址
        base_url= 'http://10.1.30.45'
        # # 这个这里先这么处理 todo
        # api_key = 'app-CseOPlx0Qj1q0mto2SG1h6Dz'
        headers = {
            "Authorization": f"Bearer {api_key}",
        }
        url = f"{base_url}/v1/datasets/{dataset_id}/document/create_file_by_mineru"
        process_rule_data = {
                                "indexing_technique": "high_quality",
                                "doc_form": "hierarchical_model",
                                "process_rule": {
                                    "rules": {
                                        "pre_processing_rules": [
                                            {"id": "remove_extra_spaces", "enabled": True},
                                            {"id": "remove_urls_emails", "enabled": True}
                                        ],
                                        "segmentation": {
                                            "separator": "###",
                                            "max_tokens": 1024
                                        },
                                        "parent_mode": "paragraph",
                                        
                                    },
                                    "mode": "hierarchical",
                                    "subchunk_segmentation":{'separator': '\n', 'max_tokens': 512}
                                }
                            }
        
            # 准备表单数据
        data = {
            'data': json.dumps(process_rule_data)
        }
        try:
            with open(file_path, 'rb') as f:
                files = {
                    'file': f
                }
            
                response = requests.post(
                    url=url,
                    headers=headers,
                    data=data,
                    files=files
                )
                
                # 检查响应状态
                response.raise_for_status()
                
                result= response.json()
                document_info = result.get('document', {})
                batch = result.get('batch')
                document_id = document_info.get('id')
                return document_id
        except Exception as e:
            print(f"请求失败: {e}")
            return None
   
   

def upload_document_segments(
    dataset_id: str,
    document_id: str,
    segments: List[Dict[str, Any]],
    # api_key: str='dataset-Ophtlt9orhgJMz59DMAtpaPV',
    # api_base_url: str = 'http://10.1.30.45'
    
    datasetKey: str,
    api_base_url: str 
) -> Dict:
    """
    上传文档分段到指定数据集
    
    Args:
        dataset_id: 数据集ID
        document_id: 文档ID
        segments: 分段列表，每个分段包含content, answer, keywords等字段
        api_key: API密钥
        api_base_url: API基础URL
    
    Returns:
        API响应结果
    """
    url = f"{api_base_url}/v1/aicenter/{dataset_id}/documents/{document_id}/segments_mineru"
    # url = f"{api_base_url}/v1/datasets/{dataset_id}/documents/{document_id}/segments"
    headers = {
        'Authorization': f'Bearer {datasetKey}',
        'Content-Type': 'application/json'
    }
    
    # 构造请求数据
    payload = {
        "segments": segments
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result= response.json()
        if 'data' in result:
            for segment_data in result['data']:
                segment_id = segment_data.get('id')
                content = segment_data.get('content', '')
                # 先删除子分段
                # 检查内容是否超过4行需要切分
                if segment_id and content:
                    # 基于 token 数量判断是否需要创建子分段
                    if num_tokens_from_string(content) > 128:
                        # 需要创建子分段
                        create_child_chunks_simple(
                            dataset_id, document_id, segment_id, content, datasetKey, api_base_url
                        )
        
        return result
    except requests.exceptions.RequestException as e:
        raise Exception(f"上传文档分段失败: {e}")

def create_segments_from_chunks(chunks: List[str]) -> List[Dict[str, Any]]:
    """
    将分块内容转换为API所需的分段格式
    
    Args:
        chunks: 分块后的文本列表
    
    Returns:
        符合API格式的分段列表
    """
    segments = []
    
    for i, chunk in enumerate(chunks):
        segment = {
            "content": chunk,
        }
        segments.append(segment)
    
    return segments
def create_child_chunks_simple(
    dataset_id: str,
    document_id: str,
    segment_id: str,
    content: str,
    datasetKey: str,
    api_base_url: str,
) -> None:
    """
    为长内容创建子分段（基于Markdown AST的语义分块）
    
    使用 markdown-it-py 解析 Markdown AST，按语义边界（标题、段落、表格、
    代码块等）进行智能切分，保护表格和代码块完整性。
    
    Args:
        dataset_id: 数据集ID
        document_id: 文档ID
        segment_id: 父分段ID
        content: 父分段内容
        datasetKey: 数据集密钥
        api_base_url: API基础URL
    """
    # 使用基于 AST 的语义分块，保护 Markdown 结构完整性
    child_chunks = create_child_chunks(content, sub_chunk_token_num=100)
    
    if not child_chunks:
        return
    
    headers = {
        'Authorization': f'Bearer {datasetKey}',
        'Content-Type': 'application/json'
    }
    
    for i, chunk_info in enumerate(child_chunks):
        # child_chunks 返回 dict 列表，提取 content 字段
        chunk_content = chunk_info.get('content', '') if isinstance(chunk_info, dict) else chunk_info
        if isinstance(chunk_content, str) and chunk_content.strip():
            try:
                url = f"{api_base_url}/v1/aicenter/{dataset_id}/documents/{document_id}/segments/{segment_id}/child_chunks"
                
                payload = {
                    "content": chunk_content.strip()
                }
                response = requests.post(url, headers=headers, json=payload)
                response.raise_for_status()
                print(f"成功创建子分段 {i+1}/{len(child_chunks)}: {segment_id}")
                
            except requests.exceptions.RequestException as e:
                print(f"创建子分段失败 {segment_id}: {e}")
            except Exception as e:
                print(f"创建子分段时发生错误: {e}")
