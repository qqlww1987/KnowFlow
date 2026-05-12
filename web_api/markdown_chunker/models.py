"""
数据模型与类型定义

本模块定义了 Markdown 分块过程中使用的所有核心数据结构，
包括分块信息、标题上下文、节点信息等。
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


def _extract_table_titles_from_nodes(nodes: List["NodeInfo"]) -> List[str]:
    """
    从节点列表中提取表格标题。

    检测规则：
    1. heading 节点：以"表"/"Table"/"TABLE" 开头
    2. paragraph 节点：以"表"/"T"开头，或包含表格指示短语
    3. 且下一个节点必须是表格（table 或 html_block 含 <table>）
    """
    table_titles: List[str] = []

    for i, node in enumerate(nodes):
        if node.node_type not in ("heading", "paragraph"):
            continue

        node_content = node.content
        is_title = False

        if node.node_type == "heading" and node.title:
            clean_title = re.sub(r"^#+\s*", "", node.title).strip()
            if re.match(r"^(表|Table|TABLE)", clean_title):
                is_title = True
        elif node.node_type == "paragraph":
            if re.match(r"^(表|Table|TABLE|T\d|下表|表格)", node_content):
                is_title = True
            elif re.search(
                r"(如下表|下表所示|表所示|如下表所示|表格如下|见下表|参见下表|"
                r"下表列出|下表给出|下表说明)",
                node_content,
            ):
                is_title = True

        # 检查下一个节点是否为表格
        if is_title and i + 1 < len(nodes):
            next_node = nodes[i + 1]
            is_next_table = (
                next_node.node_type == "table"
                or (
                    next_node.node_type == "html_block"
                    and "<table" in next_node.content.lower()
                )
            )
            if is_next_table:
                table_titles.append(node_content)

    return table_titles


@dataclass
class HeaderContext:
    """标题上下文信息"""
    level: int
    title: str


@dataclass
class NodeInfo:
    """AST 节点信息包装"""
    node: Any                          # 原始 AST 节点
    node_type: str                     # 节点类型
    content: str                       # 渲染后的内容
    headers: Dict[int, str] = field(default_factory=dict)  # 当前标题层级映射
    is_split_boundary: bool = False    # 是否作为分块边界
    level: Optional[int] = None        # 标题级别（仅 heading 节点）
    title: Optional[str] = None        # 标题文本（仅 heading 节点）
    line_start: int = 0
    line_end: int = 0

    # 扩展字段（用于增强节点）
    context_stack: List[HeaderContext] = field(default_factory=list)
    header_level: Optional[int] = None
    header_title: Optional[str] = None
    is_section_boundary: bool = False
    _is_table_title: bool = False      # 内部标记：是否已被识别为表格标题

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典（兼容旧代码）"""
        return {
            'node': self.node,
            'type': self.node_type,
            'content': self.content,
            'headers': self.headers,
            'is_split_boundary': self.is_split_boundary,
            'level': self.level,
            'title': self.title,
            'line_start': self.line_start,
            'line_end': self.line_end,
            'context_stack': [
                {'level': c.level, 'title': c.title}
                for c in self.context_stack
            ],
            'header_level': self.header_level,
            'header_title': self.header_title,
            'is_section_boundary': self.is_section_boundary,
            '_is_table_title': self._is_table_title,
        }


@dataclass
class ChunkMetadata:
    """分块元数据"""
    chunk_type: str = "normal"
    has_special_content: bool = False
    source_sections: int = 1
    headers: Dict[int, str] = field(default_factory=dict)


@dataclass
class ChunkInfo:
    """分块信息（中间表示）"""
    headers: Dict[int, str] = field(default_factory=dict)
    nodes: List[NodeInfo] = field(default_factory=list)
    chunk_type: str = "normal"
    has_special_content: bool = False
    merged_count: int = 1
    source_sections: int = 1
    has_table_title: bool = False

    def token_count(self, counter) -> int:
        """计算分块的 token 数"""
        content = "\n\n".join(
            n.content for n in self.nodes if n.content.strip()
        )
        return counter(content)


