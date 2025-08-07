import os
import gc
import json
import os
import tempfile
import requests
from glob import glob
from base64 import b64encode
from pathlib import Path
from typing import Optional, Union, Tuple, List
from urllib.parse import urlparse

import uvicorn
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from mineru.cli.common import aio_do_parse
from mineru.utils.language import remove_invalid_surrogates
from mineru.version import __version__

app = FastAPI(
    title="MinerU Web API",
    description="Compatible with MinerU official API - Parse documents using MinerU",
    version=__version__
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "version": __version__,
        "api": "MinerU Web API",
        "compatible": "Official MinerU API"
    }

# 支持的文件扩展名 - 与官方 API 保持一致
pdf_suffixes = [".pdf"]
office_suffixes = [".ppt", ".pptx", ".doc", ".docx"]
image_suffixes = [".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif"]

def validate_server_url(url: str) -> bool:
    """
    验证 server_url 的格式是否正确
    
    Args:
        url: 要验证的 URL
        
    Returns:
        bool: URL 格式是否有效
    """
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False

# Removed clean_data_for_json function - now using official API


def check_sglang_server_health(server_url: str, timeout: int = 10) -> Tuple[bool, str]:
    """
    检查 SGLang 服务器的健康状态
    
    Args:
        server_url: SGLang 服务器地址
        timeout: 超时时间（秒）
        
    Returns:
        Tuple[bool, str]: (是否健康, 状态信息)
    """
    try:
        # 尝试连接健康检查端点
        health_url = f"{server_url.rstrip('/')}/health"
        response = requests.get(health_url, timeout=timeout)
        if response.status_code == 200:
            return True, "SGLang server is healthy"
        else:
            return False, f"SGLang server returned status {response.status_code}"
    except requests.exceptions.Timeout:
        return False, f"SGLang server health check timeout after {timeout}s"
    except requests.exceptions.ConnectionError:
        return False, "Cannot connect to SGLang server"
    except Exception as e:
        return False, f"SGLang server health check failed: {str(e)}"

# Removed init_writers function - now using simpler file handling


# Removed old processing functions - now using official API's aio_do_parse


def encode_image(image_path: str) -> str:
    """Encode image using base64"""
    with open(image_path, "rb") as f:
        return b64encode(f.read()).decode()


def get_infer_result(file_suffix_identifier: str, file_name: str, parse_dir: str) -> Optional[str]:
    """从结果文件中读取推理结果 - 支持嵌套目录查找"""
    import glob
    
    # 首先尝试官方路径格式
    result_file_path = os.path.join(parse_dir, f"{file_name}{file_suffix_identifier}")
    logger.info(f"Looking for result file: {result_file_path}")
    
    if os.path.exists(result_file_path):
        logger.info(f"Found result file: {result_file_path}")
        try:
            with open(result_file_path, "r", encoding="utf-8") as fp:
                content = fp.read()
                logger.info(f"Read {len(content)} characters from {result_file_path}")
                return content
        except Exception as e:
            logger.error(f"Error reading file {result_file_path}: {e}")
            return None
    
    # 如果官方路径不存在，尝试递归查找
    logger.warning(f"Result file not found at official path: {result_file_path}")
    logger.info("Searching recursively in subdirectories...")
    
    # 构建文件名模式
    file_pattern = f"*{file_suffix_identifier}"
    logger.info(f"Searching for pattern: {file_pattern}")
    
    # 递归查找文件
    found_files = []
    for root, dirs, files in os.walk(parse_dir):
        for file in files:
            if file.endswith(file_suffix_identifier):
                full_path = os.path.join(root, file)
                found_files.append(full_path)
                logger.info(f"Found potential result file: {full_path}")
    
    if found_files:
        # 优先选择包含文件名的文件
        for file_path in found_files:
            if file_name in file_path:
                logger.info(f"Selected result file: {file_path}")
                try:
                    with open(file_path, "r", encoding="utf-8") as fp:
                        content = fp.read()
                        logger.info(f"Read {len(content)} characters from {file_path}")
                        return content
                except Exception as e:
                    logger.error(f"Error reading file {file_path}: {e}")
                    continue
        
        # 如果没有找到包含文件名的文件，使用第一个找到的文件
        if found_files:
            selected_file = found_files[0]
            logger.info(f"Using first found file: {selected_file}")
            try:
                with open(selected_file, "r", encoding="utf-8") as fp:
                    content = fp.read()
                    logger.info(f"Read {len(content)} characters from {selected_file}")
                    return content
            except Exception as e:
                logger.error(f"Error reading file {selected_file}: {e}")
                return None
    
    # 如果仍然没有找到，列出目录内容帮助调试
    logger.warning(f"No result file found for pattern: {file_pattern}")
    if os.path.exists(parse_dir):
        logger.info(f"Listing all files in {parse_dir}:")
        for root, dirs, files in os.walk(parse_dir):
            for file in files:
                logger.info(f"  {os.path.join(root, file)}")
    else:
        logger.warning(f"Parse directory does not exist: {parse_dir}")
    
    return None


