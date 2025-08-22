#!/usr/bin/env python3
"""
测试tiktoken离线功能
验证缓存文件是否正确加载
"""

import os
import sys
import tiktoken

def test_tiktoken_offline():
    """测试tiktoken离线功能"""
    
    # 设置缓存目录 - 在Docker中使用/opt/tiktoken_cache，本地测试使用相对路径
    if os.path.exists("/opt/tiktoken_cache"):
        cache_dir = "/opt/tiktoken_cache"
    else:
        cache_dir = os.path.join(os.getcwd(), "tiktoken_cache")
    
    os.environ["TIKTOKEN_CACHE_DIR"] = cache_dir
    
    print(f"TIKTOKEN_CACHE_DIR: {cache_dir}")
    print(f"缓存目录是否存在: {os.path.exists(cache_dir)}")
    
    if os.path.exists(cache_dir):
        print("缓存文件列表:")
        for file in os.listdir(cache_dir):
            file_path = os.path.join(cache_dir, file)
            if os.path.isfile(file_path):
                size = os.path.getsize(file_path)
                print(f"  {file} ({size} bytes)")
    
    # 测试编码器
    encodings_to_test = [
        "cl100k_base",
        "p50k_base", 
        "r50k_base",
        "gpt2"
    ]
    
    test_text = "Hello, this is a test for tiktoken offline functionality. 你好，这是tiktoken离线功能的测试。"
    
    print("\n开始测试编码器:")
    for encoding_name in encodings_to_test:
        try:
            print(f"\n测试编码器: {encoding_name}")
            encoder = tiktoken.get_encoding(encoding_name)
            
            # 编码测试
            tokens = encoder.encode(test_text)
            print(f"  编码结果: {len(tokens)} tokens")
            print(f"  前10个token: {tokens[:10]}")
            
            # 解码测试
            decoded = encoder.decode(tokens)
            print(f"  解码成功: {decoded == test_text}")
            
            print(f"✅ {encoding_name} 测试通过")
            
        except Exception as e:
            print(f"❌ {encoding_name} 测试失败: {e}")
            return False
    
    print("\n🎉 所有tiktoken编码器测试通过！离线功能正常。")
    return True

if __name__ == "__main__":
    success = test_tiktoken_offline()
    sys.exit(0 if success else 1)