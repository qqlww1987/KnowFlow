#!/usr/bin/env python3
"""
Model download script for Docker build
Downloads both pipeline and VLM models for offline deployment
"""

import os
import sys
from loguru import logger

def download_models():
    """Download all required models for offline deployment"""
    try:
        # Set model source from environment or default to modelscope
        model_source = os.environ.get('MINERU_MODEL_SOURCE', 'modelscope')
        os.environ['MINERU_MODEL_SOURCE'] = model_source
        
        logger.info(f'开始下载模型，使用源: {model_source}')
        
        # Import after setting environment
        from mineru.cli.models_download import download_pipeline_models, download_vlm_models
        
        # Download pipeline models
        logger.info('开始下载Pipeline模型...')
        download_pipeline_models()
        logger.info('Pipeline模型下载完成')
        
        # Download VLM models
        logger.info('开始下载VLM模型...')
        download_vlm_models()
        logger.info('VLM模型下载完成')
        
        logger.info('所有模型下载完成，镜像已实现完全离线部署')
        return True
        
    except Exception as e:
        logger.error(f'模型下载失败: {e}')
        return False

if __name__ == "__main__":
    success = download_models()
    sys.exit(0 if success else 1) 