@app.post(
    "/file_parse",
    tags=["projects"],
    summary="Parse files using MinerU - Compatible with official API",
)
async def file_parse(
    files: List[UploadFile] = File(...),
    output_dir: str = Form("./output"),
    lang_list: List[str] = Form(["ch"]),
    backend: str = Form("pipeline"),
    parse_method: str = Form("auto"),
    formula_enable: bool = Form(True),
    table_enable: bool = Form(True),
    server_url: Optional[str] = Form(None),
    return_md: bool = Form(True),
    return_middle_json: bool = Form(False),
    return_model_output: bool = Form(False),
    return_content_list: bool = Form(False),
    return_images: bool = Form(False),
    start_page_id: int = Form(0),
    end_page_id: int = Form(99999),
):
    """
    Parse files using MinerU - Compatible with official API
    
    Args:
        files: List of files to be parsed (PDF, images)
        output_dir: Output directory for results
        lang_list: List of languages for parsing (e.g., ['ch', 'en'])
        backend: Parsing backend (pipeline, vlm-transformers, vlm-sglang-engine, vlm-sglang-client)
        parse_method: Parsing method (auto, ocr, txt)
        formula_enable: Whether to enable formula parsing
        table_enable: Whether to enable table parsing
        server_url: Server URL for vlm-sglang-client backend
        return_md: Whether to return markdown content
        return_middle_json: Whether to return middle JSON
        return_model_output: Whether to return model output
        return_content_list: Whether to return content list
        return_images: Whether to return images as base64
        start_page_id: Start page ID for parsing
        end_page_id: End page ID for parsing
    """
    try:
        # 验证后端类型
        supported_backends = ["pipeline", "vlm-transformers", "vlm-sglang-engine", "vlm-sglang-client"]
        if backend not in supported_backends:
            return JSONResponse(
                content={"error": f"Unsupported backend: {backend}. Supported: {supported_backends}"},
                status_code=400,
            )

        # 对于 vlm-sglang-client，server_url 是必需的
        if backend == "vlm-sglang-client":
            # 检查是否提供了 server_url，如果没有则尝试使用环境变量或默认值
            if not server_url:
                server_url = os.environ.get("SGLANG_SERVER_URL", os.environ.get("MINERU_VLM_SERVER_URL"))
                
                # 如果仍然没有，尝试使用默认的本地地址
                if not server_url:
                    default_url = "http://localhost:30000"
                    logger.info(f"No server_url provided, attempting to use default: {default_url}")
                    
                    # 先检查默认地址是否可用
                    is_default_healthy, _ = check_sglang_server_health(default_url, timeout=3)
                    if is_default_healthy:
                        server_url = default_url
                        logger.info(f"Using default SGLang server at: {default_url}")
                    else:
                        # 提供详细的错误信息和解决方案
                        error_msg = """server_url is required for vlm-sglang-client backend.

解决方案:
1. 设置环境变量: export SGLANG_SERVER_URL=http://localhost:30000
2. 在请求中指定参数: -F "server_url=http://localhost:30000"
3. 确保SGLang服务正在运行: curl http://localhost:30000/health

如果使用Docker完整版，SGLang服务应该自动在30000端口启动。"""
                        
                        return JSONResponse(
                            content={"error": error_msg},
                            status_code=400,
                        )
            
            # 验证 server_url 格式
            if not validate_server_url(server_url):
                return JSONResponse(
                    content={"error": f"Invalid server_url format: {server_url}. Please provide a valid URL (e.g., http://localhost:30000)"},
                    status_code=400,
                )
            
            # 检查 SGLang 服务器健康状态
            logger.info(f"Checking SGLang server health at: {server_url}")
            is_healthy, health_msg = check_sglang_server_health(server_url)
            if not is_healthy:
                logger.warning(f"SGLang server health check failed: {health_msg}")
                error_msg = f"""SGLang server is not accessible: {health_msg}

故障排除:
1. 检查SGLang服务是否运行: curl {server_url}/health  
2. 确认端口是否正确开放
3. 如果使用Docker，确保使用完整版镜像 (INSTALL_TYPE=all)
4. 检查防火墙设置

服务器地址: {server_url}"""
                
                return JSONResponse(
                    content={"error": error_msg},
                    status_code=503,
                )
            logger.info(f"SGLang server health check passed: {health_msg}")

        # 验证文件
        if not files:
            return JSONResponse(
                content={"error": "No files provided"},
                status_code=400,
            )

        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        results = []
        
        for file in files:
            # 验证文件扩展名
            file_suffix = Path(file.filename).suffix.lower()
            if file_suffix not in pdf_suffixes + office_suffixes + image_suffixes:
                return JSONResponse(
                    content={"error": f"File type {file_suffix} is not supported for {file.filename}"},
                    status_code=400,
                )
            
            # 读取文件内容
            file_name = Path(file.filename).stem  # 去掉扩展名
            # 修正：使用完整文件名匹配MinerU的输出文件命名格式
            file_basename = file.filename  # 保留完整文件名
            content = await file.read()
            
            # 使用官方 API 的 aio_do_parse 函数
            try:
                logger.info(f"Starting to parse {file.filename} using backend {backend}")
                logger.info(f"Output directory: {output_dir}")
                logger.info(f"File name stem: {file_name}")
                
                await aio_do_parse(
                    output_dir=output_dir,
                    pdf_file_names=[file.filename],
                    pdf_bytes_list=[content],
                    p_lang_list=lang_list,
                    backend=backend,
                    parse_method=parse_method,
                    formula_enable=formula_enable,
                    table_enable=table_enable,
                    start_page_id=start_page_id,
                    end_page_id=end_page_id,
                    server_url=server_url,
                )
                
                logger.info(f"Parse completed for {file.filename}")
                # 列出输出目录中的所有文件
                if os.path.exists(output_dir):
                    all_files = []
                    for root, dirs, files in os.walk(output_dir):
                        for f in files:
                            all_files.append(os.path.join(root, f))
                    logger.info(f"Files created in output directory: {all_files}")
                
                # 收集结果
                file_result = {"filename": file.filename}
                logger.info(f"Collecting results for {file.filename}")
                
                if return_md:
                    md_content = get_infer_result(".md", file_basename, output_dir)
                    file_result["md_content"] = md_content
                
                if return_middle_json:
                    middle_json_content = get_infer_result("_middle.json", file_basename, output_dir)
                    if middle_json_content:
                        file_result["middle_json"] = json.loads(middle_json_content)
                
                if return_model_output:
                    model_json_content = get_infer_result("_model.json", file_basename, output_dir)
                    if model_json_content:
                        file_result["model_output"] = json.loads(model_json_content)
                
                if return_content_list:
                    content_list_content = get_infer_result("_content_list.json", file_basename, output_dir)
                    if content_list_content:
                        file_result["content_list"] = json.loads(content_list_content)
                
                if return_images:
                    # 在输出目录中查找图像文件 - 支持多种目录结构
                    image_dirs = [
                        os.path.join(output_dir, file_name, "images"),  # 原始路径
                        os.path.join(output_dir, file_name, "vlm", "images"),  # vlm 子目录
                        os.path.join(output_dir, file_name, "auto", "images"),  # auto 子目录
                    ]
                    
                    found_images = {}
                    for image_dir in image_dirs:
                        if os.path.exists(image_dir):
                            logger.info(f"Found image directory: {image_dir}")
                            # 支持多种图片格式
                            for ext in ["*.jpg", "*.jpeg", "*.png", "*.bmp", "*.tiff", "*.tif"]:
                                image_paths = glob(os.path.join(image_dir, ext))
                                for image_path in image_paths:
                                    image_name = os.path.basename(image_path)
                                    if image_name not in found_images:  # 避免重复
                                        found_images[image_name] = f"data:image/jpeg;base64,{encode_image(image_path)}"
                                        logger.info(f"Added image: {image_name}")
                    
                    file_result["images"] = found_images
                    logger.info(f"Total images found: {len(found_images)}")
                
                file_result["backend"] = backend
                results.append(file_result)
                
            except Exception as parse_error:
                logger.error(f"Error parsing {file.filename}: {str(parse_error)}")
                results.append({
                    "filename": file.filename,
                    "error": str(parse_error)
                })
            
            # 不需要清理临时文件，因为没有保存到磁盘
        
        # 返回结果
        response_data = {
            "results": results,
            "total_files": len(files),
            "successful_files": len([r for r in results if "error" not in r])
        }
        
        return JSONResponse(response_data, status_code=200)

    except Exception as e:
        error_message = remove_invalid_surrogates(str(e))
        logger.error(f"API error: {error_message}")
        return JSONResponse(content={"error": error_message}, status_code=500)
    finally:
        gc.collect()


if __name__ == "__main__":
    # os.environ['MINERU_MODEL_SOURCE'] = "modelscope"
    uvicorn.run(app, host="0.0.0.0", port=8888)
