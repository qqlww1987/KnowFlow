#!/usr/bin/env python3
"""Test script for table chunking improvements in md_utitls.py"""
import sys
sys.path.insert(0, '.')

from web_api.md_utitls import (
    _is_table_context_title,
    _parse_html_table_rows,
    _build_table_html,
    _split_large_table,
    _separate_tables_from_chunk,
    _process_non_table_content,
    _create_semantic_sub_chunks,
    split_markdown_to_chunks_advanced,
    split_markdown_to_chunks_smart,
)

# Test 1: _parse_html_table_rows + _build_table_html
print("=== Test 1: _parse_html_table_rows + _build_table_html ===")
sample_html = "<table><thead><tr><th>参数</th><th>值</th></tr></thead><tbody><tr><td>A</td><td>1</td></tr><tr><td>B</td><td>2</td></tr><tr><td>C</td><td>3</td></tr></tbody></table>"
thead, rows = _parse_html_table_rows(sample_html)
print(f"  thead: {bool(thead)}")
print(f"  tbody data rows: {len(rows) if rows else 0}")
if rows:
    chunk_content = _build_table_html(thead, rows)
    print(f"  Built table HTML length: {len(chunk_content)}")

# Test 2: Full table separation with table title
print("\n=== Test 2: _separate_tables_from_chunk (table title detection) ===")
test_chunk = {
    'headers': {1: "主标题", 2: "子标题"},
    'nodes': [
        {'content': "这是普通段落1", 'type': 'paragraph'},
        {'content': "### 表 3-1 测试表格标题", 'type': 'heading', 'title': "表 3-1 测试表格标题"},
        {'content': "<table><thead><tr><th>A</th></tr></thead><tbody><tr><td>1</td></tr></tbody></table>", 'type': 'table'},
        {'content': "这是普通段落2", 'type': 'paragraph'},
    ]
}
result = _separate_tables_from_chunk(test_chunk, 300, 500)
print(f"  Result count: {len(result)}")
for i, chunk in enumerate(result):
    nodes = chunk.get('nodes', [])
    chunk_type = chunk.get('chunk_type', 'unknown')
    has_title = chunk.get('has_table_title', False)
    print(f"  Chunk {i}: type={chunk_type}, has_table_title={has_title}, node_count={len(nodes)}")
    for n in nodes:
        c = n.get('content', '')
        if len(c) > 80:
            c = c[:80] + "..."
        print(f"    - {n.get('type', '?'):15s} | {c}")

# Test 3: Table context paragraph (not heading)
print("\n=== Test 3: _separate_tables_from_chunk (paragraph context) ===")
test_chunk2 = {
    'headers': {1: "主标题"},
    'nodes': [
        {'content': "这是普通段落", 'type': 'paragraph'},
        {'content': "下表列出了设备的主要参数：", 'type': 'paragraph'},
        {'content': "<table><thead><tr><th>参数</th><th>值</th></tr></thead><tbody><tr><td>电压</td><td>220V</td></tr></tbody></table>", 'type': 'table'},
        {'content': "这是表格后的段落", 'type': 'paragraph'},
    ]
}
result2 = _separate_tables_from_chunk(test_chunk2, 300, 500)
print(f"  Result count: {len(result2)}")
for i, chunk in enumerate(result2):
    nodes = chunk.get('nodes', [])
    chunk_type = chunk.get('chunk_type', 'unknown')
    has_title = chunk.get('has_table_title', False)
    print(f"  Chunk {i}: type={chunk_type}, has_table_title={has_title}, node_count={len(nodes)}")
    for n in nodes:
        c = n.get('content', '')
        if len(c) > 80:
            c = c[:80] + "..."
        print(f"    - {n.get('type', '?'):15s} | {c}")

# Test 4: Full Markdown chunking with table
print("\n=== Test 4: split_markdown_to_chunks_advanced (full pipeline) ===")
md_text = """# 测试文档

## 章节一

这是普通内容。

### 表 A-1 设备参数

下表列出了设备的主要参数：

| 参数 | 数值 |
|---|---|
| 电压 | 220V |
| 电流 | 5A |

这是表格后的普通段落。"""
chunks = split_markdown_to_chunks_advanced(md_text, chunk_token_num=300)
print(f"  Chunks count: {len(chunks)}")
for i, chunk in enumerate(chunks):
    content = chunk if isinstance(chunk, str) else chunk.get('content', '')
    if len(content) > 300:
        content = content[:300] + "..."
    print(f"  Chunk {i}:")
    lines = content.split('\n')
    for line in lines[:5]:
        print(f"    {line}")
    if len(lines) > 5:
        print(f"    ... ({len(lines)} lines total)")
    print()

# Test 5: _is_table_context_title edge cases
print("=== Test 5: _is_table_context_title edge cases ===")
test_cases = [
    ({"content": "下表所示：参数说明", "type": "paragraph"}, True),
    ({"content": "见下表", "type": "paragraph"}, True),
    ({"content": "参见下表了解更多", "type": "paragraph"}, True),
    ({"content": "如下表所示", "type": "paragraph"}, True),
    ({"content": "表格如下说明", "type": "paragraph"}, True),
    ({"content": "下表列出所有参数", "type": "paragraph"}, True),
    ({"content": "下表给出具体数值", "type": "paragraph"}, True),
    ({"content": "下表说明配置项", "type": "paragraph"}, True),
    ({"content": "这是一个普通句子", "type": "paragraph"}, False),
    ({"content": "介绍如下表内容说明", "type": "paragraph"}, True),
    ({"content": "表", "type": "paragraph"}, True),  # 短段落+包含表字
    ({"content": "### 表3-7 技术指标", "type": "heading", "title": "表3-7 技术指标"}, True),
    ({"content": "### Table 5 Summary", "type": "heading", "title": "Table 5 Summary"}, True),
    ({"content": "### 介绍", "type": "heading", "title": "介绍"}, False),
]
all_pass = True
for node, expected in test_cases:
    result = _is_table_context_title(node)
    status = "PASS" if result == expected else "FAIL"
    if result != expected:
        all_pass = False
    print(f"  [{status}] Expected={expected}, Got={result} | {node['content'][:50]}")

if all_pass:
    print("\n=== ALL TESTS PASSED ===")
else:
    print("\n=== SOME TESTS FAILED ===")
    sys.exit(1)