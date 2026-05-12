"""
Token 计算工具

封装 tiktoken 的调用，提供统一的 token 计数接口，
并支持缓存和异常回退。
"""

from __future__ import annotations

import functools
from typing import Callable, Optional

import tiktoken

# 全局 encoder 实例（延迟初始化避免导入时开销）
_encoder: Optional[tiktoken.Encoding] = None


def get_encoder() -> tiktoken.Encoding:
    """获取全局 encoder 实例（单例模式）"""
    global _encoder
    if _encoder is None:
        _encoder = tiktoken.get_encoding("cl100k_base")
    return _encoder


def num_tokens(text: str, encoding_name: str = "cl100k_base") -> int:
    """
    计算文本的 token 数量。

    Args:
        text: 待计算的文本
        encoding_name: 编码器名称（默认 cl100k_base）

    Returns:
        token 数量，计算失败时返回 0
    """
    if not text:
        return 0
    try:
        enc = tiktoken.get_encoding(encoding_name)
        return len(enc.encode(text))
    except Exception:
        return 0


# 兼容旧接口
num_tokens_from_string = num_tokens


def create_token_counter(
    encoding_name: str = "cl100k_base",
) -> Callable[[str], int]:
    """
    创建一个闭包形式的 token 计数器，避免重复获取 encoder。

    适用于需要高频调用 token 计数的场景（如大批量分块处理）。

    Returns:
        一个接收文本返回 token 数的函数
    """
    enc = tiktoken.get_encoding(encoding_name)

    @functools.lru_cache(maxsize=5000)
    def counter(text: str) -> int:
        if not text:
            return 0
        try:
            return len(enc.encode(text))
        except Exception:
            return 0

    return counter
