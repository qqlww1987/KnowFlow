"""
Markdown 智能分块器 — 重构版

基于 AST 的高级 Markdown 分块方法，支持：
- 标题层级分块
- 动态大小控制（自动调整阈值）
- 特殊内容保护（表格、代码块、公式）
- 表格按行拆分保留表头
- 智能上下文增强
- 子分块创建
- 父子分块结构

主入口函数：
    split_markdown_to_chunks_advanced - 高级分块（原始接口兼容）
    split_markdown_to_chunks_smart    - 智能分块
    split_markdown_parent_child       - 父子分块

使用示例::

    from markdown_chunker import split_markdown_to_chunks_advanced

    chunks = split_markdown_to_chunks_advanced(
        markdown_text,
        chunk_token_num=1024,
        min_chunk_tokens=10,
        include_metadata=False,
    )
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .chunk_builder import (
    create_sub_chunks,
    optimize_chunks,
    split_by_headers,
)
from .models import ChunkConfig
from .renderer import render_chunk
from .tokenizer import num_tokens, num_tokens_from_string

# ---------------------------------------------------------------------------
# 依赖注入：token 计数器
# ---------------------------------------------------------------------------

def _get_token_counter():
    """获取默认的 token 计数函数"""
    return num_tokens


# ---------------------------------------------------------------------------
# 主入口：高级分块
# ---------------------------------------------------------------------------

def split_markdown_to_chunks_advanced(
    txt: str,
    chunk_token_num: int = 1024,
    min_chunk_tokens: int = 10,
    overlap_ratio: float = 0.0,
    include_metadata: bool = False,
) -> List[str] | List[Dict[str, Any]]:
    """
    基于标题层级的高级 Markdown 分块方法（混合分块策略 + 动态阈值调整）。

    核心特性：
    1. 保持标题作为主要分块边界
    2. 动态大小控制：目标 300-600 tokens，最大 800 tokens，最小 50 tokens
    3. 处理超大分块：在段落边界进一步分割
    4. 处理超小分块：与相邻分块合并
    5. 特殊内容保护：保持表格、代码块、公式完整性
    6. 智能上下文增强

    Args:
        txt: Markdown 文本
        chunk_token_num: 目标分块大小（tokens）
        min_chunk_tokens: 最小分块大小
        overlap_ratio: 重叠比例（当前保留接口，未实现）
        include_metadata: 是否在结果中包含元数据

    Returns:
        分块内容字符串列表，或（当 include_metadata=True 时）包含元数据的字典列表
    """
    if not txt or not txt.strip():
        return []

    config = ChunkConfig(
        chunk_token_num=chunk_token_num,
        min_chunk_tokens=min_chunk_tokens,
        overlap_ratio=overlap_ratio,
    )
    token_counter = _get_token_counter()

    try:
        from .ast_utils import extract_nodes_with_headers, parse_markdown

        # 1. 解析为 AST
        tree = parse_markdown(txt)

        # 2. 提取所有节点和标题信息
        nodes_with_headers = extract_nodes_with_headers(
            tree, config.headers_to_split_on
        )

        # 3. 基于标题层级初步分块
        initial_chunks = split_by_headers(nodes_with_headers, config.headers_to_split_on)

        # 4. 应用动态大小控制和优化
        optimized_chunks = optimize_chunks(initial_chunks, config, token_counter)

        # 5. 渲染最终分块
        final_chunks = []
        for chunk_info in optimized_chunks:
            content = render_chunk(chunk_info)
            if not content.strip():
                continue

            if include_metadata:
                final_chunks.append({
                    "content": content,
                    "metadata": chunk_info.headers,
                    "token_count": token_counter(content),
                    "chunk_type": chunk_info.chunk_type,
                    "has_special_content": chunk_info.has_special_content,
                    "source_sections": chunk_info.source_sections,
                })
            else:
                final_chunks.append(content)

        return final_chunks

    except Exception as e:
        print(f"Advanced header-based parsing failed: {e}, falling back to smart chunking")
        return split_markdown_to_chunks_smart(txt, chunk_token_num, min_chunk_tokens)


# ---------------------------------------------------------------------------
# 智能分块
# ---------------------------------------------------------------------------

def split_markdown_to_chunks_smart(
    txt: str,
    chunk_token_num: int = 256,
    min_chunk_tokens: int = 10,
) -> List[str]:
    """
    基于 AST 的智能分块方法。

    特点：
    - 基于语义切分（使用 AST）
    - 维护表格完整性
    - 考虑 Markdown 父子分块关系
    """
    if not txt or not txt.strip():
        return []

    token_counter = _get_token_counter()

    try:
        from .ast_utils import finalize_chunk, parse_markdown, process_node

        tree = parse_markdown(txt)

        chunks: List[str] = []
        current_parts: List[str] = []
        current_tokens = 0
        context_stack = []

        for node in tree.children or []:
            content, should_break = process_node(
                node, context_stack, heading_breaks=True, table_breaks=True
            )

            # 标题触发分块
            if should_break and current_parts and current_tokens >= min_chunk_tokens:
                chunk_content = finalize_chunk(current_parts)
                if chunk_content.strip():
                    chunks.append(chunk_content)
                current_parts = []
                current_tokens = 0

            if not content:
                continue

            chunk_tokens = token_counter(content)

            # 检查是否需要分块
            if (
                current_tokens + chunk_tokens > chunk_token_num
                and current_parts
                and current_tokens >= min_chunk_tokens
            ):
                chunk_content = finalize_chunk(current_parts)
                if chunk_content.strip():
                    chunks.append(chunk_content)
                current_parts = []
                current_tokens = 0

            current_parts.append(content)
            current_tokens += chunk_tokens

        # 处理最后一块
        if current_parts:
            chunk_content = finalize_chunk(current_parts)
            if chunk_content.strip():
                chunks.append(chunk_content)

        return [c for c in chunks if c.strip()]

    except Exception as e:
        print(f"AST parsing failed: {e}")
        return []


# ---------------------------------------------------------------------------
# 子分块创建
# ---------------------------------------------------------------------------

def create_child_chunks(
    content: str,
    sub_chunk_token_num: int = 256,
    include_metadata: bool = False,
    table_sub_chunk_token_num: int = 320,
) -> List[str] | List[Dict[str, Any]]:
    """
    创建子分段，支持文本和表格使用不同阈值。

    Args:
        content: 父分块内容
        sub_chunk_token_num: 子分块最大 token 数
        include_metadata: 是否包含元数据
        table_sub_chunk_token_num: 表格子分块阈值

    Returns:
        子分块内容列表（字符串或字典）
    """
    token_counter = _get_token_counter()
    parent_tokens = token_counter(content)

    if parent_tokens <= sub_chunk_token_num:
        if include_metadata:
            return [{
                "content": content,
                "type": "child",
                "token_count": parent_tokens,
            }]
        return [content]

    sub_chunks = create_sub_chunks(
        content,
        sub_chunk_token_num=sub_chunk_token_num,
        table_sub_chunk_token_num=table_sub_chunk_token_num,
        token_counter=token_counter,
    )

    if include_metadata:
        return [
            {
                "content": c,
                "type": "child",
                "token_count": token_counter(c),
            }
            for c in sub_chunks
        ]

    return sub_chunks


# ---------------------------------------------------------------------------
# 兼容导出
# ---------------------------------------------------------------------------

__all__ = [
    "split_markdown_to_chunks_advanced",
    "split_markdown_to_chunks_smart",
    "create_child_chunks",
    "num_tokens",
    "num_tokens_from_string",
]
