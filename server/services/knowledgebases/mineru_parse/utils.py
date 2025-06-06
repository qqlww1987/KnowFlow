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