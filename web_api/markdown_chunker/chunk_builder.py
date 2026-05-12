"""
分块构建器 — 核心分块算法

包含基于标题的分块、动态大小控制、超大/超小分块处理、
表格特殊处理、子分块创建等所有分块构建逻辑。
"""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from .ast_utils import (
    create_enhanced_nodes,
    extract_nodes_with_headers,
    finalize_chunk,
    parse_markdown,
    process_node,
    update_context_stack,
)
from .models import ChunkConfig, ChunkInfo, HeaderContext, NodeInfo
from .renderer import render_chunk, render_simple_chunk
from .table_handler import (
    extract_table_blocks,
    extract_table_with_context,
    find_table_title_nodes,
    is_table_content,
    is_table_node,
    parse_html_table_rows,
    split_markdown_table,
    split_table_by_rows,
)
from .tokenizer import num_tokens


# ---------------------------------------------------------------------------
# 短标题检测
# ---------------------------------------------------------------------------

def is_short_numbered_title(title: str) -> bool:
    """
    检查标题是否为短编号（如 "3.7"、"4.1"、"A.1"）。

    这类标题通常需要与后续内容标题合并。
    有实质中文内容的标题（>=2 个汉字）不被视为短编号。
    """
    title = title.strip()
    if len(title) > 12:
        return False

    # 有实质中文内容的标题（>=2 个汉字）不是纯编号
    chinese_chars = sum(1 for ch in title if '\u4e00' <= ch <= '\u9fff')
    if chinese_chars >= 2:
        return False

    # 纯数字编号
    if title.replace(".", "").replace(" ", "").isdigit():
        return True

    # 短编号（如 "3.7"、"A.1"）
    if len(title.split()) <= 2 and any(ch.isdigit() for ch in title):
        return True

    return False


def find_content_header_ahead(
    nodes: List[NodeInfo],
    start_idx: int,
    max_lookahead: int = 3,
) -> bool:
    """
    向前查找是否有更有实质内容的标题。

    用于判断短编号标题是否应该作为分块边界。
    """
    end = min(len(nodes), start_idx + max_lookahead + 1)
    for j in range(start_idx + 1, end):
        next_node = nodes[j]
        if next_node.node_type == "heading":
            next_title = (next_node.title or "").strip()
            # 较长标题、多词标题、或包含非数字词汇
            is_content = (
                len(next_title) > 12
                or len(next_title.split()) > 2
                or any(
                    len(w) > 3 and not w.replace(".", "").isdigit()
                    for w in next_title.split()
                )
            )
            if is_content:
                return True
        elif next_node.content.strip():
            # 遇到其他内容，停止查找
            break

    return False


# ---------------------------------------------------------------------------
# 1. 基于标题的初步分块
# ---------------------------------------------------------------------------

def split_by_headers(
    nodes: List[NodeInfo],
    split_levels: Tuple[int, ...] = (1, 2, 3, 4),
) -> List[ChunkInfo]:
    """
    基于标题层级进行初步分块。

    特殊处理：
    - 短编号标题（如 "3.7"）会向前查找，如果找到内容标题则不作为分块边界
    """
    chunks: List[ChunkInfo] = []
    current = ChunkInfo()

    i = 0
    while i < len(nodes):
        node = nodes[i]

        # 检查是否为分块边界
        if node.is_split_boundary and node.node_type == "heading":
            title = (node.title or "").strip()

            # 短标题特殊处理
            if is_short_numbered_title(title):
                if find_content_header_ahead(nodes, i):
                    # 不作为分块边界，直接添加
                    current.nodes.append(node)
                    if node.headers:
                        current.headers = node.headers.copy()
                    i += 1
                    continue

            # 正常分块边界：保存当前块并开始新块
            if current.nodes and any(n.content.strip() for n in current.nodes):
                chunks.append(current)
                current = ChunkInfo()

        # 更新标题信息并添加节点
        if node.headers:
            current.headers = node.headers.copy()
        current.nodes.append(node)
        i += 1

    # 最后一块
    if current.nodes and any(n.content.strip() for n in current.nodes):
        chunks.append(current)

    return chunks


