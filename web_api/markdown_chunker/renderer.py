"""
分块内容渲染器

负责将 ChunkInfo（中间表示）渲染为最终的 Markdown 字符串，
包括标题链处理、上下文增强、格式清理等。
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from .ast_utils import build_header_chain
from .models import ChunkInfo, NodeInfo


# ---------------------------------------------------------------------------
# 标题链格式清理
# ---------------------------------------------------------------------------

def clean_header_chain(
    header_chain: Optional[str],
    *,
    use_indentation: bool = False,
) -> Optional[str]:
    """
    清理标题链，可选使用缩进替代标题符号。

    Args:
        header_chain: 原始标题链，如 "# H1\n## H2"
        use_indentation: True 时用缩进表示层级，False 时完全移除 # 符号

    Returns:
        清理后的标题链
    """
    if not header_chain:
        return None
    clean_lines: List[str] = []
    for line in header_chain.split("\n"):
        line = line.strip()
        if not line:
            continue

        level = line.count("#")
        title = line.split(" ", 1)[1] if " " in line else line

        if use_indentation:
            clean_lines.append(f"{'  ' * (level - 1)}{title}")
        else:
            clean_lines.append(title)

    return "\n".join(clean_lines)


def format_header_for_context(
    headers: Dict[int, str],
    *,
    use_indentation: bool = True,
) -> Optional[str]:
    """
    将标题字典格式化为上下文字符串。

    Args:
        headers: 标题层级映射
        use_indentation: 是否使用缩进格式

    Returns:
        格式化后的标题上下文，或 None
    """
    chain = build_header_chain(headers)
    return clean_header_chain(chain, use_indentation=use_indentation)


# ---------------------------------------------------------------------------
# 上下文标题选择策略
# ---------------------------------------------------------------------------

def select_context_header(
    headers: Dict[int, str],
    chunk_type: str = "normal",
) -> Optional[str]:
    """
    根据分块类型选择最相关的上下文标题。

    目前所有类型都返回最深标题，但保留扩展接口以便未来差异化。
    """
    if not headers:
        return None
    max_level = max(headers.keys())
    return f"{'#' * max_level} {headers[max_level]}"


def build_context_for_chunk(
    chunk: ChunkInfo,
    *,
    use_indentation: bool = True,
) -> Optional[str]:
    """
    为分块构建标题上下文。

    策略：
    - 如果分块本身以标题开头，只添加上级标题作为上下文
    - 如果分块不以标题开头，添加完整标题链
    - 已包含 context 节点的 small_enhanced 分块不再额外添加
    """
    nodes = chunk.nodes
    headers = chunk.headers
    chunk_type = chunk.chunk_type

    if not headers:
        return None

    # 已包含 context 节点的分块不额外添加上下文
    if nodes and nodes[0].node_type == "context":
        return None

    # 检查分块是否以标题开始
    starts_with_heading = bool(nodes) and nodes[0].node_type == "heading"
    first_heading_level = nodes[0].level if starts_with_heading else None

    # 特殊类型分块：使用最相关的标题
    if chunk_type in ("split_from_oversized", "small_enhanced"):
        header = select_context_header(headers, chunk_type)
        return clean_header_chain(header, use_indentation=use_indentation)

    # 正常分块
    if starts_with_heading and first_heading_level:
        # 只添加父级标题
        parent_headers = {
            level: title
            for level, title in headers.items()
            if level < first_heading_level
        }
        chain = build_header_chain(parent_headers)
    else:
        # 添加完整标题链
        chain = build_header_chain(headers)

    return clean_header_chain(chain, use_indentation=use_indentation)


# ---------------------------------------------------------------------------
# 主渲染函数
# ---------------------------------------------------------------------------

def render_chunk(chunk: ChunkInfo) -> str:
    """
    将 ChunkInfo 渲染为最终的 Markdown 字符串。

    这是唯一的渲染入口，替代原来的 _render_header_chunk 和
    _render_header_chunk_advanced。

    渲染流程：
    1. 根据分块类型和结构决定是否需要添加上下文标题
    2. 清理并拼接所有节点内容
    3. 返回格式化后的最终内容
    """
    nodes = chunk.nodes

    if not nodes:
        return ""

    content_parts: List[str] = []

    # 步骤1：构建并添加上下文标题（避免重复）
    context = build_context_for_chunk(chunk, use_indentation=True)
    if context:
        content_parts.append(context)

    # 步骤2：渲染所有节点内容
    for node in nodes:
        content = node.content.strip()
        if not content:
            continue

        if node.node_type in ("heading", "context"):
            # 标题/context 节点：清理 # 符号，保留纯文本
            cleaned = clean_header_chain(content, use_indentation=False)
            content_parts.append(cleaned or content)
        else:
            content_parts.append(content)

    return "\n\n".join(content_parts).strip()


def render_simple_chunk(
    nodes: List[NodeInfo],
    context_stack: Optional[List[Dict[str, str]]] = None,
) -> str:
    """
    简单渲染：直接拼接节点内容，不做标题上下文增强。

    适用于子分块等场景。
    """
    parts = [n.content.strip() for n in nodes if n.content.strip()]
    return "\n\n".join(parts).strip()
