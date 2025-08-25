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
import re
from markdown import markdown as md_to_html
import time
import difflib
try:
    from markdown_it import MarkdownIt
    from markdown_it.tree import SyntaxTreeNode
    MARKDOWN_IT_AVAILABLE = True
except ImportError:
    MARKDOWN_IT_AVAILABLE = False
    print("Warning: markdown-it-py not available. Please install with: pip install markdown-it-py")

from ...config import CONFIG, APP_CONFIG


# 分块模式配置
# CHUNK_METHOD = os.getenv('CHUNK_METHOD', 'smart')  # 默认使用 smart 模式


def get_configured_chunk_method():
    """获取配置的分块方法"""
    return APP_CONFIG.chunk_method


def is_dev_mode():
    """检查是否处于开发模式"""
    return APP_CONFIG.dev_mode


def should_cleanup_temp_files():
    """检查是否应该清理临时文件"""
    # 在dev模式下，默认不清理临时文件，但环境变量仍可覆盖
    if is_dev_mode():
        return APP_CONFIG.cleanup_temp_files
    # 在非dev模式下，默认清理，但环境变量仍可覆盖
    return APP_CONFIG.cleanup_temp_files


def split_markdown_to_chunks_configured(txt, chunk_token_num=256, min_chunk_tokens=10, **kwargs):
    """
    根据配置选择合适的分块方法的统一接口
    
    支持的分块方法：
    - 'parent_child': 父子分块模式，基于Smart分块的双层结构
    - 'strict_regex': 严格按正则表达式分块（当配置启用时）
    - 'advanced': split_markdown_to_chunks_advanced (高级分块，混合策略)
    - 'smart': split_markdown_to_chunks_smart (智能分块，基于AST，默认)
    - 'basic': split_markdown_to_chunks (基础分块)
    
    可通过环境变量 CHUNK_METHOD 配置，支持的值：parent_child, advanced, smart, basic
    也可通过kwargs传入自定义配置：
    - chunking_config: 分块配置字典，包含strategy等字段
    """
    # 添加调试打印
    print("=" * 80)
    print("🔍 [DEBUG] split_markdown_to_chunks_configured 调用参数:")
    print(f"📝 文本长度: {len(txt) if txt else 0} 字符")
    print(f"🔢 chunk_token_num: {chunk_token_num}")
    print(f"🔢 min_chunk_tokens: {min_chunk_tokens}")
    print(f"📋 kwargs 键值对:")
    for key, value in kwargs.items():
        if key == 'chunking_config' and isinstance(value, dict):
            print(f"  📌 {key}:")
            for sub_key, sub_value in value.items():
                print(f"    🔸 {sub_key}: {sub_value}")
        else:
            print(f"  📌 {key}: {value}")
    print("=" * 80)
    
    # 检查是否有自定义的分块配置（从文档配置传入）
    custom_chunking_config = kwargs.get('chunking_config', None)
    
    if custom_chunking_config:
        print(f"🎯 [DEBUG] 使用自定义分块配置: {custom_chunking_config}")
        # 使用文档级别的分块配置
        strategy = custom_chunking_config.get('strategy', 'smart')
        chunk_token_num = custom_chunking_config.get('chunk_token_num', chunk_token_num)
        min_chunk_tokens = custom_chunking_config.get('min_chunk_tokens', min_chunk_tokens)
        
        print(f"🚀 [DEBUG] 最终分块参数:")
        print(f"  📋 策略: {strategy}")
        print(f"  🔢 分块大小: {chunk_token_num}")
        print(f"  🔢 最小分块: {min_chunk_tokens}")
        
        # 其他策略的处理
        if strategy == 'parent_child':
            print(f"  🎯 使用父子分块策略")
            return split_markdown_to_chunks_parent_child(
                txt,
                chunk_token_num=chunk_token_num,
                min_chunk_tokens=min_chunk_tokens,
                parent_config=custom_chunking_config.get('parent_config', {}),
                doc_id=kwargs.get('doc_id', 'unknown'),
                kb_id=kwargs.get('kb_id', 'unknown')
            )
        elif strategy == 'advanced':
            include_metadata = kwargs.pop('include_metadata', False)
            overlap_ratio = kwargs.pop('overlap_ratio', 0.0)
            print(f"  🎯 使用高级分块策略")
            return split_markdown_to_chunks_advanced(
                txt, 
                chunk_token_num=chunk_token_num, 
                min_chunk_tokens=min_chunk_tokens,
                overlap_ratio=overlap_ratio,
                include_metadata=include_metadata
            )

        elif strategy == 'strict_regex':
            regex_pattern = custom_chunking_config.get('regex_pattern', '')
            print(f"  🎯 使用正则分块策略, 模式: {regex_pattern}")
            if regex_pattern:
                return split_markdown_to_chunks_strict_regex(
                    txt, 
                    chunk_token_num=chunk_token_num, 
                    min_chunk_tokens=min_chunk_tokens, 
                    regex_pattern=regex_pattern
                )
            else:
                print(f"  ⚠️ 正则表达式为空，回退到智能分块")
                # 如果没有正则表达式，回退到智能分块
                return split_markdown_to_chunks_smart(txt, chunk_token_num, min_chunk_tokens)

        elif strategy == 'smart':
            print(f"  🎯 使用智能分块策略")
            return split_markdown_to_chunks_smart(
                txt, 
                chunk_token_num=chunk_token_num, 
                min_chunk_tokens=min_chunk_tokens
            )
        elif strategy == 'basic':
            delimiter = custom_chunking_config.get('delimiter', "\n!?。；！？")
            print(f"  🎯 使用基础分块策略, 分隔符: {delimiter}")
            return split_markdown_to_chunks(
                txt, 
                chunk_token_num=chunk_token_num,
                delimiter=delimiter
            )
    else:
        print(f"🔄 [DEBUG] 使用默认配置 - 环境变量或回退到智能分块")
        # 原有的环境变量配置逻辑...
        method = get_configured_chunk_method()
        print(f"  📊 环境配置方法: {method}")
        
        if method == 'advanced':
            include_metadata = kwargs.pop('include_metadata', False)
            overlap_ratio = kwargs.pop('overlap_ratio', 0.0)
            return split_markdown_to_chunks_advanced(
                txt, 
                chunk_token_num=chunk_token_num, 
                min_chunk_tokens=min_chunk_tokens,
                overlap_ratio=overlap_ratio,
                include_metadata=include_metadata
            )
        elif method == 'basic':
            delimiter = kwargs.pop('delimiter', "\n!?。；！？")
            return split_markdown_to_chunks(
                txt, 
                chunk_token_num=chunk_token_num,
                delimiter=delimiter
            )
        else:  # 默认使用智能分块
            return split_markdown_to_chunks_smart(txt, chunk_token_num, min_chunk_tokens)


