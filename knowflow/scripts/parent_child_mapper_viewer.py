#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
父子分块映射关系查看器
用于直观显示文档的父子分块映射关系和内容
"""

import sys
import json
import argparse
import webbrowser
import tempfile
from datetime import datetime
from typing import Dict, List, Tuple

# 添加KnowFlow路径
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
# 从 knowflow/scripts/ 目录回到 knowflow/server/ 目录
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


class ParentChildViewer:
    """父子分块映射关系查看器"""
    
    def __init__(self):
        self.conn = None
        self.es_client = None
        self.doc_info = {}
    
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
            # 获取文档信息
            cursor.execute('''
                SELECT d.name, d.kb_id, d.parser_config, k.created_by 
                FROM document d 
                JOIN knowledgebase k ON d.kb_id = k.id 
                WHERE d.id = %s
            ''', (doc_id,))
            
            result = cursor.fetchone()
            if not result:
                return {}
            
            doc_name, kb_id, parser_config, tenant_id = result
            
            # 解析配置
            chunking_config = {}
            if parser_config:
                try:
                    config = json.loads(parser_config) if isinstance(parser_config, str) else parser_config
                    chunking_config = config.get('chunking_config', {})
                except:
                    pass
            
            return {
                'doc_id': doc_id,
                'doc_name': doc_name,
                'kb_id': kb_id,
                'tenant_id': tenant_id,
                'chunking_config': chunking_config,
                'index_name': f'ragflow_{tenant_id}'
            }
        except Exception as e:
            print(f"❌ 获取文档信息失败: {e}")
            return {}
        finally:
            cursor.close()
    
    def get_parent_child_mappings(self, doc_id: str) -> List[Tuple]:
        """获取父子映射关系"""
        if not self.conn:
            return []
            
        cursor = self.conn.cursor()
        try:
            cursor.execute('''
                SELECT child_chunk_id, parent_chunk_id, relevance_score, create_time 
                FROM parent_child_mapping 
                WHERE doc_id = %s 
                ORDER BY create_time ASC
            ''', (doc_id,))
            
            return cursor.fetchall()
        except Exception as e:
            print(f"❌ 获取映射关系失败: {e}")
            return []
        finally:
            cursor.close()
    
    def get_chunk_content(self, chunk_id: str, index_name: str) -> Dict:
        """从ES获取分块内容"""
        if not self.es_client:
            return {}
            
        try:
            result = self.es_client.get(index=index_name, id=chunk_id)
            return result['_source']
        except Exception as e:
            # print(f"⚠️  获取分块 {chunk_id[:8]}... 内容失败: {e}")
            return {}
    
    def display_mapping_relationship(self, doc_id: str, max_pairs: int = 5, show_content: bool = True):
        """显示父子映射关系"""
        print("=" * 100)
        print(f"🔍 父子分块映射关系查看器")
        print("=" * 100)
        
        # 获取文档信息
        self.doc_info = self.get_document_info(doc_id)
        if not self.doc_info:
            print(f"❌ 找不到文档 {doc_id}")
            return
        
        print(f"📋 文档信息:")
        print(f"   🆔 文档ID: {self.doc_info['doc_id']}")
        print(f"   📄 文档名: {self.doc_info['doc_name']}")
        print(f"   🏢 知识库ID: {self.doc_info['kb_id']}")
        print(f"   👤 租户ID: {self.doc_info['tenant_id']}")
        
        # 显示分块策略
        chunking_config = self.doc_info['chunking_config']
        if chunking_config:
            strategy = chunking_config.get('strategy', 'unknown')
            print(f"   🎯 分块策略: {strategy}")
            if strategy == 'parent_child':
                parent_config = chunking_config.get('parent_config', {})
                print(f"   👨‍👦 父分块配置:")
                print(f"      📏 父分块大小: {parent_config.get('parent_chunk_size', 'unknown')} tokens")
                print(f"      🔄 重叠大小: {parent_config.get('parent_chunk_overlap', 'unknown')} tokens")
                print(f"      🎯 检索模式: {parent_config.get('retrieval_mode', 'unknown')}")
        
        # 获取映射关系
        mappings = self.get_parent_child_mappings(doc_id)
        if not mappings:
            print("❌ 没有找到父子映射关系")
            return
        
        print(f"\n📊 映射统计:")
        print(f"   📈 总映射数量: {len(mappings)}个")
        
        # 统计父分块数量
        unique_parents = set(mapping[1] for mapping in mappings)
        print(f"   👨 唯一父分块: {len(unique_parents)}个")
        print(f"   👶 子分块数量: {len(mappings)}个")
        
        print(f"\n🔗 映射关系详情 (显示前 {min(max_pairs, len(mappings))} 对):")
        print("-" * 100)
        
        # 显示映射关系
        index_name = self.doc_info['index_name']
        
        for i, (child_id, parent_id, score, create_time) in enumerate(mappings[:max_pairs]):
            print(f"\n📌 映射对 {i+1}:")
            print(f"   🔗 子分块ID: {child_id}")
            print(f"   🔗 父分块ID: {parent_id}")
            print(f"   📊 相关度: {score}")
            print(f"   ⏰ 创建时间: {create_time}")
            
            if show_content:
                # 获取子分块内容
                child_content = self.get_chunk_content(child_id, index_name)
                if child_content:
                    child_text = child_content.get('content_with_weight', '')
                    child_type = child_content.get('chunk_type', 'unknown')
                    child_order = child_content.get('chunk_order', 'unknown')
                    print(f"   👶 子分块内容 (类型: {child_type}, 顺序: {child_order}):")
                    print(f"      📝 长度: {len(child_text)} 字符")
                    print(f"      📄 内容: {repr(child_text[:150])}{'...' if len(child_text) > 150 else ''}")
                else:
                    print(f"   👶 子分块内容: ❌ 无法获取")
                
                # 获取父分块内容
                parent_content = self.get_chunk_content(parent_id, index_name)
                if parent_content:
                    parent_text = parent_content.get('content_with_weight', '')
                    parent_type = parent_content.get('chunk_type', 'unknown')
                    parent_order = parent_content.get('chunk_order', 'unknown')
                    print(f"   👨 父分块内容 (类型: {parent_type}, 顺序: {parent_order}):")
                    print(f"      📝 长度: {len(parent_text)} 字符")
                    print(f"      📄 内容: {repr(parent_text[:200])}{'...' if len(parent_text) > 200 else ''}")
                else:
                    print(f"   👨 父分块内容: ❌ 无法获取")
                
                print("-" * 80)
        
        if len(mappings) > max_pairs:
            print(f"\n... 还有 {len(mappings) - max_pairs} 个映射对未显示")
        
        print("\n" + "=" * 100)
    
    def display_statistics(self, doc_id: str):
        """显示统计信息"""
        print(f"📊 父子分块统计分析")
        print("-" * 60)
        
        # 获取映射关系
        mappings = self.get_parent_child_mappings(doc_id)
        if not mappings:
            print("❌ 没有映射关系数据")
            return
        
        # 统计每个父分块对应的子分块数量
        parent_child_count = {}
        for child_id, parent_id, score, create_time in mappings:
            if parent_id not in parent_child_count:
                parent_child_count[parent_id] = []
            parent_child_count[parent_id].append(child_id)
        
        print(f"📈 父子分块分布:")
        print(f"   👨 父分块总数: {len(parent_child_count)}")
        print(f"   👶 子分块总数: {len(mappings)}")
        print(f"   📊 平均每个父分块包含: {len(mappings) / len(parent_child_count):.2f} 个子分块")
        
        # 显示分布情况
        child_counts = [len(children) for children in parent_child_count.values()]
        child_counts.sort()
        
        print(f"\n🔢 子分块数量分布:")
        print(f"   📉 最少: {min(child_counts)} 个子分块")
        print(f"   📈 最多: {max(child_counts)} 个子分块")
        print(f"   📊 中位数: {child_counts[len(child_counts)//2]} 个子分块")
        
        # 显示前几个父分块的详细信息
        print(f"\n🔍 父分块详情 (前5个):")
        index_name = self.doc_info['index_name']
        
        for i, (parent_id, children) in enumerate(list(parent_child_count.items())[:5]):
            parent_content = self.get_chunk_content(parent_id, index_name)
            parent_text = parent_content.get('content_with_weight', '') if parent_content else ''
            
            print(f"   👨 父分块 {i+1}: {parent_id[:8]}...")
            print(f"      👶 包含子分块: {len(children)} 个")
            print(f"      📏 内容长度: {len(parent_text)} 字符")
            print(f"      📄 内容预览: {repr(parent_text[:100])}{'...' if len(parent_text) > 100 else ''}")
            print()
    
    def generate_html_visualization(self, doc_id: str, max_pairs: int = 20) -> str:
        """生成HTML可视化页面"""
        # 获取文档信息
        self.doc_info = self.get_document_info(doc_id)
        if not self.doc_info:
            return self._generate_error_html(f"找不到文档 {doc_id}")
        
        # 获取映射关系
        mappings = self.get_parent_child_mappings(doc_id)
        if not mappings:
            return self._generate_error_html("没有找到父子映射关系")
        
        # 获取分块内容
        index_name = self.doc_info['index_name']
        visualization_data = []
        
        for i, (child_id, parent_id, score, create_time) in enumerate(mappings[:max_pairs]):
            child_content = self.get_chunk_content(child_id, index_name)
            parent_content = self.get_chunk_content(parent_id, index_name)
            
            child_data = {
                'id': child_id,
                'type': child_content.get('chunk_type', 'unknown') if child_content else 'unknown',
                'order': child_content.get('chunk_order', 'unknown') if child_content else 'unknown',
                'content': child_content.get('content_with_weight', '无法获取内容') if child_content else '无法获取内容',
                'length': len(child_content.get('content_with_weight', '')) if child_content else 0
            }
            
            parent_data = {
                'id': parent_id,
                'type': parent_content.get('chunk_type', 'unknown') if parent_content else 'unknown',
                'order': parent_content.get('chunk_order', 'unknown') if parent_content else 'unknown',
                'content': parent_content.get('content_with_weight', '无法获取内容') if parent_content else '无法获取内容',
                'length': len(parent_content.get('content_with_weight', '')) if parent_content else 0
            }
            
            visualization_data.append({
                'index': i + 1,
                'child': child_data,
                'parent': parent_data,
                'score': score,
                'create_time': str(create_time)
            })
        
        return self._generate_html_template(visualization_data, len(mappings))
    
    def _generate_error_html(self, error_message: str) -> str:
        """生成错误页面HTML"""
        return f"""
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>父子分块映射关系查看器 - 错误</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; background-color: #f5f5f5; }}
                .error-container {{ background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .error-icon {{ color: #e74c3c; font-size: 48px; margin-bottom: 20px; }}
                .error-message {{ color: #666; font-size: 18px; }}
            </style>
        </head>
        <body>
            <div class="error-container">
                <div class="error-icon">❌</div>
                <h1>错误</h1>
                <p class="error-message">{error_message}</p>
            </div>
        </body>
        </html>
        """
    
    def _generate_html_template(self, data: List[Dict], total_count: int) -> str:
        """生成HTML模板"""
        doc_info = self.doc_info
        chunking_config = doc_info.get('chunking_config', {})
        
        return f"""
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>父子分块映射关系查看器</title>
            <style>
                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}
                
                body {{
                    font-family: 'Microsoft YaHei', Arial, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    padding: 20px;
                }}
                
                .container {{
                    max-width: 1400px;
                    margin: 0 auto;
                    background: white;
                    border-radius: 12px;
                    box-shadow: 0 8px 32px rgba(0,0,0,0.1);
                    overflow: hidden;
                }}
                
                .header {{
                    background: linear-gradient(90deg, #4facfe 0%, #00f2fe 100%);
                    color: white;
                    padding: 30px;
                    text-align: center;
                }}
                
                .header h1 {{
                    font-size: 28px;
                    margin-bottom: 10px;
                }}
                
                .doc-info {{
                    background: #f8f9fa;
                    padding: 25px;
                    border-bottom: 1px solid #e9ecef;
                }}
                
                .info-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                    gap: 15px;
                    margin-bottom: 15px;
                }}
                
                .info-item {{
                    background: white;
                    padding: 15px;
                    border-radius: 6px;
                    border-left: 4px solid #007bff;
                }}
                
                .info-label {{
                    font-weight: bold;
                    color: #495057;
                    margin-bottom: 5px;
                }}
                
                .info-value {{
                    color: #6c757d;
                    word-break: break-all;
                }}
                
                .stats-bar {{
                    background: #e3f2fd;
                    padding: 20px;
                    text-align: center;
                    border-bottom: 1px solid #e9ecef;
                }}
                
                .stats-item {{
                    display: inline-block;
                    margin: 0 20px;
                    padding: 10px 20px;
                    background: white;
                    border-radius: 20px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                
                .stats-number {{
                    font-size: 24px;
                    font-weight: bold;
                    color: #007bff;
                }}
                
                .stats-label {{
                    font-size: 14px;
                    color: #6c757d;
                    margin-top: 5px;
                }}
                
                .mappings-container {{
                    padding: 20px;
                }}
                
                .mapping-card {{
                    margin-bottom: 30px;
                    border: 1px solid #e9ecef;
                    border-radius: 12px;
                    overflow: hidden;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
                }}
                
                .mapping-header {{
                    background: linear-gradient(90deg, #ff9a9e 0%, #fecfef 100%);
                    padding: 15px 20px;
                    color: #333;
                    font-weight: bold;
                }}
                
                .mapping-content {{
                    display: flex;
                    min-height: 400px;
                }}
                
                .chunk-panel {{
                    flex: 1;
                    padding: 20px;
                    position: relative;
                }}
                
                .child-panel {{
                    background: #f0f8ff;
                    border-right: 2px solid #ddd;
                }}
                
                .parent-panel {{
                    background: #fff8f0;
                }}
                
                .chunk-header {{
                    display: flex;
                    align-items: center;
                    margin-bottom: 15px;
                    padding-bottom: 10px;
                    border-bottom: 2px solid #ddd;
                }}
                
                .chunk-icon {{
                    font-size: 24px;
                    margin-right: 10px;
                }}
                
                .child-icon {{ color: #3498db; }}
                .parent-icon {{ color: #e74c3c; }}
                
                .chunk-title {{
                    font-size: 18px;
                    font-weight: bold;
                }}
                
                .chunk-meta {{
                    display: flex;
                    gap: 15px;
                    margin-bottom: 15px;
                    font-size: 12px;
                    color: #6c757d;
                }}
                
                .meta-item {{
                    background: white;
                    padding: 5px 10px;
                    border-radius: 15px;
                    border: 1px solid #dee2e6;
                }}
                
                .chunk-content {{
                    background: white;
                    border: 1px solid #dee2e6;
                    border-radius: 6px;
                    padding: 15px;
                    font-family: 'Monaco', 'Consolas', monospace;
                    font-size: 13px;
                    line-height: 1.5;
                    max-height: 300px;
                    overflow-y: auto;
                    white-space: pre-wrap;
                    word-wrap: break-word;
                }}
                
                .connection-arrow {{
                    position: absolute;
                    top: 50%;
                    left: 50%;
                    transform: translateY(-50%);
                    z-index: 10;
                    background: white;
                    border: 2px solid #28a745;
                    border-radius: 50%;
                    width: 40px;
                    height: 40px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 18px;
                    color: #28a745;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                }}
                
                .search-box {{
                    margin: 20px 0;
                    padding: 0 20px;
                }}
                
                .search-input {{
                    width: 100%;
                    padding: 12px 20px;
                    border: 1px solid #ddd;
                    border-radius: 25px;
                    font-size: 14px;
                    outline: none;
                    transition: border-color 0.3s;
                }}
                
                .search-input:focus {{
                    border-color: #007bff;
                    box-shadow: 0 0 0 3px rgba(0,123,255,0.1);
                }}
                
                .highlight {{
                    background-color: yellow;
                    font-weight: bold;
                }}
                
                .pagination {{
                    text-align: center;
                    padding: 20px;
                    color: #6c757d;
                    font-size: 14px;
                }}
                
                @media (max-width: 768px) {{
                    .mapping-content {{
                        flex-direction: column;
                    }}
                    
                    .child-panel {{
                        border-right: none;
                        border-bottom: 2px solid #ddd;
                    }}
                    
                    .connection-arrow {{
                        top: auto;
                        bottom: -20px;
                        transform: translateX(-50%) rotate(90deg);
                    }}
                    
                    .info-grid {{
                        grid-template-columns: 1fr;
                    }}
                    
                    .stats-item {{
                        display: block;
                        margin: 10px 0;
                    }}
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🔍 父子分块映射关系查看器</h1>
                    <p>直观展示文档的父子分块映射关系和内容</p>
                </div>
                
                <div class="doc-info">
                    <div class="info-grid">
                        <div class="info-item">
                            <div class="info-label">🆔 文档ID</div>
                            <div class="info-value">{doc_info['doc_id']}</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">📄 文档名称</div>
                            <div class="info-value">{doc_info['doc_name']}</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">🏢 知识库ID</div>
                            <div class="info-value">{doc_info['kb_id']}</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">👤 租户ID</div>
                            <div class="info-value">{doc_info['tenant_id']}</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">🎯 分块策略</div>
                            <div class="info-value">{chunking_config.get('strategy', 'unknown')}</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">⚙️ 配置参数</div>
                            <div class="info-value">
                                父分块: {chunking_config.get('parent_config', {}).get('parent_chunk_size', 'unknown')} tokens<br>
                                重叠: {chunking_config.get('parent_config', {}).get('parent_chunk_overlap', 'unknown')} tokens<br>
                                检索模式: {chunking_config.get('parent_config', {}).get('retrieval_mode', 'unknown')}
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="stats-bar">
                    <div class="stats-item">
                        <div class="stats-number">{total_count}</div>
                        <div class="stats-label">总映射数量</div>
                    </div>
                    <div class="stats-item">
                        <div class="stats-number">{len(set(item['parent']['id'] for item in data))}</div>
                        <div class="stats-label">唯一父分块</div>
                    </div>
                    <div class="stats-item">
                        <div class="stats-number">{len(data)}</div>
                        <div class="stats-label">显示的映射对</div>
                    </div>
                </div>
                
                <div class="search-box">
                    <input type="text" class="search-input" placeholder="🔍 搜索分块内容..." id="searchInput">
                </div>
                
                <div class="mappings-container" id="mappingsContainer">
                    {''.join(self._generate_mapping_card_html(item) for item in data)}
                </div>
                
                {f'<div class="pagination">显示前 {len(data)} 个映射对，总计 {total_count} 个映射关系</div>' if len(data) < total_count else ''}
            </div>
            
            <script>
                // 搜索功能
                document.getElementById('searchInput').addEventListener('input', function(e) {{
                    const searchTerm = e.target.value.toLowerCase();
                    const mappingCards = document.querySelectorAll('.mapping-card');
                    
                    mappingCards.forEach(card => {{
                        const content = card.textContent.toLowerCase();
                        if (searchTerm === '' || content.includes(searchTerm)) {{
                            card.style.display = 'block';
                            // 高亮搜索词
                            if (searchTerm !== '') {{
                                highlightSearchTerm(card, searchTerm);
                            }} else {{
                                removeHighlight(card);
                            }}
                        }} else {{
                            card.style.display = 'none';
                        }}
                    }});
                }});
                
                function highlightSearchTerm(element, searchTerm) {{
                    const walker = document.createTreeWalker(
                        element,
                        NodeFilter.SHOW_TEXT,
                        null,
                        false
                    );
                    
                    const textNodes = [];
                    let node;
                    while (node = walker.nextNode()) {{
                        textNodes.push(node);
                    }}
                    
                    textNodes.forEach(textNode => {{
                        const content = textNode.textContent;
                        const regex = new RegExp(`(${{searchTerm}})`, 'gi');
                        if (regex.test(content)) {{
                            const highlightedContent = content.replace(regex, '<span class="highlight">$1</span>');
                            const span = document.createElement('span');
                            span.innerHTML = highlightedContent;
                            textNode.parentNode.replaceChild(span, textNode);
                        }}
                    }});
                }}
                
                function removeHighlight(element) {{
                    const highlights = element.querySelectorAll('.highlight');
                    highlights.forEach(highlight => {{
                        const parent = highlight.parentNode;
                        parent.replaceChild(document.createTextNode(highlight.textContent), highlight);
                        parent.normalize();
                    }});
                }}
                
                // 页面加载完成提示
                console.log('父子分块映射关系查看器已加载完成 🎉');
                console.log('显示了 {len(data)} 个映射对，总计 {total_count} 个映射关系');
            </script>
        </body>
        </html>
        """
    
    def _generate_mapping_card_html(self, item: Dict) -> str:
        """生成单个映射卡片的HTML"""
        return f"""
        <div class="mapping-card">
            <div class="mapping-header">
                📌 映射对 {item['index']} - 相关度: {item['score']} - 创建时间: {item['create_time']}
            </div>
            <div class="mapping-content">
                <div class="chunk-panel child-panel">
                    <div class="chunk-header">
                        <span class="chunk-icon child-icon">👶</span>
                        <span class="chunk-title">子分块</span>
                    </div>
                    <div class="chunk-meta">
                        <span class="meta-item">ID: {item['child']['id'][:8]}...</span>
                        <span class="meta-item">类型: {item['child']['type']}</span>
                        <span class="meta-item">顺序: {item['child']['order']}</span>
                        <span class="meta-item">长度: {item['child']['length']} 字符</span>
                    </div>
                    <div class="chunk-content">{self._escape_html(item['child']['content'])}</div>
                </div>
                <div class="connection-arrow">→</div>
                <div class="chunk-panel parent-panel">
                    <div class="chunk-header">
                        <span class="chunk-icon parent-icon">👨</span>
                        <span class="chunk-title">父分块</span>
                    </div>
                    <div class="chunk-meta">
                        <span class="meta-item">ID: {item['parent']['id'][:8]}...</span>
                        <span class="meta-item">类型: {item['parent']['type']}</span>
                        <span class="meta-item">顺序: {item['parent']['order']}</span>
                        <span class="meta-item">长度: {item['parent']['length']} 字符</span>
                    </div>
                    <div class="chunk-content">{self._escape_html(item['parent']['content'])}</div>
                </div>
            </div>
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
    
    def open_html_viewer(self, doc_id: str, max_pairs: int = 20):
        """打开HTML可视化查看器"""
        print("🌐 正在生成HTML可视化页面...")
        
        html_content = self.generate_html_visualization(doc_id, max_pairs)
        
        # 创建临时HTML文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
            f.write(html_content)
            html_file_path = f.name
        
        print(f"📁 HTML文件已生成: {html_file_path}")
        print("🚀 正在打开浏览器...")
        
        # 在默认浏览器中打开
        try:
            webbrowser.open(f'file://{html_file_path}', new=2)  # new=2 表示在新标签页打开
            print("✅ HTML可视化页面已在浏览器中打开")
            print(f"💡 如果浏览器没有自动打开，请手动访问: file://{html_file_path}")
        except Exception as e:
            print(f"❌ 无法自动打开浏览器: {e}")
            print(f"💡 请手动在浏览器中打开: file://{html_file_path}")
        
        return html_file_path

    def close(self):
        """关闭连接"""
        if self.conn:
            self.conn.close()


def main():
    parser = argparse.ArgumentParser(description='父子分块映射关系查看器')
    parser.add_argument('doc_id', help='文档ID')
    parser.add_argument('--max-pairs', '-n', type=int, default=5, help='显示的最大映射对数量 (默认: 5)')
    parser.add_argument('--no-content', action='store_true', help='不显示分块内容，仅显示ID和关系')
    parser.add_argument('--stats-only', '-s', action='store_true', help='仅显示统计信息')
    parser.add_argument('--html', action='store_true', help='打开HTML可视化页面')
    parser.add_argument('--html-pairs', type=int, default=20, help='HTML页面显示的最大映射对数量 (默认: 20)')
    
    args = parser.parse_args()
    
    viewer = ParentChildViewer()
    
    try:
        if not viewer.connect_db():
            return 1
        
        if args.html:
            # HTML可视化模式
            html_file = viewer.open_html_viewer(args.doc_id, args.html_pairs)
            print(f"\n🎉 HTML可视化页面已生成并打开")
            print(f"📁 文件位置: {html_file}")
            print("\n💡 使用提示:")
            print("  - 🔍 页面顶部有搜索框，可以搜索分块内容")
            print("  - 📱 支持移动端响应式布局")
            print("  - 🎨 每个映射对都有清晰的可视化展示")
        elif args.stats_only:
            # 统计信息模式
            viewer.doc_info = viewer.get_document_info(args.doc_id)
            if viewer.doc_info:
                viewer.display_statistics(args.doc_id)
        else:
            # 命令行显示模式
            viewer.display_mapping_relationship(
                args.doc_id, 
                max_pairs=args.max_pairs,
                show_content=not args.no_content
            )
            
            if not args.no_content:
                print("\n" + "💡 更多选项:")
                print("🔍 想看统计信息？使用 --stats-only 参数")
                print("🔍 想看更多映射对？使用 --max-pairs N 参数")
                print("🔍 不想看内容？使用 --no-content 参数")
                print("🌐 想要可视化页面？使用 --html 参数")
        
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