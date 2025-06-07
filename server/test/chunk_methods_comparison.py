#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Markdown 分块方法对比脚本
对比 split_markdown_to_chunks、split_markdown_to_chunks_smart、split_markdown_to_chunks_advanced 三个方法
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path
import html
import traceback

# 添加必要的路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'services', 'knowledgebases', 'mineru_parse'))

# 导入分块方法
try:
    from utils import (
        split_markdown_to_chunks,
        split_markdown_to_chunks_smart, 
        split_markdown_to_chunks_advanced,
        num_tokens_from_string
    )
except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保 utils.py 文件存在且包含所需的方法")
    sys.exit(1)


class ChunkMethodComparator:
    """分块方法对比器"""
    
    def __init__(self, source_file_path):
        self.source_file_path = source_file_path
        self.source_content = ""
        self.results = {}
        
    def load_source_content(self):
        """加载源文件内容"""
        try:
            with open(self.source_file_path, 'r', encoding='utf-8') as f:
                self.source_content = f.read()
            print(f"✓ 已加载源文件: {self.source_file_path}")
            print(f"  文件大小: {len(self.source_content):,} 字符")
            print(f"  预估Token数: {num_tokens_from_string(self.source_content):,}")
        except Exception as e:
            print(f"✗ 加载源文件失败: {e}")
            raise
    
    def run_comparison(self, chunk_token_num=512, min_chunk_tokens=100):
        """运行三个方法的对比"""
        if not self.source_content:
            self.load_source_content()
        
        methods = [
            {
                'name': 'split_markdown_to_chunks',
                'display_name': '基础分块方法',
                'color': '#FF6B6B',  # 红色
                'func': lambda txt: split_markdown_to_chunks(txt, chunk_token_num),
                'description': '基于简单规则的分块，处理表格并合并文本段落'
            },
            {
                'name': 'split_markdown_to_chunks_smart', 
                'display_name': '智能AST分块方法',
                'color': '#4ECDC4',  # 青色
                'func': lambda txt: split_markdown_to_chunks_smart(txt, chunk_token_num, min_chunk_tokens),
                'description': '基于 markdown-it-py AST 的智能分块，维护语义完整性'
            },
            {
                'name': 'split_markdown_to_chunks_advanced',
                'display_name': '高级增强分块方法', 
                'color': '#45B7D1',  # 蓝色
                'func': lambda txt: split_markdown_to_chunks_advanced(txt, chunk_token_num, min_chunk_tokens, 
                                                                   overlap_ratio=0.1, include_metadata=False),
                'description': '包含重叠分块、上下文增强和元数据丰富化的高级方法'
            }
        ]
        
        print(f"\n🔍 开始对比分块方法...")
        print(f"参数: chunk_token_num={chunk_token_num}, min_chunk_tokens={min_chunk_tokens}")
        
        for method in methods:
            print(f"\n📊 运行 {method['display_name']}...")
            try:
                start_time = datetime.now()
                chunks = method['func'](self.source_content)
                end_time = datetime.now()
                
                # 计算统计信息
                chunk_lengths = [len(chunk) for chunk in chunks]
                chunk_tokens = [num_tokens_from_string(chunk) for chunk in chunks]
                
                stats = {
                    'chunk_count': len(chunks),
                    'total_chars': sum(chunk_lengths),
                    'total_tokens': sum(chunk_tokens),
                    'avg_chars': sum(chunk_lengths) / len(chunks) if chunks else 0,
                    'avg_tokens': sum(chunk_tokens) / len(chunks) if chunks else 0,
                    'min_tokens': min(chunk_tokens) if chunk_tokens else 0,
                    'max_tokens': max(chunk_tokens) if chunk_tokens else 0,
                    'processing_time': (end_time - start_time).total_seconds()
                }
                
                method['chunks'] = chunks
                method['stats'] = stats
                
                print(f"  ✓ 完成: {stats['chunk_count']} 个分块")
                print(f"  ⏱️ 耗时: {stats['processing_time']:.3f}s")
                print(f"  📝 平均Token数: {stats['avg_tokens']:.1f}")
                
            except Exception as e:
                print(f"  ✗ 运行失败: {e}")
                traceback.print_exc()
                method['chunks'] = []
                method['stats'] = {'error': str(e)}
        
        self.results = {
            'methods': methods,
            'source_stats': {
                'file_path': self.source_file_path,
                'total_chars': len(self.source_content),
                'total_tokens': num_tokens_from_string(self.source_content)
            },
            'parameters': {
                'chunk_token_num': chunk_token_num,
                'min_chunk_tokens': min_chunk_tokens
            },
            'timestamp': datetime.now().isoformat()
        }
        
        return self.results
    
    def generate_html_report(self, output_dir='chunk_exports'):
        """生成HTML对比报告"""
        if not self.results:
            raise ValueError("请先运行对比分析")
        
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"chunk_methods_comparison_{timestamp}.html"
        
        html_content = self._generate_html_content()
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"\n✓ HTML报告已保存: {output_file.absolute()}")
        return output_file
    
    def _generate_html_content(self):
        """生成HTML内容"""
        methods = self.results['methods']
        source_stats = self.results['source_stats']
        
        # 生成统计对比表
        stats_table = self._generate_stats_table(methods)
        
        # 生成分块对比
        chunks_comparison = self._generate_chunks_comparison(methods)
        
        html_template = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Markdown 分块方法对比报告</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f8f9fa;
        }}
        
        .header {{
            text-align: center;
            margin-bottom: 30px;
            padding: 30px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }}
        
        .header h1 {{
            margin: 0 0 10px 0;
            font-size: 2.5em;
        }}
        
        .header p {{
            margin: 5px 0;
            opacity: 0.9;
        }}
        
        .stats-section {{
            background: white;
            padding: 25px;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }}
        
        .stats-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }}
        
        .stats-table th, .stats-table td {{
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }}
        
        .stats-table th {{
            background-color: #f8f9fa;
            font-weight: 600;
            color: #495057;
        }}
        
        .method-header {{
            font-weight: 600;
            padding: 8px 12px;
            border-radius: 5px;
            color: white;
            margin-bottom: 5px;
        }}
        
        .chunks-section {{
            background: white;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }}
        
        .chunk-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }}
        
        .method-column {{
            border: 2px solid;
            border-radius: 10px;
            overflow: hidden;
        }}
        
        .method-column-header {{
            color: white;
            padding: 15px;
            font-weight: 600;
            text-align: center;
        }}
        
        .chunks-container {{
            max-height: 800px;
            overflow-y: auto;
            background: #f8f9fa;
        }}
        
        .chunk-item {{
            margin: 15px;
            padding: 15px;
            background: white;
            border-radius: 8px;
            border-left: 4px solid;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        
        .chunk-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
            font-size: 0.9em;
            color: #666;
        }}
        
        .chunk-content {{
            font-size: 0.85em;
            line-height: 1.5;
            max-height: 150px;
            overflow-y: auto;
            white-space: pre-wrap;
            background: #f8f9fa;
            padding: 10px;
            border-radius: 5px;
            border: 1px solid #e9ecef;
        }}
        
        .token-badge {{
            background: #e9ecef;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.8em;
            font-weight: 500;
        }}
        
        .comparison-nav {{
            position: sticky;
            top: 0;
            background: white;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            z-index: 100;
        }}
        
        .nav-buttons {{
            display: flex;
            gap: 10px;
            justify-content: center;
            flex-wrap: wrap;
        }}
        
        .nav-button {{
            padding: 8px 16px;
            border: none;
            border-radius: 20px;
            cursor: pointer;
            font-weight: 500;
            transition: all 0.3s ease;
            color: white;
        }}
        
        .nav-button:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
        }}
        
        .error-message {{
            color: #dc3545;
            background: #f8d7da;
            padding: 15px;
            border-radius: 5px;
            margin: 10px 0;
        }}
        
        @media (max-width: 768px) {{
            .chunk-grid {{
                grid-template-columns: 1fr;
            }}
            
            .nav-buttons {{
                flex-direction: column;
            }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 Markdown 分块方法对比报告</h1>
        <p>生成时间: {datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")}</p>
        <p>源文件: {source_stats['file_path']}</p>
        <p>源文件统计: {source_stats['total_chars']:,} 字符, {source_stats['total_tokens']:,} tokens</p>
    </div>
    
    <div class="stats-section">
        <h2>📈 统计对比</h2>
        {stats_table}
    </div>
    
    <div class="chunks-section">
        <h2>🔍 分块内容对比</h2>
        <div class="comparison-nav">
            <div class="nav-buttons">
                <button class="nav-button" style="background-color: {methods[0]['color']}" onclick="scrollToMethod(0)">
                    {methods[0]['display_name']}
                </button>
                <button class="nav-button" style="background-color: {methods[1]['color']}" onclick="scrollToMethod(1)">
                    {methods[1]['display_name']}
                </button>
                <button class="nav-button" style="background-color: {methods[2]['color']}" onclick="scrollToMethod(2)">
                    {methods[2]['display_name']}
                </button>
            </div>
        </div>
        {chunks_comparison}
    </div>
    
    <script>
        function scrollToMethod(index) {{
            const methodColumn = document.querySelectorAll('.method-column')[index];
            if (methodColumn) {{
                methodColumn.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
            }}
        }}
        
        // 同步滚动功能
        const containers = document.querySelectorAll('.chunks-container');
        containers.forEach((container, index) => {{
            container.addEventListener('scroll', () => {{
                containers.forEach((otherContainer, otherIndex) => {{
                    if (index !== otherIndex) {{
                        otherContainer.scrollTop = container.scrollTop;
                    }}
                }});
            }});
        }});
    </script>
</body>
</html>
        """
        
        return html_template
    
    def _generate_stats_table(self, methods):
        """生成统计对比表"""
        table_rows = []
        
        for method in methods:
            if 'error' in method['stats']:
                error_cell = f'<div class="error-message">错误: {method["stats"]["error"]}</div>'
                table_rows.append(f"""
                <tr>
                    <td>
                        <div class="method-header" style="background-color: {method['color']}">
                            {method['display_name']}
                        </div>
                        <small>{method['description']}</small>
                    </td>
                    <td colspan="6">{error_cell}</td>
                </tr>
                """)
            else:
                stats = method['stats']
                table_rows.append(f"""
                <tr>
                    <td>
                        <div class="method-header" style="background-color: {method['color']}">
                            {method['display_name']}
                        </div>
                        <small>{method['description']}</small>
                    </td>
                    <td>{stats['chunk_count']}</td>
                    <td>{stats['total_tokens']:,}</td>
                    <td>{stats['avg_tokens']:.1f}</td>
                    <td>{stats['min_tokens']}</td>
                    <td>{stats['max_tokens']}</td>
                    <td>{stats['processing_time']:.3f}s</td>
                </tr>
                """)
        
        return f"""
        <table class="stats-table">
            <thead>
                <tr>
                    <th>方法</th>
                    <th>分块数</th>
                    <th>总Token数</th>
                    <th>平均Token数</th>
                    <th>最小Token数</th>
                    <th>最大Token数</th>
                    <th>处理时间</th>
                </tr>
            </thead>
            <tbody>
                {''.join(table_rows)}
            </tbody>
        </table>
        """
    
    def _generate_chunks_comparison(self, methods):
        """生成分块对比内容"""
        columns = []
        
        for method in methods:
            if 'error' in method['stats']:
                column_content = f'<div class="error-message">方法执行出错: {method["stats"]["error"]}</div>'
            else:
                chunks_html = []
                for i, chunk in enumerate(method['chunks'], 1):
                    token_count = num_tokens_from_string(chunk)
                    preview = html.escape(chunk[:200] + "..." if len(chunk) > 200 else chunk)
                    
                    chunks_html.append(f"""
                    <div class="chunk-item" style="border-left-color: {method['color']}">
                        <div class="chunk-header">
                            <span>分块 #{i}</span>
                            <span class="token-badge">{token_count} tokens</span>
                        </div>
                        <div class="chunk-content">{preview}</div>
                    </div>
                    """)
                
                column_content = f'<div class="chunks-container">{"".join(chunks_html)}</div>'
            
            columns.append(f"""
            <div class="method-column" style="border-color: {method['color']}">
                <div class="method-column-header" style="background-color: {method['color']}">
                    {method['display_name']} ({method['stats'].get('chunk_count', 0)} 个分块)
                </div>
                {column_content}
            </div>
            """)
        
        return f'<div class="chunk-grid">{"".join(columns)}</div>'
    
    def generate_json_report(self, output_dir='chunk_exports'):
        """生成JSON格式的详细报告"""
        if not self.results:
            raise ValueError("请先运行对比分析")
        
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"chunk_methods_comparison_{timestamp}.json"
        
        # 准备JSON数据（移除不可序列化的函数）
        json_data = {
            'source_stats': self.results['source_stats'],
            'parameters': self.results['parameters'],
            'timestamp': self.results['timestamp'],
            'methods': []
        }
        
        for method in self.results['methods']:
            method_data = {
                'name': method['name'],
                'display_name': method['display_name'],
                'description': method['description'],
                'color': method['color'],
                'stats': method['stats'],
                'chunks': method.get('chunks', [])
            }
            json_data['methods'].append(method_data)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        
        print(f"✓ JSON报告已保存: {output_file.absolute()}")
        return output_file


def main():
    """主函数"""
    # 配置参数
    source_file = "../output/0c344536404411f0ba3a66fc51ac58de.md"
    chunk_token_num = 512
    min_chunk_tokens = 100
    
    print("🚀 启动 Markdown 分块方法对比...")
    print(f"📁 源文件: {source_file}")
    
    # 检查源文件是否存在
    if not os.path.exists(source_file):
        print(f"✗ 源文件不存在: {source_file}")
        return
    
    try:
        # 创建对比器
        comparator = ChunkMethodComparator(source_file)
        
        # 运行对比
        results = comparator.run_comparison(chunk_token_num, min_chunk_tokens)
        
        # 生成报告
        html_file = comparator.generate_html_report()
        json_file = comparator.generate_json_report()
        
        print(f"\n🎉 对比完成!")
        print(f"📊 HTML报告: {html_file}")
        print(f"📄 JSON数据: {json_file}")
        
    except Exception as e:
        print(f"✗ 对比过程中出现错误: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main() 