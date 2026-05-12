# 这个是把完整的标题放入分段中这个
import re

from markdown_it import MarkdownIt
from markdown import markdown as md_to_html
from markdown_it.tree import SyntaxTreeNode
import tiktoken
encoder = tiktoken.get_encoding("cl100k_base")

# 表格子分块目标大小（tokens），每个子表约100 tokens，提高检索命中率
TABLE_SUB_CHUNK_TARGET_TOKENS = 100
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
def build_full_header_chain(headers):
    """根据 headers 字典构建完整的标题链"""
    # 如果 headers 字典为空，则返回 None
    if not headers:
        return None
    
    # 对 headers 字典的键进行排序
    sorted_levels = sorted(headers.keys())
    # 使用列表推导式构建完整的标题链
    return '\n'.join([f"{'#' * level} {title}" for level, title in [(l, headers[l]) for l in sorted_levels]])
# 渲染对应的arkdown
def _render_header_chunk(chunk_info, use_full_header_chain=True):
    """渲染基于标题的分块内容，可选是否使用完整标题链"""
    content_parts = []
    
    chunk_has_header = any(node['type'] == 'heading' for node in chunk_info.get('nodes', []))
    
    if not chunk_has_header and chunk_info.get('headers'):
        if use_full_header_chain:
            header_content = build_full_header_chain(chunk_info['headers'])
        else:
            header_content = _get_most_relevant_header(chunk_info['headers'])
        
        if header_content:
            content_parts.append(header_content)
    
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

