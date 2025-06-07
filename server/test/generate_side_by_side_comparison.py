#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
from pathlib import Path
from datetime import datetime

# 添加server目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def create_chunk_exports_dir():
    """创建chunk_exports目录"""
    exports_dir = Path("chunk_exports")
    exports_dir.mkdir(exist_ok=True)
    return exports_dir

def generate_side_by_side_html(original_chunks, optimized_chunks, test_params, output_file):
    """生成左右两栏对比的HTML"""
    
    from services.knowledgebases.mineru_parse.utils import num_tokens_from_string
    
    # 计算统计信息
    original_total_tokens = sum(num_tokens_from_string(chunk) for chunk in original_chunks)
    optimized_total_tokens = sum(num_tokens_from_string(chunk) for chunk in optimized_chunks)
    
    original_avg_tokens = original_total_tokens // len(original_chunks) if original_chunks else 0
    optimized_avg_tokens = optimized_total_tokens // len(optimized_chunks) if optimized_chunks else 0
    
    chunk_reduction = len(original_chunks) - len(optimized_chunks)
    chunk_reduction_percent = (chunk_reduction / len(original_chunks) * 100) if original_chunks else 0
    
    html_content = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>分块方法左右对比 - {test_params} tokens</title>
    <style>
        * {{
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Microsoft YaHei', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 0;
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            min-height: 100vh;
            line-height: 1.4;
        }}
        
        .header {{
            background: white;
            padding: 20px;
            text-align: center;
            box-shadow: 0 2px 20px rgba(0,0,0,0.1);
            margin-bottom: 20px;
            position: sticky;
            top: 0;
            z-index: 100;
        }}
        
        .header h1 {{
            margin: 0 0 15px 0;
            color: #333;
            font-size: 28px;
            font-weight: 300;
        }}
        
        .meta-info {{
            color: #666;
            margin-bottom: 15px;
            font-size: 14px;
        }}
        
        .stats-bar {{
            display: flex;
            justify-content: center;
            gap: 30px;
            flex-wrap: wrap;
            margin-top: 15px;
        }}
        
        .stat-item {{
            text-align: center;
            padding: 10px 20px;
            background: #f8f9fa;
            border-radius: 8px;
            min-width: 120px;
        }}
        
        .stat-value {{
            font-size: 20px;
            font-weight: bold;
            margin-bottom: 5px;
        }}
        
        .stat-label {{
            font-size: 11px;
            color: #666;
            text-transform: uppercase;
        }}
        
        .improvement {{
            color: #28a745;
        }}
        
        .neutral {{
            color: #6c757d;
        }}
        
        .warning {{
            color: #dc3545;
        }}
        
        .comparison-container {{
            display: flex;
            gap: 10px;
            height: calc(100vh - 200px);
            min-height: 600px;
            padding: 0 10px;
        }}
        
        .column {{
            flex: 1;
            width: 50%;
            min-width: 0;
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }}
        
        .column-header {{
            padding: 20px;
            font-weight: bold;
            font-size: 16px;
            color: white;
            text-align: center;
            flex-shrink: 0;
            position: relative;
        }}
        
        .original-method {{
            background: linear-gradient(135deg, #FF6B6B, #FF8E53);
        }}
        
        .optimized-method {{
            background: linear-gradient(135deg, #4ECDC4, #44A08D);
        }}
        
        .method-badge {{
            position: absolute;
            top: 10px;
            right: 15px;
            background: rgba(255,255,255,0.2);
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 12px;
        }}
        
        .chunks-container {{
            flex: 1;
            overflow-y: auto;
            overflow-x: hidden;
            padding: 0;
            height: 100%;
        }}
        
        .chunk {{
            border-bottom: 1px solid #f0f0f0;
            padding: 20px;
            transition: all 0.2s ease;
            cursor: pointer;
            position: relative;
        }}
        
        .chunk:hover {{
            background-color: #f8f9fa;
            transform: translateX(2px);
        }}
        
        .chunk:last-child {{
            border-bottom: none;
        }}
        
        .chunk-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #e9ecef;
        }}
        
        .chunk-title {{
            font-weight: bold;
            color: #495057;
            font-size: 15px;
        }}
        
        .chunk-stats {{
            display: flex;
            gap: 10px;
            align-items: center;
        }}
        
        .chunk-tokens {{
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            padding: 4px 10px;
            border-radius: 15px;
            font-size: 12px;
            font-weight: bold;
        }}
        
        .chunk-chars {{
            background: #e9ecef;
            color: #6c757d;
            padding: 4px 8px;
            border-radius: 10px;
            font-size: 11px;
        }}
        
        .chunk-content {{
            font-size: 13px;
            line-height: 1.6;
            color: #495057;
            white-space: pre-line;
            word-wrap: break-word;
            word-break: break-word;
            background: #fafafa;
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #dee2e6;
            margin-bottom: 10px;
            position: relative;
        }}
        
        .chunk-content.collapsed {{
            max-height: 300px;
            overflow: hidden;
        }}
        
        .chunk-content.expanded {{
            max-height: none;
        }}
        
        .expand-btn {{
            position: absolute;
            bottom: 10px;
            right: 10px;
            background: rgba(102, 126, 234, 0.8);
            color: white;
            border: none;
            padding: 5px 10px;
            border-radius: 12px;
            font-size: 11px;
            cursor: pointer;
            transition: all 0.2s ease;
        }}
        
        .expand-btn:hover {{
            background: rgba(102, 126, 234, 1);
            transform: scale(1.05);
        }}
        
        .content-truncated {{
            background: linear-gradient(to bottom, transparent 0%, rgba(250,250,250,0.8) 70%, rgba(250,250,250,1) 100%);
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            height: 40px;
            pointer-events: none;
        }}
        
        .chunk-meta {{
            display: flex;
            justify-content: space-between;
            font-size: 11px;
            color: #6c757d;
            padding-top: 8px;
            border-top: 1px solid #f0f0f0;
        }}
        
        .table-indicator {{
            background: linear-gradient(135deg, #ffd54f, #ff8f00);
            color: white;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 10px;
            margin-left: 8px;
            font-weight: bold;
        }}
        
        .chunk-index {{
            position: absolute;
            top: 15px;
            right: 15px;
            background: rgba(0,0,0,0.05);
            color: #6c757d;
            padding: 2px 6px;
            border-radius: 8px;
            font-size: 10px;
            font-weight: bold;
        }}
        
        .sync-indicator {{
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: rgba(0,0,0,0.8);
            color: white;
            padding: 10px 20px;
            border-radius: 20px;
            font-size: 12px;
            display: none;
            z-index: 1000;
        }}
        
        .search-box {{
            position: fixed;
            top: 20px;
            right: 20px;
            background: white;
            padding: 10px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            z-index: 200;
        }}
        
        .search-box input {{
            padding: 8px 12px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 13px;
            width: 200px;
        }}
        
        .highlight {{
            background: yellow;
            padding: 2px 4px;
            border-radius: 2px;
        }}
        
        /* 滚动条样式 */
        .chunks-container::-webkit-scrollbar {{
            width: 8px;
        }}
        
        .chunks-container::-webkit-scrollbar-track {{
            background: #f1f1f1;
            border-radius: 4px;
        }}
        
        .chunks-container::-webkit-scrollbar-thumb {{
            background: #c1c1c1;
            border-radius: 4px;
        }}
        
        .chunks-container::-webkit-scrollbar-thumb:hover {{
            background: #a8a8a8;
        }}
        
        /* 响应式设计 */
        @media (max-width: 768px) {{
            .comparison-container {{
                flex-direction: column;
                height: auto;
                gap: 20px;
            }}
            
            .column {{
                width: 100%;
                max-height: 70vh;
            }}
            
            .stats-bar {{
                gap: 15px;
            }}
            
            .stat-item {{
                min-width: 100px;
                padding: 8px 15px;
            }}
            
            .search-box {{
                position: relative;
                top: auto;
                right: auto;
                margin-bottom: 20px;
            }}
        }}
        
        /* 高亮效果 */
        .chunk.highlighted {{
            background: linear-gradient(135deg, #fff3e0, #ffe0b2) !important;
            border-left: 4px solid #ff9800;
            transform: translateX(5px);
        }}
        
        .loading {{
            display: flex;
            justify-content: center;
            align-items: center;
            height: 200px;
            color: #6c757d;
            font-size: 14px;
        }}
        
        .controls {{
            display: flex;
            gap: 10px;
            margin-bottom: 10px;
            padding: 0 10px;
        }}
        
        .control-btn {{
            padding: 8px 16px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 12px;
            transition: all 0.2s ease;
        }}
        
        .control-btn:hover {{
            background: #5a6fd8;
            transform: translateY(-1px);
        }}
        
        .control-btn.active {{
            background: #28a745;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 分块方法左右对比分析</h1>
        <div class="meta-info">
            split_markdown_to_chunks (原方法) vs split_markdown_to_chunks_optimized (优化方法) | 
            Chunk大小: {test_params} tokens | 
            生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </div>
        
        <div class="stats-bar">
            <div class="stat-item">
                <div class="stat-value warning">{len(original_chunks)}</div>
                <div class="stat-label">原方法分块数</div>
            </div>
            <div class="stat-item">
                <div class="stat-value improvement">{len(optimized_chunks)}</div>
                <div class="stat-label">优化方法分块数</div>
            </div>
            <div class="stat-item">
                <div class="stat-value improvement">{chunk_reduction:+d}</div>
                <div class="stat-label">分块数减少</div>
            </div>
            <div class="stat-item">
                <div class="stat-value improvement">{chunk_reduction_percent:+.1f}%</div>
                <div class="stat-label">减少百分比</div>
            </div>
            <div class="stat-item">
                <div class="stat-value neutral">{original_avg_tokens}</div>
                <div class="stat-label">原方法平均tokens</div>
            </div>
            <div class="stat-item">
                <div class="stat-value improvement">{optimized_avg_tokens}</div>
                <div class="stat-label">优化方法平均tokens</div>
            </div>
        </div>
    </div>
    
    <div class="search-box">
        <input type="text" id="searchInput" placeholder="🔍 搜索内容..." />
    </div>
    
    <div class="controls">
        <button class="control-btn" onclick="expandAllChunks()">📖 展开全部</button>
        <button class="control-btn" onclick="collapseAllChunks()">📝 收起全部</button>
        <button class="control-btn" onclick="clearHighlights()">🧹 清除高亮</button>
        <button class="control-btn" onclick="jumpToNext()">⬇️ 下一个</button>
    </div>
    
    <div class="sync-indicator" id="syncIndicator">🔄 同步滚动</div>
    
    <div class="comparison-container">
        <div class="column">
            <div class="column-header original-method">
                <span>📊 原方法 (split_markdown_to_chunks)</span>
                <span class="method-badge">{len(original_chunks)} 分块</span>
            </div>
            <div class="chunks-container" id="original-chunks">
"""

    # 生成原方法的分块内容
    for i, chunk in enumerate(original_chunks):
        tokens = num_tokens_from_string(chunk)
        chars = len(chunk)
        total_lines = len(chunk.split('\n'))  # 重命名避免覆盖
        has_table = '<table>' in chunk or ('|' in chunk and '-' in chunk)
        table_indicator = '<span class="table-indicator">表格</span>' if has_table else ''
        
        # 不再限制内容长度，但提供展开/收起功能
        content_preview = chunk.replace('<', '&lt;').replace('>', '&gt;')
        
        # 清理内容：移除每行的前导和尾随空格，但保持行结构
        lines = content_preview.split('\n')
        cleaned_lines = []
        consecutive_empty_lines = 0
        
        for line in lines:
            if line.strip():
                # 有内容的行：强力空格清理
                cleaned_line = ' '.join(line.split())
                cleaned_lines.append(cleaned_line)
                consecutive_empty_lines = 0
            else:
                # 空行：限制连续空行数量
                consecutive_empty_lines += 1
                if consecutive_empty_lines <= 1:  # 最多保留1个连续空行
                    cleaned_lines.append('')
        
        # 移除开头和结尾的空行
        while cleaned_lines and not cleaned_lines[0]:
            cleaned_lines.pop(0)
        while cleaned_lines and not cleaned_lines[-1]:
            cleaned_lines.pop()
            
        content_preview = '\n'.join(cleaned_lines)
        
        needs_expand = len(chunk) > 800
        content_class = "collapsed" if needs_expand else "expanded"
        
        html_content += f"""
                <div class="chunk" data-chunk-id="{i}">
                    <div class="chunk-index">#{i+1}</div>
                    <div class="chunk-header">
                        <span class="chunk-title">分块 {i+1}{table_indicator}</span>
                        <div class="chunk-stats">
                            <span class="chunk-tokens">{tokens}T</span>
                            <span class="chunk-chars">{chars}C</span>
                        </div>
                    </div>
                    <div class="chunk-content {content_class}" data-chunk-index="{i}">
                        {content_preview}
                        {'<div class="content-truncated"></div>' if needs_expand else ''}
                        {'<button class="expand-btn" onclick="toggleExpand(this)">📖 展开完整内容</button>' if needs_expand else ''}
                    </div>
                    <div class="chunk-meta">
                        <span>字符: {chars:,}</span>
                        <span>行数: {total_lines}</span>
                        <span>Token密度: {tokens/chars*1000:.1f}T/KC</span>
                    </div>
                </div>
"""

    html_content += """
            </div>
        </div>
        
        <div class="column">
            <div class="column-header optimized-method">
                <span>🚀 优化方法 (split_markdown_to_chunks_optimized)</span>
                <span class="method-badge">""" + str(len(optimized_chunks)) + """ 分块</span>
            </div>
            <div class="chunks-container" id="optimized-chunks">
"""

    # 生成优化方法的分块内容
    for i, chunk in enumerate(optimized_chunks):
        tokens = num_tokens_from_string(chunk)
        chars = len(chunk)
        total_lines = len(chunk.split('\n'))  # 重命名避免覆盖
        has_table = '<table>' in chunk or ('|' in chunk and '-' in chunk)
        table_indicator = '<span class="table-indicator">表格</span>' if has_table else ''
        
        # 不再限制内容长度，但提供展开/收起功能
        content_preview = chunk.replace('<', '&lt;').replace('>', '&gt;')
        
        # 清理内容：移除每行的前导和尾随空格，但保持行结构
        lines = content_preview.split('\n')
        cleaned_lines = []
        consecutive_empty_lines = 0
        
        for line in lines:
            if line.strip():
                # 有内容的行：强力空格清理
                cleaned_line = ' '.join(line.split())
                cleaned_lines.append(cleaned_line)
                consecutive_empty_lines = 0
            else:
                # 空行：限制连续空行数量
                consecutive_empty_lines += 1
                if consecutive_empty_lines <= 1:  # 最多保留1个连续空行
                    cleaned_lines.append('')
        
        # 移除开头和结尾的空行
        while cleaned_lines and not cleaned_lines[0]:
            cleaned_lines.pop(0)
        while cleaned_lines and not cleaned_lines[-1]:
            cleaned_lines.pop()
            
        content_preview = '\n'.join(cleaned_lines)
        
        needs_expand = len(chunk) > 800
        content_class = "collapsed" if needs_expand else "expanded"
        
        html_content += f"""
                <div class="chunk" data-chunk-id="{i}">
                    <div class="chunk-index">#{i+1}</div>
                    <div class="chunk-header">
                        <span class="chunk-title">分块 {i+1}{table_indicator}</span>
                        <div class="chunk-stats">
                            <span class="chunk-tokens">{tokens}T</span>
                            <span class="chunk-chars">{chars}C</span>
                        </div>
                    </div>
                    <div class="chunk-content {content_class}" data-chunk-index="{i}">
                        {content_preview}
                        {'<div class="content-truncated"></div>' if needs_expand else ''}
                        {'<button class="expand-btn" onclick="toggleExpand(this)">📖 展开完整内容</button>' if needs_expand else ''}
                    </div>
                    <div class="chunk-meta">
                        <span>字符: {chars:,}</span>
                        <span>行数: {total_lines}</span>
                        <span>Token密度: {tokens/chars*1000:.1f}T/KC</span>
                    </div>
                </div>
"""

    html_content += f"""
            </div>
        </div>
    </div>
    
    <script>
        let currentSearchIndex = 0;
        let searchResults = [];
        
        document.addEventListener('DOMContentLoaded', function() {{
            const originalContainer = document.getElementById('original-chunks');
            const optimizedContainer = document.getElementById('optimized-chunks');
            const syncIndicator = document.getElementById('syncIndicator');
            const searchInput = document.getElementById('searchInput');
            
            if (!originalContainer || !optimizedContainer) {{
                console.error('无法找到滚动容器');
                return;
            }}
            
            let isScrolling = false;
            let syncTimeout;
            
            function showSyncIndicator() {{
                syncIndicator.style.display = 'block';
                clearTimeout(syncTimeout);
                syncTimeout = setTimeout(() => {{
                    syncIndicator.style.display = 'none';
                }}, 800);
            }}
            
            function syncScroll(source, target) {{
                if (!isScrolling && source.scrollHeight > source.clientHeight) {{
                    isScrolling = true;
                    const scrollRatio = source.scrollTop / (source.scrollHeight - source.clientHeight);
                    target.scrollTop = scrollRatio * (target.scrollHeight - target.clientHeight);
                    showSyncIndicator();
                    setTimeout(() => {{ isScrolling = false; }}, 100);
                }}
            }}
            
            // 滚动同步
            originalContainer.addEventListener('scroll', () => syncScroll(originalContainer, optimizedContainer));
            optimizedContainer.addEventListener('scroll', () => syncScroll(optimizedContainer, originalContainer));
            
            // 搜索功能
            searchInput.addEventListener('input', function() {{
                const searchTerm = this.value.toLowerCase();
                if (searchTerm.length > 0) {{
                    performSearch(searchTerm);
                }} else {{
                    clearHighlights();
                }}
            }});
            
            searchInput.addEventListener('keydown', function(e) {{
                if (e.key === 'Enter') {{
                    e.preventDefault();
                    jumpToNext();
                }}
            }});
            
            // 键盘导航
            document.addEventListener('keydown', function(e) {{
                if (e.key === 'ArrowDown') {{
                    originalContainer.scrollBy(0, 150);
                    e.preventDefault();
                }} else if (e.key === 'ArrowUp') {{
                    originalContainer.scrollBy(0, -150);
                    e.preventDefault();
                }} else if (e.key === 'PageDown') {{
                    originalContainer.scrollBy(0, originalContainer.clientHeight * 0.8);
                    e.preventDefault();
                }} else if (e.key === 'PageUp') {{
                    originalContainer.scrollBy(0, -originalContainer.clientHeight * 0.8);
                    e.preventDefault();
                }} else if (e.key === 'F3' || (e.ctrlKey && e.key === 'f')) {{
                    e.preventDefault();
                    searchInput.focus();
                }}
            }});
            
            // 点击分块高亮
            function highlightChunk(chunkElement) {{
                // 清除所有高亮
                document.querySelectorAll('.chunk').forEach(c => c.classList.remove('highlighted'));
                // 高亮当前分块
                chunkElement.classList.add('highlighted');
                
                // 如果是在原方法列，尝试高亮对应的优化方法分块
                const chunkId = chunkElement.dataset.chunkId;
                if (chunkId) {{
                    const correspondingChunk = document.querySelector(`#optimized-chunks .chunk[data-chunk-id="${{chunkId}}"]`);
                    if (correspondingChunk) {{
                        correspondingChunk.classList.add('highlighted');
                    }}
                }}
            }}
            
            // 为所有分块添加点击事件
            document.querySelectorAll('.chunk').forEach(chunk => {{
                chunk.addEventListener('click', function() {{
                    highlightChunk(this);
                }});
            }});
            
            // 统计信息
            console.log('🔍 分块对比分析:');
            console.log('原方法分块数:', originalContainer.children.length);
            console.log('优化方法分块数:', optimizedContainer.children.length);
            console.log('分块减少:', originalContainer.children.length - optimizedContainer.children.length);
            console.log('减少百分比:', {chunk_reduction_percent:.1f} + '%');
            
            // 键盘快捷键提示
            console.log('🎮 键盘快捷键:');
            console.log('↑/↓ 箭头键: 滚动浏览');
            console.log('PageUp/PageDown: 快速翻页');
            console.log('F3 或 Ctrl+F: 聚焦搜索框');
            console.log('Enter: 跳转到下一个搜索结果');
            console.log('点击分块: 高亮对比');
        }});
        
        // 展开/收起功能
        function toggleExpand(button) {{
            const content = button.parentElement;
            const truncated = content.querySelector('.content-truncated');
            
            if (content.classList.contains('collapsed')) {{
                content.classList.remove('collapsed');
                content.classList.add('expanded');
                if (truncated) truncated.style.display = 'none';
                button.textContent = '📝 收起内容';
            }} else {{
                content.classList.remove('expanded');
                content.classList.add('collapsed');
                if (truncated) truncated.style.display = 'block';
                button.textContent = '📖 展开完整内容';
            }}
        }}
        
        function expandAllChunks() {{
            document.querySelectorAll('.chunk-content.collapsed').forEach(content => {{
                const button = content.querySelector('.expand-btn');
                if (button) toggleExpand(button);
            }});
        }}
        
        function collapseAllChunks() {{
            document.querySelectorAll('.chunk-content.expanded').forEach(content => {{
                const button = content.querySelector('.expand-btn');
                if (button && content.textContent.length > 800) {{
                    toggleExpand(button);
                }}
            }});
        }}
        
        // 搜索功能
        function performSearch(searchTerm) {{
            clearHighlights();
            searchResults = [];
            currentSearchIndex = 0;
            
            document.querySelectorAll('.chunk-content').forEach((content, index) => {{
                const text = content.textContent;
                const regex = new RegExp(`(${{searchTerm.replace(/[.*+?^${{}}()|[\\]\\\\]/g, '\\\\$&')}})`, 'gi');
                
                if (regex.test(text)) {{
                    searchResults.push({{
                        element: content.closest('.chunk'),
                        container: content.closest('.chunks-container')
                    }});
                    
                    // 高亮搜索词
                    const highlightedText = text.replace(regex, '<span class="highlight">$1</span>');
                    const tempDiv = document.createElement('div');
                    tempDiv.innerHTML = highlightedText;
                    
                    // 保持原有的HTML结构
                    Array.from(content.childNodes).forEach(node => {{
                        if (node.nodeType === Node.TEXT_NODE) {{
                            const span = document.createElement('span');
                            span.innerHTML = node.textContent.replace(regex, '<span class="highlight">$1</span>');
                            content.replaceChild(span, node);
                        }}
                    }});
                }}
            }});
            
            if (searchResults.length > 0) {{
                jumpToResult(0);
                console.log(`找到 ${{searchResults.length}} 个搜索结果`);
            }}
        }}
        
        function clearHighlights() {{
            document.querySelectorAll('.highlight').forEach(el => {{
                el.outerHTML = el.innerHTML;
            }});
            searchResults = [];
            currentSearchIndex = 0;
        }}
        
        function jumpToNext() {{
            if (searchResults.length > 0) {{
                currentSearchIndex = (currentSearchIndex + 1) % searchResults.length;
                jumpToResult(currentSearchIndex);
            }}
        }}
        
        function jumpToResult(index) {{
            if (searchResults[index]) {{
                const result = searchResults[index];
                result.element.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                
                // 高亮该分块
                document.querySelectorAll('.chunk').forEach(c => c.classList.remove('highlighted'));
                result.element.classList.add('highlighted');
                
                console.log(`跳转到第 ${{index + 1}}/${{searchResults.length}} 个结果`);
            }}
        }}
    </script>
</body>
</html>
"""

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

def main():
    """主函数"""
    try:
        from services.knowledgebases.mineru_parse.utils import split_markdown_to_chunks, split_markdown_to_chunks_optimized, num_tokens_from_string
        
        print("🔍 生成左右对比HTML报告...")
        
        # 创建输出目录
        exports_dir = create_chunk_exports_dir()
        print(f"📁 输出目录: {exports_dir.absolute()}")
        
        # 读取测试文件
        test_file = Path("../output/0c344536404411f0ba3a66fc51ac58de.md")
        if not test_file.exists():
            print(f"✗ 测试文件不存在: {test_file}")
            return
            
        with open(test_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_tokens = num_tokens_from_string(content)
        print(f"📖 测试文件: {test_file.name}")
        print(f"📊 原文档token数: {original_tokens:,}")
        
        # 测试不同参数
        test_params = [256, 512, 1024]
        
        for chunk_tokens in test_params:
            print(f"\n🎯 处理参数: {chunk_tokens} tokens")
            
            # 生成分块
            print("  📊 执行原方法...")
            original_chunks = split_markdown_to_chunks(content, chunk_token_num=chunk_tokens)
            
            print("  🚀 执行优化方法...")
            optimized_chunks = split_markdown_to_chunks_optimized(content, chunk_token_num=chunk_tokens)
            
            # 生成HTML报告
            output_file = exports_dir / f"side_by_side_comparison_{chunk_tokens}tokens.html"
            print(f"  📝 生成HTML报告: {output_file.name}")
            
            generate_side_by_side_html(original_chunks, optimized_chunks, chunk_tokens, output_file)
            
            # 统计信息
            reduction = len(original_chunks) - len(optimized_chunks)
            reduction_percent = (reduction / len(original_chunks) * 100) if original_chunks else 0
            
            print(f"  📊 原方法: {len(original_chunks)} 个分块")
            print(f"  📊 优化方法: {len(optimized_chunks)} 个分块")
            print(f"  📊 分块减少: {reduction} 个 ({reduction_percent:+.1f}%)")
        
        print(f"\n✅ 所有左右对比报告已生成完成!")
        print(f"📁 查看报告: {exports_dir.absolute()}")
        print(f"🌐 在浏览器中打开HTML文件查看左右对比效果")
        
        # 列出生成的文件
        print(f"\n📄 生成的左右对比文件:")
        for html_file in sorted(exports_dir.glob("side_by_side_comparison_*.html")):
            print(f"  - {html_file.name}")
        
    except Exception as e:
        print(f"✗ 生成失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 