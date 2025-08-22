#!/usr/bin/env python3
"""
下载tiktoken缓存文件用于离线环境
预下载常用的tiktoken编码文件，避免在离线环境中无法下载
"""

import os
import tiktoken

def download_tiktoken_files():
    """下载所有常用的tiktoken编码文件"""
    
    # 设置缓存目录 - 在Docker中使用/opt/tiktoken_cache，本地测试使用相对路径
    if os.path.exists("/opt") and os.access("/opt", os.W_OK):
        cache_dir = "/opt/tiktoken_cache"
    else:
        cache_dir = os.path.join(os.getcwd(), "tiktoken_cache")
    
    os.makedirs(cache_dir, exist_ok=True)
    
    # 设置环境变量
    os.environ["TIKTOKEN_CACHE_DIR"] = cache_dir
    
    print(f"开始下载tiktoken编码文件到: {cache_dir}")
    
    # 常用的编码器列表
    encodings = [
        "cl100k_base"
    ]
    
    for encoding_name in encodings:
        try:
            print(f"下载编码器: {encoding_name}")
            encoder = tiktoken.get_encoding(encoding_name)
            # 触发下载
            test_tokens = encoder.encode("test")
            print(f"✅ {encoding_name} 下载完成")
        except Exception as e:
            print(f"❌ {encoding_name} 下载失败: {e}")
    
    print("\n🎉 tiktoken编码文件下载完成！")
    
    # 显示下载的文件
    if os.path.exists(cache_dir):
        print(f"\n缓存文件列表 ({cache_dir}):")
        for file in os.listdir(cache_dir):
            file_path = os.path.join(cache_dir, file)
            if os.path.isfile(file_path):
                size = os.path.getsize(file_path)
                print(f"  {file} ({size} bytes)")

if __name__ == "__main__":
    download_tiktoken_files()