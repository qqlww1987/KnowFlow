#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import os
import json
from dotenv import load_dotenv


def _setup_argparser():
    """设置命令行参数解析器"""
    parser = argparse.ArgumentParser(description='处理PDF文件，提取图片并创建RAGFlow知识库')
    parser.add_argument('--pdf_path', help='PDF文件路径')
    parser.add_argument('--api_key', help='RAGFlow API密钥（可选，默认从环境变量获取）')
    parser.add_argument('--skip_ragflow', action='store_true', help='跳过创建RAGFlow知识库，只处理图片')
    return parser.parse_args()

def _validate_environment():
    """验证环境变量配置"""
    load_dotenv("../../.env")
    api_key = os.getenv('RAGFLOW_API_KEY')
    server_ip = os.getenv('RAGFLOW_SERVER_IP')
    
    if not server_ip:
        raise ValueError("错误：请在.env文件中设置RAGFLOW_SERVER_IP或使用--server_ip参数指定。")
    
    return api_key, server_ip

def _process_pdf(pdf_path, api_key, server_ip, skip_ragflow=False):
    """处理PDF文件的主要逻辑"""
    image_dir = 'output/images'
    
   
    from mineru_test import process_pdf_with_minerU
    md_file_path = process_pdf_with_minerU(pdf_path)

    if skip_ragflow:
        print("已跳过创建RAGFlow知识库")
        print("\n处理完成！")
        print(f"- 图片已保存到: {image_dir}")
        return

    if not api_key:
        raise ValueError("错误：未提供RAGFlow API密钥，请通过--api_key参数或在.env文件中设置RAGFLOW_API_KEY")

    from ragflow_build import create_ragflow_resources
    create_ragflow_resources(md_file_path, pdf_path, image_dir, api_key, server_ip)
    
    print(f"\n全部任务处理完成！")

def main():
    # 加载环境变量
    load_dotenv()
    
    try:
        # 解析命令行参数
        args = _setup_argparser()
        
        # 验证环境
        api_key, server_ip = _validate_environment()
        
        # 处理PDF
        _process_pdf(
            pdf_path=args.pdf_path,
            api_key=api_key,
            server_ip=server_ip,
            skip_ragflow=args.skip_ragflow
        )
        
    except Exception as e:
        print(f"处理过程中出现错误：{str(e)}")
        raise

if __name__ == "__main__":
    main()