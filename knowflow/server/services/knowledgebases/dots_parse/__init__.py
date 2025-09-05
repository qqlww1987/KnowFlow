"""
DOTS OCR 文档解析模块

本模块提供基于DOTS OCR服务的文档解析功能，支持:
- 通过VLLM API进行OCR文档解析
- 智能分页和分块处理
- JSON格式的结构化输出处理
"""

from .dots_fastapi_adapter import get_global_adapter, test_adapter_connection

__all__ = [
    'get_global_adapter',
    'test_adapter_connection'
]