"""
父子分块模块

支持 AST 父子分块结构，包括：
- 自适应父分块级别选择
- 增强 AST 节点创建
- 父/子分块对象创建
- 分块间关联关系建立
"""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from .ast_utils import (
    create_enhanced_nodes,
    extract_text,
    parse_markdown,
    process_node,
    render_node,
    update_context_stack,
)
from .models import ASTChunkInfo, ChunkConfig, HeaderContext, NodeInfo
from .table_handler import (
    extract_table_blocks,
    find_table_title_nodes,
    is_table_content,
    is_table_node,
    parse_html_table_rows,
    split_markdown_table,
    split_table_by_rows,
)
from .tokenizer import num_tokens


# ---------------------------------------------------------------------------
# 全局状态（兼容原有接口）
# ---------------------------------------------------------------------------

_last_parent_child_result: Optional[Dict[str, Any]] = None


def get_last_parent_child_result() -> Optional[Dict[str, Any]]:
    """获取最后一次父子分块的完整结果"""
    return _last_parent_child_result


# ---------------------------------------------------------------------------
# 自适应父分块级别选择
# ---------------------------------------------------------------------------

def compute_adaptive_split_level(
    enhanced_nodes: List[NodeInfo],
    target_parent_tokens: Tuple[int, int] = (400, 1200),
    candidate_levels: Tuple[int, ...] = (2, 3, 4, 5),
    token_counter=None,
) -> int:
    """
    根据文档标题结构和内容分布，自适应选择最优父分块切分级别。

    评分维度：
    - 分块大小落在目标区间的比例
    - 超大分块（>max*1.5）数量
    - 碎片分块（<min*0.3）数量
    - 分块数量适中程度
    """
    if token_counter is None:
        token_counter = num_tokens

    min_target, max_target = target_parent_tokens
    max_allowed = int(max_target * 1.5)
    min_allowed = int(min_target * 0.3)

    best_level = 3
    best_score = -float("inf")

    for level in candidate_levels:
        chunk_tokens_list = []
        current = 0

        for node in enhanced_nodes:
            node_tokens = token_counter(node.content)

            is_boundary = (
                node.node_type == "heading"
                and (node.header_level or 99) <= level
            )

            if is_boundary and current > 0:
                chunk_tokens_list.append(current)
                current = node_tokens
            else:
                current += node_tokens

        if current > 0:
            chunk_tokens_list.append(current)

        if not chunk_tokens_list:
            continue

        total = len(chunk_tokens_list)
        in_range = sum(1 for t in chunk_tokens_list if min_target <= t <= max_target)
        oversized = sum(1 for t in chunk_tokens_list if t > max_allowed)
        undersized = sum(1 for t in chunk_tokens_list if t < min_allowed)
        avg_size = sum(chunk_tokens_list) / total

        in_range_ratio = in_range / total
        count_penalty = 0.0
        if total < 2:
            count_penalty = 1.5
        elif total > 40:
            count_penalty = (total - 40) * 0.05

        target_mid = (min_target + max_target) / 2
        avg_deviation = abs(avg_size - target_mid) / target_mid

        score = (
            in_range_ratio * 10.0
            - oversized * 2.0
            - undersized * 0.8
            - count_penalty
            - avg_deviation * 0.5
        )

        print(
            f"  [Adaptive] H{level}: chunks={total}, "
            f"in_range={in_range}({in_range_ratio:.1%}), "
            f"oversized={oversized}, undersized={undersized}, "
            f"avg={avg_size:.0f}, score={score:.2f}"
        )

        if score > best_score:
            best_score = score
            best_level = level

    print(f"  [Adaptive] 选择 H{best_level} 作为父分块切分级别 (score={best_score:.2f})")
    return best_level


# ---------------------------------------------------------------------------
# 节点按级别切分
# ---------------------------------------------------------------------------

