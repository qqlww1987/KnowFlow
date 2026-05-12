"""
AST 解析与节点处理工具

提供 Markdown 到 AST 的解析、节点内容提取、渲染、
标题上下文栈维护等底层操作。
"""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from markdown_it import MarkdownIt
from markdown_it.tree import SyntaxTreeNode

from .models import HeaderContext, NodeInfo


# ---------------------------------------------------------------------------
# Markdown 解析
# ---------------------------------------------------------------------------

def create_parser() -> MarkdownIt:
    """创建配置好的 markdown-it 解析器"""
    md = MarkdownIt("commonmark", {"breaks": True, "html": True})
    md.enable(["table"])
    return md


def parse_markdown(text: str) -> SyntaxTreeNode:
    """解析 Markdown 文本为 AST"""
    md = create_parser()
    tokens = md.parse(text)
    return SyntaxTreeNode(tokens)


# ---------------------------------------------------------------------------
# 标题上下文栈
# ---------------------------------------------------------------------------

def update_context_stack(
    stack: List[HeaderContext],
    level: int,
    title: str,
) -> None:
    """
    更新标题上下文栈。

    移除比当前级别更深或同级的标题，然后添加当前标题。
    """
    while stack and stack[-1].level >= level:
        stack.pop()
    stack.append(HeaderContext(level=level, title=title))


def build_header_chain(headers: Dict[int, str]) -> Optional[str]:
    """
    根据标题层级字典构建完整的标题链（Markdown 格式）。

    Args:
        headers: {级别: 标题文本} 的字典

    Returns:
        如 "# H1标题\n## H2标题" 的多行字符串，或 None
    """
    if not headers:
        return None
    sorted_levels = sorted(headers.keys())
    return "\n".join(
        f"{'#' * level} {headers[level]}"
        for level in sorted_levels
    )


def get_deepest_header(headers: Dict[int, str]) -> Optional[str]:
    """获取最深（最具体）的标题作为上下文"""
    if not headers:
        return None
    max_level = max(headers.keys())
    return f"{'#' * max_level} {headers[max_level]}"


# ---------------------------------------------------------------------------
# 节点文本提取
# ---------------------------------------------------------------------------

def extract_text(node: SyntaxTreeNode) -> str:
    """
    从 AST 节点递归提取文本内容，保留内联格式标记。

    支持：text、code_inline、strong、em、link 等内联节点。
    """
    # html_block 直接返回 content（它有 children 属性但 children 为空）
    if node.type == "html_block" and node.content:
        return node.content

    if hasattr(node, "content") and node.content and not hasattr(node, "children"):
        return node.content

    # 叶子节点直接返回
    if node.type in ("text", "code_inline"):
        return node.content

    parts: List[str] = []
    children = getattr(node, "children", []) or []

    for child in children:
        child_type = getattr(child, "type", "")
        if child_type == "text":
            parts.append(child.content)
        elif child_type == "code_inline":
            parts.append(f"`{child.content}`")
        elif child_type == "strong":
            parts.append(f"**{extract_text(child)}**")
        elif child_type == "em":
            parts.append(f"*{extract_text(child)}*")
        elif child_type == "link":
            link_text = extract_text(child)
            href = child.attrGet("href") or "" if hasattr(child, "attrGet") else ""
            parts.append(f"[{link_text}]({href})")
        elif child_type == "image":
            # 保留图片的 Markdown 语法: ![alt](src)
            alt_text = extract_text(child)
            src = ""
            if hasattr(child, "attrGet"):
                src = child.attrGet("src") or ""
            parts.append(f"![{alt_text}]({src})")
        elif child_type:
            parts.append(extract_text(child))

    return "".join(parts)


# ---------------------------------------------------------------------------
# 节点内容渲染
# ---------------------------------------------------------------------------

def render_table(node: SyntaxTreeNode) -> str:
    """
    从 AST 表格节点渲染为 Markdown 格式文本。

    注意：返回 Markdown 格式而非 HTML，由调用方决定是否需要进一步转换。
    """
    table_md: List[str] = []

    for child in node.children or []:
        if child.type == "thead":
            for row in child.children or []:
                if row.type == "tr":
                    cells = []
                    for cell in row.children or []:
                        if cell.type in ("th", "td"):
                            cells.append(extract_text(cell))
                    table_md.append("| " + " | ".join(cells) + " |")

            # 添加分隔符
            if table_md:
                col_count = len(table_md[-1].split("|")) - 2
                table_md.append("| " + " | ".join(["---"] * col_count) + " |")

        elif child.type == "tbody":
            for row in child.children or []:
                if row.type == "tr":
                    cells = []
                    for cell in row.children or []:
                        if cell.type in ("th", "td"):
                            cells.append(extract_text(cell))
                    table_md.append("| " + " | ".join(cells) + " |")

    return "\n".join(table_md)


def render_code_block(node: SyntaxTreeNode) -> str:
    """渲染代码块"""
    info = getattr(node, "info", "") or ""
    content = getattr(node, "content", "") or ""
    return f"```{info}\n{content}```"


def render_blockquote(node: SyntaxTreeNode) -> str:
    """渲染引用块"""
    content = extract_text(node)
    return "\n".join(f"> {line}" for line in content.split("\n"))


def render_list(node: SyntaxTreeNode) -> str:
    """渲染列表（有序/无序）"""
    items: List[str] = []
    list_type = node.attrGet("type") or "bullet" if hasattr(node, "attrGet") else "bullet"

    for i, item in enumerate(node.children or []):
        if item.type == "list_item":
            item_content = extract_text(item)
            if list_type == "ordered":
                items.append(f"{i + 1}. {item_content}")
            else:
                items.append(f"- {item_content}")

    return "\n".join(items)


