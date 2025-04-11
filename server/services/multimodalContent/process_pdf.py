#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import os
import json
from dotenv import load_dotenv


def main():
    # 加载.env文件中的环境变量
    load_dotenv()
    
    parser = argparse.ArgumentParser(description='处理PDF文件，提取图片并创建RAGFlow知识库')
    parser.add_argument('pdf_path', help='PDF文件路径')
    parser.add_argument('--api_key', help='RAGFlow API密钥（可选，默认从环境变量获取）')
    parser.add_argument('--image_dir', default='./images', help='本地图片存储目录，默认为./images')
    parser.add_argument('--mount_dir', default='/app/images', help='图片服务器容器内的挂载目录，默认为/app/images')
    parser.add_argument('--skip_ragflow', action='store_true', help='跳过创建RAGFlow知识库，只处理图片')
    parser.add_argument('--server_ip', help='图片服务器IP地址（可选，默认从环境变量RAGFLOW_SERVER_IP获取）')
    parser.add_argument('--doc_engine', help='文档解析器')
    
    args = parser.parse_args()
    
    # 确保本地图片目录存在
    os.makedirs(args.image_dir, exist_ok=True)
    
    # 优先使用命令行参数的API密钥，其次使用环境变量
    api_key = args.api_key or os.getenv('RAGFLOW_API_KEY')
    
    # 获取服务器IP地址，优先使用命令行参数，其次使用环境变量
    server_ip = args.server_ip or os.getenv('RAGFLOW_SERVER_IP')

    # 文档引擎
    doc_engine = args.doc_engine or os.getenv('DOC_ENGINE')

    if not server_ip:
        raise ValueError("错误：未提供图片服务器IP地址。请在.env文件中设置RAGFLOW_SERVER_IP或使用--server_ip参数指定。")
    
    print(f"使用图片服务器IP地址: {server_ip}")
    
    try:
        # 提取图片和增强文本
        print(f"第1步：处理PDF并提取内容以及图片...")

        if doc_engine == 'PyMuPDF':
            print(f"第1步：使用PyMuPDF处理PDF...")
            # 导入PyMuPDF处理函数
            from PyMuPDF_test import process_pdf_with_PyMuPDF
            enhanced_text = process_pdf_with_PyMuPDF(args.pdf_path, f"http://{server_ip}:8000/")
        elif doc_engine == 'MinerU':
            print(f"第1步：使用MinerU处理PDF...")
            # 导入MinerU处理函数
            from MinerU_test import process_pdf_with_minerU
            enhanced_text = process_pdf_with_minerU(args.pdf_path, f"http://{server_ip}:8000/")

        # 将增强文本保存到本地文件
        text_filename = os.path.splitext(os.path.basename(args.pdf_path))[0] + "_enhanced.txt"
        with open(text_filename, "w", encoding="utf-8") as f:
            f.write(enhanced_text)
        
        print(f"第3步：增强文本已保存到 {text_filename}")
        
        # 如果设置了--skip_ragflow参数，跳过创建RAGFlow知识库
        if args.skip_ragflow:
            print("已跳过创建RAGFlow知识库")
            print("\n处理完成！")
            print(f"- 图片已保存到: {args.image_dir}")
            print(f"- 增强文本已保存到: {text_filename}")
            print("\n请确保您已完成以下步骤：")
            print(f"1. 构建并运行图片服务器容器：docker build -t image-server . && docker run -d -p 8000:8000 -v {os.path.abspath(args.image_dir)}:{args.mount_dir} --name image-server image-server")
            print(f"2. 将图片服务器连接到RAGFlow网络：docker network connect rag-network ragflow-server && docker network connect rag-network image-server")
            return
        
        # 检查API密钥
        if not api_key:
            print("错误：未提供RAGFlow API密钥，请通过--api_key参数或在.env文件中设置RAGFLOW_API_KEY")
            return
        
        print(f"第4步：创建RAGFlow知识库和助手...")
        
        # 使用纯文本方式创建RAGFlow知识库和助手
        from ragflow_build import create_ragflow_resources
        dataset, assistant = create_ragflow_resources(enhanced_text, args.pdf_path, api_key, server_ip=server_ip)
        
        print(f"\n处理完成！")
        print(f"- 图片已保存到: {args.image_dir}")
        print(f"- 增强文本已保存到: {text_filename}")
        print(f"- 知识库ID: {dataset.id}")
        print(f"- 聊天助手ID: {assistant.id}")
        print("\n请确保您已完成以下步骤：")
        print(f"1. 构建并运行图片服务器容器：docker build -t image-server . && docker run -d -p 8000:8000 -v {os.path.abspath(args.image_dir)}:{args.mount_dir} --name image-server image-server")
        print(f"2. 将图片服务器连接到RAGFlow网络：docker network connect rag-network ragflow-server && docker network connect rag-network image-server")
    except Exception as e:
        print(f"处理过程中出现错误：{str(e)}")
        # 保存已提取的图片和文本，即使处理过程中出错
        if 'extracted_images' in locals() and extracted_images:
            print(f"已提取{len(extracted_images)}张图片并保存到{args.image_dir}")
        if 'enhanced_text' in locals() and enhanced_text:
            text_filename = os.path.splitext(os.path.basename(args.pdf_path))[0] + "_enhanced.txt"
            with open(text_filename, "w", encoding="utf-8") as f:
                f.write(enhanced_text)
            print(f"增强文本已保存到{text_filename}")

if __name__ == "__main__":
    main() 