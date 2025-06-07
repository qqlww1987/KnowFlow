#!/usr/bin/env python3
"""
Export markdown chunks to readable formats (HTML, Markdown, JSON)
"""

import os
import sys
import json
import html
from pathlib import Path
from datetime import datetime

# Add the parent directory and services directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
services_dir = os.path.join(parent_dir, 'services')
sys.path.insert(0, parent_dir)
sys.path.insert(0, services_dir)

try:
    from services.knowledgebases.markdown_semantic_chunker import SemanticMarkdownChunker
    from services.knowledgebases.mineru_parse.utils import num_tokens_from_string
    print("✓ Successfully imported modules")
except ImportError as e:
    print(f"✗ Failed to import: {e}")
    sys.exit(1)


class ChunkExporter:
    def __init__(self, chunker, source_file=None):
        self.chunker = chunker
        self.source_file = source_file
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
    def analyze_content(self, content):
        """Analyze content and generate chunks with metadata"""
        print("📝 正在分析内容...")
        
        # Get original stats
        original_tokens = num_tokens_from_string(content)
        original_chars = len(content)
        original_lines = content.count('\n') + 1
        
        # Generate chunks
        chunks = self.chunker.chunk_text(content)
        
        # Analyze chunks
        chunk_tokens = [chunk[1].get('tokens', 0) for chunk in chunks]
        total_chunk_tokens = sum(chunk_tokens)
        
        analysis = {
            'original': {
                'chars': original_chars,
                'lines': original_lines,
                'tokens': original_tokens
            },
            'chunks': {
                'count': len(chunks),
                'total_tokens': total_chunk_tokens,
                'avg_tokens': total_chunk_tokens / len(chunks) if chunks else 0,
                'min_tokens': min(chunk_tokens) if chunk_tokens else 0,
                'max_tokens': max(chunk_tokens) if chunk_tokens else 0,
                'median_tokens': sorted(chunk_tokens)[len(chunk_tokens)//2] if chunk_tokens else 0
            },
            'efficiency': {
                'token_ratio': total_chunk_tokens / original_tokens if original_tokens > 0 else 0,
                'overlap_tokens': total_chunk_tokens - original_tokens
            }
        }
        
        print(f"✓ 分析完成: {len(chunks)} 个分块")
        return chunks, analysis
    
    def export_to_html(self, content, output_file="chunks_output.html"):
        """Export chunks to HTML format"""
        chunks, analysis = self.analyze_content(content)
        
        html_content = self._generate_html(chunks, analysis)
        
        output_path = Path(output_file)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"✓ HTML 输出已保存到: {output_path.absolute()}")
        return output_path
    
    def export_to_markdown(self, content, output_file="chunks_output.md"):
        """Export chunks to Markdown format"""
        chunks, analysis = self.analyze_content(content)
        
        md_content = self._generate_markdown(chunks, analysis)
        
        output_path = Path(output_file)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        print(f"✓ Markdown 输出已保存到: {output_path.absolute()}")
        return output_path
    
    def export_to_json(self, content, output_file="chunks_output.json"):
        """Export chunks to JSON format"""
        chunks, analysis = self.analyze_content(content)
        
        json_data = {
            'metadata': {
                'source_file': str(self.source_file) if self.source_file else None,
                'timestamp': self.timestamp,
                'chunker_config': {
                    'target_tokens': self.chunker.chunk_token_num_target,
                    'max_tokens': self.chunker.chunk_token_num_max,
                    'overlap_tokens': self.chunker.overlap_token_num,
                    'split_headings': self.chunker.heading_levels_to_split_before
                }
            },
            'analysis': analysis,
            'chunks': [
                {
                    'id': i + 1,
                    'content': chunk_content,
                    'metadata': chunk_metadata,
                    'tokens': chunk_metadata.get('tokens', 0),
                    'elements': chunk_metadata.get('source_elements_count', 0),
                    'has_table': '<table>' in chunk_content,
                    'has_code': '```' in chunk_content or '<pre>' in chunk_content,
                    'oversized': chunk_metadata.get('oversized_element', False)
                }
                for i, (chunk_content, chunk_metadata) in enumerate(chunks)
            ]
        }
        
        output_path = Path(output_file)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        
        print(f"✓ JSON 输出已保存到: {output_path.absolute()}")
        return output_path
    
    def _generate_html(self, chunks, analysis):
        """Generate HTML content"""
        html_template = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Markdown 分块结果 - {self.timestamp}</title>
    <style>
        body {{ 
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6; 
            max-width: 1200px; 
            margin: 0 auto; 
            padding: 20px; 
            background: #f5f7fa;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }}
        .stat-card {{
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            border-left: 4px solid #667eea;
        }}
        .chunk {{
            background: white;
            margin: 15px 0;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .chunk-header {{
            background: #f8f9fa;
            padding: 12px 20px;
            border-bottom: 1px solid #e9ecef;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .chunk-id {{
            font-weight: bold;
            color: #495057;
            font-size: 1.1em;
        }}
        .chunk-meta {{
            display: flex;
            gap: 15px;
            font-size: 0.9em;
            color: #6c757d;
        }}
        .chunk-content {{
            padding: 20px;
            border-left: 4px solid #e9ecef;
        }}
        .chunk-table {{ border-left-color: #28a745 !important; }}
        .chunk-code {{ border-left-color: #fd7e14 !important; }}
        .chunk-oversized {{ border-left-color: #dc3545 !important; }}
        .tag {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.8em;
            font-weight: 500;
        }}
        .tag-table {{ background: #d4edda; color: #155724; }}
        .tag-code {{ background: #fff3cd; color: #856404; }}
        .tag-oversized {{ background: #f8d7da; color: #721c24; }}
        pre {{ background: #f8f9fa; padding: 10px; border-radius: 4px; overflow-x: auto; }}
        table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
        th, td {{ border: 1px solid #dee2e6; padding: 8px 12px; text-align: left; }}
        th {{ background: #e9ecef; font-weight: 600; }}
        .toc {{ 
            background: white; 
            padding: 20px; 
            border-radius: 8px; 
            margin: 20px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .toc ul {{ list-style: none; padding-left: 0; }}
        .toc li {{ margin: 5px 0; }}
        .toc a {{ text-decoration: none; color: #667eea; }}
        .toc a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📄 Markdown 分块分析结果</h1>
        <p>生成时间: {datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")}</p>
        {f'<p>源文件: {self.source_file}</p>' if self.source_file else ''}
    </div>
    
    <div class="stats-grid">
        <div class="stat-card">
            <h3>📊 原文统计</h3>
            <p><strong>字符数:</strong> {analysis['original']['chars']:,}</p>
            <p><strong>行数:</strong> {analysis['original']['lines']:,}</p>
            <p><strong>Token数:</strong> {analysis['original']['tokens']:,}</p>
        </div>
        <div class="stat-card">
            <h3>🔧 分块统计</h3>
            <p><strong>分块数:</strong> {analysis['chunks']['count']}</p>
            <p><strong>总Token数:</strong> {analysis['chunks']['total_tokens']:,}</p>
            <p><strong>平均大小:</strong> {analysis['chunks']['avg_tokens']:.1f} tokens</p>
        </div>
        <div class="stat-card">
            <h3>📈 大小分布</h3>
            <p><strong>最小:</strong> {analysis['chunks']['min_tokens']} tokens</p>
            <p><strong>中位数:</strong> {analysis['chunks']['median_tokens']} tokens</p>
            <p><strong>最大:</strong> {analysis['chunks']['max_tokens']} tokens</p>
        </div>
        <div class="stat-card">
            <h3>⚡ 效率分析</h3>
            <p><strong>Token比率:</strong> {analysis['efficiency']['token_ratio']:.2%}</p>
            <p><strong>重叠Token:</strong> {analysis['efficiency']['overlap_tokens']:,}</p>
        </div>
    </div>
    
    <div class="toc">
        <h3>📑 分块目录</h3>
        <ul>
            {self._generate_toc(chunks)}
        </ul>
    </div>
    
    <div class="chunks-container">
        {self._generate_html_chunks(chunks)}
    </div>
    
    <script>
        // Add smooth scrolling
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {{
            anchor.addEventListener('click', function (e) {{
                e.preventDefault();
                document.querySelector(this.getAttribute('href')).scrollIntoView({{
                    behavior: 'smooth'
                }});
            }});
        }});
    </script>
</body>
</html>
        """
        return html_template
    
    def _generate_toc(self, chunks):
        """Generate table of contents"""
        toc_items = []
        for i, (content, metadata) in enumerate(chunks, 1):
            # Extract first line as title
            first_line = content.split('\n')[0].strip()
            if len(first_line) > 60:
                first_line = first_line[:60] + "..."
            
            tokens = metadata.get('tokens', 0)
            tags = []
            if '<table>' in content:
                tags.append('<span class="tag tag-table">表格</span>')
            if '```' in content:
                tags.append('<span class="tag tag-code">代码</span>')
            if metadata.get('oversized_element'):
                tags.append('<span class="tag tag-oversized">超大</span>')
            
            tag_html = ' '.join(tags)
            toc_items.append(f'<li><a href="#chunk-{i}">#{i} {html.escape(first_line)} ({tokens} tokens)</a> {tag_html}</li>')
        
        return '\n'.join(toc_items)
    
    def _generate_html_chunks(self, chunks):
        """Generate HTML for all chunks"""
        chunk_htmls = []
        
        for i, (content, metadata) in enumerate(chunks, 1):
            tokens = metadata.get('tokens', 0)
            elements = metadata.get('source_elements_count', 0)
            
            # Determine chunk type and styling
            chunk_classes = ['chunk']
            tags = []
            
            if '<table>' in content:
                chunk_classes.append('chunk-table')
                tags.append('<span class="tag tag-table">📊 表格</span>')
            
            if '```' in content or '<pre>' in content:
                chunk_classes.append('chunk-code')
                tags.append('<span class="tag tag-code">💻 代码</span>')
            
            if metadata.get('oversized_element'):
                chunk_classes.append('chunk-oversized')
                tags.append('<span class="tag tag-oversized">⚠️ 超大</span>')
            
            tags_html = ' '.join(tags)
            
            # Escape content for HTML but preserve existing HTML (like tables)
            if '<table>' in content:
                # For content with tables, preserve the HTML structure
                display_content = content
            else:
                # For regular content, escape HTML
                display_content = html.escape(content)
            
            chunk_html = f'''
            <div id="chunk-{i}" class="{' '.join(chunk_classes)}">
                <div class="chunk-header">
                    <div class="chunk-id">分块 #{i} {tags_html}</div>
                    <div class="chunk-meta">
                        <span>🎯 {tokens} tokens</span>
                        <span>📝 {elements} 元素</span>
                    </div>
                </div>
                <div class="chunk-content">
                    <pre style="white-space: pre-wrap; font-family: inherit;">{display_content}</pre>
                </div>
            </div>
            '''
            chunk_htmls.append(chunk_html)
        
        return '\n'.join(chunk_htmls)
    
    def _generate_markdown(self, chunks, analysis):
        """Generate Markdown content"""
        md_content = f"""# 📄 Markdown 分块分析结果

**生成时间:** {datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")}
{f"**源文件:** {self.source_file}" if self.source_file else ""}

## 📊 统计信息

### 原文统计
- **字符数:** {analysis['original']['chars']:,}
- **行数:** {analysis['original']['lines']:,}
- **Token数:** {analysis['original']['tokens']:,}

### 分块统计
- **分块数:** {analysis['chunks']['count']}
- **总Token数:** {analysis['chunks']['total_tokens']:,}
- **平均大小:** {analysis['chunks']['avg_tokens']:.1f} tokens
- **最小:** {analysis['chunks']['min_tokens']} tokens
- **中位数:** {analysis['chunks']['median_tokens']} tokens
- **最大:** {analysis['chunks']['max_tokens']} tokens

### 效率分析
- **Token比率:** {analysis['efficiency']['token_ratio']:.2%}
- **重叠Token数:** {analysis['efficiency']['overlap_tokens']:,}

## 📑 分块列表

"""
        
        for i, (content, metadata) in enumerate(chunks, 1):
            tokens = metadata.get('tokens', 0)
            elements = metadata.get('source_elements_count', 0)
            
            # Add tags
            tags = []
            if '<table>' in content:
                tags.append("📊表格")
            if '```' in content:
                tags.append("💻代码")
            if metadata.get('oversized_element'):
                tags.append("⚠️超大")
            
            tag_text = f" `{' '.join(tags)}`" if tags else ""
            
            md_content += f"""
### 分块 #{i}{tag_text}

**Token数:** {tokens} | **元素数:** {elements}

```
{content}
```

---

"""
        
        return md_content


def main():
    """Main function to export chunks"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Export markdown chunks to readable formats")
    parser.add_argument("--input", "-i", default="../output/0c344536404411f0ba3a66fc51ac58de.md", 
                       help="Input markdown file")
    parser.add_argument("--format", "-f", choices=["html", "markdown", "json", "all"], 
                       default="all", help="Output format")
    parser.add_argument("--target", "-t", type=int, default=512, 
                       help="Target tokens per chunk")
    parser.add_argument("--max", "-m", type=int, default=1024, 
                       help="Maximum tokens per chunk")
    parser.add_argument("--overlap", "-o", type=int, default=100, 
                       help="Overlap tokens between chunks")
    parser.add_argument("--output-dir", "-d", default="chunk_exports", 
                       help="Output directory")
    
    args = parser.parse_args()
    
    # Check input file
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"✗ 输入文件不存在: {input_path}")
        return
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Read input content
    with open(input_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print(f"📖 读取文件: {input_path}")
    print(f"📁 输出目录: {output_dir.absolute()}")
    
    # Create chunker
    chunker = SemanticMarkdownChunker(
        num_tokens_from_string_func=num_tokens_from_string,
        chunk_token_num_target=args.target,
        chunk_token_num_max=args.max,
        overlap_token_num=args.overlap,
        heading_levels_to_split_before=[1, 2]
    )
    
    # Create exporter
    exporter = ChunkExporter(chunker, input_path)
    
    # Export in requested formats
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"chunks_{input_path.stem}_{timestamp}"
    
    if args.format in ["html", "all"]:
        html_file = output_dir / f"{base_name}.html"
        exporter.export_to_html(content, html_file)
    
    if args.format in ["markdown", "all"]:
        md_file = output_dir / f"{base_name}.md"
        exporter.export_to_markdown(content, md_file)
    
    if args.format in ["json", "all"]:
        json_file = output_dir / f"{base_name}.json"
        exporter.export_to_json(content, json_file)
    
    print("\n🎉 导出完成！")
    print(f"📂 查看结果: {output_dir.absolute()}")


if __name__ == "__main__":
    main() 