def split_nodes_by_level(
    nodes: List[NodeInfo],
    split_level: int,
) -> List[Tuple[List[NodeInfo], Optional[Dict[str, Any]]]]:
    """
    按指定标题级别将节点切分为多个段。

    Returns:
        [(段节点列表, 段标题信息), ...]
    """
    sections: List[Tuple[List[NodeInfo], Optional[Dict[str, Any]]]] = []
    current_nodes: List[NodeInfo] = []
    current_header: Optional[Dict[str, Any]] = None

    for node in nodes:
        is_boundary = (
            node.node_type == "heading"
            and (node.header_level or 99) <= split_level
        )

        if is_boundary:
            if current_nodes:
                sections.append((current_nodes, current_header))

            current_nodes = [node]
            current_header = {
                "level": node.header_level,
                "title": node.header_title,
                "context_stack": [
                    {"level": c.level, "title": c.title}
                    for c in node.context_stack
                ],
            }
        else:
            current_nodes.append(node)

    if current_nodes:
        sections.append((current_nodes, current_header))

    return sections


# ---------------------------------------------------------------------------
# 二级切分
# ---------------------------------------------------------------------------

def try_secondary_split(
    section_nodes: List[NodeInfo],
    section_header: Optional[Dict[str, Any]],
    current_level: int,
    max_level: int,
    max_allowed: int,
    doc_id: str,
    order_start: int,
    token_counter=None,
) -> List[ASTChunkInfo]:
    """
    尝试对超大段进行二级切分。

    从 current_level + 1 开始逐级尝试更低级别标题，
    选择改善程度最大的级别。
    """
    if token_counter is None:
        token_counter = num_tokens

    # 计算原始大小
    original_content = "\n\n".join(
        n.content for n in section_nodes if n.content.strip()
    )
    original_tokens = token_counter(original_content)

    best_level = None
    best_score = -float("inf")
    best_sections = None

    for try_level in range(current_level + 1, max_level + 1):
        sub_sections = split_nodes_by_level(section_nodes, try_level)

        # 过滤空段
        valid_sections = []
        for nodes, header in sub_sections:
            content = "\n\n".join(n.content for n in nodes if n.content.strip())
            if content.strip():
                valid_sections.append((nodes, header, token_counter(content)))

        if not valid_sections:
            continue

        tokens_list = [t for _, _, t in valid_sections]
        total_chunks = len(tokens_list)

        # 无效切分：只有一个分块且与原来一样大
        if total_chunks == 1 and tokens_list[0] >= original_tokens * 0.95:
            continue

        oversized = sum(1 for t in tokens_list if t > max_allowed)
        undersized = sum(1 for t in tokens_list if t < 50)
        in_range = sum(1 for t in tokens_list if 200 <= t <= max_allowed)
        oversized_ratio = oversized / total_chunks if total_chunks > 0 else 1.0
        improvement = 1.0 - oversized_ratio

        score = (
            improvement * 8.0
            + in_range * 1.0
            - undersized * 0.5
            - oversized * 0.3
        )

        if score > best_score:
            best_score = score
            best_level = try_level
            best_sections = valid_sections

    # 没有找到合适的二级切分
    if best_level is None or best_sections is None:
        chunk = ASTChunkInfo.create_parent(
            section_nodes, section_header, order_start, doc_id,
            extra_metadata={"split_strategy": "single_level_oversized"},
        )
        return [chunk]

    # 使用最优级别创建分块
    result = []
    order = order_start

    for nodes, header, _ in best_sections:
        content = "\n\n".join(n.content for n in nodes if n.content.strip())
        if not content.strip():
            continue

        # 合并上下文
        effective_header = header
        if header and section_header:
            merged_context = section_header.get("context_stack", []).copy()
            header_title = header.get("title", "")
            if header_title not in [c.get("title") for c in merged_context]:
                merged_context.append({
                    "level": header.get("level"),
                    "title": header_title,
                })
            effective_header = {
                "level": header.get("level"),
                "title": header_title,
                "context_stack": merged_context,
            }

        chunk = ASTChunkInfo.create_parent(
            nodes, effective_header, order, doc_id,
            extra_metadata={
                "split_strategy": f"secondary_H{current_level}_to_H{best_level}",
                "primary_header": section_header.get("title") if section_header else "",
            },
        )
        result.append(chunk)
        order += 1

    return result