def split_markdown_to_chunks_advanced(txt, chunk_token_num=1024, min_chunk_tokens=10, 
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
    # if not MARKDOWN_IT_AVAILABLE:
    #     return split_markdown_to_chunks(txt, chunk_token_num)
    
    if not txt or not txt.strip():
        return []

    # 动态阈值配置
    target_min_tokens = max(50, min_chunk_tokens // 2)  # 最小50 tokens
    target_tokens = min(600, chunk_token_num)  # 目标大小：300-600 tokens
    target_max_tokens = min(800, chunk_token_num * 1.5)  # 最大800 tokens
    
    # 配置要作为分块边界的标题级别
    headers_to_split_on = [1, 2, 3, 4]  # H1, H2, H3, H4 作为分块边界
    
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


def split_markdown_to_chunks_smart(txt, chunk_token_num=256, min_chunk_tokens=10):
    """
    基于 markdown-it-py AST 的智能分块方法，解决 RAG Markdown 文件分块问题：
    1. 基于语义切分（使用 AST）
    2. 维护表格完整性，即使超出了最大 tokens
    3. 考虑 markdown 父子分块关系
    """
    # if not MARKDOWN_IT_AVAILABLE:
    #     print("Warning: markdown-it-py not available, falling back to simple chunking")
    #     return split_markdown_to_chunks(txt, chunk_token_num)
    
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
    
        # return split_markdown_to_chunks(txt, chunk_token_num)

def _finalize_ast_chunk(chunk_parts, context_stack):
    """完成基于 AST 的 chunk 格式化"""
    chunk_content = "\n\n".join(chunk_parts).strip()
    
    # 可以根据需要添加上下文信息
    # 例如，如果chunk没有标题，可以考虑添加父级标题作为上下文
    
    return chunk_content
def _update_context_stack(context_stack, level, title):
    """更新标题上下文栈"""
    # 移除比当前级别更深的标题
    while context_stack and context_stack[-1]['level'] >= level:
        context_stack.pop()
    
    # 添加当前标题
    context_stack.append({'level': level, 'title': title})
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

def _render_header_chunk_advanced(chunk_info):
    """高级渲染基于标题的分块内容，包含更好的格式化"""
    content_parts = []
    chunk_nodes = chunk_info.get('nodes', [])
    # 处理标题上下文
    chunk_has_header = any(node['type'] == 'heading' for node in chunk_info.get('nodes', []))
    headers = chunk_info.get('headers', {})
        # 检查分块是否以标题开始
    starts_with_heading = chunk_nodes and chunk_nodes[0].get('type') == 'heading'
    first_heading_level = chunk_nodes[0].get('level') if starts_with_heading else None
    # 为某些类型的分块添加标题上下文
    chunk_type = chunk_info.get('chunk_type', 'normal')
    if chunk_type in ['split_from_oversized', 'small_enhanced'] and headers and not chunk_has_header:
        # 添加最相关的上下文标题
        context_header = _get_most_relevant_header_advanced(headers, chunk_type)
        if context_header:
            clean_context_header = _clean_header_chain(context_header, use_indentation=True)
            content_parts.append(clean_context_header)
    else:
        if starts_with_heading and first_heading_level:
            # 分块以标题开始，只添加父级标题
            parent_headers = {level: title for level, title in headers.items() if level < first_heading_level}
            if parent_headers:
                parent_header_chain = build_full_header_chain(parent_headers)
                if parent_header_chain:
                    clean_context_header = _clean_header_chain(parent_header_chain, use_indentation=True)
                    content_parts.append(clean_context_header)
        elif not starts_with_heading:
            # 分块不以标题开始，添加完整标题链作为上下文
            header_chain = build_full_header_chain(headers)
            if header_chain:
                clean_context_header = _clean_header_chain(header_chain, use_indentation=True)
                content_parts.append(clean_context_header)
    # 渲染所有节点内容（移除标记，保持内容干净）
    for node_info in chunk_info.get('nodes', []):
        if node_info.get('content', '').strip():
            content = node_info['content']
            if node_info.get('type') == 'heading':
                    clean_content = _clean_header_chain(content, use_indentation=False)
                    content_parts.append(clean_content)
            else:
                # 直接使用原始内容，不添加任何标记
                content_parts.append(content)
    
    result = "\n\n".join(content_parts).strip()
    
    # 移除重叠分块的标识，保持内容干净
    # if chunk_type == 'overlap':
    #     result = f"[上下文关联内容]\n{result}"
    
    return result
def _clean_header_chain(header_chain, use_indentation=False):
    """清理标题链，移除或替换标题符号"""
    # return header_chain
    if not header_chain:
        return None
    
    clean_headers = []
    for line in header_chain.split('\n'):
        if line.strip():
            if use_indentation:
                # 使用缩进代替标题符号
                level = line.count('#')
                title = line.split(' ', 1)[1] if ' ' in line else line
                clean_headers.append(f"{'  ' * (level-1)}{title}")
            else:
                # 完全移除标题符号
                clean_line = line.split(' ', 1)[1] if ' ' in line else line
                clean_headers.append(clean_line)
    
    return '\n'.join(clean_headers)
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

# 进行表格处理不要把这个拆开
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
            
        elif chunk_tokens > max_tokens:
            if not has_special_content:
                # 超大分块，需要进一步分割（除非包含特殊内容）
                split_chunks = _split_oversized_chunk(chunk, target_tokens, max_tokens)
                optimized_chunks.extend(split_chunks)
            else:
                # 父分段层面不拆分表格，保持完整性
                # 表格拆分应发生在子分段时（_create_semantic_sub_chunks）
                chunk['chunk_type'] = 'oversized_special'
                chunk['has_special_content'] = has_special_content
                optimized_chunks.append(chunk)
            
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
# 这里是对超长进行补偿处理
def _is_table_context_title(node_info):
    """
    判断节点是否为表格的标题/上下文说明文字
    
    检测规则：
    1. 标题节点（heading）：以"表"/"Table"/"TABLE" 开头
    2. 段落节点：以"表"/"T"开头，或包含"如下表"/"下表所示"/"表所示"等模式
    3. 紧贴表格前的短段落（用于表格的说明性文字）
    
    Args:
        node_info: AST节点信息字典
    
    Returns:
        bool: 是否为表格上下文
    """
    content = node_info.get('content', '').strip()
    node_type = node_info.get('type', '')
    
    if not content:
        return False
    
    # 标题节点检测
    if node_type == 'heading':
        # 获取纯文本标题（去除markdown标记）
        title = node_info.get('title', '') or content
        # 匹配以"表"/"Table"/"TABLE"开头的标题
        # 注意：不使用\b，因为Python 3 Unicode模式下中文也是\w，\b对中文无效
        if re.match(r'^(表|Table|TABLE)', title):
            return True
        # 匹配 "# 表3-1 设备参数" 这种格式
        clean_title = re.sub(r'^#+\s*', '', title).strip()
        if re.match(r'^(表|Table|TABLE)', clean_title):
            return True
    
    # 段落节点检测
    if node_type == 'paragraph':
        # 以"表"/"T"/"下表"/"表格"开头（如 "表3-1："、"表格如下："、"下表列出了"）
        if re.match(r'^(表|T|下表|表格)', content):
            return True
        # 包含常见表格指示短语（扩展模式）
        if re.search(r'(如下表|下表所示|表所示|如下表所示|表格如下|见下表|参见下表|下表列出|下表给出|下表说明)', content):
            return True
        # 短段落（<60字符）且包含"表"字，大概率是表格上下文
        if len(content) < 60 and '表' in content:
            return True
    
    return False


def _separate_tables_from_chunk(chunk, target_tokens, max_tokens):
    """
    将包含表格的分块中表格单独提取出来作为独立分块
    同时确保表格外的内容也符合大小限制
    
    【改进】识别表格前的标题/说明文字，与表格合并为一个子分段，
    保持表格与上下文的关联性，提高检索命中率。
    
    Args:
        chunk: 包含表格的分块
        target_tokens: 目标token数
        max_tokens: 最大token数
    
    Returns:
        分离后的分块列表
    """
    separated_chunks = []
    nodes = chunk.get('nodes', [])
    headers = chunk.get('headers', {})
    
    non_table_nodes = []
    non_table_tokens = 0
    
    i = 0
    while i < len(nodes):
        node_info = nodes[i]
        node_content = node_info.get('content', '')
        node_tokens = num_tokens_from_string(node_content)
        node_type = node_info.get('type', '')
        
        # 检查是否是表格节点
        is_table_node = node_type == 'table' or _is_html_table_content(node_content)
        
        if is_table_node:
            # 【关键改进】检查前一个/前两个节点是否可能是表格标题/上下文
            table_context_nodes = []
            
            # 检查前一个节点
            if non_table_nodes:
                # 检查最近一个节点是否为表格上下文（标题或说明文字）
                last_idx = len(non_table_nodes) - 1
                if _is_table_context_title(non_table_nodes[last_idx]):
                    table_context_nodes.append(non_table_nodes.pop(last_idx))
                    non_table_tokens -= num_tokens_from_string(
                        table_context_nodes[-1].get('content', '')
                    )
                    # 进一步检查：如果还有前一个节点且是短段落（也可能是上下文）
                    if non_table_nodes and len(non_table_nodes) >= 1:
                        prev_idx = len(non_table_nodes) - 1
                        prev_node = non_table_nodes[prev_idx]
                        prev_content = prev_node.get('content', '').strip()
                        # 如果前一个节点是短段落，且包含表格相关关键词
                        if (prev_node.get('type') == 'paragraph' and 
                            len(prev_content) < 60 and
                            re.search(r'(表|Table|TABLE|下表|如下)', prev_content)):
                            table_context_nodes.insert(0, non_table_nodes.pop(prev_idx))
                            non_table_tokens -= num_tokens_from_string(
                                table_context_nodes[0].get('content', '')
                            )
            
            # 处理剩余的非表格内容（如果有的话）
            if non_table_nodes:
                non_table_chunks = _process_non_table_content(
                    non_table_nodes, headers, target_tokens, max_tokens
                )
                separated_chunks.extend(non_table_chunks)
                non_table_nodes = []
                non_table_tokens = 0
            
            # 表格上下文 + 表格合并为一个子分段
            table_chunk_nodes = table_context_nodes + [node_info]
            table_chunk_content = "\n\n".join(
                [n['content'] for n in table_chunk_nodes if n['content'].strip()]
            )
            table_chunk_tokens = num_tokens_from_string(table_chunk_content)
            
            # 合并后的表格分块
            if table_chunk_tokens > max_tokens:
                # 大表格按行拆分，每个子块保留表头
                split_chunks = _split_large_table(node_info, headers.copy(), target_tokens, max_tokens)
                
                # 将表格上下文（标题等）合并到第一个拆分块
                if table_context_nodes and split_chunks:
                    first_chunk = split_chunks[0]
                    context_content = "\n\n".join(
                        [n.get('content', '') for n in table_context_nodes 
                         if n.get('content', '').strip()]
                    )
                    if context_content:
                        first_chunk['nodes'].insert(0, {
                            'type': 'context', 
                            'content': context_content
                        })
                        first_chunk['has_table_title'] = True
                
                separated_chunks.extend(split_chunks)
            else:
                table_chunk = {
                    'headers': headers.copy(),
                    'nodes': table_chunk_nodes,
                    'chunk_type': 'table_chunk',
                    'has_special_content': True,
                    'has_table_title': len(table_context_nodes) > 0
                }
                separated_chunks.append(table_chunk)
        else:
            # 非表格节点，累积到非表格内容中
            if non_table_tokens + node_tokens > target_tokens and non_table_nodes:
                # 如果非表格内容太大，需要分割
                non_table_chunks = _process_non_table_content(
                    non_table_nodes, headers, target_tokens, max_tokens
                )
                separated_chunks.extend(non_table_chunks)
                
                # 开始新的非表格分块
                non_table_nodes = [node_info]
                non_table_tokens = node_tokens
            else:
                non_table_nodes.append(node_info)
                non_table_tokens += node_tokens
        
        i += 1
    
    # 处理最后的非表格内容（如果有的话）
    if non_table_nodes:
        non_table_chunks = _process_non_table_content(
            non_table_nodes, headers, target_tokens, max_tokens
        )
        separated_chunks.extend(non_table_chunks)
    
    return separated_chunks

def _process_non_table_content(nodes, headers, target_tokens, max_tokens):
    """
    处理非表格内容，确保符合大小限制
    
    Args:
        nodes: 节点列表
        headers: 标题信息
        target_tokens: 目标token数
        max_tokens: 最大token数
    
    Returns:
        处理后的分块列表
    """
    # 计算总token数
    total_tokens = sum(num_tokens_from_string(node.get('content', '')) for node in nodes)
    
    # 如果总大小在合理范围内，作为一个分块
    if total_tokens <= max_tokens:
        return [{
            'headers': headers.copy(),
            'nodes': nodes,
            'chunk_type': 'normal',
            'has_special_content': False
        }]
    
    # 如果太大，需要分割
    # 创建一个临时chunk用于分割
    temp_chunk = {
        'headers': headers.copy(),
        'nodes': nodes,
        'chunk_type': 'normal',
        'has_special_content': False
    }
    
    # 使用现有的分割逻辑
    return _split_oversized_chunk(temp_chunk, target_tokens, max_tokens)

def _split_large_table(table_node_info, headers, target_tokens, max_tokens):
    """
    分割大表格，按行拆分，每个子块保留表头
    
    策略：
    1. 解析HTML表格结构，提取表头行和数据行
    2. 累积数据行直到接近 max_tokens，然后生成一个子块
    3. 每个子块都包含完整的表头 + 分隔行（保持表格可读性）
    4. 如果单个数据行就超过了 max_tokens，则保持该行不变（不截断）
    
    Args:
        table_node_info: 表格节点信息
        headers: 标题信息
        target_tokens: 目标token数
        max_tokens: 最大token数
    
    Returns:
        分割后的表格分块列表
    """
    table_content = table_node_info.get('content', '')
    table_tokens = num_tokens_from_string(table_content)
    
    # 如果表格大小合适，不拆分
    if table_tokens <= max_tokens:
        table_chunk = {
            'headers': headers.copy(),
            'nodes': [table_node_info],
            'chunk_type': 'table_chunk',
            'has_special_content': True
        }
        return [table_chunk]
    
    # 大表格：按行拆分（支持一个节点中包含多个表格）
    try:
        # 【修复】先提取所有 <table>...</table> 块，分别处理
        table_blocks = re.findall(
            r'<table[^>]*>.*?</table>', table_content,
            re.DOTALL | re.IGNORECASE
        )
        if not table_blocks:
            # 无法提取表格块，保持原样
            table_chunk = {
                'headers': headers.copy(),
                'nodes': [table_node_info],
                'chunk_type': 'large_table_chunk',
                'has_special_content': True
            }
            return [table_chunk]

        all_table_chunks = []

        for block_html in table_blocks:
            # 解析单个HTML表格，提取表头和数据行
            thead_html, tbody_rows_html = _parse_html_table_rows(block_html)

            if not tbody_rows_html:
                # 无法解析行结构，将该表格整体保留
                all_table_chunks.append({
                    'headers': headers.copy(),
                    'nodes': [{
                        **table_node_info,
                        'content': block_html
                    }],
                    'chunk_type': 'table_chunk_split',
                    'has_special_content': True
                })
                continue

            # 计算表头部分的token数
            header_tokens = num_tokens_from_string(thead_html) if thead_html else 0
            available_tokens = min(max_tokens, target_tokens * 2) - header_tokens

            if available_tokens <= 0:
                # 表头本身就超大了，整体保留
                all_table_chunks.append({
                    'headers': headers.copy(),
                    'nodes': [{
                        **table_node_info,
                        'content': block_html
                    }],
                    'chunk_type': 'table_chunk_split',
                    'has_special_content': True
                })
                continue

            # 累积数据行，生成多个子块
            current_rows = []
            current_tokens = 0

            for row_html in tbody_rows_html:
                row_tokens = num_tokens_from_string(row_html)

                # 单个行就超过可用空间
                if row_tokens > available_tokens:
                    # 先保存当前累积的行
                    if current_rows:
                        chunk_content = _build_table_html(thead_html, current_rows)
                        all_table_chunks.append({
                            'headers': headers.copy(),
                            'nodes': [{
                                **table_node_info,
                                'content': chunk_content
                            }],
                            'chunk_type': 'table_chunk_split',
                            'has_special_content': True
                        })
                        current_rows = []
                        current_tokens = 0

                    # 超大行单独作为一个分块（保留表头）
                    chunk_content = _build_table_html(thead_html, [row_html])
                    all_table_chunks.append({
                        'headers': headers.copy(),
                        'nodes': [{
                            **table_node_info,
                            'content': chunk_content
                        }],
                        'chunk_type': 'table_chunk_split',
                        'has_special_content': True
                    })
                    continue

                # 正常行：累积到当前块
                if current_tokens + row_tokens > available_tokens and current_rows:
                    # 当前块已满，保存并开始新块
                    chunk_content = _build_table_html(thead_html, current_rows)
                    all_table_chunks.append({
                        'headers': headers.copy(),
                        'nodes': [{
                            **table_node_info,
                            'content': chunk_content
                        }],
                        'chunk_type': 'table_chunk_split',
                        'has_special_content': True
                    })
                    current_rows = [row_html]
                    current_tokens = row_tokens
                else:
                    current_rows.append(row_html)
                    current_tokens += row_tokens

            # 处理最后剩余的行
            if current_rows:
                chunk_content = _build_table_html(thead_html, current_rows)
                all_table_chunks.append({
                    'headers': headers.copy(),
                    'nodes': [{
                        **table_node_info,
                        'content': chunk_content
                    }],
                    'chunk_type': 'table_chunk_split',
                    'has_special_content': True
                })

        return all_table_chunks

    except Exception as e:
        print(f"⚠️ [WARNING] 大表格按行拆分失败: {e}，保持原样")
        table_chunk = {
            'headers': headers.copy(),
            'nodes': [table_node_info],
            'chunk_type': 'large_table_chunk',
            'has_special_content': True
        }
        return [table_chunk]

def _parse_html_table_rows(html_content):
    """
    解析HTML表格，提取表头行和数据行
    
    Args:
        html_content: HTML表格内容
    
    Returns:
        tuple: (thead_html, tbody_rows) 
            thead_html: 表头部分HTML（含<thead>标签）
            tbody_rows: 数据行列表，每行为完整的<tr>...</tr> HTML
    """
    thead_html = ''
    tbody_rows = []
    
    # 提取 thead 部分
    thead_match = re.search(r'<thead>(.*?)</thead>', html_content, re.DOTALL)
    if thead_match:
        thead_html = '<thead>' + thead_match.group(1) + '</thead>'
    
    # 提取 tbody 中的每一行
    tbody_match = re.search(r'<tbody>(.*?)</tbody>', html_content, re.DOTALL)
    if tbody_match:
        tbody_content = tbody_match.group(1)
        # 提取所有 <tr>...</tr> 行
        rows = re.findall(r'<tr>.*?</tr>', tbody_content, re.DOTALL)
        tbody_rows = rows
    
    # 如果没有 tbody（简化表格），尝试直接提取所有 tr
    if not tbody_rows:
        all_rows = re.findall(r'<tr>.*?</tr>', html_content, re.DOTALL)
        if all_rows:
            # 第一行作为表头
            if len(all_rows) > 1:
                thead_html = '<thead>' + all_rows[0] + '</thead>'
                tbody_rows = all_rows[1:]
            else:
                # 只有一行，既是表头也是数据
                thead_html = '<thead>' + all_rows[0] + '</thead>'
                tbody_rows = []
    
    return thead_html, tbody_rows


def _build_table_html(thead_html, rows):
    """
    构建完整的HTML表格
    
    Args:
        thead_html: 表头HTML
        rows: 数据行列表
    
    Returns:
        完整的HTML表格字符串
    """
    parts = ['<table>']
    if thead_html:
        parts.append(thead_html)
    if rows:
        parts.append('<tbody>')
        parts.extend(rows)
        parts.append('</tbody>')
    parts.append('</table>')
    return '\n'.join(parts)

def _is_html_table_content(content):
    """
    检查内容是否包含HTML表格标签
    
    Args:
        content: 要检查的内容
    
    Returns:
        bool: 如果包含HTML表格标签返回True
    """
    if not content:
        return False
    
    content_lower = content.lower()
    return '<table' in content_lower or '<tr' in content_lower or '<td' in content_lower
# 超大的分段需要切割不然到上下文会超长的
def _split_oversized_chunk(chunk, target_tokens, max_tokens):
    """分割超大分块，在段落边界进行分割，同时保持特殊内容完整性"""
    split_chunks = []
    nodes = chunk.get('nodes', [])
    headers = chunk.get('headers', {})
    
    current_nodes = []
    current_tokens = 0
    
    i = 0
    while i < len(nodes):
        node_info = nodes[i]
        node_content = node_info.get('content', '')
        node_tokens = num_tokens_from_string(node_content)
        
        # 检查是否是特殊内容节点（表格、代码块等）
        is_special_content = node_info.get('type') in ['table', 'code_block'] or \
                           '$$' in node_content or '$' in node_content or \
                           ('<table>' in node_content and '</table>' in node_content)
        
        # 如果是特殊内容且单独超出了最大大小
        if is_special_content and node_tokens > max_tokens:
            # 即使超大也要保持完整性，单独作为一个块
            if current_nodes:  # 先保存当前累积的节点
                new_chunk = {
                    'headers': headers.copy(),
                    'nodes': current_nodes.copy(),
                    'chunk_type': 'split_from_oversized',
                    'has_special_content': any(_has_special_content({'nodes': [n]}) for n in current_nodes)
                }
                split_chunks.append(new_chunk)
                
                current_nodes = []
                current_tokens = 0
            
            # 添加这个超大的特殊内容块
            special_chunk = {
                'headers': headers.copy(),
                'nodes': [node_info],
                'chunk_type': 'split_from_oversized',
                'has_special_content': True
            }
            split_chunks.append(special_chunk)
            i += 1
            continue
        
        # 检查添加当前节点是否会超出目标大小或最大大小
        would_exceed_target = current_tokens + node_tokens > target_tokens and current_nodes
        would_exceed_max = current_tokens + node_tokens > max_tokens and current_nodes
        
        if would_exceed_target or would_exceed_max:
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
            if node_info.get('type') == 'heading':
                level = node_info.get('level', 3)
                title = node_info.get('title', '')
                new_headers = {k: v for k, v in headers.items() if k < level}
                new_headers[level] = title
                headers = new_headers
        else:
            current_nodes.append(node_info)
            current_tokens += node_tokens
            
            # 更新标题上下文
            if node_info.get('type') == 'heading':
                level = node_info.get('level', 3)
                title = node_info.get('title', '')
                headers = {k: v for k, v in headers.items() if k < level}
                headers[level] = title
        
        i += 1
    
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
def num_tokens_from_string(string: str, model_name: str = "cl100k_base") -> int:
    """Returns the number of tokens in a text string."""
    try:
        return len(encoder.encode(string))
    except Exception:
        return 0
    
def create_child_chunks(content, sub_chunk_token_num=256, include_metadata=False, table_sub_chunk_token_num=320):
    """创建子分段，支持文本和表格使用不同阈值"""
    parent_token_count = num_tokens_from_string(content)
    if  parent_token_count > sub_chunk_token_num:
                    # 使用相同的Markdown分块逻辑创建子分段
                    sub_chunks = _create_semantic_sub_chunks(content,
                                                           sub_chunk_token_num, include_metadata, table_sub_chunk_token_num)
                    return sub_chunks
# #这里增加父子分段的处理
# def split_markdown_to_chunks_with_hierarchy(txt, chunk_token_num=1024, min_chunk_tokens=10, 
#                                            create_sub_chunks=True, sub_chunk_token_num=256,
#                                            include_metadata=False):
#     """
#     基于标题层级的高级 Markdown 分块方法，支持父子分段结构
    
#     Args:
#         txt: 要分块的Markdown文本
#         chunk_token_num: 父分段最大token数
#         min_chunk_tokens: 最小token数
#         create_sub_chunks: 是否创建子分段
#         sub_chunk_token_num: 子分段最大token数
#         include_metadata: 是否包含元数据
#     """
#     if not txt or not txt.strip():
#         return []

#     # 动态阈值配置
#     target_min_tokens = max(50, min_chunk_tokens // 2)
#     target_tokens = min(600, chunk_token_num)
#     target_max_tokens = min(800, chunk_token_num * 1.5)
    
#     # 配置要作为分块边界的标题级别
#     headers_to_split_on = [1, 2, 3]
    
#     # 初始化 markdown-it 解析器
#     md = MarkdownIt("commonmark", {"breaks": True, "html": True})
#     md.enable(['table'])
    
#     try:
#         # 解析为 AST
#         tokens = md.parse(txt)
#         tree = SyntaxTreeNode(tokens)
        
#         # 提取所有节点和标题信息
#         nodes_with_headers = _extract_nodes_with_header_info(tree, headers_to_split_on)
        
#         # 基于标题层级进行初步分块
#         initial_chunks = _split_by_header_levels(nodes_with_headers, headers_to_split_on)
        
#         # 应用动态大小控制和优化
#         optimized_chunks = _apply_size_control_and_optimization(
#             initial_chunks, target_min_tokens, target_tokens, target_max_tokens
#         )
        
#         # 生成最终分块内容，包含父子关系
#         final_chunks = []
#         chunk_counter = 0
        
#         for chunk_info in optimized_chunks:
#             content = _render_header_chunk_advanced(chunk_info)
#             if content.strip():
#                 chunk_counter += 1
#                 parent_id = f"chunk_{chunk_counter}"
                
#                 # 创建父分段
#                 if include_metadata:
#                     parent_chunk = {
#                         'id': parent_id,
#                         'content': content,
#                         'type': 'parent',
#                         'metadata': chunk_info.get('headers', {}),
#                         'token_count': num_tokens_from_string(content),
#                         'chunk_type': chunk_info.get('chunk_type', 'header_based'),
#                         'has_special_content': chunk_info.get('has_special_content', False),
#                         'source_sections': chunk_info.get('source_sections', 1)
#                     }
#                 else:
#                     parent_chunk = {
#                         'id': parent_id,
#                         'content': content,
#                         'type': 'parent'
#                     }
                
#                 final_chunks.append(parent_chunk)
                
#                 # 如果需要创建子分段且父分段较大
#                 parent_token_count = num_tokens_from_string(content)
#                 if create_sub_chunks and parent_token_count > sub_chunk_token_num:
#                     # 使用相同的Markdown分块逻辑创建子分段
#                     sub_chunks = _create_semantic_sub_chunks(content, parent_id, 
#                                                            sub_chunk_token_num, include_metadata)
#                     final_chunks.extend(sub_chunks)
        
#         return final_chunks
    
#     except Exception as e:
#         print(f"Advanced header-based parsing failed: {e}, falling back to smart chunking")
#         return split_markdown_to_chunks_smart_with_hierarchy(txt, chunk_token_num, min_chunk_tokens,
#                                                            create_sub_chunks, sub_chunk_token_num)

# def _split_into_sentences(text):
#     """
#     将文本按句子边界拆分，兼容中英文。
    
#     按句号、问号、感叹号等句子结束符进行拆分，
#     同时处理换行符作为分隔。
    
#     Args:
#         text: 待拆分的文本
    
#     Returns:
#         句子列表（已去空白）
#     """
#     # 按句子结束符 + 空白拆分（兼容中英文标点）
#     sentences = re.split(r'(?<=[.!?。！？；;])\s*', text)
#     # 过滤空字符串并去除首尾空白
#     return [s.strip() for s in sentences if s.strip()]
import re

# URL 保护/还原的占位模式
URL_PLACEHOLDER_PATTERN = re.compile(r'\(\(URL_(\d+)\)\)')

def _split_into_sentences(text):
    """
    将文本按句子边界拆分，兼容中英文。
    
    关键保护机制：
    1. 保护 URL（避免 URL 内的标点干扰拆分）
    2. 保护数字编号（如 2.0.4、3.7、A.1 等，避免被句号错误切分）
    3. 保护小数/版本号（如 3.14、v1.0.2）
    
    按句号、问号、感叹号等句子结束符进行拆分，
    同时处理换行符作为分隔。
    """
    # 1. 保护 URL（避免 URL 内的标点干扰拆分）
    urls = []
    def _protect_url(match):
        idx = len(urls)
        urls.append(match.group(0))
        return f'((URL_{idx}))'
    
    url_pattern = re.compile(r'https?://[^\s)\]）]+')
    protected_text = url_pattern.sub(_protect_url, text)
    
    # 2. 保护页码引用标记（如 ..36、...42、. . 52、. ..36 等中文文档中常见的页码格式）
    # 这些点号不是句子结束符，而是指向页码的装饰性标记
    # 常见格式：
    #   - ..36      (两个点号直接连数字)
    #   - ...42     (三个点号连数字)
    #   - . ..36    (单点+空格+两点+数字)
    #   - . . .20   (单点间空格+数字)
    #   - .. 36     (两点+空格+数字)
    page_ref_placeholders = []
    def _protect_page_ref(match):
        idx = len(page_ref_placeholders)
        page_ref_placeholders.append(match.group(0))
        return f'((PAGE_{idx}))'
    # 匹配页码引用：一个或多个点号（可含中间空格）后跟数字
    # 覆盖格式：..36、. ..36、. . .42、.. 36、...36 等
    page_ref_pattern = re.compile(r'[\.。](?:\s*[\.。])+\s*\d+')
    protected_text = page_ref_pattern.sub(_protect_page_ref, protected_text)
    
    # 3. 保护数字编号和小数（如 2.0.4、3.7、A.1、3.14、v1.0.2）
    # 模式说明：
    #   - 数字+点+数字：如 2.0、3.7、2.0.4
    #   - 字母+点+数字：如 A.1、v1.0
    #   - 数字+点+字母：如 1.a
    # 使用占位符替换，拆分后再还原
    number_placeholders = []
    
    def _protect_number(match):
        idx = len(number_placeholders)
        number_placeholders.append(match.group(0))
        return f'((NUM_{idx}))'
    
    # 匹配数字编号模式：
    # (?:\d+\.\d+|\w\.\d+|\d+\.\w) 匹配核心编号
    # (?:\.\d+)* 匹配后续的 .x 部分（如 .4 在 2.0.4 中）
    number_pattern = re.compile(
        r'(?:\d+\.\d+|\w\.\d+|\d+\.\w)(?:\.\d+)*'
    )
    protected_text = number_pattern.sub(_protect_number, protected_text)
    
    # 3. 按句子结束符拆分（; 用于技术文档步骤分隔）
    sentences = re.split(r'(?<=[.!?。！？；;])\s*', protected_text)
    
    # 4. 还原占位符
    result = []
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        # 还原 URL
        s = URL_PLACEHOLDER_PATTERN.sub(
            lambda m: urls[int(m.group(1))], s
        )
        # 还原数字编号
        s = re.sub(
            r'\(\(NUM_(\d+)\)\)',
            lambda m: number_placeholders[int(m.group(1))],
            s
        )
        result.append(s)
    
    return result

def _force_split_long_text(text, max_tokens):
    """
    对超过 max_tokens 的超长文本（如长句子）按字符边界强制切分。
    
    Args:
        text: 超长文本
        max_tokens: 每段最大 token 数
    
    Returns:
        切分后的文本片段列表
    """
    # 保守估计算法：中文 1 char ≈ 1 token，英文 1 char ≈ 0.25 token
    # 取保守值：2 chars ≈ 1 token
    chars_per_chunk = max_tokens * 2
    chunks = []
    for i in range(0, len(text), chars_per_chunk):
        chunk = text[i:i + chars_per_chunk].strip()
        if chunk:
            chunks.append(chunk)
    return chunks


def _create_semantic_sub_chunks(parent_content, sub_chunk_token_num=256, include_metadata=False, table_sub_chunk_token_num=None):
    """
    使用与父分段相同的语义分块方式创建子分段。
    
    对段落和列表类型，先按句子拆分再累积，保证子分段粒度精细
    （~100 token），提升检索语义命中率。
    对表格、代码块、标题等结构性节点保持原子完整性。
    
    Args:
        parent_content: 父分段内容
        sub_chunk_token_num: 子分段最大token数
        include_metadata: 是否包含元数据
    
    Returns:
        子分段列表
    """
    # 表格阈值默认与文本阈值相同
    if table_sub_chunk_token_num is None:
        table_sub_chunk_token_num = sub_chunk_token_num
    
    sub_chunks = []
    
    # 初始化 markdown-it 解析器用于子分段
    md = MarkdownIt("commonmark", {"breaks": True, "html": True})
    md.enable(['table'])
    
    try:
        # 解析子内容为 AST
        tokens = md.parse(parent_content)
        tree = SyntaxTreeNode(tokens)
        
        # 可拆分为句子的节点类型（段落、列表等纯文本节点）
        BREAKABLE_TYPES = {'paragraph', 'bullet_list', 'ordered_list'}
        
        current_chunk = []
        current_tokens = 0
        context_stack = []
        
        for node in tree.children:
            chunk_data, should_break = _process_ast_node_for_subchunks(
                node, context_stack, sub_chunk_token_num, 10
            )
            
            # heading 类节点触发切分边界
            if should_break and current_chunk and current_tokens >= 10:
                chunk_content = _finalize_ast_chunk(current_chunk, context_stack)
                if chunk_content.strip():
                    if include_metadata:
                        sub_chunk = {
                            'content': chunk_content,
                            'type': 'child',
                            'token_count': current_tokens
                        }
                    else:
                        sub_chunk = {
                            'content': chunk_content,
                            'type': 'child'
                        }
                    sub_chunks.append(sub_chunk)
                
                current_chunk = []
                current_tokens = 0
            
            if not chunk_data:
                continue
            
            # 段落 / 列表：按句子拆分，逐句累积，保证子分段粒度精细
            if node.type in BREAKABLE_TYPES:
                sentences = _split_into_sentences(chunk_data)
                for sentence in sentences:
                    sentence_tokens = num_tokens_from_string(sentence)
                    
                    # 处理超长句子（如无标点的技术参数），强制按字符切分
                    if sentence_tokens > sub_chunk_token_num:
                        sub_parts = _force_split_long_text(sentence, sub_chunk_token_num)
                        for part in sub_parts:
                            part_tokens = num_tokens_from_string(part)
                            if (current_tokens + part_tokens > sub_chunk_token_num and
                                    current_chunk and current_tokens >= 10):
                                chunk_content = _finalize_ast_chunk(current_chunk, context_stack)
                                if chunk_content.strip():
                                    if include_metadata:
                                        sub_chunk = {
                                            'content': chunk_content,
                                            'type': 'child',
                                            'token_count': current_tokens
                                        }
                                    else:
                                        sub_chunk = {
                                            'content': chunk_content,
                                            'type': 'child'
                                        }
                                    sub_chunks.append(sub_chunk)
                                current_chunk = []
                                current_tokens = 0
                            current_chunk.append(part)
                            current_tokens += part_tokens
                        continue
                    
                    # 正常句子：累积到阈值时切分
                    if (current_tokens + sentence_tokens > sub_chunk_token_num and
                            current_chunk and current_tokens >= 10):
                        chunk_content = _finalize_ast_chunk(current_chunk, context_stack)
                        if chunk_content.strip():
                            if include_metadata:
                                sub_chunk = {
                                    'content': chunk_content,
                                    'type': 'child',
                                    'token_count': current_tokens
                                }
                            else:
                                sub_chunk = {
                                    'content': chunk_content,
                                    'type': 'child'
                                }
                            sub_chunks.append(sub_chunk)
                        current_chunk = []
                        current_tokens = 0
                    
                    current_chunk.append(sentence)
                    current_tokens += sentence_tokens
            
            else:
                # 表格、代码块、引用块等结构性节点：保持原子完整性
                chunk_tokens = num_tokens_from_string(chunk_data)
                
                # 大表格特殊处理：逐行累积，按token阈值切分（每块都带表头）
                is_table = node.type == 'table' or _contains_html_table(chunk_data)
                if is_table and chunk_tokens > table_sub_chunk_token_num:
                    # 先flush当前累积的内容（如果有）
                    if current_chunk and current_tokens >= 10:
                        chunk_content = _finalize_ast_chunk(current_chunk, context_stack)
                        if chunk_content.strip():
                            if include_metadata:
                                sub_chunk = {
                                    'content': chunk_content,
                                    'type': 'child',
                                    'token_count': current_tokens
                                }
                            else:
                                sub_chunk = {
                                    'content': chunk_content,
                                    'type': 'child'
                                }
                            sub_chunks.append(sub_chunk)
                        current_chunk = []
                        current_tokens = 0
                    
                    # 【修复】支持一个节点中包含多个表格的情况
                    # 先分割为独立的表格块，再逐个处理
                    if _contains_html_table(chunk_data):
                        # HTML表格：提取每个 <table>...</table> 块分别处理
                        table_blocks = re.findall(
                            r'<table[^>]*>.*?</table>', chunk_data,
                            re.DOTALL | re.IGNORECASE
                        )
                        # 如果没有提取到完整的 <table> 块，将整个内容作为一个块
                        if not table_blocks:
                            table_blocks = [chunk_data]
                    else:
                        # Markdown表格：按表格分割（通过双换行分隔）
                        # 先尝试按完整表格结构分割
                        md_table_blocks = []
                        current_md_table = []
                        for line in chunk_data.strip().split('\n'):
                            if '|' in line:
                                current_md_table.append(line)
                            else:
                                if current_md_table:
                                    md_table_blocks.append('\n'.join(current_md_table))
                                    current_md_table = []
                        if current_md_table:
                            md_table_blocks.append('\n'.join(current_md_table))
                        # 如果无法分割，将整个内容作为一个块
                        table_blocks = md_table_blocks if md_table_blocks else [chunk_data]

                    # 逐个处理每个表格块
                    for table_block in table_blocks:
                        if not table_block.strip():
                            continue

                        is_html = _contains_html_table(table_block)
                        if is_html:
                            table_open_match = re.search(
                                r'(<table[^>]*>)', table_block, re.IGNORECASE
                            )
                            table_close_match = re.search(
                                r'(</table>)', table_block, re.IGNORECASE
                            )
                            table_open = (
                                table_open_match.group(1)
                                if table_open_match else '<table>'
                            )
                            table_close = (
                                table_close_match.group(1)
                                if table_close_match else '</table>'
                            )

                            all_tr_rows = re.findall(
                                r'<tr[^>]*>.*?</tr>', table_block,
                                re.DOTALL | re.IGNORECASE
                            )
                            header_lines = [
                                row for row in all_tr_rows
                                if re.search(r'<th\b', row, re.IGNORECASE)
                            ]
                            header_line = (
                                header_lines[0] if header_lines else
                                (all_tr_rows[0] if all_tr_rows else '')
                            )
                            data_lines = [
                                row for row in all_tr_rows
                                if row != header_line
                                and re.search(r'<td\b', row, re.IGNORECASE)
                            ]
                            header_content = table_open + '\n' + header_line
                        else:
                            table_lines = table_block.strip().split('\n')
                            header_line = (
                                table_lines[0]
                                if len(table_lines) >= 1 else ''
                            )
                            data_lines = [
                                line for line in table_lines[2:]
                                if line.strip() and '|' in line
                            ]
                            header_content = (
                                table_lines[0] + '\n'
                                + (table_lines[1] if len(table_lines) > 1 else '')
                            )

                        header_tokens = num_tokens_from_string(
                            header_content.strip()
                        )

                        # 逐行累积，按token阈值切分
                        current_table_rows = []
                        current_table_tokens = 0

                        for row_line in data_lines:
                            row_tokens = num_tokens_from_string(row_line)
                            new_block_tokens = (
                                header_tokens + current_table_tokens + row_tokens
                            )

                            if (new_block_tokens > table_sub_chunk_token_num
                                    and current_table_rows):
                                if is_html:
                                    sub_lines = [
                                        table_open, header_line
                                    ]
                                    sub_lines.extend(current_table_rows)
                                    sub_lines.append(table_close)
                                else:
                                    sub_lines = [header_content]
                                    sub_lines.extend(current_table_rows)
                                sub_content = '\n'.join(sub_lines)

                                sub_tokens = num_tokens_from_string(sub_content)
                                if include_metadata:
                                    sub_chunk = {
                                        'content': sub_content,
                                        'type': 'child',
                                        'token_count': sub_tokens
                                    }
                                else:
                                    sub_chunk = {
                                        'content': sub_content,
                                        'type': 'child'
                                    }
                                sub_chunks.append(sub_chunk)
                                current_table_rows = []
                                current_table_tokens = 0

                            current_table_rows.append(row_line)
                            current_table_tokens += row_tokens

                        # 处理剩余行
                        if current_table_rows:
                            if is_html:
                                sub_lines = [table_open, header_line]
                                sub_lines.extend(current_table_rows)
                                sub_lines.append(table_close)
                            else:
                                sub_lines = [header_content]
                                sub_lines.extend(current_table_rows)
                            sub_content = '\n'.join(sub_lines)

                            sub_tokens = num_tokens_from_string(sub_content)
                            if include_metadata:
                                sub_chunk = {
                                    'content': sub_content,
                                    'type': 'child',
                                    'token_count': sub_tokens
                                }
                            else:
                                sub_chunk = {
                                    'content': sub_content,
                                    'type': 'child'
                                }
                            sub_chunks.append(sub_chunk)

                    continue
                
                # 原有逻辑：保持原子完整性
                if (current_tokens + chunk_tokens > sub_chunk_token_num and
                        current_chunk and current_tokens >= 10):
                    chunk_content = _finalize_ast_chunk(current_chunk, context_stack)
                    if chunk_content.strip():
                        if include_metadata:
                            sub_chunk = {
                                'content': chunk_content,
                                'type': 'child',
                                'token_count': current_tokens
                            }
                        else:
                            sub_chunk = {
                                'content': chunk_content,
                                'type': 'child'
                            }
                        sub_chunks.append(sub_chunk)
                    
                    current_chunk = []
                    current_tokens = 0
                
                current_chunk.append(chunk_data)
                current_tokens += chunk_tokens
        
        # 处理最后的子分段
        if current_chunk:
            chunk_content = _finalize_ast_chunk(current_chunk, context_stack)
            if chunk_content.strip():
                if include_metadata:
                    sub_chunk = {
                        'content': chunk_content,
                        'type': 'child',
                        'token_count': current_tokens
                    }
                else:
                    sub_chunk = {
                        'content': chunk_content,
                        'type': 'child'
                    }
                sub_chunks.append(sub_chunk)
        
        return [chunk['content'] for chunk in sub_chunks if chunk['content'].strip()]
    
    except Exception as e:
        print(f"Sub-chunking failed: {e}, falling back to line-based splitting")
        # 回退到基于行的分割方式
        return _create_line_based_sub_chunks(parent_content, sub_chunk_token_num, include_metadata)

def _process_ast_node_for_subchunks(node, context_stack, chunk_token_num, min_chunk_tokens):
    """
    为子分段处理 AST 节点（简化版本）
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
        
    elif node_type in ("bullet_list", "ordered_list"):
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

def _contains_html_table(content):
    """
    检查内容是否包含HTML表格
    """
    content_lower = content.lower()
    return '<table' in content_lower or '<td' in content_lower or '<tr' in content_lower

def _create_line_based_sub_chunks(parent_content, sub_chunk_token_num=256, include_metadata=False):
    """
    基于行的子分段创建（当语义分块失败时的回退方案）
    """
    sub_chunks = []
    lines = parent_content.split('\n')
    
    current_chunk_lines = []
    current_tokens = 0
    sub_chunk_counter = 0
    
    for line in lines:
        line_tokens = num_tokens_from_string(line)
        
        # 如果当前行会导致超出目标大小，且当前已有内容
        if current_tokens + line_tokens > sub_chunk_token_num and current_chunk_lines:
            # 创建子分段
            sub_chunk_counter += 1
            sub_chunk_content = '\n'.join(current_chunk_lines).strip()
            if sub_chunk_content:

                
                if include_metadata:
                    sub_chunk = {
              
                        'content': sub_chunk_content,
                        'type': 'child',
                        'token_count': current_tokens
                    }
                else:
                    sub_chunk = {
              
                        'content': sub_chunk_content,
                        'type': 'child'
                    }
                sub_chunks.append(sub_chunk)
            
            # 开始新分段
            current_chunk_lines = [line]
            current_tokens = line_tokens
        else:
            current_chunk_lines.append(line)
            current_tokens += line_tokens
    
    # 添加最后一个分段
    if current_chunk_lines:
        sub_chunk_counter += 1
        sub_chunk_content = '\n'.join(current_chunk_lines).strip()
        if sub_chunk_content:
            
            if include_metadata:
                sub_chunk = {
            
                    'content': sub_chunk_content,
                    'type': 'child',
                    'token_count': current_tokens
                }
            else:
                sub_chunk = {
            
                    'content': sub_chunk_content,
                    'type': 'child'
                }
            sub_chunks.append(sub_chunk)
    return [chunk['content'] for chunk in sub_chunks if chunk['content'].strip()]
    # return sub_chunks

def split_markdown_to_chunks_smart_with_hierarchy(txt, chunk_token_num=256, min_chunk_tokens=10,
                                                 create_sub_chunks=True, sub_chunk_token_num=128,
                                                 table_sub_chunk_token_num=None):
    """
    智能分块方法，支持父子分段结构
    """
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
        context_stack = []
        chunk_counter = 0
        
        for node in tree.children:
            chunk_data, should_break = _process_ast_node(
                node, context_stack, chunk_token_num, min_chunk_tokens
            )
            
            if should_break and current_chunk and current_tokens >= min_chunk_tokens:
                # 完成当前块
                chunk_content = _finalize_ast_chunk(current_chunk, context_stack)
                if chunk_content.strip():
                    chunk_counter += 1
                    parent_id = f"chunk_{chunk_counter}"
                    parent_chunk = {
                        'id': parent_id,
                        'content': chunk_content,
                        'type': 'parent',
                        'token_count': current_tokens
                    }
                    chunks.append(parent_chunk)
                    
                    # 创建子分段
                    if create_sub_chunks and current_tokens > sub_chunk_token_num:
                        sub_chunks = _create_semantic_sub_chunks(chunk_content,
                                                               sub_chunk_token_num=sub_chunk_token_num,
                                                               include_metadata=False,
                                                               table_sub_chunk_token_num=table_sub_chunk_token_num)
                        chunks.extend(sub_chunks)
                
                current_chunk = []
                current_tokens = 0
            
            if chunk_data:
                chunk_tokens = num_tokens_from_string(chunk_data)
                
                # 检查是否需要分块
                if (current_tokens + chunk_tokens > chunk_token_num and 
                    current_chunk and current_tokens >= min_chunk_tokens):
                    
                    chunk_content = _finalize_ast_chunk(current_chunk, context_stack)
                    if chunk_content.strip():
                        chunk_counter += 1
                        parent_id = f"chunk_{chunk_counter}"
                        parent_chunk = {
                            'id': parent_id,
                            'content': chunk_content,
                            'type': 'parent',
                            'token_count': current_tokens
                        }
                        chunks.append(parent_chunk)
                        
                        # 创建子分段
                        if create_sub_chunks and current_tokens > sub_chunk_token_num:
                            sub_chunks = _create_semantic_sub_chunks(chunk_content,
                                                                   sub_chunk_token_num=sub_chunk_token_num,
                                                                   include_metadata=False,
                                                                   table_sub_chunk_token_num=table_sub_chunk_token_num)
                            chunks.extend(sub_chunks)
                    
                    current_chunk = []
                    current_tokens = 0
                
                current_chunk.append(chunk_data)
                current_tokens += chunk_tokens
        
        # 处理最后的块
        if current_chunk:
            chunk_content = _finalize_ast_chunk(current_chunk, context_stack)
            if chunk_content.strip():
                chunk_counter += 1
                parent_id = f"chunk_{chunk_counter}"
                parent_chunk = {
                    'id': parent_id,
                    'content': chunk_content,
                    'type': 'parent',
                    'token_count': current_tokens
                }
                chunks.append(parent_chunk)
                
                # 创建子分段
                if create_sub_chunks and current_tokens > sub_chunk_token_num:
                    sub_chunks = _create_semantic_sub_chunks(chunk_content,
                                                           sub_chunk_token_num=sub_chunk_token_num,
                                                           include_metadata=False,
                                                           table_sub_chunk_token_num=table_sub_chunk_token_num)
                    chunks.extend(sub_chunks)
        
        return [chunk for chunk in chunks if chunk['content'].strip()]
    
    except Exception as e:
        print(f"AST parsing failed: {e}")
        return []
def split_markdown_to_chunks_parent_child(txt, chunk_token_num=256, min_chunk_tokens=10, 
                                         doc_id='unknown'):
    """
    优化后的父子分块方法 - 本地完成所有处理，避免HTTP调用
    
    Args:
        txt: 要分块的文本
        chunk_token_num: 子分块大小（tokens）
        min_chunk_tokens: 最小子分块大小
        parent_config: 父分块配置
        doc_id: 文档ID
        kb_id: 知识库ID
        
    Returns:
        list: 子分块列表（用于向量存储和前端显示）
        
    Note:
        现在直接在KnowFlow本地完成所有父子分块处理，避免跨容器HTTP调用
    """
    if not txt or not txt.strip():
        return []
    
    try:
        print(f"🚀 [DEBUG] 本地处理父子分块（优化后无HTTP调用）")
        print(f"  📝 文本长度: {len(txt)} 字符")
        print(f"  🔢 子分块大小: {chunk_token_num}")
        
        # 直接调用本地AST父子分块函数
        parent_chunks, child_chunks, relationships = split_markdown_to_chunks_ast_parent_child(
            txt=txt,
            chunk_token_num=chunk_token_num,
            min_chunk_tokens=min_chunk_tokens,
            doc_id=doc_id,
        )
        
        print(f"📊 [DEBUG] 本地父子分块完成:")
        print(f"  👨 父分块: {len(parent_chunks)} 个")
        print(f"  👶 子分块: {len(child_chunks)} 个")
        print(f"  🔗 关联关系: {len(relationships)} 个")
        
        # 构建详细结果供后续使用
        detailed_result = {
            'parent_chunks': [
                {
                    'id': chunk.id,
                    'content': chunk.content,
                    'order': chunk.order,
                    'metadata': chunk.metadata
                }
                for chunk in parent_chunks
            ],
            'child_chunks': [
                {
                    'id': chunk.id,
                    'content': chunk.content,
                    'order': chunk.order,
                    'metadata': chunk.metadata
                }
                for chunk in child_chunks
            ],
            'relationships': relationships,
            'total_parents': len(parent_chunks),
            'total_children': len(child_chunks)
        }
        
        # 保存详细结果到全局变量（供ragflow_build.py使用）
        global _last_parent_child_result
        _last_parent_child_result = detailed_result
        
        # 返回子分块内容列表（用于向量存储和前端显示）
        child_chunks_content = [chunk.content for chunk in child_chunks]
        
        print(f"✅ [DEBUG] 本地父子分块优化完成，返回 {len(child_chunks_content)} 个子分块内容")
        
        return child_chunks_content
        
    except Exception as e:
        print(f"❌ [ERROR] 本地父子分块失败: {e}，回退到智能分块")
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


def _compute_adaptive_split_level(enhanced_nodes,
                                  target_parent_tokens=(400, 1200),
                                  candidate_levels=(2, 3, 4, 5)):
    """
    根据文档标题结构和内容分布，自适应选择最优父分块切分级别。

    策略：
    1. 对每个候选级别，模拟切分并计算各分块的 token 分布。
    2. 用评分函数衡量该级别的"质量"：
       - 分块大小落在目标区间 [min_target, max_target] 的比例越高越好
       - 超大分块（>max_target*1.5）越少越好
       - 碎片分块（<min_target*0.3）越少越好
       - 分块数量适中（避免过多或过少）
    3. 选择得分最高的级别；如果全部都很差，回退到默认级别 3。

    Args:
        enhanced_nodes: 增强 AST 节点列表
        target_parent_tokens: (最小目标, 最大目标) token 数，默认 (400, 1200)
        candidate_levels: 候选标题级别，默认考察 H2~H5

    Returns:
        int: 最优父分块切分级别
    """
    min_target, max_target = target_parent_tokens
    max_allowed = int(max_target * 1.5)
    min_allowed = int(min_target * 0.3)

    best_level = 3  # 默认回退
    best_score = -float('inf')

    # 预先收集所有 heading 的位置和级别，用于快速模拟
    heading_indices = [
        (i, n['header_level'])
        for i, n in enumerate(enhanced_nodes)
        if n['type'] == 'heading' and n.get('header_level')
    ]

    for level in candidate_levels:
        # 模拟按当前 level 切分
        chunk_tokens = []
        current_tokens = 0

        for i, node in enumerate(enhanced_nodes):
            node_tokens = num_tokens_from_string(node.get('content', ''))

            # 检查是否是切分边界
            is_boundary = (
                node['type'] == 'heading' and
                node.get('header_level', 99) <= level
            )

            if is_boundary and current_tokens > 0:
                chunk_tokens.append(current_tokens)
                current_tokens = node_tokens
            else:
                current_tokens += node_tokens

        if current_tokens > 0:
            chunk_tokens.append(current_tokens)

        if not chunk_tokens:
            continue

        total_chunks = len(chunk_tokens)
        in_range = sum(1 for t in chunk_tokens if min_target <= t <= max_target)
        oversized = sum(1 for t in chunk_tokens if t > max_allowed)
        undersized = sum(1 for t in chunk_tokens if t < min_allowed)
        avg_size = sum(chunk_tokens) / total_chunks

        # 评分公式（可调参数）
        # 核心：鼓励落在目标区间，惩罚超大和超小
        in_range_ratio = in_range / total_chunks
        oversized_penalty = oversized * 2.0          # 超大分块惩罚较重
        undersized_penalty = undersized * 0.8        # 碎片惩罚较轻
        count_penalty = 0.0

        # 分块数量适中：假设理想范围是 3~30 个父分块
        if total_chunks < 2:
            count_penalty = 1.5
        elif total_chunks > 40:
            count_penalty = (total_chunks - 40) * 0.05

        # 平均大小偏离目标中点的惩罚
        target_mid = (min_target + max_target) / 2
        avg_deviation = abs(avg_size - target_mid) / target_mid
        avg_penalty = avg_deviation * 0.5

        score = (
            in_range_ratio * 10.0
            - oversized_penalty
            - undersized_penalty
            - count_penalty
            - avg_penalty
        )

        print(f"  [Adaptive] H{level}: chunks={total_chunks}, "
              f"in_range={in_range}({in_range_ratio:.1%}), "
              f"oversized={oversized}, undersized={undersized}, "
              f"avg={avg_size:.0f}, score={score:.2f}")

        if score > best_score:
            best_score = score
            best_level = level

    print(f"  [Adaptive] ✅ 选择 H{best_level} 作为父分块切分级别 (score={best_score:.2f})")
    return best_level


def split_markdown_to_chunks_ast_parent_child(txt, chunk_token_num=256, min_chunk_tokens=10,
                                              doc_id='unknown',
                                              parent_split_level=None,
                                              adaptive_split=True,
                                              target_parent_tokens=(400, 1200)):
    """
    基于AST的父子分块方法（支持自适应父分块级别）

    Args:
        txt: 要分块的文本
        chunk_token_num: 子分块大小（tokens）
        min_chunk_tokens: 最小子分块大小
        doc_id: 文档ID
        parent_split_level: 显式指定父分块切分级别（H1=1, H2=2...），
                            若提供则忽略 adaptive_split
        adaptive_split: 是否启用自适应切分级别，默认 True
        target_parent_tokens: 自适应时的目标父分块大小区间 (min, max)

    Returns:
        tuple: (parent_chunks, child_chunks, relationships)
    """

    if not txt or not txt.strip():
        return [], [], []

    try:
        # 1. 解析AST并创建增强节点
        enhanced_nodes = _create_enhanced_ast_nodes(txt)

        # 2. 确定父分块切分级别
        if parent_split_level is not None:
            chosen_level = parent_split_level
            print(f"🎯 [AST] 使用显式父分块级别: H{chosen_level}")
        elif adaptive_split:
            print(f"🎯 [AST] 启动自适应父分块级别选择...")
            chosen_level = _compute_adaptive_split_level(
                enhanced_nodes,
                target_parent_tokens=target_parent_tokens
            )
        else:
            chosen_level = 4  # 传统默认
            print(f"🎯 [AST] 使用默认父分块级别: H{chosen_level}")

        # 3. 基于AST创建子分块
        child_chunks = _create_ast_child_chunks(
            enhanced_nodes, chunk_token_num, min_chunk_tokens, doc_id
        )

        # 4. 基于AST和标题层级创建父分块（支持智能二级切分）
        parent_chunks = _create_ast_parent_chunks(
            enhanced_nodes, chosen_level, doc_id,
            target_parent_tokens=target_parent_tokens
        )

        # 5. 建立精确的AST关联关系
        relationships = _create_ast_relationships(
            child_chunks, parent_chunks, enhanced_nodes, doc_id,
        )

        print(f"🎯 [AST] 创建父子分块完成:")
        print(f"  👨 父分块: {len(parent_chunks)} 个 (H{chosen_level}切分)")
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


def _find_table_title_nodes(enhanced_nodes, table_index):
    """
    向前查找表格的标题/说明节点。
    
    检测规则（按优先级）：
    1. 紧邻表格前的 heading 节点（以"表"/"Table"开头）
    2. 紧邻表格前的 paragraph 节点（以"表"/"Table"/"下表"/"如下表"开头，或包含表格指示短语）
    3. 短段落（<60字符）且包含"表"字
    
    Args:
        enhanced_nodes: 增强节点列表
        table_index: 表格节点在列表中的索引
        
    Returns:
        list: 标题节点索引列表（可能为空）
    """
    if table_index <= 0:
        return []
    
    title_indices = []
    
    # 只向前看最多2个节点
    for lookback in range(1, min(3, table_index + 1)):
        idx = table_index - lookback
        node = enhanced_nodes[idx]
        content = node.get('content', '').strip()
        node_type = node.get('type', '')
        
        if not content:
            continue
        
        # 跳过已经被标记为其他表格标题的节点
        if node.get('_is_table_title', False):
            continue
            
        # heading 节点检测
        if node_type == 'heading':
            title_text = node.get('header_title', '') or content
            clean_title = re.sub(r'^#+\s*', '', title_text).strip()
            if re.match(r'^(表|Table|TABLE)', clean_title):
                title_indices.insert(0, idx)
                break  # heading 作为最强信号，找到就停止
        
        # paragraph 节点检测
        elif node_type == 'paragraph':
            # 以"表"/"T"/"下表"/"表格"开头
            if re.match(r'^(表|Table|TABLE|T\d|下表|表格)', content):
                title_indices.insert(0, idx)
                break
            # 包含常见表格指示短语
            if re.search(r'(如下表|下表所示|表所示|如下表所示|表格如下|见下表|参见下表|下表列出|下表给出|下表说明)', content):
                title_indices.insert(0, idx)
                break
            # 短段落且包含"表"字
            if len(content) < 60 and '表' in content:
                title_indices.insert(0, idx)
                break
    
    return title_indices


def _split_table_into_row_chunks(table_node_info, chunk_token_num, doc_id, chunk_order_start):
    """
    将表格按行拆分为多个子分块，每个子块保留完整表头。
    
    Args:
        table_node_info: 表格节点信息字典
        chunk_token_num: 子分块最大token数
        doc_id: 文档ID
        chunk_order_start: 起始chunk order编号
        
    Returns:
        tuple: (子分块列表, 下一个chunk_order)
    """
    table_content = table_node_info.get('content', '')
    table_tokens = num_tokens_from_string(table_content)
    
    # 如果表格不大，直接作为一个子分块
    if table_tokens <= chunk_token_num:
        chunk = _create_ast_child_chunk_obj(
            [table_node_info], chunk_order_start, doc_id
        )
        chunk.metadata['chunk_subtype'] = 'table_content'
        chunk.metadata['table_split'] = False
        return [chunk], chunk_order_start + 1
    
    # 大表格：按行拆分
    sub_chunks = []
    chunk_order = chunk_order_start
    
    try:
        thead_html, tbody_rows = _parse_html_table_rows(table_content)
        
        if not tbody_rows:
            # 无法解析行，保持原样
            chunk = _create_ast_child_chunk_obj(
                [table_node_info], chunk_order, doc_id
            )
            chunk.metadata['chunk_subtype'] = 'table_content'
            chunk.metadata['table_split'] = False
            return [chunk], chunk_order + 1
        
        # 计算表头token数
        header_tokens = num_tokens_from_string(thead_html) if thead_html else 0
        # 每块可用token（保留表头 + 部分数据行）
        available_tokens = chunk_token_num - header_tokens - 20  # 20为表格标签缓冲
        
        if available_tokens <= 0:
            # 表头本身就超大，保持原样
            chunk = _create_ast_child_chunk_obj(
                [table_node_info], chunk_order, doc_id
            )
            chunk.metadata['chunk_subtype'] = 'table_content'
            chunk.metadata['table_split'] = False
            return [chunk], chunk_order + 1
        
        # 如果表头占用了超过 chunk_token_num 的 40%，说明表头太复杂
        # 按行拆分后每个子分块都会超过限制，不如保持原样
        if header_tokens > chunk_token_num * 0.4:
            chunk = _create_ast_child_chunk_obj(
                [table_node_info], chunk_order, doc_id
            )
            chunk.metadata['chunk_subtype'] = 'table_content'
            chunk.metadata['table_split'] = False
            chunk.metadata['table_skip_split_reason'] = 'header_too_large'
            return [chunk], chunk_order + 1
        
        # 累积数据行
        current_rows = []
        current_tokens = 0
        
        for row_html in tbody_rows:
            row_tokens = num_tokens_from_string(row_html)
            
            # 单个行就超过可用空间
            if row_tokens > available_tokens:
                # 先保存当前累积的行
                if current_rows:
                    chunk_content = _build_table_html(thead_html, current_rows)
                    chunk_node = {
                        **table_node_info,
                        'content': chunk_content,
                        'line_start': table_node_info.get('line_start', 0),
                        'line_end': table_node_info.get('line_end', 0),
                    }
                    chunk = _create_ast_child_chunk_obj(
                        [chunk_node], chunk_order, doc_id
                    )
                    chunk.metadata['chunk_subtype'] = 'table_content_split'
                    chunk.metadata['table_split'] = True
                    chunk.metadata['table_row_count'] = len(current_rows)
                    sub_chunks.append(chunk)
                    chunk_order += 1
                    current_rows = []
                    current_tokens = 0
                
                # 超大行单独作为一个分块
                chunk_content = _build_table_html(thead_html, [row_html])
                chunk_node = {
                    **table_node_info,
                    'content': chunk_content,
                    'line_start': table_node_info.get('line_start', 0),
                    'line_end': table_node_info.get('line_end', 0),
                }
                chunk = _create_ast_child_chunk_obj(
                    [chunk_node], chunk_order, doc_id
                )
                chunk.metadata['chunk_subtype'] = 'table_content_split'
                chunk.metadata['table_split'] = True
                chunk.metadata['table_row_count'] = 1
                sub_chunks.append(chunk)
                chunk_order += 1
                continue
            
            # 正常行：累积到当前块
            if current_tokens + row_tokens > available_tokens and current_rows:
                # 当前块已满，保存并开始新块
                chunk_content = _build_table_html(thead_html, current_rows)
                chunk_node = {
                    **table_node_info,
                    'content': chunk_content,
                    'line_start': table_node_info.get('line_start', 0),
                    'line_end': table_node_info.get('line_end', 0),
                }
                chunk = _create_ast_child_chunk_obj(
                    [chunk_node], chunk_order, doc_id
                )
                chunk.metadata['chunk_subtype'] = 'table_content_split'
                chunk.metadata['table_split'] = True
                chunk.metadata['table_row_count'] = len(current_rows)
                sub_chunks.append(chunk)
                chunk_order += 1
                current_rows = [row_html]
                current_tokens = row_tokens
            else:
                current_rows.append(row_html)
                current_tokens += row_tokens
        
        # 处理最后剩余的行
        if current_rows:
            chunk_content = _build_table_html(thead_html, current_rows)
            chunk_node = {
                **table_node_info,
                'content': chunk_content,
                'line_start': table_node_info.get('line_start', 0),
                'line_end': table_node_info.get('line_end', 0),
            }
            chunk = _create_ast_child_chunk_obj(
                [chunk_node], chunk_order, doc_id
            )
            chunk.metadata['chunk_subtype'] = 'table_content_split'
            chunk.metadata['table_split'] = True
            chunk.metadata['table_row_count'] = len(current_rows)
            sub_chunks.append(chunk)
            chunk_order += 1
        
        return sub_chunks, chunk_order
        
    except Exception as e:
        print(f"[WARNING] 表格按行拆分失败: {e}，保持原样")
        chunk = _create_ast_child_chunk_obj(
            [table_node_info], chunk_order, doc_id
        )
        chunk.metadata['chunk_subtype'] = 'table_content'
        chunk.metadata['table_split'] = False
        return [chunk], chunk_order + 1


def _create_ast_child_chunks(enhanced_nodes, chunk_token_num, min_chunk_tokens, doc_id):
    """
    基于AST节点创建子分块。
    
    特殊处理表格：
    1. 表格标题（heading/段落）单独作为一个子chunk
    2. 表格内容按行拆分，每块保留表头
    3. 普通节点按token累积
    """
    child_chunks = []
    current_chunk_nodes = []
    current_tokens = 0
    chunk_order = 0
    
    i = 0
    while i < len(enhanced_nodes):
        node_info = enhanced_nodes[i]
        content = node_info['content']
        if not content.strip():
            i += 1
            continue
            
        content_tokens = num_tokens_from_string(content)
        node_type = node_info.get('type', '')
        
        # 检查是否需要分块（heading 边界）
        should_break = (
            node_type == 'heading' and 
            node_info.get('header_level', 99) <= 3  # H1, H2, H3作为分块边界
        )
        
        if should_break and current_chunk_nodes:
            # heading 边界：总是先完成当前 chunk（即使 token 不够也输出，避免累积过多）
            child_chunk = _create_ast_child_chunk_obj(
                current_chunk_nodes, chunk_order, doc_id
            )
            child_chunks.append(child_chunk)
            chunk_order += 1
            current_chunk_nodes = []
            current_tokens = 0
        
        # ===== 表格节点特殊处理 =====
        is_table_node = (node_type == 'table' or 
                        node_type == 'html_block' and _is_html_table_content(content))
        
        if is_table_node:
            # 1. 查找表格标题（向前看）
            title_indices = _find_table_title_nodes(enhanced_nodes, i)
            
            # 收集标题节点，并标记
            title_nodes = []
            if title_indices:
                for ti in title_indices:
                    title_node = enhanced_nodes[ti]
                    title_node['_is_table_title'] = True
                    title_nodes.append(title_node)
            
            # 2. 从 current_chunk_nodes 中分离出表格标题和 heading 上下文
            # 标题节点和紧邻的 heading 需要从 current_chunk 中移除，单独处理
            heading_context_nodes = []
            if title_nodes and title_indices:
                first_title_idx = title_indices[0]
                # 检查标题前是否紧邻 heading
                if first_title_idx > 0:
                    prev_node = enhanced_nodes[first_title_idx - 1]
                    if prev_node.get('type') == 'heading' and prev_node in current_chunk_nodes:
                        heading_context_nodes.append(prev_node)
                # 标题节点本身
                for tn in title_nodes:
                    if tn in current_chunk_nodes:
                        heading_context_nodes.append(tn)
            
            # 从 current_chunk_nodes 中移除标题相关节点
            for hc_node in heading_context_nodes:
                if hc_node in current_chunk_nodes:
                    current_chunk_nodes.remove(hc_node)
                    current_tokens -= num_tokens_from_string(hc_node.get('content', ''))
            
            # 3. 输出剩余的非标题内容（如果有）
            if current_chunk_nodes and current_tokens >= min_chunk_tokens:
                child_chunk = _create_ast_child_chunk_obj(
                    current_chunk_nodes, chunk_order, doc_id
                )
                child_chunks.append(child_chunk)
                chunk_order += 1
                current_chunk_nodes = []
                current_tokens = 0
            elif current_chunk_nodes:
                # token 不够，保留到后续处理
                pass
            
            # 4. 输出表格上下文 chunk（heading + 标题）
            if heading_context_nodes:
                context_chunk = _create_ast_child_chunk_obj(
                    heading_context_nodes, chunk_order, doc_id
                )
                context_chunk.metadata['chunk_subtype'] = 'table_context'
                context_chunk.metadata['contains_tables'] = False
                child_chunks.append(context_chunk)
                chunk_order += 1
            elif title_nodes:
                # 只有标题，没有 heading 上下文
                title_chunk = _create_ast_child_chunk_obj(
                    title_nodes, chunk_order, doc_id
                )
                title_chunk.metadata['chunk_subtype'] = 'table_title'
                title_chunk.metadata['contains_tables'] = False
                child_chunks.append(title_chunk)
                chunk_order += 1
            
            # 5. 表格内容按行拆分
            table_sub_chunks, chunk_order = _split_table_into_row_chunks(
                node_info, chunk_token_num, doc_id, chunk_order
            )
            child_chunks.extend(table_sub_chunks)
            
            i += 1
            continue
        
        # 如果节点已被标记为表格标题，跳过（已在表格处理时处理）
        if node_info.get('_is_table_title', False):
            i += 1
            continue
        
        # ===== 普通节点：检查token限制 =====
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
        i += 1
    
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
    
    content = "\n\n".join([n['content'] for n in nodes if n.get('content', '').strip()])
    chunk_id = f"{doc_id}_child_ast_{order:04d}_{hashlib.md5(content.encode('utf-8')).hexdigest()[:8]}"
    
    # 检测是否包含表格（支持 table 类型和 html_block 中的表格）
    has_table = any(
        n.get('type') == 'table' or 
        (n.get('type') == 'html_block' and _is_html_table_content(n.get('content', '')))
        for n in nodes
    )
    
    # 基础metadata
    metadata = {
        'chunk_type': 'child',
        'creation_method': 'ast_semantic',
        'contains_headers': any(n.get('type') == 'heading' for n in nodes),
        'contains_tables': has_table,
        'contains_code': any(n.get('type') == 'code_block' for n in nodes),
        'ast_node_count': len(nodes),
        'context_stack': nodes[0].get('context_stack', []) if nodes else []
    }
    
    return ASTChunkInfo(
        id=chunk_id,
        content=content,
        start_line=nodes[0].get('line_start', 0) if nodes else 0,
        end_line=nodes[-1].get('line_end', 0) if nodes else 0,
        order=order,
        doc_id=doc_id,
        ast_nodes=nodes,
        metadata=metadata
    )


def _create_ast_parent_chunks(enhanced_nodes, parent_split_level, doc_id,
                                 target_parent_tokens=(400, 1200),
                                 max_split_level=6):
    """
    基于AST和标题层级创建父分块（支持智能二级切分）

    核心策略：
    1. 先按 parent_split_level 进行一级切分
    2. 对每个分块，如果其 token 数超过 max_target * 1.5，
       则尝试用更低级别的标题（parent_split_level + 1, +2...）进行二级切分
    3. 二级切分时，子分块会继承父分块的标题上下文

    Args:
        enhanced_nodes: 增强AST节点列表
        parent_split_level: 一级切分标题级别
        doc_id: 文档ID
        target_parent_tokens: 目标父分块大小区间 (min, max)
        max_split_level: 最大切分标题级别（防止无限递归）

    Returns:
        list: 父分块列表
    """
    min_target, max_target = target_parent_tokens
    max_allowed = int(max_target * 1.5)

    # 第一步：按一级级别切分
    raw_sections = _split_nodes_by_level(enhanced_nodes, parent_split_level)

    parent_chunks = []
    parent_order = 0

    for section_nodes, section_header in raw_sections:
        if not section_nodes:
            continue

        section_content = "\n\n".join(
            n['content'] for n in section_nodes if n.get('content', '').strip()
        )
        section_tokens = num_tokens_from_string(section_content)

        # 判断是否需要二级切分
        needs_secondary_split = (
            section_tokens > max_allowed and
            parent_split_level < max_split_level
        )

        if needs_secondary_split:
            # 尝试二级切分：查找更低级别的标题作为子边界
            sub_chunks = _try_secondary_split(
                section_nodes, section_header,
                parent_split_level, max_split_level,
                max_allowed, doc_id, parent_order
            )
            parent_chunks.extend(sub_chunks)
            parent_order += len(sub_chunks)
        else:
            # 不需要二级切分，直接创建父分块
            parent_chunk = _create_ast_parent_chunk_obj(
                section_nodes, section_header, parent_order, doc_id
            )
            parent_chunks.append(parent_chunk)
            parent_order += 1

    return parent_chunks


def _split_nodes_by_level(nodes, split_level):
    """
    按指定标题级别将节点切分为多个段

    Returns:
        list of (section_nodes, section_header): 每个段及其标题信息
    """
    sections = []
    current_nodes = []
    current_header = None

    for node in nodes:
        is_boundary = (
            node['type'] == 'heading' and
            node.get('header_level', 99) <= split_level
        )

        if is_boundary:
            # 保存当前段
            if current_nodes:
                sections.append((current_nodes, current_header))

            # 开始新段
            current_nodes = [node]
            current_header = {
                'level': node['header_level'],
                'title': node['header_title'],
                'context_stack': node['context_stack']
            }
        else:
            current_nodes.append(node)

    # 保存最后一段
    if current_nodes:
        sections.append((current_nodes, current_header))

    return sections


def _try_secondary_split(section_nodes, section_header, current_level, max_level,
                          max_allowed, doc_id, order_start):
    """
    尝试对超大段进行二级切分（改进版：允许部分超大分块，优先整体改善）

    策略：
    1. 从 current_level + 1 开始，逐级尝试更低级别的标题
    2. 评估标准：相比不切分，超大分块的比例是否显著降低
    3. 接受"大部分分块合理，少数仍略大"的情况（避免一刀切）
    4. 如果所有级别都无法改善，则保持原样

    Returns:
        list: 切分后的父分块列表
    """
    # 计算原始段的大小
    original_content = "\n\n".join(
        n['content'] for n in section_nodes if n.get('content', '').strip()
    )
    original_tokens = num_tokens_from_string(original_content)

    # 先尝试找到最优的二级切分级别
    best_level = None
    best_score = -float('inf')
    best_sections = None

    for try_level in range(current_level + 1, max_level + 1):
        sub_sections = _split_nodes_by_level(section_nodes, try_level)

        # 过滤掉只有标题的空段
        valid_sections = []
        for nodes, header in sub_sections:
            content = "\n\n".join(
                n['content'] for n in nodes if n.get('content', '').strip()
            )
            if content.strip():
                valid_sections.append((nodes, header, num_tokens_from_string(content)))

        if not valid_sections:
            continue

        # 评估这个级别的切分质量
        tokens_list = [t for _, _, t in valid_sections]
        total_chunks = len(tokens_list)
        oversized = sum(1 for t in tokens_list if t > max_allowed)
        undersized = sum(1 for t in tokens_list if t < 50)
        in_range = sum(1 for t in tokens_list if 200 <= t <= max_allowed)

        # 改进的评分逻辑：
        # 1. 鼓励产生多个分块（说明有有效切分）
        # 2. 鼓励分块落在合理范围
        # 3. 轻微惩罚超大分块（但不是一票否决）
        # 4. 如果只有一个分块且和原来一样大，说明这个级别无效

        if total_chunks == 1 and tokens_list[0] >= original_tokens * 0.95:
            # 这个级别没有实际切分效果，跳过
            continue

        # 超大分块比例（越低越好）
        oversized_ratio = oversized / total_chunks if total_chunks > 0 else 1.0
        # 原始超大比例是 1.0（整个段都是超大）
        improvement = 1.0 - oversized_ratio

        score = (
            improvement * 8.0           # 改善程度是核心指标
            + in_range * 1.0             # 合理范围分块奖励
            - undersized * 0.5           # 碎片惩罚
            - oversized * 0.3            # 剩余超大分块轻微惩罚
        )

        if score > best_score:
            best_score = score
            best_level = try_level
            best_sections = valid_sections

    # 如果没有找到合适的二级切分级别，保持原样
    if best_level is None or best_sections is None:
        chunk = _create_ast_parent_chunk_obj(
            section_nodes, section_header, order_start, doc_id
        )
        chunk.metadata['split_strategy'] = 'single_level_oversized'
        return [chunk]

    # 使用最优级别进行二级切分
    result_chunks = []
    order = order_start

    for nodes, header, _ in best_sections:
        content = "\n\n".join(
            n['content'] for n in nodes if n.get('content', '').strip()
        )
        if not content.strip():
            continue

        # 二级切分的分块继承一级标题上下文
        effective_header = header or section_header
        if header and section_header:
            # 合并上下文：保留高级别标题信息
            merged_context = section_header['context_stack'].copy()
            # 确保当前标题也在上下文中
            if header['title'] not in [c['title'] for c in merged_context]:
                merged_context.append({
                    'level': header['level'],
                    'title': header['title']
                })
            effective_header = {
                'level': header['level'],
                'title': header['title'],
                'context_stack': merged_context
            }

        chunk = _create_ast_parent_chunk_obj(
            nodes, effective_header, order, doc_id
        )
        chunk.metadata['split_strategy'] = f'secondary_H{current_level}_to_H{best_level}'
        chunk.metadata['primary_header'] = section_header['title'] if section_header else ''
        result_chunks.append(chunk)
        order += 1

    return result_chunks


def _create_ast_parent_chunk_obj(nodes, header_info, order, doc_id):
    """创建父分块对象"""
    import hashlib
    
    content = "\n\n".join([n['content'] for n in nodes if n.get('content', '').strip()])
    chunk_id = f"{doc_id}_parent_ast_{order:04d}_{hashlib.md5(content.encode('utf-8')).hexdigest()[:8]}"
    
    # 检测表格相关信息
    table_nodes = [
        n for n in nodes 
        if n.get('type') == 'table' or 
           (n.get('type') == 'html_block' and _is_html_table_content(n.get('content', '')))
    ]
    table_count = len(table_nodes)
    
    # 提取表格标题列表
    table_titles = []
    for i, n in enumerate(nodes):
        if n.get('type') in ('paragraph', 'heading'):
            node_content = n.get('content', '')
            # 检测是否为表格标题
            is_title = False
            if n.get('type') == 'heading':
                clean_title = re.sub(r'^#+\s*', '', node_content).strip()
                if re.match(r'^(表|Table|TABLE)', clean_title):
                    is_title = True
            elif n.get('type') == 'paragraph':
                if re.match(r'^(表|Table|TABLE|T\d|下表|表格)', node_content):
                    is_title = True
                elif re.search(r'(如下表|下表所示|表所示|表格如下|见下表)', node_content):
                    is_title = True
            
            # 检查下一个节点是否为表格
            if is_title and i + 1 < len(nodes):
                next_node = nodes[i + 1]
                if (next_node.get('type') == 'table' or 
                    (next_node.get('type') == 'html_block' and _is_html_table_content(next_node.get('content', '')))):
                    table_titles.append(node_content)
    
    return ASTChunkInfo(
        id=chunk_id,
        content=content,
        start_line=nodes[0].get('line_start', 0) if nodes else 0,
        end_line=nodes[-1].get('line_end', 0) if nodes else 0,
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
            'ast_node_count': len(nodes),
            'contains_tables': table_count > 0,
            'table_count': table_count,
            'table_titles': table_titles
        }
    )


def _create_ast_relationships(child_chunks, parent_chunks, enhanced_nodes, doc_id):
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
