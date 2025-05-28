import os
import re
import tempfile
import shutil
from typing import Callable, Tuple
from loguru import logger
from .minio_server import get_image_url
from magic_pdf.data.data_reader_writer import FileBasedDataWriter, FileBasedDataReader
from magic_pdf.data.dataset import PymuDocDataset
from magic_pdf.model.doc_analyze_by_custom_model import doc_analyze
from magic_pdf.config.enums import SupportedPdfParseMethod
from .file_converter import ensure_pdf

# 常量定义
OUTPUT_DIR_NAME = "output"
IMAGE_DIR_NAME = "images"

def _setup_directories(base_job_temp_dir: str) -> Tuple[str, str]:
    """在指定的任务根临时目录下初始化 'output' 和 'output/images' 子目录。
    Args:
        base_job_temp_dir: 当前任务的专属根临时目录。
    Returns:
        A tuple: (full_path_to_images_dir, full_path_to_output_dir)
    """
    output_dir_path = os.path.join(base_job_temp_dir, OUTPUT_DIR_NAME)
    images_dir_path = os.path.join(output_dir_path, IMAGE_DIR_NAME)
    os.makedirs(images_dir_path, exist_ok=True)
    logger.info(f"Ensured output directory exists: {output_dir_path}")
    logger.info(f"Ensured images directory exists: {images_dir_path}")
    return images_dir_path, output_dir_path

def _read_pdf_bytes(pdf_file_path: str) -> bytes:
    """读取PDF文件为字节流"""
    logger.debug(f"Reading PDF bytes from: {pdf_file_path}")
    reader = FileBasedDataReader("")
    return reader.read(pdf_file_path)

def _process_pdf_content(pdf_bytes: bytes, images_full_path: str) -> any:
    """处理PDF内容
    
    Args:
        pdf_bytes: PDF文件的二进制内容
        images_full_path: 图片写入器将使用的绝对基础路径 (例如 /tmp/jobXYZ/output/images)
    
    Returns:
        pipe_result: 处理后的结果对象
    """
    ds = PymuDocDataset(pdf_bytes)
    pdf_type = ds.classify()
    logger.info(f"PDF分类结果: {pdf_type}")
    
    image_writer = FileBasedDataWriter(images_full_path)
    if pdf_type == SupportedPdfParseMethod.OCR:
        logger.info("使用OCR模式处理PDF...")
        return ds.apply(doc_analyze, ocr=True).pipe_ocr_mode(image_writer)
    else:
        logger.info("使用文本模式处理PDF...")
        return ds.apply(doc_analyze, ocr=False).pipe_txt_mode(image_writer)

def _generate_markdown(pipe_result: any, name_without_suff: str, output_full_path: str, images_subdir_name_for_ref: str) -> str:
    """生成Markdown文件及相关内容"""
    md_writer = FileBasedDataWriter(output_full_path)
    md_file_name = f"{name_without_suff}.md"
    md_file_path = os.path.join(output_full_path, md_file_name)
    logger.info(f"生成Markdown文件: {md_file_path}")
    pipe_result.dump_md(md_writer, md_file_name, images_subdir_name_for_ref)
    pipe_result.dump_content_list(md_writer, f"{name_without_suff}_content_list.json", images_subdir_name_for_ref)
    pipe_result.dump_middle_json(md_writer, f'{name_without_suff}_middle.json')
    return md_file_path