# ---------------------------------------------------------------------------
# 子分块创建（父子分块专用）
# ---------------------------------------------------------------------------

def create_child_chunks_with_tables(
    enhanced_nodes: List[NodeInfo],
    chunk_token_num: int,
    min_chunk_tokens: int,
    doc_id: str,
    token_counter=None,
) -> List[ASTChunkInfo]:
    """
    基于 AST 节点创建子分块，特殊处理表格。

    策略：
    1. 表格标题（heading/段落）单独作为子 chunk
    2. 表格内容按行拆分，每块保留表头
    3. 普通节点按 token 累积
    """
    if token_counter is None:
        token_counter = num_tokens

    child_chunks: List[ASTChunkInfo] = []
    current_nodes: List[NodeInfo] = []
    current_tokens = 0
    chunk_order = 0

    i = 0
    while i < len(enhanced_nodes):
        node = enhanced_nodes[i]
        content = node.content

        if not content.strip():
            i += 1
            continue

        content_tokens = token_counter(content)

        # heading 边界检查（H1-H3）
        should_break = (
            node.node_type == "heading"
            and (node.header_level or 99) <= 3
        )

        if should_break and current_nodes:
            child_chunk = ASTChunkInfo.create_child(
                current_nodes, chunk_order, doc_id
            )
            child_chunks.append(child_chunk)
            chunk_order += 1
            current_nodes = []
            current_tokens = 0

        # 表格特殊处理
        if is_table_node(node):
            # 查找表格标题
            title_indices = find_table_title_nodes(enhanced_nodes, i)
            title_nodes = []
            for ti in title_indices:
                enhanced_nodes[ti]._is_table_title = True
                title_nodes.append(enhanced_nodes[ti])

            # 从当前累积中移除标题节点
            for tn in title_nodes:
                if tn in current_nodes:
                    current_nodes.remove(tn)
                    current_tokens -= token_counter(tn.content)

            # 输出剩余非表格内容
            if current_nodes and current_tokens >= min_chunk_tokens:
                child_chunk = ASTChunkInfo.create_child(
                    current_nodes, chunk_order, doc_id
                )
                child_chunks.append(child_chunk)
                chunk_order += 1
                current_nodes = []
                current_tokens = 0
            elif current_nodes:
                pass  # token 不够，保留

            # 输出表格上下文
            if title_nodes:
                context_chunk = ASTChunkInfo.create_child(
                    title_nodes, chunk_order, doc_id,
                    extra_metadata={
                        "chunk_subtype": "table_context",
                        "contains_tables": False,
                    },
                )
                child_chunks.append(context_chunk)
                chunk_order += 1

            # 表格内容按行拆分
            table_token_count = token_counter(node.content)
            if table_token_count > chunk_token_num:
                sub_tables = split_table_by_rows(
                    node.content, chunk_token_num, token_counter
                )
                for sub_table in sub_tables:
                    table_node = NodeInfo(
                        node=node.node,
                        node_type="table",
                        content=sub_table,
                        headers=node.headers.copy() if node.headers else {},
                    )
                    chunk = ASTChunkInfo.create_child(
                        [table_node], chunk_order, doc_id,
                        extra_metadata={
                            "chunk_subtype": "table_content_split",
                            "table_split": True,
                        },
                    )
                    child_chunks.append(chunk)
                    chunk_order += 1
            else:
                chunk = ASTChunkInfo.create_child(
                    [node], chunk_order, doc_id,
                    extra_metadata={
                        "chunk_subtype": "table_content",
                        "table_split": False,
                    },
                )
                child_chunks.append(chunk)
                chunk_order += 1

            i += 1
            continue

        # 跳过已标记的表格标题
        if node._is_table_title:
            i += 1
            continue

        # 普通节点 token 检查
        if (
            current_tokens + content_tokens > chunk_token_num
            and current_nodes
            and current_tokens >= min_chunk_tokens
        ):
            child_chunk = ASTChunkInfo.create_child(
                current_nodes, chunk_order, doc_id
            )
            child_chunks.append(child_chunk)
            chunk_order += 1
            current_nodes = []
            current_tokens = 0

        current_nodes.append(node)
        current_tokens += content_tokens
        i += 1

    # 最后一块
    if current_nodes and current_tokens >= min_chunk_tokens:
        child_chunk = ASTChunkInfo.create_child(
            current_nodes, chunk_order, doc_id
        )
        child_chunks.append(child_chunk)

    return child_chunks


