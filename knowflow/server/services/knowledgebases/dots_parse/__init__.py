"""
DOTS OCR 文档解析模块

本模块提供基于DOTS OCR服务的文档解析功能，支持:
- 通过VLLM API进行OCR文档解析
- 统一的分块和坐标处理
- 完全复用MinerU分块策略
- 支持父子分块和高级分块策略
"""

from .dots_fastapi_adapter import get_global_adapter, test_adapter_connection
from .dots_processor import process_dots_result, DOTSProcessor
from .process_document import process_document_with_dots

__all__ = [
    'get_global_adapter',
    'test_adapter_connection', 
    'process_dots_result',
    'DOTSProcessor',
    'process_document_with_dots'
]