#
#  Copyright 2024 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
import mysql.connector
import os
import tiktoken
import tempfile
import json
from markdown import markdown as md_to_html
import time
try:
    from markdown_it import MarkdownIt
    from markdown_it.tree import SyntaxTreeNode
    MARKDOWN_IT_AVAILABLE = True
except ImportError:
    MARKDOWN_IT_AVAILABLE = False
    print("Warning: markdown-it-py not available. Please install with: pip install markdown-it-py")



def singleton(cls, *args, **kw):
    instances = {}

    def _singleton():
        key = str(cls) + str(os.getpid())
        if key not in instances:
            instances[key] = cls(*args, **kw)
        return instances[key]

    return _singleton


tiktoken_cache_dir = tempfile.gettempdir()
os.environ["TIKTOKEN_CACHE_DIR"] = tiktoken_cache_dir
# encoder = tiktoken.encoding_for_model("gpt-3.5-turbo")
encoder = tiktoken.get_encoding("cl100k_base")


def num_tokens_from_string(string: str) -> int:
    """Returns the number of tokens in a text string."""
    try:
        return len(encoder.encode(string))
    except Exception:
        return 0


def truncate(string: str, max_len: int) -> str:
    """Returns truncated text if the length of text exceed max_len."""
    return encoder.decode(encoder.encode(string)[:max_len])


def _extract_tables_and_remainder_md(txt: str) -> (str, list[str]):
    """
    Extracts markdown tables from text and returns the remaining text
    and a list of table strings.
    This is a simplified implementation.
    """
    lines = txt.split('\n')
    tables = []
    remainder_lines = []
    in_table = False
    current_table = []

    for line in lines:
        stripped_line = line.strip()
        # Basic check for table row (starts and ends with |)
        is_table_line = stripped_line.startswith('|') and stripped_line.endswith('|')
        # Basic check for table separator (e.g., |---|---| or |:---|:---:|)
        is_separator_line = True
        if is_table_line and '-' in stripped_line:
            parts = [p.strip() for p in stripped_line[1:-1].split('|')]
            if not all(set(p) <= set('-:') for p in parts if p): # allow only -, :
                is_separator_line = False
            if not parts: # Handles | | case
                is_separator_line = False
        else:
            is_separator_line = False


        if is_table_line or (in_table and stripped_line): # Continue table if already in it and line is not empty
            if not in_table and is_table_line and not is_separator_line: # Potential start of a new table (header)
                # Look ahead for a separator line
                next_line_index = lines.index(line) + 1
                if next_line_index < len(lines):
                    next_line_stripped = lines[next_line_index].strip()
                    next_is_separator = next_line_stripped.startswith('|') and next_line_stripped.endswith('|') and '-' in next_line_stripped
                    if next_is_separator:
                        parts_next = [p.strip() for p in next_line_stripped[1:-1].split('|')]
                        if not all(set(p) <= set('-:') for p in parts_next if p):
                            next_is_separator = False
                        if not parts_next:
                            next_is_separator = False
                    if next_is_separator:
                        in_table = True
                        current_table.append(line)
                    else: # Not a table header
                        remainder_lines.append(line)
                else: # No next line
                     remainder_lines.append(line)
            elif in_table:
                current_table.append(line)
                if not is_table_line and not stripped_line: # Empty line might end the table
                    tables.append("\n".join(current_table))
                    current_table = []
                    in_table = False
                    remainder_lines.append(line) # Add the empty line to remainder
            else: # A line that looks like a table line but isn't starting a valid table
                remainder_lines.append(line)

        elif in_table and not stripped_line : # An empty line definitely ends a table
            tables.append("\n".join(current_table))
            current_table = []
            in_table = False
            remainder_lines.append(line) # Add the empty line to remainder
        elif in_table and not is_table_line : # A non-table line also ends a table
            tables.append("\n".join(current_table))
            current_table = []
            in_table = False
            remainder_lines.append(line) # Add this line to remainder
        else:
            remainder_lines.append(line)

    if current_table: # Add any remaining table
        tables.append("\n".join(current_table))

    return "\n".join(remainder_lines), tables

