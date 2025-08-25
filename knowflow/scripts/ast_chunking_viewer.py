#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AST父子分块预览工具
基于Abstract Syntax Tree的语义分块可视化工具
"""

import sys
import json
import argparse
import webbrowser
import tempfile
from typing import List, Dict

# 添加KnowFlow路径
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
knowflow_server_dir = os.path.join(current_dir, '..', 'server')
knowflow_server_dir = os.path.abspath(knowflow_server_dir)
sys.path.insert(0, knowflow_server_dir)

try:
    from database import get_db_connection, get_es_client
except ImportError as e:
    print(f"❌ 无法导入数据库模块: {e}")
    print(f"当前目录: {current_dir}")
    print(f"KnowFlow服务器目录: {knowflow_server_dir}")
    print("请确保在KnowFlow项目根目录下运行此脚本")
    sys.exit(1)


class ASTChunkingViewer:
    """AST父子分块预览工具"""
    
    def __init__(self):
        self.conn = None
        self.es_client = None
    
    def connect_db(self):
        """连接数据库"""
        try:
            self.conn = get_db_connection()
            self.es_client = get_es_client()
            print("✅ 数据库连接成功")
        except Exception as e:
            print(f"❌ 数据库连接失败: {e}")
            return False
        return True
    
    def get_document_info(self, doc_id: str) -> Dict:
        """获取文档基本信息"""
        if not self.conn:
            return {}
            
        cursor = self.conn.cursor()
        try:
            cursor.execute('''
                SELECT d.name, d.kb_id, k.created_by 
                FROM document d 
                JOIN knowledgebase k ON d.kb_id = k.id 
                WHERE d.id = %s
            ''', (doc_id,))
            
            result = cursor.fetchone()
            if not result:
                return {}
            
            doc_name, kb_id, tenant_id = result
            
            return {
                'doc_id': doc_id,
                'doc_name': doc_name,
                'kb_id': kb_id,
                'tenant_id': tenant_id,
                'index_name': f'ragflow_{tenant_id}'
            }
        except Exception as e:
            print(f"❌ 获取文档信息失败: {e}")
            return {}
        finally:
            cursor.close()
    
    def get_document_content(self, doc_id: str) -> str:
        """从数据库获取文档的原始内容"""
        if not self.conn:
            return ""
            
        cursor = self.conn.cursor()
        try:
            # 获取文档信息
            doc_info = self.get_document_info(doc_id)
            if not doc_info:
                print(f"❌ 找不到文档 {doc_id}")
                return ""
                
            index_name = doc_info['index_name']
            
            # 从Elasticsearch获取所有分块内容并重组
            if self.es_client:
                try:
                    search_body = {
                        "query": {
                            "term": {"doc_id": doc_id}
                        },
                        "sort": [
                            {"position_int": {"order": "asc"}}
                        ],
                        "size": 10000
                    }
                    
                    response = self.es_client.search(
                        index=index_name,
                        body=search_body
                    )
                    
                    chunks = []
                    for hit in response['hits']['hits']:
                        source = hit['_source']
                        content = source.get('content_with_weight', '')
                        chunks.append(content)
                    
                    if chunks:
                        combined_content = '\n\n'.join(chunks)
                        print(f"📄 从ES重组文档内容: {len(chunks)} 个分块，总长度 {len(combined_content)} 字符")
                        return combined_content
                    
                except Exception as e:
                    print(f"❌ 从ES获取分块失败: {e}")
            
            print(f"⚠️  无法获取文档 {doc_id} 的内容")
            return ""
            
        except Exception as e:
            print(f"❌ 获取文档内容失败: {e}")
            return ""
        finally:
            cursor.close()
    
    def preview_ast_chunking(self, markdown_text, child_chunk_size=256, parent_split_level=2, generate_html=False):
        """预览基于AST的父子分块效果"""
        try:
            from services.knowledgebases.mineru_parse.utils import split_markdown_to_chunks_ast_parent_child
            
            print("🎯 基于AST的父子分块预览")
            print("=" * 80)
            print(f"📝 文档长度: {len(markdown_text)} 字符")
            print(f"🔢 子分块大小: {child_chunk_size} tokens")
            print(f"📊 父分块层级: H{parent_split_level}")
            print()
            
            parent_config = {
                'parent_split_level': parent_split_level,
                'retrieval_mode': 'parent'
            }
            
            # 执行AST父子分块
            parent_chunks, child_chunks, relationships = split_markdown_to_chunks_ast_parent_child(
                txt=markdown_text,
                chunk_token_num=child_chunk_size,
                min_chunk_tokens=10,
                parent_config=parent_config,
                doc_id='preview_doc',
                kb_id='preview_kb'
            )
            
            print(f"📊 分块结果统计:")
            print(f"   👨 父分块数量: {len(parent_chunks)}")
            print(f"   👶 子分块数量: {len(child_chunks)}")
            print(f"   🔗 关联关系: {len(relationships)}")
            print()
            
            # 显示父分块详情
            print("👨 父分块详情:")
            print("-" * 60)
            for i, parent in enumerate(parent_chunks):
                section_title = parent.metadata.get('section_title', '(无标题)')
                header_level = parent.metadata.get('header_level', 'N/A')
                print(f"📄 父分块 {i+1}: {section_title}")
                print(f"   📏 内容长度: {len(parent.content)} 字符")
                print(f"   📍 行号范围: {parent.start_line}-{parent.end_line}")
                print(f"   🏷️  层级: H{header_level}")
                print(f"   📝 内容预览: {repr(parent.content[:100])}{'...' if len(parent.content) > 100 else ''}")
                print()
            
            # 显示子分块详情  
            print("👶 子分块详情:")
            print("-" * 60)
            for i, child in enumerate(child_chunks[:10]):  # 只显示前10个
                semantic = child.metadata
                semantic_tags = []
                if semantic.get('contains_headers', False):
                    semantic_tags.append('🎯 标题')
                if semantic.get('contains_tables', False):
                    semantic_tags.append('📊 表格')
                if semantic.get('contains_code', False):
                    semantic_tags.append('💻 代码')
                if semantic.get('contains_lists', False):
                    semantic_tags.append('📝 列表')
                
                semantic_display = ' | '.join(semantic_tags) if semantic_tags else '📄 普通文本'
                
                print(f"📄 子分块 {i+1}:")
                print(f"   📏 内容长度: {len(child.content)} 字符")
                print(f"   📍 行号范围: {child.start_line}-{child.end_line}")
                print(f"   🧠 语义信息: {semantic_display}")
                print(f"   📝 内容预览: {repr(child.content[:150])}{'...' if len(child.content) > 150 else ''}")
                print()
            
            if len(child_chunks) > 10:
                print(f"   ... 还有 {len(child_chunks) - 10} 个子分块未显示")
                print()
            
            # 显示关联关系示例
            print("🔗 关联关系示例:")
            print("-" * 60)
            for i, rel in enumerate(relationships[:5]):  # 显示前5个关联
                print(f"关联 {i+1}:")
                print(f"   👶 子分块: {rel['child_chunk_id'][:20]}...")
                print(f"   👨 父分块: {rel['parent_chunk_id'][:20]}...")
                print(f"   📑 章节: {rel.get('section_title', 'N/A')}")
                print(f"   🧠 语义信息: {rel.get('semantic_info', {})}")
                print()
            
            # 生成HTML可视化页面（如果请求）
            if generate_html:
                print("\n🌐 正在生成AST分块HTML可视化页面...")
                html_file = self._generate_ast_preview_html(parent_chunks, child_chunks, relationships, markdown_text)
                if html_file:
                    print(f"✅ HTML页面已生成: {html_file}")
                    
                    # 在默认浏览器中打开
                    try:
                        webbrowser.open(f'file://{html_file}', new=2)
                        print("🚀 HTML可视化页面已在浏览器中打开")
                    except Exception as e:
                        print(f"❌ 无法自动打开浏览器: {e}")
                        print(f"💡 请手动在浏览器中打开: file://{html_file}")
            
            return parent_chunks, child_chunks, relationships
            
        except ImportError as e:
            print(f"❌ 无法导入AST分块模块: {e}")
            print("请确保在KnowFlow项目环境中运行")
            return None, None, None
        except Exception as e:
            print(f"❌ AST预览失败: {e}")
            import traceback
            traceback.print_exc()
            return None, None, None

    def _generate_ast_preview_html(self, parent_chunks, child_chunks, relationships, original_text):
        """生成AST分块预览的HTML页面"""
        try:
            # 准备数据
            preview_data = {
                'original_text': original_text,
                'original_length': len(original_text),
                'parent_chunks': [
                    {
                        'id': p.id if hasattr(p, 'id') else f'parent_{i}',
                        'content': p.content,
                        'order': getattr(p, 'order', i),
                        'length': len(p.content),
                        'start_line': getattr(p, 'start_line', 0),
                        'end_line': getattr(p, 'end_line', 0),
                        'section_title': p.metadata.get('section_title', '无标题') if hasattr(p, 'metadata') else '无标题',
                        'header_level': p.metadata.get('header_level', 'N/A') if hasattr(p, 'metadata') else 'N/A'
                    }
                    for i, p in enumerate(parent_chunks)
                ],
                'child_chunks': [
                    {
                        'id': c.id if hasattr(c, 'id') else f'child_{i}',
                        'content': c.content,
                        'order': getattr(c, 'order', i),
                        'length': len(c.content),
                        'start_line': getattr(c, 'start_line', 0),
                        'end_line': getattr(c, 'end_line', 0),
                        'semantic': c.metadata if hasattr(c, 'metadata') else {}
                    }
                    for i, c in enumerate(child_chunks)
                ],
                'relationships': relationships,
                'stats': {
                    'parent_count': len(parent_chunks),
                    'child_count': len(child_chunks),
                    'relationship_count': len(relationships)
                }
            }
            
            html_content = self._generate_ast_html_template(preview_data)
            
            # 创建临时HTML文件
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
                f.write(html_content)
                return f.name
                
        except Exception as e:
            print(f"❌ 生成AST预览HTML失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _generate_ast_html_template(self, data):
        """生成AST预览HTML模板"""
        return f"""
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>🎯 AST父子分块预览</title>
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{ font-family: 'Microsoft YaHei', Arial, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; padding: 20px; }}
                .container {{ max-width: 1600px; margin: 0 auto; background: white; border-radius: 12px; box-shadow: 0 8px 32px rgba(0,0,0,0.1); overflow: hidden; }}
                .header {{ background: linear-gradient(90deg, #4facfe 0%, #00f2fe 100%); color: white; padding: 30px; text-align: center; }}
                .header h1 {{ font-size: 28px; margin-bottom: 10px; }}
                .stats-bar {{ background: #e3f2fd; padding: 20px; display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; }}
                .stat-item {{ background: white; padding: 20px; border-radius: 8px; text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
                .stat-number {{ font-size: 32px; font-weight: bold; color: #1976d2; margin-bottom: 5px; }}
                .stat-label {{ color: #666; font-size: 14px; }}
                .main-content {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; padding: 20px; }}
                .panel {{ background: #f8f9fa; border-radius: 8px; padding: 20px; max-height: 80vh; overflow-y: auto; }}
                .parent-panel {{ border-left: 4px solid #e74c3c; }}
                .child-panel {{ border-left: 4px solid #3498db; }}
                .panel-header {{ display: flex; align-items: center; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 2px solid #ddd; }}
                .panel-icon {{ font-size: 24px; margin-right: 10px; }}
                .parent-icon {{ color: #e74c3c; }}
                .child-icon {{ color: #3498db; }}
                .panel-title {{ font-size: 20px; font-weight: bold; }}
                .chunk-item {{ background: white; margin-bottom: 15px; border-radius: 8px; padding: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); transition: transform 0.2s, box-shadow 0.2s; }}
                .chunk-item:hover {{ transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.15); }}
                .chunk-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }}
                .chunk-id {{ font-family: 'Monaco', 'Consolas', monospace; font-size: 12px; color: #666; background: #f0f0f0; padding: 2px 6px; border-radius: 4px; }}
                .chunk-meta {{ display: flex; gap: 10px; margin-bottom: 10px; font-size: 12px; }}
                .meta-tag {{ background: #e9ecef; padding: 2px 8px; border-radius: 12px; color: #495057; }}
                .chunk-content {{ background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 6px; padding: 12px; font-family: 'Monaco', 'Consolas', monospace; font-size: 13px; line-height: 1.5; max-height: 200px; overflow-y: auto; white-space: pre-wrap; word-wrap: break-word; }}
                .original-text {{ grid-column: 1 / -1; background: #f0f8ff; border-radius: 8px; padding: 20px; margin-bottom: 20px; }}
                .original-text-header {{ display: flex; align-items: center; margin-bottom: 15px; padding-bottom: 10px; border-bottom: 2px solid #ddd; }}
                .original-text-content {{ background: white; border: 1px solid #dee2e6; border-radius: 6px; padding: 15px; font-family: 'Monaco', 'Consolas', monospace; font-size: 13px; line-height: 1.5; max-height: 300px; overflow-y: auto; white-space: pre-wrap; word-wrap: break-word; }}
                .search-box {{ padding: 20px; background: #f8f9fa; border-bottom: 1px solid #dee2e6; }}
                .search-input {{ width: 100%; padding: 12px 20px; border: 1px solid #ddd; border-radius: 25px; font-size: 14px; outline: none; }}
                .search-input:focus {{ border-color: #007bff; box-shadow: 0 0 0 3px rgba(0,123,255,0.1); }}
                .highlight {{ background-color: yellow; font-weight: bold; }}
                @media (max-width: 1200px) {{ .main-content {{ grid-template-columns: 1fr; }} }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎯 AST父子分块预览</h1>
                    <p>基于Abstract Syntax Tree的智能语义分块可视化</p>
                </div>
                
                <div class="stats-bar">
                    <div class="stat-item">
                        <div class="stat-number">{data['stats']['parent_count']}</div>
                        <div class="stat-label">父分块数量</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-number">{data['stats']['child_count']}</div>
                        <div class="stat-label">子分块数量</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-number">{data['stats']['relationship_count']}</div>
                        <div class="stat-label">关联关系</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-number">{data['original_length']}</div>
                        <div class="stat-label">原文字符数</div>
                    </div>
                </div>
                
                <div class="search-box">
                    <input type="text" class="search-input" placeholder="🔍 搜索分块内容..." id="searchInput">
                </div>
                
                <div class="main-content">
                    <div class="original-text">
                        <div class="original-text-header">
                            <span class="panel-icon">📄</span>
                            <span class="panel-title">原始文档</span>
                        </div>
                        <div class="original-text-content">{self._escape_html(data['original_text'])}</div>
                    </div>
                    
                    <div class="panel parent-panel">
                        <div class="panel-header">
                            <span class="panel-icon parent-icon">👨</span>
                            <span class="panel-title">父分块 ({data['stats']['parent_count']}个)</span>
                        </div>
                        {''.join(self._generate_parent_chunk_html(chunk) for chunk in data['parent_chunks'])}
                    </div>
                    
                    <div class="panel child-panel">
                        <div class="panel-header">
                            <span class="panel-icon child-icon">👶</span>
                            <span class="panel-title">子分块 ({data['stats']['child_count']}个)</span>
                        </div>
                        {''.join(self._generate_child_chunk_html(chunk) for chunk in data['child_chunks'])}
                    </div>
                </div>
            </div>
            
            <script>
                document.getElementById('searchInput').addEventListener('input', function(e) {{
                    const searchTerm = e.target.value.toLowerCase();
                    const chunkItems = document.querySelectorAll('.chunk-item');
                    
                    chunkItems.forEach(item => {{
                        const content = item.textContent.toLowerCase();
                        if (searchTerm === '' || content.includes(searchTerm)) {{
                            item.style.display = 'block';
                        }} else {{
                            item.style.display = 'none';
                        }}
                    }});
                }});
                
                console.log('🎉 AST父子分块预览页面加载完成');
            </script>
        </body>
        </html>
        """

    def _generate_parent_chunk_html(self, chunk):
        """生成父分块HTML"""
        return f"""
        <div class="chunk-item">
            <div class="chunk-header">
                <div class="chunk-id">👨 {chunk['id'][:12]}...</div>
                <div class="meta-tag">#{chunk['order']}</div>
            </div>
            <div class="chunk-meta">
                <span class="meta-tag">📑 {chunk['section_title']}</span>
                <span class="meta-tag">🏷️ H{chunk['header_level']}</span>
                <span class="meta-tag">📏 {chunk['length']} 字符</span>
                <span class="meta-tag">📍 {chunk['start_line']}-{chunk['end_line']}行</span>
            </div>
            <div class="chunk-content">{self._escape_html(chunk['content'])}</div>
        </div>
        """

    def _generate_child_chunk_html(self, chunk):
        """生成子分块HTML"""
        semantic = chunk['semantic']
        semantic_tags = []
        if semantic.get('contains_headers', False):
            semantic_tags.append('🎯 标题')
        if semantic.get('contains_tables', False):
            semantic_tags.append('📊 表格')
        if semantic.get('contains_code', False):
            semantic_tags.append('💻 代码')
        if semantic.get('contains_lists', False):
            semantic_tags.append('📝 列表')
        
        semantic_display = ' | '.join(semantic_tags) if semantic_tags else '📄 普通文本'
        
        return f"""
        <div class="chunk-item">
            <div class="chunk-header">
                <div class="chunk-id">👶 {chunk['id'][:12]}...</div>
                <div class="meta-tag">#{chunk['order']}</div>
            </div>
            <div class="chunk-meta">
                <span class="meta-tag">🧠 {semantic_display}</span>
                <span class="meta-tag">📏 {chunk['length']} 字符</span>
                <span class="meta-tag">📍 {chunk['start_line']}-{chunk['end_line']}行</span>
            </div>
            <div class="chunk-content">{self._escape_html(chunk['content'])}</div>
        </div>
        """

    def _escape_html(self, text: str) -> str:
        """转义HTML特殊字符"""
        if not text:
            return ""
        return (text.replace('&', '&amp;')
                   .replace('<', '&lt;')
                   .replace('>', '&gt;')
                   .replace('"', '&quot;')
                   .replace("'", '&#39;'))

    def close(self):
        """关闭连接"""
        if self.conn:
            self.conn.close()


def main():
    parser = argparse.ArgumentParser(description='AST父子分块预览工具')
    parser.add_argument('doc_id', help='文档ID（使用 "example" 运行内置示例）')
    parser.add_argument('--parent-level', type=int, default=2, 
                       help='父分块分割层级: 1=H1, 2=H2, 3=H3, 4=H4, 5=H5, 6=H6 (默认: 2)')
    parser.add_argument('--child-size', type=int, default=256, 
                       help='子分块大小（tokens）(默认: 256)')
    parser.add_argument('--html', action='store_true', 
                       help='生成HTML可视化页面')
    parser.add_argument('--markdown-file', type=str, 
                       help='指定Markdown文件路径（可选）')
    
    args = parser.parse_args()
    
    viewer = ASTChunkingViewer()
    
    try:
        markdown_text = None
        
        if args.markdown_file:
            # 从文件读取Markdown内容
            try:
                with open(args.markdown_file, 'r', encoding='utf-8') as f:
                    markdown_text = f.read()
                print(f"📁 从文件加载Markdown: {args.markdown_file}")
            except Exception as e:
                print(f"❌ 无法读取文件 {args.markdown_file}: {e}")
                return 1
        elif args.doc_id == "example":
            # 使用内置示例
            markdown_text = """# 人工智能概述

人工智能（Artificial Intelligence，AI）是计算机科学的一个分支，致力于创建能够执行通常需要人类智能的任务的智能机器。这个领域包括专家系统、自然语言处理、语音识别和机器视觉等多个方面。

## 机器学习基础

机器学习是人工智能的一个重要子集，它使计算机能够从数据中学习和改进，而无需被明确编程。机器学习算法通过分析大量数据来识别模式，并使用这些模式来对新数据进行预测或决策。

### 监督学习

监督学习是机器学习的一种方法，它使用标记的训练数据来学习从输入到输出的映射函数。在这种学习方式中，算法通过观察输入-输出对的例子来学习如何做出正确的预测。

### 无监督学习

无监督学习是另一种机器学习方法，它在没有标记数据的情况下发现数据中的隐藏模式和结构。这种方法主要用于数据挖掘、聚类分析和降维等任务。

## 深度学习

深度学习是机器学习的一个专门子集，它模拟人脑神经网络的工作方式。深度学习使用多层神经网络来学习数据的复杂模式，在图像识别、语音处理和自然语言理解等领域取得了突破性进展。

### 神经网络架构

神经网络由多个相互连接的节点（神经元）组成，这些节点组织成多个层。每个连接都有一个权重，通过训练过程不断调整这些权重以优化网络性能。

### 训练过程

深度学习模型的训练涉及大量的计算和数据处理。通过反向传播算法，网络可以学习如何调整权重以最小化预测误差。

## 应用领域

### 自然语言处理

- 机器翻译
- 情感分析
- 文本生成

### 计算机视觉

- 图像识别
- 目标检测
- 人脸识别

### 语音技术

- 语音识别
- 语音合成
- 语音助手

## 未来发展

人工智能技术正在快速发展，未来将在更多领域发挥重要作用，包括自动驾驶、医疗诊断、金融分析等。"""
            
            print("📝 使用内置示例Markdown内容")
        else:
            # 从数据库获取文档内容
            if not viewer.connect_db():
                return 1
            
            markdown_text = viewer.get_document_content(args.doc_id)
            
            if not markdown_text:
                print("❌ 无法获取文档内容")
                return 1
        
        # 执行AST预览
        viewer.preview_ast_chunking(
            markdown_text, 
            child_chunk_size=args.child_size,
            parent_split_level=args.parent_level,
            generate_html=args.html
        )
        
    except KeyboardInterrupt:
        print("\n\n👋 用户中断，正在退出...")
    except Exception as e:
        print(f"\n❌ 运行错误: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        viewer.close()
    
    return 0


if __name__ == '__main__':
    exit(main())