# ---------------------------------------------------------------------------
# 2. 大小评估与分类
# ---------------------------------------------------------------------------

def classify_chunk_size(
    chunk: ChunkInfo,
    min_tokens: int,
    max_tokens: int,
    token_counter,
) -> str:
    """
    分类分块大小。

    Returns:
        "normal" - 大小合适
        "oversized" - 超大
        "undersized" - 超小
    """
    content = "\n\n".join(n.content for n in chunk.nodes if n.content.strip())
    tokens = token_counter(content)

    if tokens < min_tokens:
        return "undersized"
    if tokens > max_tokens:
        return "oversized"
    return "normal"


def has_special_content(chunk: ChunkInfo) -> bool:
    """检查分块是否包含特殊内容（表格、代码块、公式等）"""
    for node in chunk.nodes:
        if node.node_type in ("table", "code_block"):
            return True
        content = node.content
        if "$$" in content or "$" in content:
            return True
        if "<table>" in content and "</table>" in content:
            return True

    return False


# ---------------------------------------------------------------------------
# 3. 超大分块处理
# ---------------------------------------------------------------------------

def split_oversized_chunk(
    chunk: ChunkInfo,
    target_tokens: int,
    max_tokens: int,
    token_counter,
) -> List[ChunkInfo]:
    """
    在段落边界分割超大分块，同时保持特殊内容完整性。
    """
    result: List[ChunkInfo] = []
    headers = chunk.headers.copy()
    current_nodes: List[NodeInfo] = []
    current_tokens = 0

    for node in chunk.nodes:
        node_tokens = token_counter(node.content)

        # 检查特殊内容
        is_special = node.node_type in ("table", "code_block")
        is_latex = "$$" in node.content or "$" in node.content
        is_html_table = "<table>" in node.content and "</table>" in node.content
        is_oversized_special = (is_special or is_latex or is_html_table) and node_tokens > max_tokens

        if is_oversized_special:
            # 先保存当前累积
            if current_nodes:
                result.append(ChunkInfo(
                    headers=headers.copy(),
                    nodes=current_nodes.copy(),
                    chunk_type="split_from_oversized",
                    has_special_content=has_special_content(
                        ChunkInfo(nodes=current_nodes)
                    ),
                ))
                current_nodes = []
                current_tokens = 0

            # 超大特殊内容单独成块
            result.append(ChunkInfo(
                headers=headers.copy(),
                nodes=[node],
                chunk_type="split_from_oversized",
                has_special_content=True,
            ))
            continue

        # 检查是否会超出限制
        would_exceed = (
            current_tokens + node_tokens > target_tokens
            or current_tokens + node_tokens > max_tokens
        ) if current_nodes else False

        if would_exceed:
            result.append(ChunkInfo(
                headers=headers.copy(),
                nodes=current_nodes.copy(),
                chunk_type="split_from_oversized",
                has_special_content=has_special_content(
                    ChunkInfo(nodes=current_nodes)
                ),
            ))
            current_nodes = [node]
            current_tokens = node_tokens

            # 更新标题上下文
            if node.node_type == "heading":
                level = node.level or 3
                title = node.title or ""
                headers = {k: v for k, v in headers.items() if k < level}
                headers[level] = title
        else:
            current_nodes.append(node)
            current_tokens += node_tokens

            if node.node_type == "heading":
                level = node.level or 3
                title = node.title or ""
                headers = {k: v for k, v in headers.items() if k < level}
                headers[level] = title

    # 最后一块
    if current_nodes:
        result.append(ChunkInfo(
            headers=headers.copy(),
            nodes=current_nodes,
            chunk_type="split_from_oversized",
            has_special_content=has_special_content(
                ChunkInfo(nodes=current_nodes)
            ),
        ))

    return result


# ---------------------------------------------------------------------------
# 3b. 超大分块降级拆分（按更低级别标题）
# ---------------------------------------------------------------------------