def split_markdown_to_chunks(txt, chunk_token_num=128, delimiter="\n!?。；！？"):
    """
    Splits markdown text into chunks, processing tables separately and merging text sections
    to be consistent with RAGFlow's naive.py markdown handling.
    """
    if not txt or not txt.strip():
        return []

    # 1. Extract tables and remainder text
    remainder_text, extracted_tables = _extract_tables_and_remainder_md(txt)
    
    processed_chunks = []
    
    # 2. Process tables: convert to HTML and add as individual chunks
    for table_md in extracted_tables:
        if table_md.strip():
            # Ensure markdown.extensions.tables is available
            try:
                table_html = md_to_html(table_md, extensions=['markdown.extensions.tables'])
                processed_chunks.append(table_html)
            except Exception as e:
                # If conversion fails, add raw table markdown as a fallback
                # Or log an error and skip
                processed_chunks.append(table_md)
                print(f"[WARNING] Failed to convert table to HTML: {e}. Added raw table markdown.")


    # 3. Initial splitting of remainder_text (non-table text)
    initial_sections = []
    if remainder_text and remainder_text.strip():
        for sec_line in remainder_text.split("\n"):
            line_content = sec_line.strip()
            if not line_content: # Keep empty lines if they are part of structure or to respect original newlines for merging
                initial_sections.append(sec_line) # Add the original line with its spacing
                continue

            if num_tokens_from_string(sec_line) > 3 * chunk_token_num:
                # Split long lines, trying to preserve original spacing if line was just very long
                mid_point = len(sec_line) // 2
                initial_sections.append(sec_line[:mid_point])
                initial_sections.append(sec_line[mid_point:])
            else:
                initial_sections.append(sec_line)
    
    # 4. Merge initial text sections into chunks respecting token limits (naive_merge logic)
    # This part needs to be careful about document order with tables.
    # The strategy here is to process text between tables.
    # However, _extract_tables_and_remainder_md might not preserve order perfectly if tables are interspersed.
    # For simplicity, we'll process all tables first, then all text. A more sophisticated approach
    # would interleave them based on original position.

    final_text_chunks = []
    current_chunk_parts = []
    current_token_count = 0

    for section_text in initial_sections:
        section_token_count = num_tokens_from_string(section_text)
        
        if not section_text.strip() and not current_chunk_parts: # Skip leading empty/whitespace sections
            continue

        if current_token_count + section_token_count <= chunk_token_num:
            current_chunk_parts.append(section_text)
            current_token_count += section_token_count
        else:
            # Finalize current_chunk if it's not empty
            if current_chunk_parts:
                final_text_chunks.append("\n".join(current_chunk_parts).strip())
            
            # Start a new chunk with the current section
            # If a single section itself is too large, it will be added as is.
            # RAGFlow's naive_merge might have more sophisticated splitting for oversized single sections.
            # For now, we add it as is or split it if it's drastically oversized.
            if section_token_count > chunk_token_num and section_token_count <= 3 * chunk_token_num: # Tolerable oversize
                 final_text_chunks.append(section_text.strip())
                 current_chunk_parts = []
                 current_token_count = 0
            elif section_token_count > 3 * chunk_token_num: # Drastically oversized, needs splitting
                # This split is basic, RAGFlow might be more nuanced
                mid = len(section_text) // 2
                final_text_chunks.append(section_text[:mid].strip())
                final_text_chunks.append(section_text[mid:].strip())
                current_chunk_parts = []
                current_token_count = 0
            else: # Start new chunk
                current_chunk_parts = [section_text]
                current_token_count = section_token_count
    
    # Add any remaining part as the last chunk
    if current_chunk_parts:
        final_text_chunks.append("\n".join(current_chunk_parts).strip())

    # Combine table HTML chunks and text chunks.
    # This simple combination appends all text chunks after all table chunks.
    # A more accurate implementation would require knowing the original order.
    # Given the current _extract_tables_and_remainder_md, this is a limitation.
    all_chunks = [chunk for chunk in processed_chunks if chunk.strip()] # Add table chunks first
    all_chunks.extend([chunk for chunk in final_text_chunks if chunk.strip()])
    
    return all_chunks


_blocks_cache = {}
def get_blocks_from_md(md_file_path):
    if md_file_path in _blocks_cache:
        return _blocks_cache[md_file_path]
    json_path = md_file_path.replace('.md', '_middle.json')
    with open(json_path, 'r') as f:
        data = json.load(f)
        block_list = []
        for page_idx, page in enumerate(data['pdf_info']):
            for block in page['preproc_blocks']:
                bbox = block.get('bbox')
                if not bbox:
                    continue

                if block['type'] in ('text', 'title'):
                    for line in block.get('lines', []):
                        for span in line.get('spans', []):
                            content = span.get('content', '').strip()
                            if content:
                                block_list.append({'content': content, 'bbox': bbox, 'page_number': page_idx })
                
                elif block['type'] == 'table':
                    html_content = ""
                    # Traverse the nested structure to find the HTML content
                    for inner_block in block.get('blocks', []):
                        for line in inner_block.get('lines', []):
                            for span in line.get('spans', []):
                                if 'html' in span:
                                    html_content = span.get('html', '').strip()
                                    if html_content:
                                        break  # Exit spans loop
                            if html_content:
                                break  # Exit lines loop
                        if html_content:
                            break  # Exit inner_blocks loop
                    
                    if html_content:
                        # Use the top-level block's bbox for the entire table
                        block_list.append({'content': html_content, 'bbox': bbox, 'page_number': page_idx })

    _blocks_cache[md_file_path] = block_list
    return block_list

def get_bbox_for_chunk(md_file_path, chunk_content):
    """
    根据 md 文件路径和 chunk 内容，返回 chunk 中所有独立内容的"最大匹配" block 的 bbox 列表。
    该算法首先找到所有匹配的 block，然后过滤掉那些本身是其他更长匹配项子集的 block。
    """
    block_list = get_blocks_from_md(md_file_path)
    if not block_list:
        return None

    chunk_content_clean = chunk_content.strip()
    if not chunk_content_clean:
        return None

    # Step 1: Find all blocks whose content is a substring of the chunk content.
    matched_blocks = []
    for block in block_list:
        if block.get('content') and block['content'] in chunk_content_clean:
            matched_blocks.append(block)

    if not matched_blocks:
        return None

    # Step 2: Filter for "maximal" matches. A match is maximal if its content
    # is not a substring of any other longer match's content.
    maximal_matches = []
    for b1 in matched_blocks:
        is_maximal = True
        for b2 in matched_blocks:
            if b1 is b2:
                continue
            # If b1's content is a proper substring of b2's content, it's not maximal.
            if b1['content'] in b2['content'] and len(b1['content']) < len(b2['content']):
                is_maximal = False
                break
        if is_maximal:
            maximal_matches.append(b1)

    # Step 3: Format and deduplicate the final positions.
    found_positions = []
    for block in maximal_matches:
        bbox = block.get('bbox')
        page_number = block.get('page_number')
        if bbox and page_number is not None:
            position = [page_number, bbox[0], bbox[2], bbox[1], bbox[3]]
            if position not in found_positions:
                found_positions.append(position)
    
    return found_positions if found_positions else None