@dataclass
class ChunkConfig:
    """
    分块配置参数。

    默认按 H1-H3 分块，遇到超大 chunk 时自动降级到 fallback_split_levels
    中的层级进行二级拆分。
    """
    chunk_token_num: int = 1024
    min_chunk_tokens: int = 10
    overlap_ratio: float = 0.0
    headers_to_split_on: Tuple[int, ...] = (1, 2, 3)

    # 降级拆分层级：当主层级分块超大时，依次尝试这些层级
    fallback_split_levels: Tuple[int, ...] = (4,)

    # 动态阈值
    @property
    def target_min_tokens(self) -> int:
        return max(50, self.min_chunk_tokens // 2)

    @property
    def target_tokens(self) -> int:
        return min(self.chunk_token_num, 600)

    @property
    def target_max_tokens(self) -> int:
        """
        允许的最大 token 数。

        基于 chunk_token_num 动态计算，不再硬编码 800，
        确保增大 chunk_token_num 能有效减少分块数量。
        """
        return int(self.chunk_token_num * 1.5)

    # 子分块配置
    sub_chunk_token_num: int = 256
    table_sub_chunk_token_num: int = 320

    # 父分块配置
    parent_split_level: Optional[int] = None
    adaptive_split: bool = True
    target_parent_tokens: Tuple[int, int] = (400, 1200)


@dataclass
class ASTChunkInfo:
    """基于 AST 的最终分块信息类（兼容原有接口）"""
    id: str
    content: str
    start_line: int
    end_line: int
    order: int
    doc_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    ast_nodes: List[Any] = field(default_factory=list)

    # 便捷属性
    @property
    def section_title(self) -> str:
        return self.metadata.get("section_title", "")

    @property
    def context_stack(self) -> List[Dict[str, Any]]:
        return self.metadata.get("context_stack", [])

    @property
    def semantic_elements(self) -> Dict[str, Any]:
        return self.metadata.get("semantic_elements", {})

    @classmethod
    def create_child(
        cls,
        nodes: List[NodeInfo],
        order: int,
        doc_id: str,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> "ASTChunkInfo":
        """从 NodeInfo 列表创建子分块"""
        content = "\n\n".join(
            n.content for n in nodes if n.content.strip()
        )
        chunk_id = (
            f"{doc_id}_child_ast_{order:04d}_"
            f"{hashlib.md5(content.encode('utf-8')).hexdigest()[:8]}"
        )

        has_table = any(
            n.node_type == "table" for n in nodes
        )

        metadata: Dict[str, Any] = {
            "chunk_type": "child",
            "creation_method": "ast_semantic",
            "contains_headers": any(n.node_type == "heading" for n in nodes),
            "contains_tables": has_table,
            "contains_code": any(n.node_type == "code_block" for n in nodes),
            "ast_node_count": len(nodes),
            "context_stack": [
                {"level": c.level, "title": c.title}
                for c in (nodes[0].context_stack if nodes else [])
            ],
        }
        if extra_metadata:
            metadata.update(extra_metadata)

        return cls(
            id=chunk_id,
            content=content,
            start_line=nodes[0].line_start if nodes else 0,
            end_line=nodes[-1].line_end if nodes else 0,
            order=order,
            doc_id=doc_id,
            metadata=metadata,
            ast_nodes=[n.to_dict() for n in nodes],
        )

    @classmethod
    def create_parent(
        cls,
        nodes: List[NodeInfo],
        header_info: Optional[Dict[str, Any]],
        order: int,
        doc_id: str,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> "ASTChunkInfo":
        """从 NodeInfo 列表创建父分块"""
        content = "\n\n".join(
            n.content for n in nodes if n.content.strip()
        )
        chunk_id = (
            f"{doc_id}_parent_ast_{order:04d}_"
            f"{hashlib.md5(content.encode('utf-8')).hexdigest()[:8]}"
        )

        # 提取表格相关信息
        table_count = sum(
            1 for n in nodes
            if n.node_type == "table"
        )

        # 提取表格标题
        table_titles = _extract_table_titles_from_nodes(nodes)

        metadata: Dict[str, Any] = {
            "chunk_type": "parent",
            "creation_method": "ast_semantic",
            "section_title": header_info.get("title", "") if header_info else "",
            "header_level": header_info.get("level", 0) if header_info else 0,
            "context_stack": (
                header_info.get("context_stack", []) if header_info else []
            ),
            "semantic_completeness": True,
            "ast_node_count": len(nodes),
            "contains_tables": table_count > 0,
            "table_count": table_count,
            "table_titles": table_titles,
        }
        if extra_metadata:
            metadata.update(extra_metadata)

        return cls(
            id=chunk_id,
            content=content,
            start_line=nodes[0].line_start if nodes else 0,
            end_line=nodes[-1].line_end if nodes else 0,
            order=order,
            doc_id=doc_id,
            metadata=metadata,
            ast_nodes=[n.to_dict() for n in nodes],
        )