def process_pdf_with_minerU(file_input, update_progress=None):
    """
    处理PDF文件并生成Markdown
    Args:
        file_input: 可以是PDF文件路径、URL或Office文件路径
        update_progress: 进度回调函数
    Returns:
        str: 生成的Markdown文件路径
    """
    # 使用当前目录作为工作目录
    job_specific_temp_dir = os.getcwd()
    
    # 确保PDF文件存在
    pdf_path_to_process, path_to_delete_after_processing = ensure_pdf(file_input, job_specific_temp_dir)

    try:
        update_progress(0.1, "=== 开始文件预处理 ===")
        logger.info(f"接收到输入进行处理: {file_input}")

        if not pdf_path_to_process:
            logger.error(f"无法获取或生成用于处理的PDF文件，源输入: {file_input}")
            raise Exception(f"无法处理输入 {file_input}，未能转换为PDF或找到PDF。")
        
        logger.info(f"将要处理的PDF文件: {pdf_path_to_process}")
        if path_to_delete_after_processing:
            logger.info(f"此PDF是临时转换文件，将在处理后删除: {path_to_delete_after_processing}")

        update_progress(0.3, f"PDF文件准备就绪 ({os.path.basename(pdf_path_to_process)})，开始MinerU核心处理...")
        
        images_full_path, output_full_path = _setup_directories(job_specific_temp_dir)
        
        name_without_suff = os.path.splitext(os.path.basename(pdf_path_to_process))[0]
        pdf_bytes = _read_pdf_bytes(pdf_path_to_process)
        
        pipe_result = _process_pdf_content(pdf_bytes, images_full_path)
        
        md_file_path = _generate_markdown(pipe_result, name_without_suff, output_full_path, IMAGE_DIR_NAME)
        
        update_progress(0.5, f"文件处理和Markdown生成完成: {os.path.basename(md_file_path)}")
        logger.info(f"最终生成的Markdown文件路径: {md_file_path}")
        
        return md_file_path

    except Exception as e:
        logger.exception(f"在 process_pdf_with_minerU 中发生严重错误，输入: {file_input}, 错误: {e}")
        update_progress(0.5, f"文件处理失败: {str(e)}")
        raise
    finally:
        if path_to_delete_after_processing and os.path.exists(path_to_delete_after_processing):
            try:
                os.remove(path_to_delete_after_processing)
                logger.info(f"已清理临时转换的PDF文件: {path_to_delete_after_processing}")
            except OSError as e_remove:
                logger.error(f"清理临时转换的PDF文件失败: {path_to_delete_after_processing}, 错误: {e_remove}")
        
        if job_specific_temp_dir and os.path.exists(job_specific_temp_dir):
            logger.info(f"任务专属临时目录 {job_specific_temp_dir} 及其内容 (包括最终输出的 markdown 和图片) 被保留。调用者负责后续清理。")
            pass

def update_markdown_image_urls(md_file_path, kb_id):
    """更新Markdown文件中的图片URL"""
    def _replace_img(match):
        alt_text = match.group(1)
        img_src = match.group(2)
        img_name = os.path.basename(img_src)
        
        if not img_src.startswith(('http://', 'https://')):
            final_img_url = get_image_url(kb_id, img_name)
        else:
            final_img_url = img_src
        return f'<img src="{final_img_url}" style="max-width: 300px;" alt="{alt_text if alt_text else img_name}">'
    
    if not md_file_path or not os.path.exists(md_file_path):
        logger.error(f"Markdown文件路径无效或文件不存在: {md_file_path} (update_markdown_image_urls)")
        return ""

    try:
        with open(md_file_path, 'r+', encoding='utf-8') as f:
            content = f.read()
            updated_content = re.sub(r'!\[(.*?)\]\\((.*?)\\)', _replace_img, content)
            if content != updated_content:
                f.seek(0)
                f.write(updated_content)
                f.truncate()
                logger.info(f"Markdown文件中的图片链接已更新: {md_file_path}")
            else:
                logger.info(f"Markdown文件中没有图片链接需要更新: {md_file_path}")
        return updated_content
    except FileNotFoundError:
        logger.error(f"Markdown文件 {md_file_path} 未找到 (update_markdown_image_urls)")
        return ""
    except Exception as e:
        logger.exception(f"更新Markdown图片URL时发生错误: {md_file_path}, 错误: {e}")
        try:
            with open(md_file_path, 'r', encoding='utf-8') as f_orig:
                return f_orig.read()
        except Exception:
            return ""