def try_fallback_split(
    chunk: ChunkInfo,
    fallback_levels: Tuple[int, ...],
    max_tokens: int,
    token_counter,
) -> Optional[List[ChunkInfo]]:
    """
    尝试用更低级别的标题对超大 chunk 进行二级拆分。

    策略：
    1. 依次尝试 fallback_levels 中的每个层级
    2. 找到该层级中能将超大 chunk 拆分成更合理大小的最优层级
    3. 如果拆分后没有改善（仍然全部超大或产生过多碎片），则放弃

    Args:
        chunk: 超大 chunk
        fallback_levels: 降级层级（如 (4,) 或 (4, 5)）
        max_tokens: 最大 token 阈值
        token_counter: token 计数函数

    Returns:
        拆分后的 ChunkInfo 列表，如果无法改善则返回 None
    """
    nodes = chunk.nodes
    if not nodes:
        return None

    # 计算原始大小
    original_tokens = token_counter(
        "\n\n".join(n.content for n in nodes if n.content.strip())
    )

    best_result = None
    best_score = -float("inf")

    for level in fallback_levels:
        # 在该 chunk 内部按 level 拆分
        sub_chunks: List[ChunkInfo] = []
        current = ChunkInfo(
            headers=chunk.headers.copy(),
            chunk_type="fallback_split",
        )

        for node in nodes:
            is_boundary = (
                node.node_type == "heading"
                and node.level == level
            )

            if is_boundary and current.nodes:
                sub_chunks.append(current)
                current = ChunkInfo(
                    headers=node.headers.copy(),
                    chunk_type="fallback_split",
                )

            if node.headers:
                current.headers = node.headers.copy()
            current.nodes.append(node)

        if current.nodes:
            sub_chunks.append(current)

        # 评估拆分质量
        if not sub_chunks:
            continue

        # 如果拆分后只有一个块且和原来一样大，说明这个层级无效
        if len(sub_chunks) == 1:
            continue

        # 计算各块大小分布
        tokens_list = [
            token_counter("\n\n".join(n.content for n in sc.nodes if n.content.strip()))
            for sc in sub_chunks
        ]

        oversized = sum(1 for t in tokens_list if t > max_tokens)
        undersized = sum(1 for t in tokens_list if t < 50)
        in_range = sum(1 for t in tokens_list if 50 <= t <= max_tokens)
        total = len(tokens_list)

        # 如果拆分后所有块仍然超大，尝试下一个层级
        if oversized == total:
            continue

        # 评分：鼓励合理范围的分块，惩罚超大和碎片
        score = (
            in_range * 2.0              # 合理范围奖励
            - oversized * 3.0           # 超大惩罚（较重）
            - undersized * 0.5          # 碎片惩罚
        )

        # 必须比不切分好才有意义
        if score > best_score:
            best_score = score
            best_result = sub_chunks

    return best_result


# ---------------------------------------------------------------------------
# 4. 超小分块处理
# ---------------------------------------------------------------------------

def try_merge_with_next(
    chunk: ChunkInfo,
    all_chunks: List[ChunkInfo],
    current_index: int,
    target_tokens: int,
    token_counter,
) -> Optional[ChunkInfo]:
    """
    尝试将小分块与后续分块合并。

    Returns:
        合并后的 ChunkInfo，如果无法合并则返回 None
    """
    if current_index >= len(all_chunks) - 1:
        return None

    next_chunk = all_chunks[current_index + 1]

    current_content = render_chunk(chunk)
    next_content = render_chunk(next_chunk)
    merged_content = current_content + "\n\n" + next_content
    merged_tokens = token_counter(merged_content)

    if merged_tokens <= target_tokens * 1.2:
        return ChunkInfo(
            headers=next_chunk.headers or chunk.headers,
            nodes=chunk.nodes + next_chunk.nodes,
            chunk_type="merged_small",
            has_special_content=has_special_content(chunk) or has_special_content(next_chunk),
            merged_count=2,
            source_sections=2,
        )

    return None