def update_document_progress(doc_id, progress=None, message=None, status=None, run=None, chunk_count=None, process_duration=None):
    """更新数据库中文档的进度和状态"""
    conn = None
    cursor = None
    try:
        from database import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        updates = []
        params = []

        if progress is not None:
            updates.append("progress = %s")
            params.append(float(progress))
        if message is not None:
            updates.append("progress_msg = %s")
            params.append(message)
        if status is not None:
            updates.append("status = %s")
            params.append(status)
        if run is not None:
            updates.append("run = %s")
            params.append(run)
        if chunk_count is not None:
             updates.append("chunk_num = %s")
             params.append(chunk_count)
        if process_duration is not None:
            updates.append("process_duation = %s")
            params.append(process_duration)


        if not updates:
            return

        query = f"UPDATE document SET {', '.join(updates)} WHERE id = %s"
        params.append(doc_id)
        cursor.execute(query, params)
        conn.commit()
    except Exception as e:
        print(f"[Parser-ERROR] 更新文档 {doc_id} 进度失败: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def split_markdown_to_chunks_smart(txt, chunk_token_num=512, min_chunk_tokens=100):
    """
    基于 markdown-it-py AST 的智能分块方法，解决 RAG Markdown 文件分块问题：
    1. 基于语义切分（使用 AST）
    2. 维护表格完整性，即使超出了最大 tokens
    3. 考虑 markdown 父子分块关系
    """
    if not MARKDOWN_IT_AVAILABLE:
        print("Warning: markdown-it-py not available, falling back to simple chunking")
        return split_markdown_to_chunks(txt, chunk_token_num)
    
    if not txt or not txt.strip():
        return []

    # 初始化 markdown-it 解析器
    md = MarkdownIt("commonmark", {"breaks": True, "html": True})
    md.enable(['table'])
    
    try:
        # 解析为 AST
        tokens = md.parse(txt)
        tree = SyntaxTreeNode(tokens)
        
        # 基于 AST 进行智能分块
        chunks = []
        current_chunk = []
        current_tokens = 0
        context_stack = []  # 维护标题层级栈
        
        for node in tree.children:
            chunk_data, should_break = _process_ast_node(
                node, context_stack, chunk_token_num, min_chunk_tokens
            )
            
            if should_break and current_chunk and current_tokens >= min_chunk_tokens:
                # 完成当前块
                chunk_content = _finalize_ast_chunk(current_chunk, context_stack)
                if chunk_content.strip():
                    chunks.append(chunk_content)
                current_chunk = []
                current_tokens = 0
            
            if chunk_data:
                chunk_tokens = num_tokens_from_string(chunk_data)
                
                # 检查是否需要分块
                if (current_tokens + chunk_tokens > chunk_token_num and 
                    current_chunk and current_tokens >= min_chunk_tokens):
                    
                    chunk_content = _finalize_ast_chunk(current_chunk, context_stack)
                    if chunk_content.strip():
                        chunks.append(chunk_content)
                    current_chunk = []
                    current_tokens = 0
                
                current_chunk.append(chunk_data)
                current_tokens += chunk_tokens
        
        # 处理最后的块
        if current_chunk:
            chunk_content = _finalize_ast_chunk(current_chunk, context_stack)
            if chunk_content.strip():
                chunks.append(chunk_content)
        
        return [chunk for chunk in chunks if chunk.strip()]
    
    except Exception as e:
        print(f"AST parsing failed: {e}, falling back to simple chunking")
        return split_markdown_to_chunks(txt, chunk_token_num)


def _process_ast_node(node, context_stack, chunk_token_num, min_chunk_tokens):
    """
    处理 AST 节点，返回 (内容, 是否应该分块)
    """
    node_type = node.type
    should_break = False
    content = ""
    
    if node_type == "heading":
        # 标题处理
        level = int(node.tag[1])  # h1 -> 1, h2 -> 2, etc.
        title_text = _extract_text_from_node(node)
        
        # 更新上下文栈
        _update_context_stack(context_stack, level, title_text)
        
        content = node.markup + " " + title_text
        should_break = True  # 标题通常作为分块边界
        
    elif node_type == "table":
        # 表格处理 - 保持完整性
        content = _render_table_from_ast(node)
        table_tokens = num_tokens_from_string(content)
        
        # 表格过大时也要保持完整性
        if table_tokens > chunk_token_num:
            should_break = True
            
    elif node_type == "code_block":
        # 代码块处理
        content = f"```{node.info or ''}\n{node.content}```"
        
    elif node_type == "blockquote":
        # 引用块处理
        content = _render_blockquote_from_ast(node)
        
    elif node_type == "list":
        # 列表处理
        content = _render_list_from_ast(node)
        
    elif node_type == "paragraph":
        # 段落处理
        content = _extract_text_from_node(node)
        
    elif node_type == "hr":
        # 分隔符
        content = "---"
        should_break = True
        
    else:
        # 其他类型节点
        content = _extract_text_from_node(node)
    
    return content, should_break


def _update_context_stack(context_stack, level, title):
    """更新标题上下文栈"""
    # 移除比当前级别更深的标题
    while context_stack and context_stack[-1]['level'] >= level:
        context_stack.pop()
    
    # 添加当前标题
    context_stack.append({'level': level, 'title': title})


def _extract_text_from_node(node):
    """从 AST 节点提取文本内容"""
    if hasattr(node, 'content') and node.content:
        return node.content
    
    text_parts = []
    if hasattr(node, 'children') and node.children:
        for child in node.children:
            if child.type == "text":
                text_parts.append(child.content)
            elif child.type == "code_inline":
                text_parts.append(f"`{child.content}`")
            elif child.type == "strong":
                text_parts.append(f"**{_extract_text_from_node(child)}**")
            elif child.type == "em":
                text_parts.append(f"*{_extract_text_from_node(child)}*")
            elif child.type == "link":
                link_text = _extract_text_from_node(child)
                text_parts.append(f"[{link_text}]({child.attrGet('href') or ''})")
            else:
                text_parts.append(_extract_text_from_node(child))
    
    return "".join(text_parts)


def _render_table_from_ast(table_node):
    """从 AST 渲染表格为 HTML"""
    try:
        # 构建表格的 markdown 表示
        table_md = []
        
        for child in table_node.children:
            if child.type == "thead":
                # 表头处理
                for row in child.children:
                    if row.type == "tr":
                        cells = []
                        for cell in row.children:
                            if cell.type in ["th", "td"]:
                                cells.append(_extract_text_from_node(cell))
                        table_md.append("| " + " | ".join(cells) + " |")
                
                # 添加分隔符
                if table_md:
                    separator = "| " + " | ".join(["---"] * len(cells)) + " |"
                    table_md.append(separator)
                    
            elif child.type == "tbody":
                # 表体处理
                for row in child.children:
                    if row.type == "tr":
                        cells = []
                        for cell in row.children:
                            if cell.type in ["th", "td"]:
                                cells.append(_extract_text_from_node(cell))
                        table_md.append("| " + " | ".join(cells) + " |")
        
        # 转换为 HTML
        table_markdown = "\n".join(table_md)
        return md_to_html(table_markdown, extensions=['markdown.extensions.tables'])
        
    except Exception as e:
        print(f"Table rendering error: {e}")
        return _extract_text_from_node(table_node)


def _render_list_from_ast(list_node):
    """从 AST 渲染列表"""
    list_items = []
    list_type = list_node.attrGet('type') or 'bullet'
    
    for i, item in enumerate(list_node.children):
        if item.type == "list_item":
            item_content = _extract_text_from_node(item)
            if list_type == 'ordered':
                list_items.append(f"{i+1}. {item_content}")
            else:
                list_items.append(f"- {item_content}")
    
    return "\n".join(list_items)


def _render_blockquote_from_ast(blockquote_node):
    """从 AST 渲染引用块"""
    content = _extract_text_from_node(blockquote_node)
    lines = content.split('\n')
    return '\n'.join(f"> {line}" for line in lines)


def _finalize_ast_chunk(chunk_parts, context_stack):
    """完成基于 AST 的 chunk 格式化"""
    chunk_content = "\n\n".join(chunk_parts).strip()
    
    # 可以根据需要添加上下文信息
    # 例如，如果chunk没有标题，可以考虑添加父级标题作为上下文
    
    return chunk_content


def split_markdown_to_chunks_advanced(txt, chunk_token_num=512, min_chunk_tokens=100, 
                                     overlap_ratio=0.1, include_metadata=False):
    """
    高级RAG分块方法，包含以下优化：
    1. 上下文增强: 为没有标题的分块添加父级标题上下文
    2. 智能分块边界: 考虑语义完整性，避免在句子中间分块
    3. 表格关联处理: 将表格与其前后的说明文字关联
    4. 嵌套结构处理: 正确处理多层嵌套的markdown结构
    5. 性能优化: 缓存token计算，减少重复计算
    """
    if not MARKDOWN_IT_AVAILABLE:
        return split_markdown_to_chunks(txt, chunk_token_num)
    
    if not txt or not txt.strip():
        return []

    # 性能优化：Token计算缓存
    token_cache = {}
    
    def cached_token_count(content):
        if content in token_cache:
            return token_cache[content]
        count = num_tokens_from_string(content)
        token_cache[content] = count
        return count

    # 初始化 markdown-it 解析器
    md = MarkdownIt("commonmark", {"breaks": True, "html": True})
    md.enable(['table'])
    
    try:
        # 解析为 AST
        tokens = md.parse(txt)
        tree = SyntaxTreeNode(tokens)
        
        # 第一步：深度解析文档结构，建立上下文关系
        doc_structure = _extract_advanced_document_structure(tree)
        
        # 第二步：智能分块处理
        chunks = []
        current_chunk = AdvancedChunkBuilder()
        context_stack = []  # 标题上下文栈
        
        # 遍历所有节点进行智能分块
        for i, node in enumerate(tree.children):
            # 获取节点的详细信息和关联关系
            node_info = _analyze_advanced_node(node, context_stack, doc_structure, i, cached_token_count)
            
            if not node_info:
                continue
            
            # 决定分块策略
            should_break, break_reason = _should_break_chunk_advanced(
                current_chunk, node_info, chunk_token_num, min_chunk_tokens
            )
            
            if should_break and not current_chunk.is_empty() and current_chunk.token_count >= min_chunk_tokens:
                # 完成当前块并添加上下文
                chunk_content = _finalize_advanced_chunk(current_chunk, context_stack, doc_structure)
                if chunk_content.strip():
                    chunks.append(chunk_content)
                current_chunk = AdvancedChunkBuilder()
            
            # 将节点添加到当前块
            current_chunk.add_node(node_info)
            
            # 更新上下文栈
            if node_info['type'] == 'heading':
                _update_context_stack(context_stack, node_info['level'], node_info['title'])
        
        # 处理最后的块
        if not current_chunk.is_empty():
            chunk_content = _finalize_advanced_chunk(current_chunk, context_stack, doc_structure)
            if chunk_content.strip():
                chunks.append(chunk_content)
        
        # 后处理：重叠分块（如果启用）
        if overlap_ratio > 0:
            chunks = _create_semantic_overlap_chunks(chunks, overlap_ratio, chunk_token_num, cached_token_count)
        
        # 元数据处理
        if include_metadata:
            enhanced_chunks = []
            for i, chunk in enumerate(chunks):
                chunk_data = {
                    'content': chunk,
                    'index': i,
                    'token_count': cached_token_count(chunk)
                }
                metadata = _extract_advanced_chunk_metadata(chunk, doc_structure, i)
                chunk_data.update(metadata)
                enhanced_chunks.append(chunk_data)
            return enhanced_chunks
        
        return [chunk for chunk in chunks if chunk.strip()]
    
    except Exception as e:
        print(f"Advanced parsing failed: {e}, falling back to smart chunking")
        return split_markdown_to_chunks_smart(txt, chunk_token_num, min_chunk_tokens)


class AdvancedChunkBuilder:
    """高级分块构建器，支持智能边界和关联处理"""
    
    def __init__(self):
        self.nodes = []
        self.token_count = 0
        self.has_heading = False
        self.content_types = set()
        
    def add_node(self, node_info):
        """添加节点到当前块"""
        self.nodes.append(node_info)
        self.token_count += node_info['tokens']
        
        if node_info['type'] == 'heading':
            self.has_heading = True
        
        self.content_types.add(node_info['type'])
    
    def is_empty(self):
        return len(self.nodes) == 0
    
    def get_last_node(self):
        return self.nodes[-1] if self.nodes else None
    
    def contains_type(self, node_type):
        return node_type in self.content_types


def _extract_advanced_document_structure(tree):
    """提取高级文档结构，包含节点关系和位置信息"""
    structure = {
        'headings': [],
        'tables': [],
        'table_contexts': {},  # 表格与前后文的关联
        'code_blocks': [],
        'lists': [],
        'nested_structures': {},  # 嵌套结构映射
        'node_positions': {},  # 节点位置映射
    }
    
    def traverse_advanced(node, path=[], parent=None, depth=0):
        node_id = f"{node.type}_{len(path)}"
        position = len(structure.get('node_positions', {}))
        
        # 记录节点位置
        structure['node_positions'][node_id] = {
            'position': position,
            'depth': depth,
            'parent': parent,
            'path': path.copy()
        }
        
        if node.type == 'heading':
            level = int(node.tag[1]) if node.tag else 1
            title = _extract_text_from_node(node)
            heading_info = {
                'level': level,
                'title': title,
                'position': position,
                'node_id': node_id
            }
            structure['headings'].append(heading_info)
            
        elif node.type == 'table':
            table_content = _render_table_from_ast(node)
            table_info = {
                'content': table_content,
                'position': position,
                'node_id': node_id
            }
            structure['tables'].append(table_info)
            
            # 分析表格前后文（前后2个节点）
            _analyze_table_context(structure, position, tree.children)
            
        elif node.type == 'code_block':
            structure['code_blocks'].append({
                'language': getattr(node, 'info', '') or '',
                'content': getattr(node, 'content', ''),
                'position': position,
                'node_id': node_id
            })
            
        elif node.type in ['bullet_list', 'ordered_list']:
            list_info = {
                'type': node.type,
                'content': _render_list_from_ast(node),
                'position': position,
                'node_id': node_id,
                'nested_items': []
            }
            
            # 处理嵌套列表
            _extract_nested_list_structure(node, list_info['nested_items'], depth + 1)
            structure['lists'].append(list_info)
        
        # 递归处理子节点
        if hasattr(node, 'children') and node.children:
            for i, child in enumerate(node.children):
                child_path = path + [i]
                traverse_advanced(child, child_path, node_id, depth + 1)
    
    # 遍历根节点
    for i, node in enumerate(tree.children):
        traverse_advanced(node, [i])
    
    return structure


def _analyze_table_context(structure, table_position, all_nodes):
    """分析表格的前后文关系"""
    context_range = 2  # 前后各2个节点
    context_info = {
        'preceding': [],
        'following': []
    }
    
    # 分析前文
    start_idx = max(0, table_position - context_range)
    for i in range(start_idx, table_position):
        if i < len(all_nodes):
            node = all_nodes[i]
            if node.type in ['paragraph', 'heading']:
                context_info['preceding'].append({
                    'type': node.type,
                    'content': _extract_text_from_node(node)[:200],  # 限制长度
                    'position': i
                })
    
    # 分析后文
    end_idx = min(len(all_nodes), table_position + context_range + 1)
    for i in range(table_position + 1, end_idx):
        if i < len(all_nodes):
            node = all_nodes[i]
            if node.type in ['paragraph', 'heading']:
                context_info['following'].append({
                    'type': node.type,
                    'content': _extract_text_from_node(node)[:200],
                    'position': i
                })
    
    structure['table_contexts'][table_position] = context_info


def _extract_nested_list_structure(list_node, nested_items, depth):
    """提取嵌套列表结构"""
    for item in list_node.children:
        if item.type == "list_item":
            item_info = {
                'content': _extract_text_from_node(item),
                'depth': depth,
                'sub_items': []
            }
            
            # 检查是否有嵌套列表
            if hasattr(item, 'children'):
                for child in item.children:
                    if child.type in ['bullet_list', 'ordered_list']:
                        _extract_nested_list_structure(child, item_info['sub_items'], depth + 1)
            
            nested_items.append(item_info)


def _analyze_advanced_node(node, context_stack, doc_structure, position, cached_token_count):
    """深度分析节点，返回详细的节点信息"""
    node_type = node.type
    content = ""
    metadata = {}
    
    if node_type == "heading":
        level = int(node.tag[1])
        title = _extract_text_from_node(node)
        content = node.markup + " " + title
        metadata = {
            'level': level,
            'title': title,
            'is_major_section': level <= 2
        }
        
    elif node_type == "table":
        content = _render_table_from_ast(node)
        
        # 获取表格关联的上下文
        table_context = doc_structure['table_contexts'].get(position, {})
        metadata = {
            'has_context': bool(table_context.get('preceding') or table_context.get('following')),
            'context_info': table_context
        }
        
    elif node_type == "code_block":
        content = f"```{node.info or ''}\n{node.content}```"
        metadata = {
            'language': getattr(node, 'info', '') or '',
            'is_executable': getattr(node, 'info', '') in ['python', 'javascript', 'bash', 'sql']
        }
        
    elif node_type == "paragraph":
        content = _extract_text_from_node(node)
        
        # 智能分析段落的语义完整性
        metadata = {
            'sentence_count': len([s for s in content.split('.') if s.strip()]),
            'ends_complete': content.strip().endswith(('.', '!', '?', '。', '！', '？')),
            'is_transition': any(keyword in content.lower() for keyword in 
                               ['因此', '所以', '总之', '另外', 'therefore', 'however', 'moreover'])
        }
        
    elif node_type in ["bullet_list", "ordered_list"]:
        content = _render_list_from_ast(node)
        
        # 分析列表的嵌套深度
        nested_info = next((item for item in doc_structure['lists'] 
                          if item['position'] == position), {})
        metadata = {
            'list_type': node_type,
            'has_nested': bool(nested_info.get('nested_items')),
            'nested_depth': _calculate_max_nested_depth(nested_info.get('nested_items', []))
        }
        
    elif node_type == "blockquote":
        content = _render_blockquote_from_ast(node)
        metadata = {'is_citation': True}
        
    elif node_type == "hr":
        content = "---"
        metadata = {'is_section_break': True}
        
    else:
        content = _extract_text_from_node(node)
        metadata = {}
    
    if not content:
        return None
    
    return {
        'type': node_type,
        'content': content,
        'tokens': cached_token_count(content),
        'position': position,
        'metadata': metadata,
        **metadata  # 展开metadata到顶层，方便访问
    }


def _calculate_max_nested_depth(nested_items):
    """计算嵌套列表的最大深度"""
    if not nested_items:
        return 0
    
    max_depth = 0
    for item in nested_items:
        if item.get('sub_items'):
            depth = 1 + _calculate_max_nested_depth(item['sub_items'])
            max_depth = max(max_depth, depth)
    
    return max_depth


def _should_break_chunk_advanced(current_chunk, node_info, chunk_token_num, min_chunk_tokens):
    """高级分块边界判断，考虑语义完整性"""
    node_type = node_info['type']
    node_tokens = node_info['tokens']
    
    # 强制分块情况
    force_break_conditions = [
        # 1. 主要标题（h1, h2）
        (node_type == 'heading' and node_info.get('is_major_section', False)),
        
        # 2. 分隔符
        (node_type == 'hr'),
        
        # 3. 大表格独立成块
        (node_type == 'table' and node_tokens > chunk_token_num * 0.8),
        
        # 4. 大代码块独立成块
        (node_type == 'code_block' and node_tokens > chunk_token_num * 0.6),
    ]
    
    if any(force_break_conditions):
        return True, "force_break"
    
    # 智能分块判断
    if current_chunk.token_count + node_tokens > chunk_token_num:
        
        # 如果当前块还没到最小大小，优先不分块
        if current_chunk.token_count < min_chunk_tokens:
            return False, "under_min_size"
        
        # 语义完整性检查
        last_node = current_chunk.get_last_node()
        if last_node:
            # 避免在句子中间分块
            if (last_node['type'] == 'paragraph' and 
                not last_node.get('ends_complete', False)):
                # 如果不会造成严重超标，就不分块
                if current_chunk.token_count + node_tokens < chunk_token_num * 1.3:
                    return False, "incomplete_sentence"
            
            # 保持相关内容的连贯性
            if _should_keep_together(last_node, node_info):
                if current_chunk.token_count + node_tokens < chunk_token_num * 1.5:
                    return False, "keep_related_content"
        
        return True, "size_limit"
    
    return False, "continue"


def _should_keep_together(last_node, current_node):
    """判断两个节点是否应该保持在一起"""
    # 表格与其说明文字保持在一起
    if (last_node['type'] == 'paragraph' and current_node['type'] == 'table'):
        return True
    
    if (last_node['type'] == 'table' and current_node['type'] == 'paragraph'):
        return True
    
    # 代码块与其说明保持在一起
    if (last_node['type'] == 'paragraph' and current_node['type'] == 'code_block'):
        return True
    
    # 列表项之间保持连贯性
    if (last_node['type'] in ['bullet_list', 'ordered_list'] and 
        current_node['type'] in ['bullet_list', 'ordered_list']):
        return True
    
    # 小标题与紧随的内容保持在一起
    if (last_node['type'] == 'heading' and 
        last_node.get('level', 1) >= 3 and
        current_node['type'] in ['paragraph', 'list']):
        return True
    
    return False


def _finalize_advanced_chunk(chunk_builder, context_stack, doc_structure):
    """完成高级分块的格式化，添加上下文增强"""
    if chunk_builder.is_empty():
        return ""
    
    content_parts = []
    
    # 1. 上下文增强：如果块没有标题，添加父级标题上下文
    if not chunk_builder.has_heading and context_stack:
        # 选择最相关的上下文标题
        context_title = _select_relevant_context(context_stack, chunk_builder)
        if context_title:
            content_parts.append(f"## 上下文: {context_title}\n")
    
    # 2. 按类型优化排序和格式化
    sorted_nodes = _sort_chunk_nodes_semantically(chunk_builder.nodes)
    
    # 3. 生成最终内容
    for node_info in sorted_nodes:
        content = node_info['content']
        
        # 特殊处理：为表格添加关联说明
        if node_info['type'] == 'table' and node_info.get('has_context'):
            context_info = node_info.get('context_info', {})
            
            # 添加前文说明
            preceding = context_info.get('preceding', [])
            if preceding:
                relevant_context = [p['content'] for p in preceding[-1:]]  # 最近的1个前文
                if relevant_context:
                    content = f"*相关说明: {relevant_context[0][:100]}...*\n\n{content}"
        
        content_parts.append(content)
    
    return "\n\n".join(content_parts).strip()


def _select_relevant_context(context_stack, chunk_builder):
    """选择最相关的上下文标题"""
    if not context_stack:
        return None
    
    # 优先选择最近的、级别合适的标题
    for i in range(len(context_stack) - 1, -1, -1):
        context = context_stack[i]
        if context['level'] <= 3:  # 只使用较高级别的标题作为上下文
            return context['title']
    
    return context_stack[-1]['title']  # 默认使用最近的标题


def _sort_chunk_nodes_semantically(nodes):
    """按语义相关性对块内节点排序"""
    # 排序优先级：标题 > 段落 > 列表 > 表格 > 代码块 > 其他
    priority_map = {
        'heading': 1,
        'paragraph': 2,
        'bullet_list': 3,
        'ordered_list': 3,
        'table': 4,
        'code_block': 5,
        'blockquote': 6,
        'hr': 7
    }
    
    return sorted(nodes, key=lambda x: (priority_map.get(x['type'], 8), x['position']))


def _create_semantic_overlap_chunks(chunks, overlap_ratio, max_tokens, cached_token_count):
    """创建语义感知的重叠分块"""
    if overlap_ratio <= 0 or len(chunks) < 2:
        return chunks
    
    overlapped_chunks = []
    
    for i in range(len(chunks)):
        # 添加原始分块
        overlapped_chunks.append(chunks[i])
        
        # 在相邻分块之间创建重叠分块
        if i < len(chunks) - 1:
            current_content = chunks[i]
            next_content = chunks[i + 1]
            
            # 创建语义感知的重叠
            overlap_content = _create_semantic_overlap(
                current_content, next_content, overlap_ratio, max_tokens, cached_token_count
            )
            
            if overlap_content:
                overlapped_chunks.append(overlap_content)
    
    return overlapped_chunks


def _create_semantic_overlap(current_content, next_content, overlap_ratio, max_tokens, cached_token_count):
    """创建语义感知的重叠内容"""
    # 按段落分割，而不是按词分割
    current_paragraphs = [p.strip() for p in current_content.split('\n\n') if p.strip()]
    next_paragraphs = [p.strip() for p in next_content.split('\n\n') if p.strip()]
    
    if not current_paragraphs or not next_paragraphs:
        return None
    
    # 取最后的段落和开头的段落
    overlap_parts = []
    
    # 从当前内容的末尾取段落
    current_tokens = cached_token_count(current_content)
    target_overlap_tokens = int(current_tokens * overlap_ratio)
    
    for p in reversed(current_paragraphs):
        overlap_parts.insert(0, p)
        if cached_token_count('\n\n'.join(overlap_parts)) >= target_overlap_tokens // 2:
            break
    
    # 从下一个内容的开头取段落
    next_tokens = cached_token_count(next_content)
    target_next_tokens = int(next_tokens * overlap_ratio)
    
    for p in next_paragraphs:
        overlap_parts.append(p)
        if cached_token_count('\n\n'.join(overlap_parts)) >= target_overlap_tokens:
            break
    
    overlap_content = '\n\n'.join(overlap_parts)
    
    # 确保重叠内容有意义
    if cached_token_count(overlap_content) >= 50:
        return overlap_content
    
    return None


def _extract_advanced_chunk_metadata(chunk_content, doc_structure, chunk_index):
    """提取高级块元数据"""
    metadata = {
        'chunk_type': 'mixed',
        'has_context_enhancement': '[上下文:' in chunk_content,
        'contains_table': False,
        'contains_code': False,
        'contains_list': False,
        'contains_overlap_marker': '[...内容继续...]' in chunk_content,
        'semantic_completeness': 0.0,
        'content_density': 0.0,
        'structure_types': []
    }
    
    # 分析内容类型
    if '<table' in chunk_content or '|' in chunk_content:
        metadata['contains_table'] = True
        metadata['structure_types'].append('table')
        if metadata['chunk_type'] == 'mixed':
            metadata['chunk_type'] = 'table'
    
    if '```' in chunk_content:
        metadata['contains_code'] = True
        metadata['structure_types'].append('code')
        if metadata['chunk_type'] == 'mixed':
            metadata['chunk_type'] = 'code'
    
    if any(line.strip().startswith(('- ', '* ', '+ ')) or 
           (len(line.strip()) > 2 and line.strip()[0].isdigit() and line.strip()[1:3] in ['. ', ') ']) 
           for line in chunk_content.split('\n')):
        metadata['contains_list'] = True
        metadata['structure_types'].append('list')
        if metadata['chunk_type'] == 'mixed':
            metadata['chunk_type'] = 'list'
    
    # 语义完整性评分
    metadata['semantic_completeness'] = _calculate_semantic_completeness_score(chunk_content)
    
    # 内容密度评分
    metadata['content_density'] = _calculate_content_density_score(chunk_content)
    
    return metadata


def _calculate_semantic_completeness_score(content):
    """计算语义完整性评分"""
    score = 0.0
    
    # 检查是否有完整的句子结构
    sentences = [s.strip() for s in content.replace('。', '.').split('.') if s.strip()]
    if sentences:
        complete_sentences = sum(1 for s in sentences if len(s.split()) >= 3)
        score += min(complete_sentences / len(sentences), 0.4)
    
    # 检查是否有标题结构
    if any(line.strip().startswith('#') for line in content.split('\n')):
        score += 0.3
    
    # 检查内容是否以完整句子结束
    if content.strip().endswith(('.', '。', '!', '！', '?', '？')):
        score += 0.3
    
    return min(score, 1.0)


def _calculate_content_density_score(content):
    """计算内容密度评分"""
    if not content.strip():
        return 0.0
    
    # 计算信息词汇比例
    words = content.split()
    if not words:
        return 0.0
    
    # 过滤停用词和功能词汇
    stopwords = {'的', '是', '在', '有', '和', '与', '或', '但', '因为', '所以', 'the', 'is', 'in', 'and', 'or', 'but'}
    content_words = [w for w in words if len(w) > 2 and w.lower() not in stopwords]
    
    density = len(content_words) / len(words)
    return min(density, 1.0)


def optimize_chunks_for_rag(chunks, target_vector_dim=1536):
    """
    针对RAG优化分块：
    1. 长度标准化
    2. 质量评分
    3. 向量化友好性
    4. 语义完整性增强
    """
    optimized_chunks = []
    
    for chunk_data in chunks:
        if isinstance(chunk_data, str):
            chunk_data = {'content': chunk_data, 'token_count': num_tokens_from_string(chunk_data)}
        
        # 质量评分
        quality_score = _calculate_chunk_quality(chunk_data['content'])
        chunk_data['quality_score'] = quality_score
        
        # 向量化友好性评分
        vector_friendliness = _calculate_vector_friendliness(chunk_data['content'])
        chunk_data['vector_friendliness'] = vector_friendliness
        
        # 语义完整性检查
        semantic_completeness = _calculate_semantic_completeness_score(chunk_data['content'])
        chunk_data['semantic_completeness'] = semantic_completeness
        
        optimized_chunks.append(chunk_data)
    
    # 按质量评分排序（可选）
    optimized_chunks.sort(key=lambda x: x.get('quality_score', 0), reverse=True)
    
    return optimized_chunks


def _calculate_chunk_quality(content):
    """计算chunk质量评分"""
    score = 0.0
    
    # 长度适中加分
    token_count = num_tokens_from_string(content)
    if 100 <= token_count <= 800:
        score += 0.3
    
    # 包含完整句子加分
    sentences = content.split('.')
    complete_sentences = sum(1 for s in sentences if len(s.strip()) > 10)
    score += min(complete_sentences * 0.1, 0.3)
    
    # 结构化内容加分
    if any(marker in content for marker in ['#', '##', '###', '- ', '* ', '1. ']):
        score += 0.2
    
    # 信息密度
    words = content.split()
    unique_words = len(set(word.lower() for word in words if len(word) > 3))
    if words:
        diversity_ratio = unique_words / len(words)
        score += diversity_ratio * 0.2
    
    return min(score, 1.0)


def _calculate_vector_friendliness(content):
    """计算向量化友好性"""
    score = 0.0
    
    # 避免过多的特殊字符
    special_char_ratio = sum(1 for c in content if not c.isalnum() and c not in ' \n\t.,!?') / len(content)
    score += max(0, 0.3 - special_char_ratio)
    
    # 包含关键信息词汇
    key_indicators = ['是', '的', '在', '有', '为', '与', '和', '或', '但', '因为', '所以']
    indicator_count = sum(1 for word in key_indicators if word in content)
    score += min(indicator_count * 0.05, 0.3)
    
    # 语言连贯性
    sentences = [s.strip() for s in content.split('.') if s.strip()]
    if len(sentences) >= 2:
        score += 0.4
    
    return min(score, 1.0)