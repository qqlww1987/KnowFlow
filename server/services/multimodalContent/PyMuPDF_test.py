import fitz  # PyMuPDF
import os
import uuid
import shutil
import sys
from PIL import Image
import io


def process_pdf_with_PyMuPDF(pdf_file_path, server_base="http://172.21.4.35:8000/"):
    """
    使用PyMuPDF处理PDF文件的主方法
    参数:
    - pdf_file_path: PDF文件路径
    - server_base: 服务器基础URL
    返回:
    - 增强文本的Markdown文件路径
    """
    # 从server_base中提取server_ip
    server_ip = server_base.split("//")[1].split(":")[0]
    
    # 调用原有方法处理PDF
    enhanced_text, extracted_images = extract_images_from_pdf(
        pdf_file_path, 
        image_server_dir="./images",
        server_ip=server_ip
    )
    
    # 复制图片到服务器目录
    copy_images_to_server(extracted_images, "./images")

    return enhanced_text


def extract_images_from_pdf(pdf_path, image_server_dir="./images", image_server_url=None, server_ip=None):
    """
    提取PDF中的图片和文本，返回带有图片位置标记的增强文本
    
    参数:
    - pdf_path: PDF文件路径
    - image_server_dir: 图片服务器的图片存储目录
    - image_server_url: 图片服务器URL前缀（如果为None，则会根据server_ip自动构建）
    - server_ip: 图片服务器IP地址（必须提供）
    """
    # 检查是否提供了server_ip
    if server_ip is None:
        raise ValueError("必须提供图片服务器IP地址(server_ip)。请在.env文件中设置RAGFLOW_SERVER_IP或通过--server_ip参数指定。")

    # 如果没有提供image_server_url，使用server_ip构建
    if image_server_url is None:
        image_server_url = f"http://{server_ip}:8000/images"
    
    print(f"正在处理PDF: {pdf_path}")
    print(f"使用图片服务器URL: {image_server_url}")
    
    # 确保本地临时目录存在
    os.makedirs("temp_images", exist_ok=True)
    
    # 提前声明变量，以确保在异常处理中可以访问
    doc = None
    extracted_text = []
    extracted_images = []
    page_count = 0
    
    try:
        # 先尝试打开PDF并提取所有内容，避免多次操作PDF对象
        doc = fitz.open(pdf_path)
        page_count = len(doc)
        print(f"PDF打开成功，共{page_count}页")
        
        # 一次性提取所有页面的文本和图片
        for page_idx in range(page_count):
            page = doc[page_idx]
            print(f"处理第{page_idx+1}页...")
            
            # 获取页面文本
            text = page.get_text()
            extracted_text.append({"page": page_idx+1, "text": text})
            
            # 提取图片
            image_list = page.get_images(full=True)
            print(f"第{page_idx+1}页发现{len(image_list)}张图片")
            
            # 处理当前页的图片
            for img_idx, img in enumerate(image_list):
                try:
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    
                    # 生成唯一图片名称
                    image_filename = f"page{page_idx+1}_img{img_idx+1}_{uuid.uuid4().hex[:8]}.png"
                    
                    # 保存图片临时文件
                    temp_path = os.path.join("temp_images", image_filename)
                    
                    with open(temp_path, "wb") as f:
                        f.write(image_bytes)
                    
                    # 构建图片URL
                    image_url = f"{image_server_url}/{image_filename}"
                    
                    # 记录图片信息
                    extracted_images.append({
                        "filename": image_filename,
                        "temp_path": temp_path,
                        "page": page_idx + 1,
                        "content_type": base_image["ext"],
                        "url": image_url
                    })
                    print(f"成功提取并保存图片: {image_filename}")
                except Exception as e:
                    print(f"提取图片出错: {str(e)}")
        
        # 关闭文档，防止后续引用出错
        doc.close()
        doc = None
        
        # 现在我们有了所有的文本和图片，开始构建增强文本
        enhanced_text = []
        
        # 检查是否为维修案例文档
        is_maintenance_doc = any("设备名称" in page_data["text"] for page_data in extracted_text)
        
        if is_maintenance_doc:
            print("检测到维修案例文档格式")
            # 对于机械维修案例，每页是一个独立的案例，添加页面分隔符
            for page_data in extracted_text:
                page_num = page_data["page"]
                page_text = page_data["text"].strip()
                
                # 添加页面标题
                enhanced_text.append(f"## 维修案例 {page_num}\n")
                
                # 添加文本
                enhanced_text.append(page_text)
                
                # 查找该页的图片
                page_images = [img for img in extracted_images if img["page"] == page_num]
                
                # 添加图片
                if page_images:
                    enhanced_text.append("\n### 相关图片\n")
                    for img in page_images:
                        enhanced_text.append(f"\n<img src=\"{img['url']}\" alt=\"维修图片\" width=\"300\">\n")
                
                # 添加页面分隔
                enhanced_text.append("\n---\n")
        else:
            # 一般文档处理
            print("使用一般文档格式处理")
            for page_data in extracted_text:
                page_num = page_data["page"]
                page_text = page_data["text"].strip()
                
                # 添加文本
                paragraphs = page_text.split('\n\n')
                for para in paragraphs:
                    if para.strip():
                        enhanced_text.append(para.strip())
                
                # 查找该页的图片
                page_images = [img for img in extracted_images if img["page"] == page_num]
                
                # 添加图片
                if page_images:
                    for img in page_images:
                        enhanced_text.append(f"\n<img src=\"{img['url']}\" alt=\"文档图片\" width=\"300\">\n")
        
        return "\n".join(enhanced_text), extracted_images
    
    except Exception as e:
        print(f"处理PDF文件出错: {str(e)}")
        
        # 如果已经提取了图片，尝试只使用图片构建文本
        if extracted_images:
            print("使用已提取的图片构建文本...")
            enhanced_text = []
            
            for page_num in range(1, page_count + 1):
                page_images = [img for img in extracted_images if img["page"] == page_num]
                
                if page_images:
                    enhanced_text.append(f"## 第{page_num}页图片\n")
                    for img in page_images:
                        enhanced_text.append(f"\n<img src=\"{img['url']}\" alt=\"图片\" width=\"300\">\n")
            
            if enhanced_text:
                return "\n".join(enhanced_text), extracted_images
        
        # 处理PDF失败但有图片，则直接将图片作为文档
        if os.path.exists(pdf_path):
            try:
                img = Image.open(pdf_path)
                img_filename = f"document_image_{uuid.uuid4().hex[:8]}.png"
                temp_path = os.path.join("temp_images", img_filename)
                img.save(temp_path)
                
                image_url = f"{image_server_url}/{img_filename}"
                
                img_info = {
                    "filename": img_filename,
                    "temp_path": temp_path,
                    "page": 1,
                    "content_type": "png",
                    "url": image_url
                }
                
                extracted_images = [img_info]
                return f"<img src=\"{image_url}\" alt=\"图片\" width=\"300\">", extracted_images
            except:
                pass
        
        # 如果所有尝试都失败
        raise Exception(f"无法处理文件: {pdf_path}, 原因: {str(e)}")
    finally:
        # 确保文档已关闭
        if doc:
            try:
                doc.close()
            except:
                pass

def copy_images_to_server(extracted_images, target_dir="./images"):
    """
    将提取的图片复制到图片服务器的目录
    
    参数:
    - extracted_images: 从PDF提取的图片信息列表
    - target_dir: 图片服务器的图片存储目录
    """
    os.makedirs(target_dir, exist_ok=True)
    
    for img_info in extracted_images:
        source_path = img_info["temp_path"]
        target_path = os.path.join(target_dir, img_info["filename"])
        
        # 复制图片到图片服务器目录
        shutil.copy(source_path, target_path)
    
    print(f"已将{len(extracted_images)}张图片复制到图片服务器目录: {target_dir}")