def enhance_small_chunk(chunk: ChunkInfo) -> ChunkInfo:
    """
    为小分块增强上下文信息。

    在节点前添加上级标题路径作为上下文（不包含 chunk 自身的标题）。
    """
    enhanced = ChunkInfo(
        headers=chunk.headers.copy(),
        nodes=chunk.nodes.copy(),
        chunk_type="small_enhanced",
        has_special_content=has_special_content(chunk),
    )

    headers = chunk.headers
    if not headers:
        return enhanced

    # 确定 chunk 中最低级别的标题（如果有）
    chunk_heading_levels = [
        n.level for n in chunk.nodes
        if n.node_type == "heading" and n.level is not None
    ]
    min_heading_level = min(chunk_heading_levels) if chunk_heading_levels else 99

    # 只添加上级标题作为上下文
    context_parts = []
    for level in sorted(headers.keys()):
        if level < min_heading_level:
            context_parts.append(f"{'#' * level} {headers[level]}")

    if context_parts:
        context_node = NodeInfo(
            node=None,
            node_type="context",
            content="\n".join(context_parts),
            headers=headers.copy(),
        )
        enhanced.nodes = [context_node] + enhanced.nodes

    return enhanced


# ---------------------------------------------------------------------------
# 5. 表格分离处理
# ---------------------------------------------------------------------------

def separate_tables(
    chunk: ChunkInfo,
    target_tokens: int,
    max_tokens: int,
    token_counter,
) -> List[ChunkInfo]:
    """
    将包含表格的分块中表格单独提取。

    同时确保表格前的标题/说明文字与表格合并为一个子分块。
    """
    separated: List[ChunkInfo] = []
    headers = chunk.headers.copy()
    non_table_nodes: List[NodeInfo] = []
    non_table_tokens = 0

    i = 0
    nodes = chunk.nodes

    while i < len(nodes):
        node = nodes[i]
        node_tokens = token_counter(node.content)

        if is_table_node(node):
            # 提取表格上下文标题
            context_nodes, _ = extract_table_with_context(nodes, i)

            # 从 non_table_nodes 中移除上下文节点
            for cn in context_nodes:
                if cn in non_table_nodes:
                    non_table_nodes.remove(cn)
                    non_table_tokens -= token_counter(cn.content)

            # 输出非表格内容
            if non_table_nodes:
                for nt_chunk in _process_non_table_nodes(
                    non_table_nodes, headers, target_tokens, max_tokens, token_counter
                ):
                    separated.append(nt_chunk)
                non_table_nodes = []
                non_table_tokens = 0

            # 输出表格上下文
            if context_nodes:
                separated.append(ChunkInfo(
                    headers=headers.copy(),
                    nodes=context_nodes.copy(),
                    chunk_type="table_context",
                    has_table_title=True,
                ))

            # 输出表格（如果太大则按行拆分）
            table_token_count = token_counter(node.content)
            if table_token_count > max_tokens:
                sub_tables = split_table_by_rows(node.content, max_tokens, token_counter)
                for sub_table in sub_tables:
                    table_node = NodeInfo(
                        node=node.node,
                        node_type="table",
                        content=sub_table,
                        headers=headers.copy(),
                    )
                    separated.append(ChunkInfo(
                        headers=headers.copy(),
                        nodes=[table_node],
                        chunk_type="table_chunk",
                        has_special_content=True,
                    ))
            else:
                separated.append(ChunkInfo(
                    headers=headers.copy(),
                    nodes=[node],
                    chunk_type="table_chunk",
                    has_special_content=True,
                ))
        else:
            # 非表格节点累积
            if non_table_tokens + node_tokens > target_tokens and non_table_nodes:
                for nt_chunk in _process_non_table_nodes(
                    non_table_nodes, headers, target_tokens, max_tokens, token_counter
                ):
                    separated.append(nt_chunk)
                non_table_nodes = [node]
                non_table_tokens = node_tokens
            else:
                non_table_nodes.append(node)
                non_table_tokens += node_tokens

        i += 1

    # 处理剩余非表格内容
    if non_table_nodes:
        for nt_chunk in _process_non_table_nodes(
            non_table_nodes, headers, target_tokens, max_tokens, token_counter
        ):
            separated.append(nt_chunk)

    return separated


