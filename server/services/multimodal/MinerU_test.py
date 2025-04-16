import os
import shutil
import re  # 新增re模块导入
from magic_pdf.data.data_reader_writer import FileBasedDataWriter, FileBasedDataReader
from magic_pdf.data.dataset import PymuDocDataset
from magic_pdf.model.doc_analyze_by_custom_model import doc_analyze
from magic_pdf.config.enums import SupportedPdfParseMethod




def process_pdf_with_minerU(pdf_file_path):
    """
    使用minerU处理PDF文件的主方法
    """
    print(f"=== 开始处理PDF文件: {pdf_file_path} ===")
    
    # 初始化参数和目录
    name_without_suff = os.path.splitext(os.path.basename(pdf_file_path))[0]
    local_image_dir, local_md_dir = "output/images", "output"
    print(f"创建输出目录: 图片目录={local_image_dir}, Markdown目录={local_md_dir}")
    os.makedirs(local_image_dir, exist_ok=True)
    
    #处理PDF核心逻辑
    print("初始化文件读写器...")
    image_writer, md_writer = FileBasedDataWriter(local_image_dir), FileBasedDataWriter(local_md_dir)
    reader = FileBasedDataReader("")
    
    print("读取PDF文件内容...")
    pdf_bytes = reader.read(pdf_file_path)
    
    print("创建PDF数据集并分类...")
    ds = PymuDocDataset(pdf_bytes)
    pdf_type = ds.classify()
    print(f"PDF分类结果: {pdf_type}")
    
    if pdf_type == SupportedPdfParseMethod.OCR:
        print("使用OCR模式处理PDF...")
        pipe_result = ds.apply(doc_analyze, ocr=True).pipe_ocr_mode(image_writer)
    else:
        print("使用文本模式处理PDF...")
        pipe_result = ds.apply(doc_analyze, ocr=False).pipe_txt_mode(image_writer)
    
    # 生成Markdown文件
    md_file_path = os.path.join(local_md_dir, f"{name_without_suff}.md")
    print(f"生成Markdown文件: {md_file_path}")
    pipe_result.dump_md(md_writer, f"{name_without_suff}.md", "images")
    
    print("=== PDF处理完成 ===")
    return md_file_path


def update_markdown_image_urls(md_file_path, kb_id):
    """
    更新Markdown文件中的图片URL并转换为HTML标签
    1. 添加服务器地址前缀
    2. 将Markdown图片语法转为HTML img标签
    
    Args:
        md_file_path: Markdown文件路径
        kb_id: 知识库ID
    """
    with open(md_file_path, 'r+', encoding='utf-8') as f:
        content = f.read()
        
        # 替换图片URL并转换为HTML标签
        pattern = r'!\[\]\((.*?)\)'
        def replace_img(match):
            img_url = match.group(1)
            # 去掉 images/ 前缀 
            img_url = os.path.basename(img_url)
            from minio_server import get_image_url
            if not img_url.startswith(('http://', 'https://')):
                 img_url = get_image_url(kb_id, img_url)
            return f'<img src="{img_url}" width="300" alt="图片">'
            
        updated_content = re.sub(pattern, replace_img, content)
        
        # 写回文件
        f.seek(0)
        f.write(updated_content)
        f.truncate()

    return updated_content

if __name__ == "__main__":
    pdf_file = "demo2.pdf"  # 替换为实际PDF路径
    process_pdf_with_minerU(pdf_file)

