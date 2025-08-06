#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模型下载脚本
用于在 Docker 构建时预下载所有必要的模型
"""

import os
import json
import sys
import logging
from pathlib import Path
from typing import Dict, Any

try:
    from huggingface_hub import snapshot_download, login
    from transformers import AutoTokenizer, AutoModel
except ImportError as e:
    print(f"导入错误: {e}")
    print("请安装必要的依赖: pip install transformers huggingface_hub")
    sys.exit(1)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ModelDownloader:
    def __init__(self, config_path: str = "/app/config/models.json"):
        self.config_path = config_path
        self.config = self.load_config()
        
    def load_config(self) -> Dict[str, Any]:
        """加载模型配置"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"配置文件未找到: {self.config_path}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            logger.error(f"配置文件格式错误: {e}")
            sys.exit(1)
    
    def setup_hf_token(self):
        """设置 Hugging Face Token（如果存在）"""
        hf_token = os.getenv('HF_TOKEN')
        if hf_token:
            logger.info("使用 Hugging Face Token 进行认证")
            login(token=hf_token)
        else:
            logger.info("未设置 HF_TOKEN，使用公开模型")
    
    def download_chat_model(self, model_config: Dict[str, Any]):
        """下载对话模型"""
        model_name = model_config['name']
        model_path = model_config['path']
        
        logger.info(f"开始下载对话模型: {model_name}")
        
        # 创建目录
        os.makedirs(model_path, exist_ok=True)
        
        try:
            # 下载 Qwen3-32B 模型
            repo_id = f"Qwen/{model_name}"
            logger.info(f"从 {repo_id} 下载模型到 {model_path}")
            
            snapshot_download(
                repo_id=repo_id,
                local_dir=model_path,
                local_dir_use_symlinks=False,
                resume_download=True,
                ignore_patterns=[
                    "*.bin",  # 忽略旧格式的权重文件
                    "*.pth",
                    "*.pt",
                    "*.onnx",
                    "*.tflite"
                ]
            )
            
            # 验证下载
            self.verify_model(model_path, "chat")
            logger.info(f"对话模型 {model_name} 下载完成")
            
        except Exception as e:
            logger.error(f"下载对话模型失败: {e}")
            raise
    
    def download_embedding_model(self, model_config: Dict[str, Any]):
        """下载嵌入模型"""
        model_name = model_config['name']
        model_path = model_config['path']
        
        logger.info(f"开始下载嵌入模型: {model_name}")
        
        # 创建目录
        os.makedirs(model_path, exist_ok=True)
        
        try:
            # 下载 bge-m3 模型
            repo_id = f"BAAI/{model_name}"
            logger.info(f"从 {repo_id} 下载模型到 {model_path}")
            
            snapshot_download(
                repo_id=repo_id,
                local_dir=model_path,
                local_dir_use_symlinks=False,
                resume_download=True
            )
            
            # 验证下载
            self.verify_model(model_path, "embedding")
            logger.info(f"嵌入模型 {model_name} 下载完成")
            
        except Exception as e:
            logger.error(f"下载嵌入模型失败: {e}")
            raise
    
    def download_rerank_model(self, model_config: Dict[str, Any]):
        """下载重排序模型"""
        model_name = model_config['name']
        model_path = model_config['path']
        
        logger.info(f"开始下载重排序模型: {model_name}")
        
        # 创建目录
        os.makedirs(model_path, exist_ok=True)
        
        try:
            # 下载 bge-reranker-v2-m3 模型
            repo_id = f"BAAI/{model_name}"
            logger.info(f"从 {repo_id} 下载模型到 {model_path}")
            
            snapshot_download(
                repo_id=repo_id,
                local_dir=model_path,
                local_dir_use_symlinks=False,
                resume_download=True
            )
            
            # 验证下载
            self.verify_model(model_path, "rerank")
            logger.info(f"重排序模型 {model_name} 下载完成")
            
        except Exception as e:
            logger.error(f"下载重排序模型失败: {e}")
            raise
    
    def verify_model(self, model_path: str, model_type: str):
        """验证模型文件完整性"""
        required_files = {
            "chat": ["config.json", "tokenizer.json", "tokenizer_config.json"],
            "embedding": ["config.json", "tokenizer.json"],
            "rerank": ["config.json", "tokenizer.json"]
        }
        
        missing_files = []
        for file_name in required_files.get(model_type, []):
            file_path = os.path.join(model_path, file_name)
            if not os.path.exists(file_path):
                missing_files.append(file_name)
        
        if missing_files:
            raise FileNotFoundError(f"模型文件不完整，缺少: {missing_files}")
        
        # 检查权重文件
        weight_files = list(Path(model_path).glob("*.safetensors")) + \
                      list(Path(model_path).glob("model*.bin"))
        
        if not weight_files:
            raise FileNotFoundError("未找到模型权重文件")
        
        logger.info(f"模型验证通过: {model_path}")
    
    def download_all_models(self):
        """下载所有模型"""
        logger.info("开始下载所有模型...")
        
        # 设置 HF Token
        self.setup_hf_token()
        
        models = self.config.get('models', {})
        
        # 下载各类型模型
        download_methods = {
            'chat': self.download_chat_model,
            'embedding': self.download_embedding_model,
            'rerank': self.download_rerank_model
        }
        
        for model_type, model_config in models.items():
            if model_type in download_methods:
                try:
                    download_methods[model_type](model_config)
                except Exception as e:
                    logger.error(f"下载 {model_type} 模型失败: {e}")
                    raise
            else:
                logger.warning(f"未知的模型类型: {model_type}")
        
        logger.info("所有模型下载完成！")
    
    def get_total_size(self):
        """计算所有模型的总大小"""
        total_size = 0
        models = self.config.get('models', {})
        
        for model_type, model_config in models.items():
            model_path = model_config['path']
            if os.path.exists(model_path):
                for root, dirs, files in os.walk(model_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        if os.path.exists(file_path):
                            total_size += os.path.getsize(file_path)
        
        return total_size

def main():
    """主函数"""
    try:
        downloader = ModelDownloader()
        downloader.download_all_models()
        
        # 显示总大小
        total_size = downloader.get_total_size()
        size_gb = total_size / (1024**3)
        logger.info(f"模型总大小: {size_gb:.2f} GB")
        
    except Exception as e:
        logger.error(f"模型下载失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()