def _process_non_table_nodes(
    nodes: List[NodeInfo],
    headers: Dict[int, str],
    target_tokens: int,
    max_tokens: int,
    token_counter,
) -> List[ChunkInfo]:
    """
    处理非表格内容节点，确保符合大小限制。

    内部辅助函数。
    """
    total_tokens = sum(token_counter(n.content) for n in nodes)

    if total_tokens <= max_tokens:
        return [ChunkInfo(
            headers=headers.copy(),
            nodes=nodes.copy(),
            chunk_type="normal",
        )]

    # 太大则进一步分割
    temp_chunk = ChunkInfo(
        headers=headers.copy(),
        nodes=nodes.copy(),
        chunk_type="normal",
    )
    return split_oversized_chunk(temp_chunk, target_tokens, max_tokens, token_counter)


# ---------------------------------------------------------------------------
# 6. 大小控制与优化（整合入口）
# ---------------------------------------------------------------------------

def optimize_chunks(
    chunks: List[ChunkInfo],
    config: ChunkConfig,
    token_counter,
) -> List[ChunkInfo]:
    """
    应用动态大小控制和优化策略。

    处理流程：
    1. 大小合适的直接保留
    2. 超大分块 -> 进一步分割（保留特殊内容完整性）
    3. 超小分块 -> 尝试合并，无法合并则增强上下文
    """
    optimized: List[ChunkInfo] = []
    i = 0

    while i < len(chunks):
        chunk = chunks[i]
        size_class = classify_chunk_size(
            chunk, config.target_min_tokens, config.target_max_tokens, token_counter
        )
        has_special = has_special_content(chunk)

        if size_class == "normal":
            chunk.chunk_type = chunk.chunk_type or "normal"
            chunk.has_special_content = has_special
            optimized.append(chunk)

        elif size_class == "oversized":
            if not has_special:
                # 尝试用更低级别标题降级拆分（如 H4）
                fallback_result = None
                if config.fallback_split_levels:
                    fallback_result = try_fallback_split(
                        chunk,
                        config.fallback_split_levels,
                        config.target_max_tokens,
                        token_counter,
                    )

                if fallback_result:
                    # 降级拆分成功：对拆分结果递归优化
                    for fc in fallback_result:
                        fc_size = classify_chunk_size(
                            fc, config.target_min_tokens,
                            config.target_max_tokens, token_counter,
                        )
                        if fc_size == "normal":
                            fc.has_special_content = has_special_content(fc)
                            optimized.append(fc)
                        elif fc_size == "oversized":
                            # 仍然超大，走段落级拆分
                            para_split = split_oversized_chunk(
                                fc, config.target_tokens,
                                config.target_max_tokens, token_counter,
                            )
                            optimized.extend(para_split)
                        else:  # undersized
                            enhanced = enhance_small_chunk(fc)
                            optimized.append(enhanced)
                else:
                    # 降级拆分不可用，直接走段落级拆分
                    split_result = split_oversized_chunk(
                        chunk, config.target_tokens, config.target_max_tokens, token_counter
                    )
                    optimized.extend(split_result)
            else:
                # 包含特殊内容：尝试表格分离
                table_separated = separate_tables(
                    chunk, config.target_tokens, config.target_max_tokens, token_counter
                )
                if len(table_separated) > 1 or (
                    table_separated and classify_chunk_size(
                        table_separated[0], config.target_min_tokens,
                        config.target_max_tokens, token_counter
                    ) != "oversized"
                ):
                    optimized.extend(table_separated)
                else:
                    chunk.chunk_type = "oversized_special"
                    chunk.has_special_content = has_special
                    optimized.append(chunk)

        elif size_class == "undersized":
            merged = try_merge_with_next(
                chunk, chunks, i, config.target_tokens, token_counter
            )
            if merged:
                optimized.append(merged)
                i += merged.merged_count - 1
            else:
                enhanced = enhance_small_chunk(chunk)
                optimized.append(enhanced)

        i += 1

    return optimized


# ---------------------------------------------------------------------------
# 7. 子分块创建
# ---------------------------------------------------------------------------

