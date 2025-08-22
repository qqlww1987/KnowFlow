#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模型下载脚本
支持下载 qwen3-14B、bge-reranker-v2-m3、bge-m3 模型
下载完成后可通过 gpustack 本地加载
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Optional

try:
    from huggingface_hub import snapshot_download, login
except ImportError:
    print("请先安装 huggingface_hub: pip install huggingface_hub")
    sys.exit(1)

# 模型配置
MODEL_CONFIGS = {
    "qwen3-14b": {
        "repo_id": "Qwen/Qwen2.5-14B-Instruct",
        "description": "Qwen2.5 14B 指令微调模型",
        "size": "约 28GB"
    },
    "bge-reranker-v2-m3": {
        "repo_id": "BAAI/bge-reranker-v2-m3",
        "description": "BGE Reranker v2 M3 模型",
        "size": "约 2GB"
    },
    "bge-m3": {
        "repo_id": "BAAI/bge-m3",
        "description": "BGE M3 嵌入模型",
        "size": "约 2GB"
    }
}

class ModelDownloader:
    def __init__(self, base_dir: str = "/var/lib/docker/volumes/gpustack-data/_data/models", hf_token: Optional[str] = None):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.hf_token = hf_token
        
        if self.hf_token:
            login(token=self.hf_token)
    
    def download_model(self, model_name: str, force_download: bool = False) -> bool:
        """
        下载指定模型
        
        Args:
            model_name: 模型名称
            force_download: 是否强制重新下载
            
        Returns:
            bool: 下载是否成功
        """
        if model_name not in MODEL_CONFIGS:
            print(f"错误: 不支持的模型 '{model_name}'")
            print(f"支持的模型: {', '.join(MODEL_CONFIGS.keys())}")
            return False
        
        config = MODEL_CONFIGS[model_name]
        repo_id = config["repo_id"]
        local_dir = self.base_dir / model_name
        
        print(f"\n开始下载模型: {model_name}")
        print(f"模型描述: {config['description']}")
        print(f"预计大小: {config['size']}")
        print(f"Hugging Face 仓库: {repo_id}")
        print(f"本地保存路径: {local_dir}")
        
        # 检查模型是否已存在
        if local_dir.exists() and not force_download:
            print(f"模型已存在于 {local_dir}，使用 --force 强制重新下载")
            return True
        
        try:
            snapshot_download(
                repo_id=repo_id,
                local_dir=str(local_dir),
                local_dir_use_symlinks=False,
                resume_download=True
            )
            print(f"✅ 模型 {model_name} 下载完成")
            
            # 创建模型信息文件
            info_file = local_dir / "model_info.json"
            with open(info_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "model_name": model_name,
                    "repo_id": repo_id,
                    "description": config["description"],
                    "local_path": str(local_dir),
                    "download_complete": True
                }, f, indent=2, ensure_ascii=False)
            
            return True
            
        except Exception as e:
            print(f"❌ 下载模型 {model_name} 失败: {str(e)}")
            return False
    
    def download_models(self, model_names: List[str], force_download: bool = False) -> Dict[str, bool]:
        """
        批量下载模型
        
        Args:
            model_names: 模型名称列表
            force_download: 是否强制重新下载
            
        Returns:
            Dict[str, bool]: 每个模型的下载结果
        """
        results = {}
        
        for model_name in model_names:
            results[model_name] = self.download_model(model_name, force_download)
        
        return results
    
    def list_models(self):
        """列出所有支持的模型"""
        print("\n支持的模型列表:")
        print("=" * 60)
        for name, config in MODEL_CONFIGS.items():
            status = "✅ 已下载" if (self.base_dir / name).exists() else "⏳ 未下载"
            print(f"模型名称: {name}")
            print(f"描述: {config['description']}")
            print(f"大小: {config['size']}")
            print(f"状态: {status}")
            print("-" * 40)
    
    def get_gpustack_config(self) -> str:
        """
        生成 gpustack 模型配置信息
        """
        config_lines = []
        config_lines.append("# GPUStack 模型配置")
        config_lines.append("# 将下载的模型添加到 gpustack 中:")
        config_lines.append("")
        
        for model_name in MODEL_CONFIGS.keys():
            model_path = self.base_dir / model_name
            if model_path.exists():
                config_lines.append(f"# {model_name}:")
                config_lines.append(f"# 模型路径: {model_path.absolute()}")
                config_lines.append(f"# 在 gpustack 界面中添加本地模型，指向上述路径")
                config_lines.append("")
        
        return "\n".join(config_lines)

def main():
    parser = argparse.ArgumentParser(
        description="模型下载脚本 - 支持下载 qwen3-14B、bge-reranker-v2-m3、bge-m3",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python download_models.py --list                    # 列出所有支持的模型
  python download_models.py --all                     # 下载所有模型
  python download_models.py qwen3-14b                 # 下载单个模型
  python download_models.py qwen3-14b bge-m3          # 下载多个模型
  python download_models.py --all --force             # 强制重新下载所有模型
  python download_models.py --config                  # 显示 gpustack 配置信息
        """
    )
    
    parser.add_argument(
        "models",
        nargs="*",
        help="要下载的模型名称"
    )
    
    parser.add_argument(
        "--all",
        action="store_true",
        help="下载所有支持的模型"
    )
    
    parser.add_argument(
        "--list",
        action="store_true",
        help="列出所有支持的模型"
    )
    
    parser.add_argument(
        "--config",
        action="store_true",
        help="显示 gpustack 配置信息"
    )
    
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制重新下载（即使模型已存在）"
    )
    
    parser.add_argument(
        "--base-dir",
        default="/var/lib/docker/volumes/gpustack-data/_data/models",
        help="模型保存的基础目录（默认: /var/lib/docker/volumes/gpustack-data/_data/models）"
    )
    
    parser.add_argument(
        "--hf-token",
        help="Hugging Face 访问令牌（用于私有模型）"
    )
    
    args = parser.parse_args()
    
    # 创建下载器
    downloader = ModelDownloader(args.base_dir, args.hf_token)
    
    # 处理不同的命令
    if args.list:
        downloader.list_models()
        return
    
    if args.config:
        print(downloader.get_gpustack_config())
        return
    
    # 确定要下载的模型
    if args.all:
        models_to_download = list(MODEL_CONFIGS.keys())
    elif args.models:
        models_to_download = args.models
    else:
        parser.print_help()
        return
    
    # 下载模型
    print(f"准备下载 {len(models_to_download)} 个模型...")
    results = downloader.download_models(models_to_download, args.force)
    
    # 显示结果
    print("\n下载结果:")
    print("=" * 40)
    success_count = 0
    for model_name, success in results.items():
        status = "✅ 成功" if success else "❌ 失败"
        print(f"{model_name}: {status}")
        if success:
            success_count += 1
    
    print(f"\n总计: {success_count}/{len(results)} 个模型下载成功")
    
    if success_count > 0:
        print("\n下载完成！现在可以在 gpustack 中添加这些本地模型。")
        print("使用 --config 参数查看具体配置信息。")

if __name__ == "__main__":
    main()