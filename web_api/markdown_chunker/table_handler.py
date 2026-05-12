"""
表格处理模块

负责表格检测、表格上下文识别（如标题、说明文字）、
HTML 表格解析、按行拆分大表格等功能。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from .models import NodeInfo


# ---------------------------------------------------------------------------
# 表格检测
# ---------------------------------------------------------------------------

def is_table_content(content: str) -> bool:
    """检查内容是否包含 HTML 表格标签"""
    if not content:
        return False
    lower = content.lower()
    return "<table" in lower or "<tr" in lower or "<td" in lower


def is_table_node(node: NodeInfo) -> bool:
    """检查节点是否为表格节点（支持 table 类型和 html_block）"""
    if node.node_type == "table":
        return True
    if node.node_type == "html_block":
        return is_table_content(node.content)
    return False


# ---------------------------------------------------------------------------
# 表格上下文标题检测
# ---------------------------------------------------------------------------

# 表格标题匹配正则
_TABLE_TITLE_PATTERNS = {
    "heading_prefix": re.compile(r"^(表|Table|TABLE)"),
    "paragraph_prefix": re.compile(r"^(表|T\d|下表|表格)"),
    "paragraph_phrase": re.compile(
        r"(如下表|下表所示|表所示|如下表所示|表格如下|见下表|"
        r"参见下表|下表列出|下表给出|下表说明)"
    ),
}


def is_table_context_title(node: NodeInfo) -> bool:
    """
    判断节点是否为表格的标题/上下文说明文字。

    检测规则：
    1. heading 节点：以"表"/"Table"/"TABLE" 开头
    2. paragraph 节点：以"表"/"T"开头，或包含表格指示短语
    3. 短段落（<60字符）且包含"表"字
    """
    content = node.content.strip()
    if not content:
        return False

    node_type = node.node_type

    # heading 节点检测
    if node_type == "heading":
        title = node.header_title or content
        clean_title = re.sub(r"^#+\s*", "", title).strip()
        if _TABLE_TITLE_PATTERNS["heading_prefix"].match(clean_title):
            return True

    # paragraph 节点检测
    if node_type == "paragraph":
        if _TABLE_TITLE_PATTERNS["paragraph_prefix"].match(content):
            return True
        if _TABLE_TITLE_PATTERNS["paragraph_phrase"].search(content):
            return True
        if len(content) < 60 and "表" in content:
            return True

    return False


def find_table_title_nodes(
    nodes: List[NodeInfo],
    table_index: int,
) -> List[int]:
    """
    向前查找表格的标题/说明节点索引。

    只向前看最多2个节点，按优先级匹配。

    Returns:
        标题节点索引列表（按文档顺序）
    """
    if table_index <= 0:
        return []

    for lookback in range(1, min(3, table_index + 1)):
        idx = table_index - lookback
        node = nodes[idx]

        if node._is_table_title:
            continue

        if node.node_type == "heading":
            title_text = node.header_title or node.content
            clean_title = re.sub(r"^#+\s*", "", title_text).strip()
            if re.match(r"^(表|Table|TABLE)", clean_title):
                return [idx]

        elif node.node_type == "paragraph":
            content = node.content.strip()
            if re.match(r"^(表|Table|TABLE|T\d|下表|表格)", content):
                return [idx]
            if re.search(
                r"(如下表|下表所示|表所示|如下表所示|表格如下|见下表|参见下表|"
                r"下表列出|下表给出|下表说明)",
                content,
            ):
                return [idx]
            if len(content) < 60 and "表" in content:
                return [idx]

    return []


# ---------------------------------------------------------------------------
# HTML 表格解析
# ---------------------------------------------------------------------------

def parse_html_table_rows(html_content: str) -> Tuple[str, List[str]]:
    """
    解析 HTML 表格，提取表头行和数据行。

    Returns:
        (thead_html, tbody_rows)
        thead_html: 表头部分 HTML（含 <thead> 标签）
        tbody_rows: 数据行列表，每行为完整的 <tr>...</tr> HTML
    """
    thead_html = ""
    tbody_rows: List[str] = []

    # 提取 thead
    thead_match = re.search(r"<thead>(.*?)</thead>", html_content, re.DOTALL)
    if thead_match:
        thead_html = "<thead>" + thead_match.group(1) + "</thead>"

    # 提取 tbody 中的行
    tbody_match = re.search(r"<tbody>(.*?)</tbody>", html_content, re.DOTALL)
    if tbody_match:
        tbody_content = tbody_match.group(1)
        tbody_rows = re.findall(r"<tr[^>]*>.*?</tr>", tbody_content, re.DOTALL)

    # 没有 tbody 的简化表格
    if not tbody_rows:
        all_rows = re.findall(r"<tr[^>]*>.*?</tr>", html_content, re.DOTALL)
        if all_rows:
            thead_html = "<thead>" + all_rows[0] + "</thead>"
            tbody_rows = all_rows[1:]

    return thead_html, tbody_rows


def build_html_table(thead_html: str, rows: List[str]) -> str:
    """
    构建完整的 HTML 表格字符串。

    Args:
        thead_html: 表头 HTML
        rows: 数据行列表

    Returns:
        完整的 <table>...</table> HTML
    """
    parts = ["<table>"]
    if thead_html:
        parts.append(thead_html)
    if rows:
        parts.append("<tbody>")
        parts.extend(rows)
        parts.append("</tbody>")
    parts.append("</table>")
    return "\n".join(parts)


def extract_table_blocks(content: str) -> List[str]:
    """
    从内容中提取所有 <table>...</table> 块。

    支持一个节点中包含多个表格的情况。
    """
    blocks = re.findall(
        r"<table[^>]*>.*?</table>", content,
        re.DOTALL | re.IGNORECASE,
    )
    return blocks if blocks else [content]


# ---------------------------------------------------------------------------
# 表格拆分
# ---------------------------------------------------------------------------

def split_table_by_rows(
    table_content: str,
    max_tokens: int,
    token_counter,
) -> List[str]:
    """
    将大表格按行拆分为多个子表格 HTML 字符串。

    每个子表格保留完整表头。

    Args:
        table_content: 原始表格 HTML
        max_tokens: 每个子表格的最大 token 数
        token_counter: token 计数函数

    Returns:
        子表格 HTML 字符串列表
    """
    table_tokens = token_counter(table_content)
    if table_tokens <= max_tokens:
        return [table_content]

    # 提取所有表格块
    table_blocks = extract_table_blocks(table_content)
    result: List[str] = []

    for block_html in table_blocks:
        thead_html, tbody_rows = parse_html_table_rows(block_html)

        if not tbody_rows:
            result.append(block_html)
            continue

        header_tokens = token_counter(thead_html) if thead_html else 0
        available = max_tokens - header_tokens - 20  # 20 为标签缓冲

        if available <= 0:
            result.append(block_html)
            continue

        current_rows: List[str] = []
        current_tokens = 0

        for row_html in tbody_rows:
            row_tokens = token_counter(row_html)

            # 单个行就超过可用空间
            if row_tokens > available:
                if current_rows:
                    result.append(build_html_table(thead_html, current_rows))
                    current_rows = []
                    current_tokens = 0
                # 超大行单独作为一个分块
                result.append(build_html_table(thead_html, [row_html]))
                continue

            if current_tokens + row_tokens > available and current_rows:
                result.append(build_html_table(thead_html, current_rows))
                current_rows = [row_html]
                current_tokens = row_tokens
            else:
                current_rows.append(row_html)
                current_tokens += row_tokens

        if current_rows:
            result.append(build_html_table(thead_html, current_rows))

    return result


# ---------------------------------------------------------------------------
# 表格上下文提取
# ---------------------------------------------------------------------------

def extract_table_with_context(
    nodes: List[NodeInfo],
    table_idx: int,
) -> Tuple[List[NodeInfo], NodeInfo]:
    """
    提取表格及其上下文标题节点。

    Args:
        nodes: 完整节点列表
        table_idx: 表格节点索引

    Returns:
        (上下文节点列表, 表格节点)
    """
    title_indices = find_table_title_nodes(nodes, table_idx)

    context_nodes: List[NodeInfo] = []
    for ti in title_indices:
        nodes[ti]._is_table_title = True
        context_nodes.append(nodes[ti])

    return context_nodes, nodes[table_idx]


# ---------------------------------------------------------------------------
# Markdown 表格分割
# ---------------------------------------------------------------------------

def split_markdown_table(
    table_md: str,
    max_tokens: int,
    token_counter,
) -> List[str]:
    """
    将 Markdown 格式表格按行拆分。

    Args:
        table_md: Markdown 表格文本
        max_tokens: 最大 token 数
        token_counter: token 计数函数

    Returns:
        子表格 Markdown 字符串列表
    """
    lines = table_md.strip().split("\n")
    if len(lines) < 3:
        return [table_md]

    header_lines = lines[:2]  # 表头 + 分隔符
    header_content = "\n".join(header_lines)
    header_tokens = token_counter(header_content)

    data_lines = [line for line in lines[2:] if line.strip() and "|" in line]
    available = max_tokens - header_tokens

    if available <= 0:
        return [table_md]

    result: List[str] = []
    current_rows: List[str] = []
    current_tokens = 0

    for row in data_lines:
        row_tokens = token_counter(row)

        if current_tokens + row_tokens > available and current_rows:
            result.append("\n".join(header_lines + current_rows))
            current_rows = [row]
            current_tokens = row_tokens
        else:
            current_rows.append(row)
            current_tokens += row_tokens

    if current_rows:
        result.append("\n".join(header_lines + current_rows))

    return result if result else [table_md]