def split_into_sentences(text: str) -> List[str]:
    """
    将文本按句子边界拆分，兼容中英文。

    保护机制：
    - Markdown 图片语法 ![alt](src)（避免 ! 被切断）
    - URL（避免 URL 内标点干扰）
    - 数字编号（如 2.0.4、3.7）
    - 页码引用（如 ..36）
    """
    if not text:
        return []

    # 0. 保护 Markdown 图片语法 ![alt](src)
    images: List[str] = []
    image_pattern = re.compile(r"!\[[^\]]*\]\([^)]+\)")
    protected = image_pattern.sub(lambda m: f"((IMG_{len(images)}))", text)
    images = image_pattern.findall(text)

    # 1. 保护 URL
    urls: List[str] = []
    url_pattern = re.compile(r"https?://[^\s)\]）]+")
    urls = url_pattern.findall(protected)
    protected = url_pattern.sub(lambda m: f"((URL_{len(urls)}))", protected)

    # 2. 保护页码引用
    page_ref_pattern = re.compile(r"[\.。](?:\s*[\.。])+\s*\d+")
    page_refs: List[str] = page_ref_pattern.findall(protected)
    protected = page_ref_pattern.sub(
        lambda m: f"((PAGE_{page_refs.index(m.group(0))}))",
        protected,
    ) if page_refs else protected

    # 3. 保护数字编号
    number_pattern = re.compile(
        r"(?:\d+\.\d+|\w\.\d+|\d+\.\w)(?:\.\d+)*"
    )
    numbers: List[str] = number_pattern.findall(protected)
    protected = number_pattern.sub(
        lambda m: f"((NUM_{numbers.index(m.group(0))}))",
        protected,
    ) if numbers else protected

    # 4. 按句子结束符拆分
    sentences = re.split(r"(?<=[.!?。！？；;])\s*", protected)

    # 5. 还原占位符
    result: List[str] = []
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        # 还原图片
        for idx, img in enumerate(images):
            s = s.replace(f"((IMG_{idx}))", img)
        # 还原 URL
        for idx, url in enumerate(urls):
            s = s.replace(f"((URL_{idx}))", url)
        # 还原数字
        for idx, num in enumerate(numbers):
            s = s.replace(f"((NUM_{idx}))", num)
        # 还原页码
        for idx, ref in enumerate(page_refs):
            s = s.replace(f"((PAGE_{idx}))", ref)
        result.append(s)

    return result


def force_split_long_text(text: str, max_tokens: int) -> List[str]:
    """
    对超过 max_tokens 的超长文本按字符边界强制切分。

    保守估计：2 chars ≈ 1 token（中文场景）
    """
    chars_per_chunk = max_tokens * 2
    chunks: List[str] = []
    for i in range(0, len(text), chars_per_chunk):
        chunk = text[i:i + chars_per_chunk].strip()
        if chunk:
            chunks.append(chunk)
    return chunks