def singleton(cls, *args, **kw):
    instances = {}

    def _singleton():
        key = str(cls) + str(os.getpid())
        if key not in instances:
            instances[key] = cls(*args, **kw)
        return instances[key]

    return _singleton


# 设置tiktoken缓存目录，优先使用环境变量，否则使用默认路径
tiktoken_cache_dir = os.environ.get("TIKTOKEN_CACHE_DIR", "/opt/tiktoken_cache")
# 确保缓存目录存在
os.makedirs(tiktoken_cache_dir, exist_ok=True)
os.environ["TIKTOKEN_CACHE_DIR"] = tiktoken_cache_dir
# encoder = tiktoken.encoding_for_model("gpt-3.5-turbo")
encoder = tiktoken.get_encoding("cl100k_base")


def num_tokens_from_string(string: str, model_name: str = "cl100k_base") -> int:
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
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
            block_list = []
            
            # 检查数据结构类型
            if 'pdf_info' not in data:
                print(f"[WARNING] 无效的数据结构: 缺少 pdf_info 字段")
                _blocks_cache[md_file_path] = []
                return []
            
            for page_idx, page in enumerate(data['pdf_info']):
                # Pipeline模式：有preproc_blocks字段
                if 'preproc_blocks' in page:
                    print(f"[INFO] 检测到Pipeline模式数据结构")
                    for block in page['preproc_blocks']:
                        bbox = block.get('bbox')
                        if not bbox:
                            continue
                        
                        # 提取文本内容
                        text_content = ''
                        if 'lines' in block:
                            for line in block['lines']:
                                if 'spans' in line:
                                    for span in line['spans']:
                                        if 'content' in span:
                                            text_content += span['content']
                        
                        block_data = {
                            'bbox': bbox,
                            'type': block.get('type', 'unknown'),
                            'text': text_content.strip(),
                            'page_idx': page_idx,
                            'index': block.get('index', 0),
                            'source_mode': 'pipeline'
                        }
                        block_list.append(block_data)
                
                # VLM模式：使用para_blocks字段（数组格式）
                elif 'para_blocks' in page:
                    print(f"[INFO] 检测到VLM模式数据结构")
                    para_blocks = page['para_blocks']
                    if isinstance(para_blocks, list):
                        # VLM模式: para_blocks是数组
                        for block in para_blocks:
                            bbox = block.get('bbox')
                            if not bbox:
                                continue
                            
                            # 提取文本内容
                            text_content = ''
                            if 'lines' in block:
                                for line in block['lines']:
                                    if 'spans' in line:
                                        for span in line['spans']:
                                            if 'content' in span:
                                                text_content += span['content']
                            
                            block_data = {
                                'bbox': bbox,
                                'type': block.get('type', 'unknown'),
                                'text': text_content.strip(),
                                'page_idx': page_idx,
                                'index': block.get('index', 0),
                                'source_mode': 'vlm'
                            }
                            block_list.append(block_data)
                    else:
                        print(f"[WARNING] VLM模式para_blocks格式异常，期望数组但得到: {type(para_blocks)}")
                
                else:
                    print(f"[WARNING] 第{page_idx}页缺少preproc_blocks和para_blocks字段")
                    # 尝试其他可能的字段名
                    possible_fields = ['blocks', 'text_blocks', 'content_blocks']
                    found = False
                    for field_name in possible_fields:
                        if field_name in page:
                            print(f"[INFO] 尝试使用字段: {field_name}")
                            found = True
                            break
                    
                    if not found:
                        print(f"[WARNING] 无法识别页面数据结构，跳过第{page_idx}页")
            
            print(f"[INFO] 从{json_path}提取了{len(block_list)}个块")
            _blocks_cache[md_file_path] = block_list
            return block_list
            
    except FileNotFoundError:
        print(f"[WARNING] JSON文件不存在: {json_path}")
        _blocks_cache[md_file_path] = []
        return []
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON解析失败: {e}")
        _blocks_cache[md_file_path] = []
        return []
    except Exception as e:
        print(f"[ERROR] 获取块列表失败: {e}")
        _blocks_cache[md_file_path] = []
        return []

# 全局或外部传入
matched_global_indices = set()

def get_bbox_for_chunk(md_file_path, chunk_content, block_list=None, matched_global_indices=None):
    """
    根据 md 文件路径和 chunk 内容，返回构成该 chunk 的连续 block 的 bbox 列表。
    采用 difflib.SequenceMatcher 找出最相似的 block（相似度最高），
    然后从该锚点向前后扩展，寻找同样存在于 chunk 中的连续 block。
    支持外部传入 block_list，避免重复解析。
    支持Pipeline模式和VLM模式的数据结构。
    匹配到的块会通过 matched_global_indices 记录，避免后续 chunk 重复匹配。
    """
    try:
        if block_list is None:
            block_list = get_blocks_from_md(md_file_path)
        if matched_global_indices is None:
            matched_global_indices = set()
        if not block_list:
            print(f"[WARNING] 无法获取块列表，跳过位置信息获取")
            return None

        chunk_content_clean = chunk_content.strip()
        if not chunk_content_clean:
            return None

        # 用 difflib.SequenceMatcher 找最相似的 block
        best_idx = -1
        best_ratio = 0.0
        for i, block in enumerate(block_list):
            if i in matched_global_indices:
                continue
            block_text = block.get('text', '').strip()
            if not block_text:
                continue
            ratio = difflib.SequenceMatcher(None, chunk_content_clean, block_text).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_idx = i
        if best_idx == -1 or best_ratio < 0.1:  # 阈值可调整
            print(f"[WARNING] 未找到足够相似的块 (最高相似度: {best_ratio:.3f})")
            return None

        # 从锚点扩展
        matched_indices = [best_idx]
        # 向前扩展
        for i in range(best_idx - 1, -1, -1):
            if i in matched_global_indices:
                continue
            block_text = block_list[i].get('text', '').strip()
            if block_text and block_text in chunk_content_clean:
                matched_indices.insert(0, i)
            else:
                break
        # 向后扩展
        for i in range(best_idx + 1, len(block_list)):
            if i in matched_global_indices:
                continue
            block_text = block_list[i].get('text', '').strip()
            if block_text and block_text in chunk_content_clean:
                matched_indices.append(i)
            else:
                break
        # 提取位置信息
        positions = []
        for idx in matched_indices:
            block = block_list[idx]
            bbox = block.get('bbox')
            page_number = block.get('page_idx')
            if bbox and page_number is not None:
                position = [page_number, bbox[0], bbox[2], bbox[1], bbox[3]]
                positions.append(position)
        # 记录已匹配 block 索引
        matched_global_indices.update(matched_indices)
        if positions:
            print(f"[INFO] 为chunk找到{len(positions)}个位置（最高相似度: {best_ratio:.3f}），并已记录 matched_global_indices")
            return positions
        else:
            print(f"[WARNING] 未能提取到有效的位置信息")
            return None
    except Exception as e:
        print(f"[ERROR] 获取chunk位置失败: {e}")
        return None


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
            updates.append("process_duration = %s")
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