# ---------------------------------------------------------------------------
# 父分块创建
# ---------------------------------------------------------------------------

def create_parent_chunks(
    enhanced_nodes: List[NodeInfo],
    parent_split_level: int,
    doc_id: str,
    target_parent_tokens: Tuple[int, int] = (400, 1200),
    max_split_level: int = 6,
    token_counter=None,
) -> List[ASTChunkInfo]:
    """
    创建父分块，支持智能二级切分。

    当一级切分后的段仍然超大时，尝试用更低级别的标题进行二级切分。
    """
    if token_counter is None:
        token_counter = num_tokens

    min_target, max_target = target_parent_tokens
    max_allowed = int(max_target * 1.5)

    # 一级切分
    raw_sections = split_nodes_by_level(enhanced_nodes, parent_split_level)

    parent_chunks: List[ASTChunkInfo] = []
    parent_order = 0

    for section_nodes, section_header in raw_sections:
        if not section_nodes:
            continue

        section_content = "\n\n".join(
            n.content for n in section_nodes if n.content.strip()
        )
        section_tokens = token_counter(section_content)

        needs_secondary = (
            section_tokens > max_allowed
            and parent_split_level < max_split_level
        )

        if needs_secondary:
            sub_chunks = try_secondary_split(
                section_nodes, section_header,
                parent_split_level, max_split_level,
                max_allowed, doc_id, parent_order,
                token_counter,
            )
            parent_chunks.extend(sub_chunks)
            parent_order += len(sub_chunks)
        else:
            parent_chunk = ASTChunkInfo.create_parent(
                section_nodes, section_header, parent_order, doc_id
            )
            parent_chunks.append(parent_chunk)
            parent_order += 1

    return parent_chunks


# ---------------------------------------------------------------------------
# 关联关系建立
# ---------------------------------------------------------------------------

def create_relationships(
    child_chunks: List[ASTChunkInfo],
    parent_chunks: List[ASTChunkInfo],
    doc_id: str,
) -> List[Dict[str, Any]]:
    """基于行号范围创建精确的父子关联关系"""
    relationships = []

    for child in child_chunks:
        parent = _find_parent_by_line_range(
            child.start_line, child.end_line, parent_chunks
        )

        if parent:
            relationships.append({
                "child_chunk_id": child.id,
                "parent_chunk_id": parent.id,
                "doc_id": doc_id,
                "relevance_score": 100,
                "relationship_type": "ast_containment",
                "section_title": parent.section_title,
                "child_start_line": child.start_line,
                "child_end_line": child.end_line,
                "parent_start_line": parent.start_line,
                "parent_end_line": parent.end_line,
                "semantic_info": _extract_semantic_info(child, parent),
            })

    return relationships


def _find_parent_by_line_range(
    child_start: int,
    child_end: int,
    parent_chunks: List[ASTChunkInfo],
) -> Optional[ASTChunkInfo]:
    """通过行号范围找到对应的父分块"""
    for parent in parent_chunks:
        if parent.start_line <= child_start and parent.end_line >= child_end:
            return parent
    return None


def _extract_semantic_info(
    child: ASTChunkInfo,
    parent: ASTChunkInfo,
) -> Dict[str, Any]:
    """从 AST 中提取语义信息"""
    child_nodes = child.ast_nodes

    node_types = []
    for n in child_nodes:
        if isinstance(n, dict):
            node_types.append(n.get("type", ""))
        else:
            node_types.append(getattr(n, "type", ""))

    return {
        "contains_headers": sum(1 for t in node_types if t == "heading"),
        "contains_tables": sum(1 for t in node_types if t == "table"),
        "contains_code": sum(1 for t in node_types if t == "code_block"),
        "contains_lists": sum(1 for t in node_types if t in ("bullet_list", "ordered_list")),
        "context_hierarchy": parent.context_stack,
        "ast_node_types": list(set(node_types)),
        "parent_section_title": parent.section_title,
    }


