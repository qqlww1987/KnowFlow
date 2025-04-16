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
    parser.add_argument('--pdf_path', help='PDF文件路径')
    parser.add_argument('--api_key', help='RAGFlow API密钥（可选，默认从环境变量获取）')
    parser.add_argument('--skip_ragflow', action='store_true', help='跳过创建RAGFlow知识库，只处理图片')

    
    args = parser.parse_args()

    api_key =  os.getenv('RAGFLOW_API_KEY')
    server_ip = os.getenv('RAGFLOW_SERVER_IP')

    # 文件路径
    pdf_path = args.pdf_path

    # 图片目录
    image_dir = 'output/images'

    if not server_ip:
        raise ValueError("错误：请在.env文件中设置RAGFLOW_SERVER_IP或使用--server_ip参数指定。")
    
    print(f"使用图片服务器IP地址: {server_ip}")
    
    try:
       
        print(f"第1步：通过 MinerU 识别文本")
        from mineru_test import process_pdf_with_minerU
        md_file_path = process_pdf_with_minerU(pdf_path)

        # 如果设置了--skip_ragflow参数，跳过创建RAGFlow知识库
        if args.skip_ragflow:
            print("已跳过创建RAGFlow知识库")
            print("\n处理完成！")
            print(f"- 图片已保存到: {args.image_dir}")
            return
        
        # 检查API密钥
        if not api_key:
            print("错误：未提供RAGFlow API密钥，请通过--api_key参数或在.env文件中设置RAGFLOW_API_KEY")
            return
        
        # 使用纯文本方式创建RAGFlow知识库和助手
        from ragflow_build import create_ragflow_resources
        create_ragflow_resources(md_file_path, pdf_path, image_dir,api_key, server_ip)
        
        print(f"\n处理完成！")
    
       
    except Exception as e:
        print(f"处理过程中出现错误：{str(e)}")
        # 保存已提取的图片和文本，即使处理过程中出错


if __name__ == "__main__":
    main() 