def split_markdown_to_chunks_smart(txt, chunk_token_num=256, min_chunk_tokens=10):
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


def split_markdown_to_chunks_advanced(txt, chunk_token_num=256, min_chunk_tokens=10, 
                                     overlap_ratio=0.0, include_metadata=False):
    """
    基于标题层级的高级 Markdown 分块方法 (混合分块策略 + 动态阈值调整)
    
    核心特性：
    1. 保持标题作为主要分块边界
    2. 动态大小控制：目标300-600 tokens，最大800 tokens，最小50 tokens  
    3. 处理超大分块：在段落边界进一步分割
    4. 处理超小分块：与相邻分块合并
    5. 特殊内容处理：保持表格、代码块、公式完整性
    6. 智能上下文增强
    """
    if not MARKDOWN_IT_AVAILABLE:
        return split_markdown_to_chunks(txt, chunk_token_num)
    
    if not txt or not txt.strip():
        return []

    # 动态阈值配置
    target_min_tokens = max(50, min_chunk_tokens // 2)  # 最小50 tokens
    target_tokens = min(600, chunk_token_num)  # 目标大小：300-600 tokens
    target_max_tokens = min(800, chunk_token_num * 1.5)  # 最大800 tokens
    
    # 配置要作为分块边界的标题级别
    headers_to_split_on = [1, 2, 3]  # H1, H2, H3 作为分块边界
    
    # 初始化 markdown-it 解析器
    md = MarkdownIt("commonmark", {"breaks": True, "html": True})
    md.enable(['table'])
    
    try:
        # 解析为 AST
        tokens = md.parse(txt)
        tree = SyntaxTreeNode(tokens)
        
        # 提取所有节点和标题信息
        nodes_with_headers = _extract_nodes_with_header_info(tree, headers_to_split_on)
        
        # 基于标题层级进行初步分块
        initial_chunks = _split_by_header_levels(nodes_with_headers, headers_to_split_on)
        
        # 应用动态大小控制和优化
        optimized_chunks = _apply_size_control_and_optimization(
            initial_chunks, target_min_tokens, target_tokens, target_max_tokens
        )
        
        # 生成最终分块内容
        final_chunks = []
        for chunk_info in optimized_chunks:
            content = _render_header_chunk_advanced(chunk_info)
            if content.strip():
                if include_metadata:
                    chunk_data = {
                        'content': content,
                        'metadata': chunk_info.get('headers', {}),
                        'token_count': num_tokens_from_string(content),
                        'chunk_type': chunk_info.get('chunk_type', 'header_based'),
                        'has_special_content': chunk_info.get('has_special_content', False),
                        'source_sections': chunk_info.get('source_sections', 1)
                    }
                    final_chunks.append(chunk_data)
                else:
                    final_chunks.append(content)
        
        return final_chunks
    
    except Exception as e:
        print(f"Advanced header-based parsing failed: {e}, falling back to smart chunking")
        return split_markdown_to_chunks_smart(txt, chunk_token_num, min_chunk_tokens)


def _apply_size_control_and_optimization(chunks, min_tokens, target_tokens, max_tokens):
    """应用动态大小控制和优化策略"""
    optimized_chunks = []
    
    i = 0
    while i < len(chunks):
        chunk = chunks[i]
        chunk_content = _render_header_chunk(chunk)
        chunk_tokens = num_tokens_from_string(chunk_content)
        
        # 检查特殊内容类型
        has_special_content = _has_special_content(chunk)
        
        if chunk_tokens <= max_tokens and chunk_tokens >= min_tokens:
            # 大小合适，直接添加
            chunk['chunk_type'] = 'normal'
            chunk['has_special_content'] = has_special_content
            optimized_chunks.append(chunk)
            
        elif chunk_tokens > max_tokens and not has_special_content:
            # 超大分块，需要进一步分割（除非包含特殊内容）
            split_chunks = _split_oversized_chunk(chunk, target_tokens, max_tokens)
            optimized_chunks.extend(split_chunks)
            
        elif chunk_tokens < min_tokens:
            # 超小分块，尝试与下一个分块合并
            merged_chunk = _try_merge_with_next(chunk, chunks, i, target_tokens)
            if merged_chunk:
                optimized_chunks.append(merged_chunk)
                # 跳过被合并的分块
                i += merged_chunk.get('merged_count', 1) - 1
            else:
                # 无法合并，添加上下文增强
                enhanced_chunk = _enhance_small_chunk_with_context(chunk)
                optimized_chunks.append(enhanced_chunk)
        else:
            # 包含特殊内容的超大分块，保持完整性但添加标记
            chunk['chunk_type'] = 'oversized_special'
            chunk['has_special_content'] = has_special_content
            optimized_chunks.append(chunk)
        
        i += 1
    
    return optimized_chunks


def _has_special_content(chunk):
    """检查分块是否包含特殊内容（表格、代码块、公式等）"""
    for node_info in chunk.get('nodes', []):
        node_type = node_info.get('type', '')
        content = node_info.get('content', '')
        
        # 检查特殊内容类型
        if node_type in ['table', 'code_block']:
            return True
        
        # 检查数学公式
        if '$$' in content or '$' in content:
            return True
            
        # 检查HTML表格
        if '<table>' in content and '</table>' in content:
            return True
            
    return False


def _split_oversized_chunk(chunk, target_tokens, max_tokens):
    """分割超大分块，在段落边界进行分割"""
    split_chunks = []
    nodes = chunk.get('nodes', [])
    headers = chunk.get('headers', {})
    
    current_nodes = []
    current_tokens = 0
    
    for node_info in nodes:
        node_content = node_info.get('content', '')
        node_tokens = num_tokens_from_string(node_content)
        
        # 检查是否是标题节点
        is_heading = node_info.get('type') == 'heading'
        
        # 如果当前节点会导致超出目标大小，且当前已有内容
        if current_tokens + node_tokens > target_tokens and current_nodes:
            # 创建一个分块
            new_chunk = {
                'headers': headers.copy(),
                'nodes': current_nodes.copy(),
                'chunk_type': 'split_from_oversized',
                'has_special_content': any(_has_special_content({'nodes': [n]}) for n in current_nodes)
            }
            split_chunks.append(new_chunk)
            
            # 开始新分块
            current_nodes = [node_info]
            current_tokens = node_tokens
            
            # 如果是标题，更新headers上下文
            if is_heading:
                level = node_info.get('level', 3)
                title = node_info.get('title', '')
                new_headers = {k: v for k, v in headers.items() if k < level}
                new_headers[level] = title
                headers = new_headers
        else:
            current_nodes.append(node_info)
            current_tokens += node_tokens
            
            # 更新标题上下文
            if is_heading:
                level = node_info.get('level', 3)
                title = node_info.get('title', '')
                headers = {k: v for k, v in headers.items() if k < level}
                headers[level] = title
    
    # 添加最后一个分块
    if current_nodes:
        final_chunk = {
            'headers': headers.copy(),
            'nodes': current_nodes,
            'chunk_type': 'split_from_oversized',
            'has_special_content': any(_has_special_content({'nodes': [n]}) for n in current_nodes)
        }
        split_chunks.append(final_chunk)
    
    return split_chunks


def _try_merge_with_next(current_chunk, all_chunks, current_index, target_tokens):
    """尝试将小分块与后续分块合并"""
    if current_index >= len(all_chunks) - 1:
        return None
    
    next_chunk = all_chunks[current_index + 1]
    
    # 计算合并后的大小
    current_content = _render_header_chunk(current_chunk)
    next_content = _render_header_chunk(next_chunk)
    merged_tokens = num_tokens_from_string(current_content + "\n\n" + next_content)
    
    # 如果合并后大小合适
    if merged_tokens <= target_tokens * 1.2:  # 允许轻微超出目标大小
        merged_chunk = {
            'headers': next_chunk.get('headers', current_chunk.get('headers', {})),
            'nodes': current_chunk.get('nodes', []) + next_chunk.get('nodes', []),
            'chunk_type': 'merged_small',
            'has_special_content': (_has_special_content(current_chunk) or 
                                  _has_special_content(next_chunk)),
            'merged_count': 2,
            'source_sections': 2
        }
        return merged_chunk
    
    return None


def _enhance_small_chunk_with_context(chunk):
    """为小分块增强上下文信息"""
    enhanced_chunk = chunk.copy()
    enhanced_chunk['chunk_type'] = 'small_enhanced'
    enhanced_chunk['has_special_content'] = _has_special_content(chunk)
    
    # 确保包含足够的标题上下文
    headers = chunk.get('headers', {})
    if headers:
        # 添加完整的标题路径作为上下文
        context_parts = []
        for level in sorted(headers.keys()):
            context_parts.append(f"{'#' * level} {headers[level]}")
        
        # 在节点前添加上下文信息
        if context_parts:
            context_node = {
                'type': 'context',
                'content': '\n'.join(context_parts),
                'headers': headers.copy(),
                'is_split_boundary': False
            }
            enhanced_chunk['nodes'] = [context_node] + enhanced_chunk.get('nodes', [])
    
    return enhanced_chunk


def _render_header_chunk_advanced(chunk_info):
    """高级渲染基于标题的分块内容，包含更好的格式化"""
    content_parts = []
    
    # 处理标题上下文
    chunk_has_header = any(node['type'] == 'heading' for node in chunk_info.get('nodes', []))
    headers = chunk_info.get('headers', {})
    
    # 为某些类型的分块添加标题上下文
    chunk_type = chunk_info.get('chunk_type', 'normal')
    if chunk_type in ['split_from_oversized', 'small_enhanced'] and headers and not chunk_has_header:
        # 添加最相关的上下文标题
        context_header = _get_most_relevant_header_advanced(headers, chunk_type)
        if context_header:
            content_parts.append(context_header)
    
    # 渲染所有节点内容（移除标记，保持内容干净）
    for node_info in chunk_info.get('nodes', []):
        if node_info.get('content', '').strip():
            content = node_info['content']
            # 直接使用原始内容，不添加任何标记
            content_parts.append(content)
    
    result = "\n\n".join(content_parts).strip()
    
    # 移除重叠分块的标识，保持内容干净
    # if chunk_type == 'overlap':
    #     result = f"[上下文关联内容]\n{result}"
    
    return result


def _get_most_relevant_header_advanced(headers, chunk_type):
    """获取最相关的上下文标题（高级版本）"""
    if not headers:
        return None
    
    # 根据分块类型选择不同的上下文策略
    if chunk_type == 'split_from_oversized':
        # 分割分块：显示最深层级的标题
        max_level = max(headers.keys())
        return f"{'#' * max_level} {headers[max_level]}"
    
    elif chunk_type in ['small_enhanced']:
        # 增强分块：显示最相关的标题
        max_level = max(headers.keys())
        return f"{'#' * max_level} {headers[max_level]}"
    
    else:
        # 普通分块：显示最相关的标题
        max_level = max(headers.keys())
        return f"{'#' * max_level} {headers[max_level]}"


def optimize_chunks_for_rag(chunks, target_vector_dim=1536):
    """
    基础RAG分块优化，为向量化做准备
    """
    optimized_chunks = []
    
    for chunk_data in chunks:
        if isinstance(chunk_data, str):
            chunk_data = {'content': chunk_data, 'token_count': num_tokens_from_string(chunk_data)}
        
        optimized_chunks.append(chunk_data)
    
    return optimized_chunks

def _extract_nodes_with_header_info(tree, headers_to_split_on):
    """提取所有节点及其对应的标题信息"""
    nodes_with_headers = []
    current_headers = {}  # 当前的标题层级路径
    
    for node in tree.children:
        if node.type == "heading":
            level = int(node.tag[1])  # h1 -> 1, h2 -> 2, etc.
            title = _extract_text_from_node(node)
            
            # 更新当前标题路径
            # 移除比当前级别更深的标题
            current_headers = {k: v for k, v in current_headers.items() if k < level}
            # 添加当前标题
            current_headers[level] = title
            
            # 如果是分块边界标题，标记为分块起始点
            is_split_boundary = level in headers_to_split_on
            
            nodes_with_headers.append({
                'node': node,
                'type': 'heading',
                'level': level,
                'title': title,
                'headers': current_headers.copy(),
                'is_split_boundary': is_split_boundary,
                'content': node.markup + " " + title
            })
        else:
            # 非标题节点
            content = _render_node_content(node)
            if content.strip():
                nodes_with_headers.append({
                    'node': node,
                    'type': node.type,
                    'headers': current_headers.copy(),
                    'is_split_boundary': False,
                    'content': content
                })
    
    return nodes_with_headers


def _render_node_content(node):
    """渲染单个节点的内容"""
    if node.type == "table":
        return _render_table_from_ast(node)
    elif node.type == "code_block":
        return f"```{node.info or ''}\n{node.content}```"
    elif node.type == "blockquote":
        return _render_blockquote_from_ast(node)
    elif node.type in ["bullet_list", "ordered_list"]:
        return _render_list_from_ast(node)
    elif node.type == "paragraph":
        return _extract_text_from_node(node)
    elif node.type == "hr":
        return "---"
    else:
        return _extract_text_from_node(node)


def _split_by_header_levels(nodes_with_headers, headers_to_split_on):
    """基于标题层级进行分块，智能处理连续标题"""
    chunks = []
    current_chunk = {
        'headers': {},
        'nodes': []
    }
    
    i = 0
    while i < len(nodes_with_headers):
        node_info = nodes_with_headers[i]
        
        # 检查是否为分块边界标题
        if node_info['is_split_boundary']:
            # 先检查是否为连续短标题的情况
            if node_info['type'] == 'heading':
                current_title = node_info.get('title', '').strip()
                
                # 检查当前标题是否很短（可能只是编号）
                is_short_title = (
                    len(current_title) <= 12 and 
                    (
                        # 纯数字编号如 "3.7", "4.1"
                        (current_title.replace('.', '').replace(' ', '').isdigit()) or
                        # 短编号如 "3.7", "4", "A.1"  
                        (len(current_title.split()) <= 2 and 
                         any(char.isdigit() for char in current_title))
                    )
                )
                
                # 如果是短标题，向前查找看是否有紧跟的内容标题
                if is_short_title:
                    # 查找接下来的几个节点，看是否有实质性内容标题
                    found_content_header = False
                    j = i + 1
                    
                    # 向前查看最多3个节点
                    while j < len(nodes_with_headers) and j < i + 4:
                        next_node = nodes_with_headers[j]
                        
                        # 如果找到另一个标题
                        if next_node.get('type') == 'heading':
                            next_title = next_node.get('title', '').strip()
                            
                            # 检查是否为更有实质内容的标题
                            is_content_header = (
                                len(next_title) > 12 or  # 较长的标题
                                (len(next_title.split()) > 2) or  # 多个词
                                any(word for word in next_title.split() 
                                    if len(word) > 3 and not word.replace('.', '').isdigit())  # 有非数字词汇
                            )
                            
                            if is_content_header:
                                found_content_header = True
                                break
                        
                        # 如果遇到其他内容，停止查找
                        elif next_node.get('content', '').strip():
                            break
                        
                        j += 1
                    
                    # 如果找到了内容标题，跳过当前标题的分块处理
                    if found_content_header:
                        # 直接添加到当前块，不作为分块边界
                        current_chunk['nodes'].append(node_info)
                        i += 1
                        continue
            
            # 正常的分块边界处理
            # 完成当前块（如果有内容）
            if (current_chunk['nodes'] and 
                any(n for n in current_chunk['nodes'] if n['content'].strip())):
                chunks.append(current_chunk)
                current_chunk = {
                    'headers': {},
                    'nodes': []
                }
        
        # 更新当前块的标题信息
        if node_info['headers']:
            current_chunk['headers'] = node_info['headers'].copy()
        
        # 添加节点到当前块
        current_chunk['nodes'].append(node_info)
        i += 1
    
    # 添加最后一个块
    if current_chunk['nodes'] and any(n for n in current_chunk['nodes'] if n['content'].strip()):
        chunks.append(current_chunk)
    
    return chunks


def _render_header_chunk(chunk_info):
    """渲染基于标题的分块内容（原始版本，用于兼容性）"""
    content_parts = []
    
    # 添加标题上下文（如果分块本身不包含标题）
    chunk_has_header = any(node['type'] == 'heading' for node in chunk_info.get('nodes', []))
    
    if not chunk_has_header and chunk_info.get('headers'):
        # 添加最相关的上下文标题
        context_header = _get_most_relevant_header(chunk_info['headers'])
        if context_header:
            content_parts.append(context_header)
    
    # 渲染所有节点内容
    for node_info in chunk_info.get('nodes', []):
        if node_info.get('content', '').strip():
            content_parts.append(node_info['content'])
    
    return "\n\n".join(content_parts).strip()


def _get_most_relevant_header(headers):
    """获取最相关的上下文标题（原始版本）"""
    if not headers:
        return None
    
    # 选择最深层级的标题作为上下文
    max_level = max(headers.keys())
    return f"{'#' * max_level} {headers[max_level]}"


def split_markdown_to_chunks_strict_regex(txt, chunk_token_num=256, min_chunk_tokens=10, regex_pattern=''):
    """
    使用自定义正则表达式进行严格分块
    
    Args:
        txt: 要分块的文本
        chunk_token_num: 目标分块大小（tokens）
        min_chunk_tokens: 最小分块大小（tokens）
        regex_pattern: 自定义正则表达式
        
    Returns:
        分块列表
    """
    if not txt or not txt.strip():
        return []
    
    if not regex_pattern or not regex_pattern.strip():
        print(f"⚠️ [WARNING] 正则表达式为空，回退到智能分块")
        return split_markdown_to_chunks_smart(txt, chunk_token_num, min_chunk_tokens)
    
    try:
        print(f"🎯 [DEBUG] 使用自定义正则表达式进行分块: {regex_pattern}")
        
        # 使用更精确的方法：逐行处理，确保每个匹配都开始新分块
        # 优化正则表达式，只匹配行开头或前面只有空格的条文
        precise_pattern = r'^\s*' + regex_pattern
        
        lines = txt.split('\n')
        chunks = []
        current_chunk = []
        
        for line in lines:
            # 检查当前行是否以正则表达式匹配开始（真正的条文开始）
            if re.search(precise_pattern, line) and current_chunk:
                # 如果当前行包含匹配且当前已有内容，先保存当前分块
                chunk_content = '\n'.join(current_chunk).strip()
                if chunk_content:
                    chunks.append(chunk_content)
                
                # 开始新分块
                current_chunk = [line]
            else:
                # 将当前行添加到当前分块
                current_chunk.append(line)
        
        # 添加最后一个分块
        if current_chunk:
            chunk_content = '\n'.join(current_chunk).strip()
            if chunk_content:
                chunks.append(chunk_content)
        
        # 过滤和统计
        final_chunks = [chunk for chunk in chunks if chunk.strip()]
        
        print(f"📊 [DEBUG] 正则分块结果: {len(final_chunks)} 个分块")
        if final_chunks:
            token_counts = [num_tokens_from_string(chunk) for chunk in final_chunks]
            print(f"📈 [DEBUG] Token分布: {min(token_counts)}-{max(token_counts)} (平均: {sum(token_counts)/len(token_counts):.1f})")
        
        return final_chunks
        
    except re.error as e:
        print(f"❌ [ERROR] 自定义正则分块失败，正则表达式错误: {e}，回退到智能分块")
        return split_markdown_to_chunks_smart(txt, chunk_token_num, min_chunk_tokens)
    except Exception as e:
        print(f"❌ [ERROR] 自定义正则分块发生异常: {e}，回退到智能分块")
        return split_markdown_to_chunks_smart(txt, chunk_token_num, min_chunk_tokens)


def split_markdown_to_chunks_parent_child(txt, chunk_token_num=256, min_chunk_tokens=10, 
                                         parent_config=None, doc_id='unknown', kb_id='unknown'):
    """
    基于Smart分块的父子分块方法 - 通过HTTP API调用
    调用RAGFlow API层的父子分块服务
    
    Args:
        txt: 要分块的文本
        chunk_token_num: 子分块大小（tokens）
        min_chunk_tokens: 最小子分块大小
        parent_config: 父分块配置
        doc_id: 文档ID
        kb_id: 知识库ID
        
    Returns:
        list: 父分块列表（用于常规分块接口兼容）
        
    Note:
        该函数通过HTTP调用RAGFlow API，实现跨容器通信
    """
    if not txt or not txt.strip():
        return []
    
    parent_config = parent_config or {}
    
    try:
        import requests
        import json
        
        print(f"🚀 [DEBUG] 通过HTTP API调用父子分块")
        print(f"  📝 文本长度: {len(txt)} 字符")
        print(f"  📋 doc_id: {doc_id}, kb_id: {kb_id}")
        print(f"  🔢 子分块大小: {chunk_token_num}")
        print(f"  📊 父分块配置: {parent_config}")
        
        # 获取RAGFlow API服务地址
        ragflow_api_url = os.getenv('RAGFLOW_API_URL', 'http://localhost:9380')
        api_endpoint = f"{ragflow_api_url}/v1/chunk/parent_child_split"
        
        # 准备请求数据
        request_data = {
            'text': txt,
            'doc_id': doc_id,
            'kb_id': kb_id,
            'chunk_token_num': chunk_token_num,
            'min_chunk_tokens': min_chunk_tokens,
            'parent_config': parent_config,
            'metadata': {'source': 'mineru_parse'}
        }
        
        print(f"🌐 [DEBUG] 调用API: {api_endpoint}")
        
        # 发送HTTP请求
        response = requests.post(
            api_endpoint,
            json=request_data,
            headers={'Content-Type': 'application/json'},
            timeout=120  # 2分钟超时
        )
        
        if response.status_code == 200:
            result_data = response.json()
            
            if result_data.get('code') == 0:
                # 成功获取结果
                chunks = result_data.get('data', {}).get('chunks', [])  # 这是父分块（用于检索上下文）
                vector_chunks = result_data.get('data', {}).get('vector_chunks', [])  # 这是子分块（用于向量存储）
                detailed_result = result_data.get('data', {}).get('detailed_result', {})
                
                print(f"📊 [DEBUG] API调用成功:")
                print(f"  👨 父分块: {len(chunks)} 个（用于检索上下文）")
                print(f"  👶 子分块: {len(vector_chunks)} 个（用于向量存储）")
                print(f"  📈 详细结果: {detailed_result.get('total_parents', 0)} 父分块, {detailed_result.get('total_children', 0)} 子分块")
                
                # 保存详细结果到全局变量（供其他模块使用）
                global _last_parent_child_result
                _last_parent_child_result = detailed_result
                
                # ⭐ 关键修改：返回子分块列表，这样前端显示的就是子分块数量
                # 子分块用于向量存储，数量与智能分块一致
                return vector_chunks if vector_chunks else chunks
            else:
                error_msg = result_data.get('message', 'Unknown API error')
                print(f"❌ [ERROR] API返回错误: {error_msg}")
                raise Exception(f"API Error: {error_msg}")
        else:
            print(f"❌ [ERROR] HTTP请求失败: {response.status_code}")
            print(f"  响应内容: {response.text}")
            raise Exception(f"HTTP Error: {response.status_code}")
        
    except requests.exceptions.Timeout:
        print(f"⏰ [ERROR] API调用超时，回退到智能分块")
        return split_markdown_to_chunks_smart(txt, chunk_token_num, min_chunk_tokens)
    except requests.exceptions.ConnectionError:
        print(f"🔌 [ERROR] 无法连接到RAGFlow API服务，回退到智能分块")
        return split_markdown_to_chunks_smart(txt, chunk_token_num, min_chunk_tokens)
    except Exception as e:
        print(f"❌ [ERROR] 父子分块HTTP调用失败: {e}，回退到智能分块")
        import traceback
        traceback.print_exc()
        return split_markdown_to_chunks_smart(txt, chunk_token_num, min_chunk_tokens)


# _save_parent_child_chunks_to_db 函数已移至 RAGFlow API 层处理


# 全局变量存储最后一次父子分块结果
_last_parent_child_result = None


def get_last_parent_child_result():
    """获取最后一次父子分块的完整结果"""
    global _last_parent_child_result
    return _last_parent_child_result


# ===== 基于AST的父子分块实现 =====

class ASTChunkInfo:
    """基于AST的分块信息类"""
    def __init__(self, id, content, start_line, end_line, order, doc_id='', metadata=None, ast_nodes=None):
        self.id = id
        self.content = content
        self.start_line = start_line
        self.end_line = end_line
        self.order = order
        self.doc_id = doc_id
        self.metadata = metadata or {}
        self.ast_nodes = ast_nodes or []
        
        # AST特有信息
        self.section_title = metadata.get('section_title', '')
        self.context_stack = metadata.get('context_stack', [])
        self.semantic_elements = metadata.get('semantic_elements', {})


def split_markdown_to_chunks_ast_parent_child(txt, chunk_token_num=256, min_chunk_tokens=10, 
                                             parent_config=None, doc_id='unknown', kb_id='unknown'):
    """
    基于AST的父子分块方法
    
    Args:
        txt: 要分块的文本
        chunk_token_num: 子分块大小（tokens）
        min_chunk_tokens: 最小子分块大小
        parent_config: 父分块配置
        doc_id: 文档ID
        kb_id: 知识库ID
        
    Returns:
        tuple: (parent_chunks, child_chunks, relationships)
    """
    if not MARKDOWN_IT_AVAILABLE:
        print("Warning: markdown-it-py not available, falling back to simple parent-child")
        # 回退到现有的父子分块实现
        from api.apps.chunk_app import parent_child_split
        return parent_child_split()
    
    if not txt or not txt.strip():
        return [], [], []
    
    parent_config = parent_config or {}
    parent_split_level = parent_config.get('parent_split_level', 2)  # 默认H2分割
    
    try:
        # 1. 解析AST并创建增强节点
        enhanced_nodes = _create_enhanced_ast_nodes(txt)
        
        # 2. 基于AST创建子分块
        child_chunks = _create_ast_child_chunks(
            enhanced_nodes, chunk_token_num, min_chunk_tokens, doc_id
        )
        
        # 3. 基于AST和标题层级创建父分块  
        parent_chunks = _create_ast_parent_chunks(
            enhanced_nodes, parent_split_level, doc_id
        )
        
        # 4. 建立精确的AST关联关系
        relationships = _create_ast_relationships(
            child_chunks, parent_chunks, enhanced_nodes, doc_id, kb_id
        )
        
        print(f"🎯 [AST] 创建父子分块完成:")
        print(f"  👨 父分块: {len(parent_chunks)} 个")
        print(f"  👶 子分块: {len(child_chunks)} 个") 
        print(f"  🔗 关联关系: {len(relationships)} 个")
        
        return parent_chunks, child_chunks, relationships
        
    except Exception as e:
        print(f"❌ [ERROR] AST父子分块失败: {e}")
        import traceback
        traceback.print_exc()
        return [], [], []


def _create_enhanced_ast_nodes(txt):
    """创建增强的AST节点信息"""
    from markdown_it import MarkdownIt
    from markdown_it.tree import SyntaxTreeNode
    
    md = MarkdownIt("commonmark", {"breaks": True, "html": True})
    md.enable(['table'])
    
    tokens = md.parse(txt)
    tree = SyntaxTreeNode(tokens)
    
    enhanced_nodes = []
    context_stack = []  # 标题上下文栈
    line_offset = 0
    
    for node in tree.children:
        node_info = _create_enhanced_node_info(node, context_stack, line_offset)
        if node_info['content'].strip():  # 只保留有内容的节点
            enhanced_nodes.append(node_info)
        line_offset = node_info['line_end']
    
    return enhanced_nodes


def _create_enhanced_node_info(node, context_stack, line_offset):
    """为AST节点创建增强信息"""
    content = _render_node_content(node)  # 复用现有函数
    
    # 估算行号（markdown-it-py的map信息可能不准确）
    content_lines = content.count('\n') + 1 if content.strip() else 0
    line_start = line_offset
    line_end = line_offset + content_lines
    
    node_info = {
        'node': node,
        'type': node.type,
        'content': content,
        'line_start': line_start,
        'line_end': line_end,
        'context_stack': [c.copy() for c in context_stack],  # 深拷贝上下文
        'is_section_boundary': False,
        'header_level': None,
        'header_title': None
    }
    
    # 处理标题节点
    if node.type == "heading":
        level = int(node.tag[1]) if hasattr(node, 'tag') and node.tag else 1
        title = _extract_text_from_node(node)
        
        # 更新上下文栈
        _update_context_stack(context_stack, level, title)
        
        node_info.update({
            'header_level': level,
            'header_title': title,
            'is_section_boundary': True,
            'context_stack': [c.copy() for c in context_stack]  # 更新后的上下文
        })
    
    return node_info


def _create_ast_child_chunks(enhanced_nodes, chunk_token_num, min_chunk_tokens, doc_id):
    """基于AST节点创建子分块"""
    child_chunks = []
    current_chunk_nodes = []
    current_tokens = 0
    chunk_order = 0
    
    for node_info in enhanced_nodes:
        content = node_info['content']
        if not content.strip():
            continue
            
        content_tokens = num_tokens_from_string(content)
        
        # 检查是否需要分块
        should_break = (
            node_info['type'] == 'heading' and 
            node_info.get('header_level', 99) <= 3  # H1, H2, H3作为分块边界
        )
        
        if should_break and current_chunk_nodes and current_tokens >= min_chunk_tokens:
            # 创建子分块
            child_chunk = _create_ast_child_chunk_obj(
                current_chunk_nodes, chunk_order, doc_id
            )
            child_chunks.append(child_chunk)
            chunk_order += 1
            current_chunk_nodes = []
            current_tokens = 0
        
        # 检查token限制
        if (current_tokens + content_tokens > chunk_token_num and 
            current_chunk_nodes and current_tokens >= min_chunk_tokens):
            
            child_chunk = _create_ast_child_chunk_obj(
                current_chunk_nodes, chunk_order, doc_id
            )
            child_chunks.append(child_chunk)
            chunk_order += 1
            current_chunk_nodes = []
            current_tokens = 0
        
        current_chunk_nodes.append(node_info)
        current_tokens += content_tokens
    
    # 处理最后一个分块
    if current_chunk_nodes and current_tokens >= min_chunk_tokens:
        child_chunk = _create_ast_child_chunk_obj(
            current_chunk_nodes, chunk_order, doc_id
        )
        child_chunks.append(child_chunk)
    
    return child_chunks


def _create_ast_child_chunk_obj(nodes, order, doc_id):
    """创建子分块对象"""
    import hashlib
    
    content = "\n\n".join([n['content'] for n in nodes if n['content'].strip()])
    chunk_id = f"{doc_id}_child_ast_{order:04d}_{hashlib.md5(content.encode('utf-8')).hexdigest()[:8]}"
    
    return ASTChunkInfo(
        id=chunk_id,
        content=content,
        start_line=nodes[0]['line_start'],
        end_line=nodes[-1]['line_end'],
        order=order,
        doc_id=doc_id,
        ast_nodes=nodes,
        metadata={
            'chunk_type': 'child',
            'creation_method': 'ast_semantic',
            'contains_headers': any(n['type'] == 'heading' for n in nodes),
            'contains_tables': any(n['type'] == 'table' for n in nodes),
            'contains_code': any(n['type'] == 'code_block' for n in nodes),
            'ast_node_count': len(nodes),
            'context_stack': nodes[0]['context_stack'] if nodes else []
        }
    )


def _create_ast_parent_chunks(enhanced_nodes, parent_split_level, doc_id):
    """基于AST和标题层级创建父分块"""
    parent_chunks = []
    current_section_nodes = []
    current_section_header = None
    parent_order = 0
    
    for node_info in enhanced_nodes:
        # 检查是否是父分块边界标题
        if (node_info['type'] == 'heading' and 
            node_info.get('header_level', 99) <= parent_split_level):
            
            # 完成当前父分块
            if current_section_nodes:
                parent_chunk = _create_ast_parent_chunk_obj(
                    current_section_nodes, current_section_header, parent_order, doc_id
                )
                parent_chunks.append(parent_chunk)
                parent_order += 1
            
            # 开始新的父分块
            current_section_nodes = [node_info]
            current_section_header = {
                'level': node_info['header_level'],
                'title': node_info['header_title'],
                'context_stack': node_info['context_stack']
            }
        else:
            current_section_nodes.append(node_info)
    
    # 处理最后一个父分块
    if current_section_nodes:
        parent_chunk = _create_ast_parent_chunk_obj(
            current_section_nodes, current_section_header, parent_order, doc_id
        )
        parent_chunks.append(parent_chunk)
    
    return parent_chunks


def _create_ast_parent_chunk_obj(nodes, header_info, order, doc_id):
    """创建父分块对象"""
    import hashlib
    
    content = "\n\n".join([n['content'] for n in nodes if n['content'].strip()])
    chunk_id = f"{doc_id}_parent_ast_{order:04d}_{hashlib.md5(content.encode('utf-8')).hexdigest()[:8]}"
    
    return ASTChunkInfo(
        id=chunk_id,
        content=content,
        start_line=nodes[0]['line_start'],
        end_line=nodes[-1]['line_end'],
        order=order,
        doc_id=doc_id,
        ast_nodes=nodes,
        metadata={
            'chunk_type': 'parent',
            'creation_method': 'ast_semantic',
            'section_title': header_info['title'] if header_info else '',
            'header_level': header_info['level'] if header_info else 0,
            'context_stack': header_info['context_stack'] if header_info else [],
            'semantic_completeness': True,
            'ast_node_count': len(nodes)
        }
    )


def _create_ast_relationships(child_chunks, parent_chunks, enhanced_nodes, doc_id, kb_id):
    """基于AST结构创建精确的父子关联"""
    relationships = []
    
    for child_chunk in child_chunks:
        # 通过行号范围找到对应的父分块
        matching_parent = _find_parent_by_line_range(
            child_chunk.start_line, child_chunk.end_line, parent_chunks
        )
        
        if matching_parent:
            # 从AST中提取语义信息
            semantic_info = _extract_ast_semantic_info(child_chunk, matching_parent)
            
            relationships.append({
                'child_chunk_id': child_chunk.id,
                'parent_chunk_id': matching_parent.id,
                'doc_id': doc_id,
                'kb_id': kb_id,
                'relevance_score': 100,
                'relationship_type': 'ast_containment',
                'section_title': matching_parent.section_title,
                'child_start_line': child_chunk.start_line,
                'child_end_line': child_chunk.end_line,
                'parent_start_line': matching_parent.start_line,
                'parent_end_line': matching_parent.end_line,
                'semantic_info': semantic_info
            })
    
    return relationships


def _find_parent_by_line_range(child_start, child_end, parent_chunks):
    """通过行号范围找到对应的父分块"""
    for parent in parent_chunks:
        if (parent.start_line <= child_start and parent.end_line >= child_end):
            return parent
    return None


def _extract_ast_semantic_info(child_chunk, parent_chunk):
    """从AST中提取语义信息"""
    child_nodes = child_chunk.ast_nodes
    
    semantic_info = {
        'contains_headers': len([n for n in child_nodes if n['type'] == 'heading']),
        'contains_tables': len([n for n in child_nodes if n['type'] == 'table']),
        'contains_code': len([n for n in child_nodes if n['type'] == 'code_block']),
        'contains_lists': len([n for n in child_nodes if n['type'] in ['bullet_list', 'ordered_list']]),
        'context_hierarchy': parent_chunk.context_stack,
        'ast_node_types': list(set([n['type'] for n in child_nodes])),
        'parent_section_title': parent_chunk.section_title
    }
    
    return semantic_info