import os
import re
from .minio_server import get_image_url
from magic_pdf.data.data_reader_writer import FileBasedDataWriter, FileBasedDataReader
from magic_pdf.data.dataset import PymuDocDataset
from magic_pdf.model.doc_analyze_by_custom_model import doc_analyze
from magic_pdf.config.enums import SupportedPdfParseMethod

# 常量定义
OUTPUT_DIR = "output"
IMAGE_DIR = os.path.join(OUTPUT_DIR, "images")

def _setup_directories():
    """初始化输出目录"""
    os.makedirs(IMAGE_DIR, exist_ok=True)
    return IMAGE_DIR, OUTPUT_DIR

def _read_pdf_bytes(pdf_file_path):
    """读取PDF文件为字节流"""
    reader = FileBasedDataReader("")
    return reader.read(pdf_file_path)

def _process_pdf_content(pdf_bytes):
    """处理PDF内容
    
    Args:
        pdf_bytes: PDF文件的二进制内容
    
    Returns:
        pipe_result: 处理后的结果对象
    """
    ds = PymuDocDataset(pdf_bytes)
    pdf_type = ds.classify()
    print(f"PDF分类结果: {pdf_type}")
    
    image_writer = FileBasedDataWriter(IMAGE_DIR)
    if pdf_type == SupportedPdfParseMethod.OCR:
        print("使用OCR模式处理PDF...")
        return ds.apply(doc_analyze, ocr=True).pipe_ocr_mode(image_writer)
    else:
        print("使用文本模式处理PDF...")
        return ds.apply(doc_analyze, ocr=False).pipe_txt_mode(image_writer)

def _generate_markdown(pipe_result, name_without_suff, output_dir, image_dir):
    """生成Markdown文件及相关内容"""
    md_writer = FileBasedDataWriter(output_dir)
    md_file_path = os.path.join(output_dir, f"{name_without_suff}.md")
    print(f"生成Markdown文件: {md_file_path}")
    pipe_result.dump_md(md_writer, f"{name_without_suff}.md", image_dir)
    # 生成内容列表和中间json
    pipe_result.dump_content_list(md_writer, f"{name_without_suff}_content_list.json", image_dir)
    pipe_result.dump_middle_json(md_writer, f'{name_without_suff}_middle.json')
    return md_file_path

def process_pdf_with_minerU(pdf_file_path, update_progress):
    """使用minerU处理PDF文件"""
    update_progress(0.3, f"=== 开始处理PDF文件 ===")
    image_dir, output_dir = _setup_directories()
    name_without_suff = os.path.splitext(os.path.basename(pdf_file_path))[0]
    pdf_bytes = _read_pdf_bytes(pdf_file_path)
    pipe_result = _process_pdf_content(pdf_bytes)
    md_file_path = _generate_markdown(pipe_result, name_without_suff, output_dir, image_dir)
    update_progress(0.5, f"=== PDF 文件处理完成 ===")
    return md_file_path

def update_markdown_image_urls(md_file_path, kb_id):
    """更新Markdown文件中的图片URL"""
    def _replace_img(match):
        img_url = os.path.basename(match.group(1))
        if not img_url.startswith(('http://', 'https://')):
            img_url = get_image_url(kb_id, img_url)
        return f'<img src="{img_url}" style="max-width: 300px;" alt="图片">'
    with open(md_file_path, 'r+', encoding='utf-8') as f:
        content = f.read()
        updated_content = re.sub(r'!\[\]\((.*?)\)', _replace_img, content)
        f.seek(0)
        f.write(updated_content)
        f.truncate()
    return updated_content