# ---------------------------------------------------------------------------
# 主入口：父子分块
# ---------------------------------------------------------------------------

def split_markdown_parent_child(
    txt: str,
    chunk_token_num: int = 256,
    min_chunk_tokens: int = 10,
    doc_id: str = "unknown",
    parent_split_level: Optional[int] = None,
    adaptive_split: bool = True,
    target_parent_tokens: Tuple[int, int] = (400, 1200),
    token_counter=None,
) -> Tuple[List[ASTChunkInfo], List[ASTChunkInfo], List[Dict[str, Any]]]:
    """
    基于 AST 的父子分块方法（支持自适应父分块级别）。

    Args:
        txt: 要分块的文本
        chunk_token_num: 子分块大小（tokens）
        min_chunk_tokens: 最小子分块大小
        doc_id: 文档 ID
        parent_split_level: 显式指定父分块切分级别
        adaptive_split: 是否启用自适应切分
        target_parent_tokens: 目标父分块大小区间

    Returns:
        (parent_chunks, child_chunks, relationships)
    """
    global _last_parent_child_result

    if token_counter is None:
        token_counter = num_tokens

    if not txt or not txt.strip():
        return [], [], []

    try:
        # 1. 创建增强 AST 节点
        enhanced_nodes = create_enhanced_nodes(txt)

        # 2. 确定父分块切分级别
        if parent_split_level is not None:
            chosen_level = parent_split_level
            print(f"[AST] 使用显式父分块级别: H{chosen_level}")
        elif adaptive_split:
            print("[AST] 启动自适应父分块级别选择...")
            chosen_level = compute_adaptive_split_level(
                enhanced_nodes,
                target_parent_tokens=target_parent_tokens,
                token_counter=token_counter,
            )
        else:
            chosen_level = 4
            print(f"[AST] 使用默认父分块级别: H{chosen_level}")

        # 3. 创建子分块
        child_chunks = create_child_chunks_with_tables(
            enhanced_nodes, chunk_token_num, min_chunk_tokens, doc_id, token_counter
        )

        # 4. 创建父分块
        parent_chunks = create_parent_chunks(
            enhanced_nodes, chosen_level, doc_id,
            target_parent_tokens=target_parent_tokens,
            token_counter=token_counter,
        )

        # 5. 建立关联关系
        relationships = create_relationships(
            child_chunks, parent_chunks, doc_id
        )

        print(f"[AST] 创建父子分块完成:")
        print(f"  父分块: {len(parent_chunks)} 个 (H{chosen_level}切分)")
        print(f"  子分块: {len(child_chunks)} 个")
        print(f"  关联关系: {len(relationships)} 个")

        # 保存详细结果
        _last_parent_child_result = {
            "parent_chunks": [
                {
                    "id": c.id,
                    "content": c.content,
                    "order": c.order,
                    "metadata": c.metadata,
                }
                for c in parent_chunks
            ],
            "child_chunks": [
                {
                    "id": c.id,
                    "content": c.content,
                    "order": c.order,
                    "metadata": c.metadata,
                }
                for c in child_chunks
            ],
            "relationships": relationships,
            "total_parents": len(parent_chunks),
            "total_children": len(child_chunks),
        }

        return parent_chunks, child_chunks, relationships

    except Exception as e:
        print(f"[ERROR] AST 父子分块失败: {e}")
        import traceback
        traceback.print_exc()
        return [], [], []


def split_markdown_parent_child_simple(
    txt: str,
    chunk_token_num: int = 256,
    min_chunk_tokens: int = 10,
    doc_id: str = "unknown",
) -> List[str]:
    """
    简化接口：只返回子分块内容列表（兼容旧接口）。
    """
    _, child_chunks, _ = split_markdown_parent_child(
        txt, chunk_token_num, min_chunk_tokens, doc_id
    )
    return [c.content for c in child_chunks if c.content.strip()]
