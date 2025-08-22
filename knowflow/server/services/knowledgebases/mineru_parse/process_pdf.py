#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import tempfile
import json
import base64
from .ragflow_build import create_ragflow_resources
from .fastapi_adapter import get_global_adapter

# 聊天助手 Prompt 模板:
#   请参考{knowledge}内容回答用户问题。
#   如果知识库内容包含图片，请在回答中包含图片URL。
#   注意这个 html 格式的 URL 是来自知识库本身，URL 不能做任何改动。
#   示例如下：<img src="http://172.21.4.35:8000/images/filename.png" alt="图片" width="300">。
#   请确保回答简洁、专业，将图片自然地融入回答内容中。


def _save_images_from_result(result, images_dir):
    """从 FastAPI 结果中保存图片到临时目录"""
    saved_count = 0
    
    if 'images' in result and result['images']:
        os.makedirs(images_dir, exist_ok=True)
        
        for image_name, image_data in result['images'].items():
            try:
                # 提取 base64 数据（去掉 data:image/jpeg;base64, 前缀）
                if image_data.startswith('data:image/'):
                    base64_data = image_data.split(',', 1)[1]
                else:
                    base64_data = image_data
                
                # 解码并保存图片
                image_bytes = base64.b64decode(base64_data)
                image_path = os.path.join(images_dir, image_name)
                
                with open(image_path, 'wb') as f:
                    f.write(image_bytes)
                    
                saved_count += 1
                print(f"[INFO] 保存图片: {image_path}")
                
            except Exception as e:
                print(f"[ERROR] 保存图片 {image_name} 失败: {e}")
    else:
        print(f"[INFO] API响应中没有图片数据 - 图片可能已保存到服务器端")
    
    print(f"[INFO] 总共保存了 {saved_count} 张图片到 {images_dir}")
    return saved_count


def _process_pdf_with_fastapi(pdf_path, update_progress):
    """
    使用 FastAPI 处理 PDF 文件
    
    Args:
        pdf_path (str): PDF 文件路径
        update_progress (function): 进度回调函数
    Returns:
        str: 生成的 Markdown 文件路径
    """
    if update_progress:
        update_progress(0.25, "PDF文件检查完成")
    
    # 获取适配器并处理文件
    adapter = get_global_adapter()
    result = adapter.process_file(
        file_path=pdf_path,
        update_progress=update_progress,
        return_middle_json=True,   # 确保返回 middle_json 信息
        return_images=True         # 获取原始图片数据
    )
    
    # 调试信息
    print(f"[DEBUG] FastAPI 响应结构: {type(result)}")
    print(f"[DEBUG] FastAPI 响应字段: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
    
    # 处理 FastAPI 的响应结构
    # 根据curl请求，可能直接返回结果，也可能嵌套在 results 数组中
    if 'results' in result and len(result['results']) > 0:
        # 从 results 数组中获取第一个结果（兼容旧格式）
        first_result = result['results'][0]
        print(f"[DEBUG] 使用 results 数组格式")
    elif 'md_content' in result or 'middle_json' in result:
        # 直接使用结果（新格式）
        first_result = result
        print(f"[DEBUG] 使用直接结果格式")
    else:
        raise ValueError("FastAPI 返回的数据格式不符合预期，既没有 results 数组也没有直接的 md_content")
    
    # 调试信息
    print(f"[DEBUG] 处理结果字段: {list(first_result.keys())}")
    print(f"[DEBUG] md_content 存在: {'md_content' in first_result}")
    print(f"[DEBUG] middle_json 存在: {'middle_json' in first_result}")
    if 'middle_json' in first_result:
        print(f"[DEBUG] middle_json 类型: {type(first_result['middle_json'])}")
        print(f"[DEBUG] middle_json 是否为空: {not first_result['middle_json']}")
    
    # 检查是否有 md_content
    if 'md_content' in first_result and first_result['md_content']:
        temp_dir = tempfile.mkdtemp()
        
        # 保存 Markdown 文件
        md_file_path = os.path.join(temp_dir, "result.md")
        with open(md_file_path, 'w', encoding='utf-8') as f:
            f.write(first_result['md_content'])
        
        # 保存 middle_json 数据到对应位置，供 get_bbox_for_chunk 使用
        if 'middle_json' in first_result and first_result['middle_json']:
            middle_json_path = os.path.join(temp_dir, "result_middle.json")
            with open(middle_json_path, 'w', encoding='utf-8') as f:
                json.dump(first_result['middle_json'], f, ensure_ascii=False, indent=2)
            print(f"[INFO] 已保存位置信息文件: {middle_json_path}")
        else:
            print(f"[WARNING] FastAPI 未返回位置信息数据 (middle_json 字段为空或不存在)")
        
        # 创建并保存图片到临时目录
        images_dir = os.path.join(temp_dir, 'images')
        _save_images_from_result(first_result, images_dir)
            
        return md_file_path
    else:
        raise ValueError("FastAPI 返回的结果中未包含 md_content 或 md_content 为空")


def _safe_create_ragflow(doc_id, kb_id, md_file_path, image_dir, update_progress):
    """封装RAGFlow资源创建，便于异常捕获和扩展"""
    return create_ragflow_resources(doc_id, kb_id, md_file_path, image_dir, update_progress)


def process_pdf_entry(doc_id, pdf_path, kb_id, update_progress):
    """
    供外部调用的PDF处理接口（FastAPI 模式）
    
    Args:
        doc_id (str): 文档ID
        pdf_path (str): PDF文件路径
        kb_id (str): 知识库ID
        update_progress (function): 进度回调
    Returns:
        dict: 处理结果
    """
    try:
        if update_progress:
            update_progress(0.01, "PDF 处理模式: FastAPI")
            
        # 使用 FastAPI 处理
        md_file_path = _process_pdf_with_fastapi(pdf_path, update_progress)
        
        # 处理图片目录（已在 _process_pdf_with_fastapi 中创建）
        images_dir = os.path.join(os.path.dirname(md_file_path), 'images')
        
        # 创建 RAGFlow 资源
        result = _safe_create_ragflow(doc_id, kb_id, md_file_path, images_dir, update_progress)
        
        return result
    except Exception as e:
        print(f"FastAPI 处理失败: {e}")
        # 抛出异常让调用方知道处理失败，而不是返回0
        raise Exception(f"MinerU 文档解析失败: {str(e)}")


# 配置函数
def configure_fastapi(base_url: str = None, backend: str = None):
    """
    配置 FastAPI 设置
    
    Args:
        base_url: FastAPI 服务地址
        backend: 默认后端类型
    """
    if base_url:
        os.environ['MINERU_FASTAPI_URL'] = base_url
    if backend:
        os.environ['MINERU_FASTAPI_BACKEND'] = backend
        
    # 重新配置适配器
    from .fastapi_adapter import configure_adapter
    configure_adapter(base_url=base_url, backend=backend)
    
    print(f"FastAPI 配置已更新: {base_url or 'http://localhost:8888'}, 后端: {backend or 'pipeline'}")


def get_processing_info():
    """获取当前处理信息"""
    adapter = get_global_adapter()
    return {
        'mode': 'FastAPI',
        'url': adapter.base_url,
        'backend': adapter.backend,
        'timeout': adapter.timeout
    }