def render_node(node: SyntaxTreeNode) -> str:
    """
    根据节点类型渲染为 Markdown 字符串。

    这是统一的节点渲染入口，所有特殊节点类型都有专门的处理。
    """
    node_type = node.type

    renderers = {
        "table": render_table,
        "code_block": render_code_block,
        "blockquote": render_blockquote,
        "bullet_list": render_list,
        "ordered_list": render_list,
    }

    if node_type in renderers:
        return renderers[node_type](node)
    if node_type == "paragraph":
        return extract_text(node)
    if node_type == "html_block":
        return node.content
    if node_type == "hr":
        return "---"

    # 通用回退
    return extract_text(node)


# ---------------------------------------------------------------------------
# 节点处理（统一处理流程）
# ---------------------------------------------------------------------------

def process_node(
    node: SyntaxTreeNode,
    context_stack: List[HeaderContext],
    *,
    heading_breaks: bool = True,
    table_breaks: bool = True,
) -> Tuple[str, bool]:
    """
    处理单个 AST 节点，返回 (内容, 是否应该分块)。

    Args:
        node: AST 节点
        context_stack: 标题上下文栈（会被修改）
        heading_breaks: 标题是否触发分块边界
        table_breaks: 大表格是否触发分块边界

    Returns:
        (内容字符串, 是否触发分块)
    """
    node_type = node.type
    should_break = False
    content = ""

    if node_type == "heading":
        level = int(node.tag[1])  # h1 -> 1
        title_text = extract_text(node)
        update_context_stack(context_stack, level, title_text)
        content = f"{node.markup} {title_text}"
        should_break = heading_breaks

    elif node_type == "table":
        content = render_table(node)
        # 大表格需要特殊处理标记
        should_break = table_breaks

    elif node_type == "code_block":
        content = render_code_block(node)

    elif node_type == "blockquote":
        content = render_blockquote(node)

    elif node_type in ("bullet_list", "ordered_list", "list"):
        content = render_list(node)

    elif node_type == "paragraph":
        content = extract_text(node)

    elif node_type == "hr":
        content = "---"
        should_break = True

    else:
        content = extract_text(node)

    return content, should_break


# ---------------------------------------------------------------------------
# 节点信息提取（批量）
# ---------------------------------------------------------------------------

def extract_nodes_with_headers(
    tree: SyntaxTreeNode,
    split_levels: Tuple[int, ...] = (1, 2, 3, 4),
) -> List[NodeInfo]:
    """
    提取所有节点及其对应的标题信息。

    Args:
        tree: AST 树根节点
        split_levels: 作为分块边界的标题级别

    Returns:
        NodeInfo 列表
    """
    nodes: List[NodeInfo] = []
    current_headers: Dict[int, str] = {}

    for node in tree.children or []:
        if node.type == "heading":
            level = int(node.tag[1])
            title = extract_text(node)

            # 更新标题路径
            current_headers = {k: v for k, v in current_headers.items() if k < level}
            current_headers[level] = title

            is_boundary = level in split_levels

            nodes.append(NodeInfo(
                node=node,
                node_type="heading",
                content=f"{node.markup} {title}",
                headers=current_headers.copy(),
                is_split_boundary=is_boundary,
                level=level,
                title=title,
            ))
        else:
            content = render_node(node)
            if content.strip():
                nodes.append(NodeInfo(
                    node=node,
                    node_type=node.type,
                    content=content,
                    headers=current_headers.copy(),
                    is_split_boundary=False,
                ))

    return nodes


def create_enhanced_nodes(text: str) -> List[NodeInfo]:
    """
    创建增强的 AST 节点列表，包含行号、上下文栈等扩展信息。

    用于父子分块等需要精确位置信息的场景。
    """
    tree = parse_markdown(text)
    enhanced: List[NodeInfo] = []
    context_stack: List[HeaderContext] = []
    line_offset = 0

    for node in tree.children or []:
        content = render_node(node)
        content_lines = content.count("\n") + 1 if content.strip() else 0

        node_info = NodeInfo(
            node=node,
            node_type=node.type,
            content=content,
            line_start=line_offset,
            line_end=line_offset + content_lines,
            context_stack=[HeaderContext(c.level, c.title) for c in context_stack],
            is_section_boundary=False,
            header_level=None,
            header_title=None,
        )

        if node.type == "heading":
            level = int(node.tag[1]) if hasattr(node, "tag") and node.tag else 1
            title = extract_text(node)
            update_context_stack(context_stack, level, title)

            node_info.header_level = level
            node_info.header_title = title
            node_info.is_section_boundary = True
            node_info.context_stack = [
                HeaderContext(c.level, c.title) for c in context_stack
            ]

        if content.strip():
            enhanced.append(node_info)

        line_offset = node_info.line_end

    return enhanced


# ---------------------------------------------------------------------------
# 内容拼接
# ---------------------------------------------------------------------------

def finalize_chunk(
    parts: List[str],
    context_stack: Optional[List[HeaderContext]] = None,
) -> str:
    """
    将多个内容片段拼接为最终 chunk 字符串。

    Args:
        parts: 内容片段列表
        context_stack: 可选的上下文栈，用于添加上下文信息

    Returns:
        拼接后的 chunk 内容
    """
    content = "\n\n".join(p.strip() for p in parts if p.strip())
    return content.strip()