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
    
    def get_document_content(self, doc_id: str) -> str:
        """从数据库获取文档的原始内容"""
        if not self.conn:
            return ""
            
        cursor = self.conn.cursor()
        try:
            # 首先查看document表结构，尝试获取可能的内容字段
            cursor.execute("SHOW COLUMNS FROM document")
            columns = [col[0] for col in cursor.fetchall()]
            print(f"📋 document表字段: {columns}")
            
            # 检查可能包含原始内容的字段
            possible_content_fields = ['content', 'raw_content', 'original_content', 'text', 'markdown_content']
            content_field = None
            
            for field in possible_content_fields:
                if field in columns:
                    content_field = field
                    break
            
            if content_field:
                cursor.execute(f'''
                    SELECT {content_field}, name FROM document WHERE id = %s
                ''', (doc_id,))
                
                result = cursor.fetchone()
                if result and result[0]:
                    print(f"📄 从数据库{content_field}字段获取文档内容: {result[1]}")
                    return result[0]
                else:
                    print(f"⚠️  文档 {doc_id} 的{content_field}字段为空")
            else:
                print("⚠️  document表中未找到内容字段")
            
            # 如果document表没有内容，尝试从Elasticsearch获取所有分块内容并重组
            doc_info = self.get_document_info(doc_id)
            if not doc_info:
                print(f"❌ 找不到文档 {doc_id}")
                return ""
                
            index_name = doc_info['index_name']
            
            # 获取该文档的所有分块
            if self.es_client:
                try:
                    # 搜索该文档的所有分块
                    search_body = {
                        "query": {
                            "term": {"doc_id": doc_id}
                        },
                        "sort": [
                            {"position_int": {"order": "asc"}}  # 按位置排序
                        ],
                        "size": 10000  # 获取所有分块
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

    def preview_ast_chunking(self, markdown_text, child_chunk_size=256, parent_split_level=2, generate_html=False):
        """预览基于AST的父子分块效果"""
        try:
            # 导入AST分块函数
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
                print(f"📄 父分块 {i+1}: {parent.metadata.get('section_title', '(无标题)')}")
                print(f"   📏 内容长度: {len(parent.content)} 字符")
                print(f"   📍 行号范围: {parent.start_line}-{parent.end_line}")
                print(f"   🏷️  层级: H{parent.metadata.get('header_level', 'N/A')}")
                print(f"   📝 内容预览: {repr(parent.content[:100])}{'...' if len(parent.content) > 100 else ''}")
                print()
            
            # 显示子分块详情  
            print("👶 子分块详情:")
            print("-" * 60)
            for i, child in enumerate(child_chunks[:10]):  # 只显示前10个
                print(f"📄 子分块 {i+1}:")
                print(f"   📏 内容长度: {len(child.content)} 字符")
                print(f"   📍 行号范围: {child.start_line}-{child.end_line}")
                semantic = child.metadata
                print(f"   🧠 语义信息: 标题={semantic.get('contains_headers', False)}, 表格={semantic.get('contains_tables', False)}, 代码={semantic.get('contains_code', False)}")
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
            <title>🎯 AST父子分块预览 - 基于语义结构的智能分块</title>
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
                    max-width: 1600px;
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
                
                .stats-bar {{
                    background: #e3f2fd;
                    padding: 20px;
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                    gap: 20px;
                }}
                
                .stat-item {{
                    background: white;
                    padding: 20px;
                    border-radius: 8px;
                    text-align: center;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                }}
                
                .stat-number {{
                    font-size: 32px;
                    font-weight: bold;
                    color: #1976d2;
                    margin-bottom: 5px;
                }}
                
                .stat-label {{
                    color: #666;
                    font-size: 14px;
                }}
                
                .main-content {{
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 20px;
                    padding: 20px;
                }}
                
                .panel {{
                    background: #f8f9fa;
                    border-radius: 8px;
                    padding: 20px;
                    max-height: 80vh;
                    overflow-y: auto;
                }}
                
                .parent-panel {{
                    border-left: 4px solid #e74c3c;
                }}
                
                .child-panel {{
                    border-left: 4px solid #3498db;
                }}
                
                .panel-header {{
                    display: flex;
                    align-items: center;
                    margin-bottom: 20px;
                    padding-bottom: 10px;
                    border-bottom: 2px solid #ddd;
                }}
                
                .panel-icon {{
                    font-size: 24px;
                    margin-right: 10px;
                }}
                
                .parent-icon {{ color: #e74c3c; }}
                .child-icon {{ color: #3498db; }}
                
                .panel-title {{
                    font-size: 20px;
                    font-weight: bold;
                }}
                
                .chunk-item {{
                    background: white;
                    margin-bottom: 15px;
                    border-radius: 8px;
                    padding: 15px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    transition: transform 0.2s, box-shadow 0.2s;
                }}
                
                .chunk-item:hover {{
                    transform: translateY(-2px);
                    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                }}
                
                .chunk-header {{
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 10px;
                }}
                
                .chunk-id {{
                    font-family: 'Monaco', 'Consolas', monospace;
                    font-size: 12px;
                    color: #666;
                    background: #f0f0f0;
                    padding: 2px 6px;
                    border-radius: 4px;
                }}
                
                .chunk-meta {{
                    display: flex;
                    gap: 10px;
                    margin-bottom: 10px;
                    font-size: 12px;
                }}
                
                .meta-tag {{
                    background: #e9ecef;
                    padding: 2px 8px;
                    border-radius: 12px;
                    color: #495057;
                }}
                
                .chunk-content {{
                    background: #f8f9fa;
                    border: 1px solid #dee2e6;
                    border-radius: 6px;
                    padding: 12px;
                    font-family: 'Monaco', 'Consolas', monospace;
                    font-size: 13px;
                    line-height: 1.5;
                    max-height: 200px;
                    overflow-y: auto;
                    white-space: pre-wrap;
                    word-wrap: break-word;
                }}
                
                .relationships {{
                    grid-column: 1 / -1;
                    background: #fff3e0;
                    border-radius: 8px;
                    padding: 20px;
                    margin-top: 20px;
                }}
                
                .relationship-item {{
                    background: white;
                    padding: 15px;
                    margin-bottom: 10px;
                    border-radius: 8px;
                    border-left: 4px solid #ff9800;
                    display: grid;
                    grid-template-columns: 1fr auto 1fr;
                    gap: 15px;
                    align-items: center;
                }}
                
                .relation-arrow {{
                    font-size: 20px;
                    color: #ff9800;
                    text-align: center;
                }}
                
                .search-box {{
                    padding: 20px;
                    background: #f8f9fa;
                    border-bottom: 1px solid #dee2e6;
                }}
                
                .search-input {{
                    width: 100%;
                    padding: 12px 20px;
                    border: 1px solid #ddd;
                    border-radius: 25px;
                    font-size: 14px;
                    outline: none;
                }}
                
                .search-input:focus {{
                    border-color: #007bff;
                    box-shadow: 0 0 0 3px rgba(0,123,255,0.1);
                }}
                
                .highlight {{
                    background-color: yellow;
                    font-weight: bold;
                }}
                
                @media (max-width: 1200px) {{
                    .main-content {{
                        grid-template-columns: 1fr;
                    }}
                }}
                
                .original-text {{
                    grid-column: 1 / -1;
                    background: #f0f8ff;
                    border-radius: 8px;
                    padding: 20px;
                    margin-bottom: 20px;
                }}
                
                .original-text-header {{
                    display: flex;
                    align-items: center;
                    margin-bottom: 15px;
                    padding-bottom: 10px;
                    border-bottom: 2px solid #ddd;
                }}
                
                .original-text-content {{
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
                    
                    <div class="relationships">
                        <div class="panel-header">
                            <span class="panel-icon">🔗</span>
                            <span class="panel-title">父子关联关系 ({data['stats']['relationship_count']}个)</span>
                        </div>
                        {''.join(self._generate_relationship_html(rel) for rel in data['relationships'])}
                    </div>
                </div>
            </div>
            
            <script>
                // 搜索功能
                document.getElementById('searchInput').addEventListener('input', function(e) {{
                    const searchTerm = e.target.value.toLowerCase();
                    const chunkItems = document.querySelectorAll('.chunk-item');
                    
                    chunkItems.forEach(item => {{
                        const content = item.textContent.toLowerCase();
                        if (searchTerm === '' || content.includes(searchTerm)) {{
                            item.style.display = 'block';
                            if (searchTerm !== '') {{
                                highlightSearchTerm(item, searchTerm);
                            }} else {{
                                removeHighlight(item);
                            }}
                        }} else {{
                            item.style.display = 'none';
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
                
                console.log('🎉 AST父子分块预览页面加载完成');
                console.log('📊 统计信息:', {{
                    parent_chunks: {data['stats']['parent_count']},
                    child_chunks: {data['stats']['child_count']},
                    relationships: {data['stats']['relationship_count']},
                    original_length: {data['original_length']}
                }});
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

    def _generate_relationship_html(self, rel):
        """生成关联关系HTML"""
        return f"""
        <div class="relationship-item">
            <div>
                <strong>👶 子分块:</strong> {rel['child_chunk_id'][:20]}...<br>
                <small>📑 章节: {rel.get('section_title', 'N/A')}</small>
            </div>
            <div class="relation-arrow">→</div>
            <div>
                <strong>👨 父分块:</strong> {rel['parent_chunk_id'][:20]}...<br>
                <small>🧠 语义: {rel.get('semantic_info', {})}</small>
            </div>
        </div>
        """

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
    parser.add_argument('--ast-preview', action='store_true', help='预览基于AST的父子分块效果')
    parser.add_argument('--parent-level', type=int, default=2, help='AST预览模式下的父分块分割层级 (默认: 2)')
    parser.add_argument('--child-size', type=int, default=256, help='AST预览模式下的子分块大小 (默认: 256)')
    parser.add_argument('--markdown-file', type=str, help='用于AST预览的Markdown文件路径')
    parser.add_argument('--ast-html', action='store_true', help='AST预览模式下生成HTML可视化页面')
    
    args = parser.parse_args()
    
    viewer = ParentChildViewer()
    
    try:
        if args.ast_preview:
            # AST预览模式
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
            else:
                # 从数据库获取文档内容
                if not viewer.connect_db():
                    return 1
                
                # 获取真实文档内容
                markdown_text = viewer.get_document_content(args.doc_id)
                
                if not markdown_text:
                    print("❌ 无法获取文档内容，使用示例Markdown进行预览")
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
            
            # 执行AST预览
            viewer.preview_ast_chunking(
                markdown_text, 
                child_chunk_size=args.child_size,
                parent_split_level=args.parent_level,
                generate_html=args.ast_html
            )
            
        elif not viewer.connect_db():
            return 1
        elif args.html:
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
                print("🎯 想要预览AST分块？使用 --ast-preview 参数")
                print("🌐 想要AST分块HTML可视化？使用 --ast-preview --ast-html 参数")
        
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