def create_sub_chunks(
    parent_content: str,
    sub_chunk_token_num: int = 256,
    table_sub_chunk_token_num: Optional[int] = None,
    token_counter=None,
) -> List[str]:
    """
    使用与父分段相同的语义分块方式创建子分段。

    对段落和列表按句子拆分再累积，保证粒度精细。
    对表格、代码块、标题等结构性节点保持原子完整性。

    Args:
        parent_content: 父分段内容
        sub_chunk_token_num: 子分段最大 token 数
        table_sub_chunk_token_num: 表格子分段阈值（默认与文本相同）
        token_counter: token 计数函数（默认使用 num_tokens）

    Returns:
        子分段内容字符串列表
    """
    if token_counter is None:
        token_counter = num_tokens

    if table_sub_chunk_token_num is None:
        table_sub_chunk_token_num = sub_chunk_token_num

    sub_chunks: List[str] = []

    try:
        tree = parse_markdown(parent_content)

        # 可拆分为句子的节点类型
        BREAKABLE_TYPES = {"paragraph", "bullet_list", "ordered_list", "list"}

        current_parts: List[str] = []
        current_tokens = 0
        context_stack: List[HeaderContext] = []

        for node in tree.children or []:
            content, should_break = process_node(
                node, context_stack, heading_breaks=True, table_breaks=True
            )

            # 标题触发分块
            if should_break and current_parts and current_tokens >= 10:
                chunk_content = finalize_chunk(current_parts)
                if chunk_content.strip():
                    sub_chunks.append(chunk_content)
                current_parts = []
                current_tokens = 0

            if not content:
                continue

            node_tokens = token_counter(content)

            # 段落/列表：按句子拆分
            if node.type in BREAKABLE_TYPES:
                for sentence in split_into_sentences(content):
                    sentence_tokens = token_counter(sentence)

                    # 超长句子强制切分
                    if sentence_tokens > sub_chunk_token_num:
                        for part in force_split_long_text(sentence, sub_chunk_token_num):
                            part_tokens = token_counter(part)
                            if (
                                current_tokens + part_tokens > sub_chunk_token_num
                                and current_parts
                                and current_tokens >= 10
                            ):
                                chunk_content = finalize_chunk(current_parts)
                                if chunk_content.strip():
                                    sub_chunks.append(chunk_content)
                                current_parts = []
                                current_tokens = 0
                            current_parts.append(part)
                            current_tokens += part_tokens
                        continue

                    # 正常句子累积
                    if (
                        current_tokens + sentence_tokens > sub_chunk_token_num
                        and current_parts
                        and current_tokens >= 10
                    ):
                        chunk_content = finalize_chunk(current_parts)
                        if chunk_content.strip():
                            sub_chunks.append(chunk_content)
                        current_parts = []
                        current_tokens = 0

                    current_parts.append(sentence)
                    current_tokens += sentence_tokens

            else:
                # 表格、代码块等：保持原子完整性
                is_table = node.type == "table" or is_table_content(content)

                if is_table and node_tokens > table_sub_chunk_token_num:
                    # 先 flush 当前累积
                    if current_parts and current_tokens >= 10:
                        chunk_content = finalize_chunk(current_parts)
                        if chunk_content.strip():
                            sub_chunks.append(chunk_content)
                        current_parts = []
                        current_tokens = 0

                    # 拆分表格
                    if node.type == "table":
                        # 使用渲染后的 Markdown 表格
                        for sub_table in split_markdown_table(
                            content, table_sub_chunk_token_num, token_counter
                        ):
                            sub_chunks.append(sub_table)
                    else:
                        # HTML 表格
                        for sub_table in split_table_by_rows(
                            content, table_sub_chunk_token_num, token_counter
                        ):
                            sub_chunks.append(sub_table)
                    continue

                # 普通结构性节点
                if (
                    current_tokens + node_tokens > sub_chunk_token_num
                    and current_parts
                    and current_tokens >= 10
                ):
                    chunk_content = finalize_chunk(current_parts)
                    if chunk_content.strip():
                        sub_chunks.append(chunk_content)
                    current_parts = []
                    current_tokens = 0

                current_parts.append(content)
                current_tokens += node_tokens

        # 处理最后一段
        if current_parts:
            chunk_content = finalize_chunk(current_parts)
            if chunk_content.strip():
                sub_chunks.append(chunk_content)

        return [c for c in sub_chunks if c.strip()]

    except Exception as e:
        print(f"Sub-chunking failed: {e}, falling back to line-based splitting")
        return _create_line_based_sub_chunks(
            parent_content, sub_chunk_token_num, token_counter
        )


def _create_line_based_sub_chunks(
    content: str,
    max_tokens: int,
    token_counter,
) -> List[str]:
    """
    基于行的子分段创建（当语义分块失败时的回退方案）。
    """
    lines = content.split("\n")
    result: List[str] = []
    current_lines: List[str] = []
    current_tokens = 0

    for line in lines:
        line_tokens = token_counter(line)

        if current_tokens + line_tokens > max_tokens and current_lines:
            chunk = "\n".join(current_lines).strip()
            if chunk:
                result.append(chunk)
            current_lines = [line]
            current_tokens = line_tokens
        else:
            current_lines.append(line)
            current_tokens += line_tokens

    if current_lines:
        chunk = "\n".join(current_lines).strip()
        if chunk:
            result.append(chunk)

    return result