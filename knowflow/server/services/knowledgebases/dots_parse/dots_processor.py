#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DOTS OCR 结果处理器

将DOTS OCR的JSON结果转换为RAGFlow兼容的格式，支持:
- 布局元素提取和分类
- Markdown格式转换
- 分块生成和存储
"""

import json
import logging
from typing import Dict, List, Any, Optional, Callable
from pathlib import Path

logger = logging.getLogger(__name__)

class DOTSLayoutElement:
    """DOTS布局元素类"""
    
    def __init__(self, element_data: Dict[str, Any]):
        """初始化布局元素
        
        Args:
            element_data: DOTS返回的单个布局元素数据
        """
        self.bbox = element_data.get('bbox', [0, 0, 0, 0])
        self.category = element_data.get('category', 'Text')
        self.text = element_data.get('text', '')
        self.confidence = element_data.get('confidence', 1.0)
        
        # 计算元素面积和位置信息
        if len(self.bbox) == 4:
            self.x1, self.y1, self.x2, self.y2 = self.bbox
            self.width = self.x2 - self.x1
            self.height = self.y2 - self.y1
            self.area = self.width * self.height
            self.center_x = (self.x1 + self.x2) / 2
            self.center_y = (self.y1 + self.y2) / 2
        else:
            self.width = self.height = self.area = 0
            self.center_x = self.center_y = 0
    
    def to_markdown(self) -> str:
        """将元素转换为Markdown格式
        
        Returns:
            str: Markdown格式的文本
        """
        if not self.text or self.text.strip() == '':
            return ''
        
        text = self.text.strip()
        
        # 根据类别添加Markdown标记
        if self.category == 'Title':
            return f"# {text}\n\n"
        elif self.category == 'Section-header':
            return f"## {text}\n\n"
        elif self.category == 'List-item':
            return f"- {text}\n"
        elif self.category == 'Formula':
            # LaTeX公式已经是正确格式
            return f"$${text}$$\n\n"
        elif self.category == 'Table':
            # HTML表格保持原格式
            return f"{text}\n\n"
        elif self.category == 'Caption':
            return f"*{text}*\n\n"
        elif self.category == 'Footnote':
            return f"^{text}^\n\n"
        elif self.category in ['Page-header', 'Page-footer']:
            # 页眉页脚用小字体
            return f"<small>{text}</small>\n\n"
        else:
            # 默认文本处理
            return f"{text}\n\n"
    
    def __repr__(self):
        return f"DOTSLayoutElement(category={self.category}, bbox={self.bbox}, text='{self.text[:50]}...')"

class DOTSProcessor:
    """DOTS OCR结果处理器"""
    
    def __init__(self):
        """初始化处理器"""
        self.elements = []
        self.pages_data = []
    
    def process_page_result(self, page_result: Dict[str, Any]) -> List[DOTSLayoutElement]:
        """处理单页的DOTS解析结果
        
        Args:
            page_result: DOTS适配器返回的页面解析结果
            
        Returns:
            list: DOTSLayoutElement对象列表
        """
        elements = []
        
        if not page_result.get('success', False):
            logger.warning(f"页面解析失败: {page_result.get('error', 'Unknown error')}")
            return elements
        
        layout_elements = page_result.get('layout_elements', [])
        
        for element_data in layout_elements:
            try:
                element = DOTSLayoutElement(element_data)
                elements.append(element)
            except Exception as e:
                logger.warning(f"处理布局元素失败: {e}, 元素数据: {element_data}")
        
        logger.info(f"成功处理 {len(elements)} 个布局元素")
        return elements
    
    def process_document_results(self, document_results: List[Dict[str, Any]]) -> List[DOTSLayoutElement]:
        """处理整个文档的DOTS解析结果
        
        Args:
            document_results: 所有页面的解析结果列表
            
        Returns:
            list: 所有页面的DOTSLayoutElement对象列表
        """
        all_elements = []
        
        for i, page_result in enumerate(document_results):
            logger.info(f"处理第 {i+1}/{len(document_results)} 页结果")
            
            page_elements = self.process_page_result(page_result)
            
            # 为每个元素添加页面信息
            for element in page_elements:
                element.page_number = page_result.get('page_number', i + 1)
                all_elements.append(element)
        
        self.elements = all_elements
        self.pages_data = document_results
        
        logger.info(f"文档处理完成，共 {len(all_elements)} 个元素，{len(document_results)} 页")
        return all_elements
    
    def to_markdown(self) -> str:
        """将所有元素转换为Markdown格式的文档
        
        Returns:
            str: 完整的Markdown文档
        """
        if not self.elements:
            return ""
        
        # 按页面和位置排序元素
        sorted_elements = sorted(self.elements, key=lambda e: (e.page_number, e.center_y, e.center_x))
        
        markdown_lines = []
        current_page = 0
        
        for element in sorted_elements:
            # 添加页面分隔符
            if element.page_number != current_page:
                if current_page > 0:
                    markdown_lines.append(f"\n---\n<!-- Page {element.page_number} -->\n")
                current_page = element.page_number
            
            # 添加元素内容
            element_md = element.to_markdown()
            if element_md:
                markdown_lines.append(element_md)
        
        return ''.join(markdown_lines)
    
    def generate_chunks(self, chunk_size: int = 512, overlap: int = 50) -> List[Dict[str, Any]]:
        """生成用于RAGFlow的文本分块
        
        Args:
            chunk_size: 分块大小（字符数）
            overlap: 重叠大小（字符数）
            
        Returns:
            list: 分块数据列表
        """
        if not self.elements:
            return []
        
        # 按页面和类别组织元素
        page_sections = {}
        for element in self.elements:
            page_num = element.page_number
            if page_num not in page_sections:
                page_sections[page_num] = []
            page_sections[page_num].append(element)
        
        chunks = []
        chunk_id = 0
        
        for page_num in sorted(page_sections.keys()):
            elements = page_sections[page_num]
            
            # 按位置排序元素
            elements.sort(key=lambda e: (e.center_y, e.center_x))
            
            # 生成页面级别的分块
            page_text = ""
            for element in elements:
                if element.text and element.text.strip():
                    page_text += element.to_markdown()
            
            # 如果页面内容太长，进行分块
            if len(page_text) > chunk_size:
                # 简单的滑动窗口分块
                start = 0
                while start < len(page_text):
                    end = min(start + chunk_size, len(page_text))
                    chunk_text = page_text[start:end]
                    
                    if chunk_text.strip():
                        chunks.append({
                            'id': chunk_id,
                            'content': chunk_text,
                            'page_number': page_num,
                            'start_pos': start,
                            'end_pos': end,
                            'element_count': len([e for e in elements if e.text.strip()])
                        })
                        chunk_id += 1
                    
                    # 移动窗口，考虑重叠
                    start = end - overlap if end < len(page_text) else end
            else:
                # 页面内容较短，作为单个分块
                if page_text.strip():
                    chunks.append({
                        'id': chunk_id,
                        'content': page_text,
                        'page_number': page_num,
                        'start_pos': 0,
                        'end_pos': len(page_text),
                        'element_count': len([e for e in elements if e.text.strip()])
                    })
                    chunk_id += 1
        
        logger.info(f"生成 {len(chunks)} 个文本分块")
        return chunks
    
    def save_debug_info(self, output_dir: str):
        """保存调试信息到文件
        
        Args:
            output_dir: 输出目录路径
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 保存Markdown文档
        markdown_content = self.to_markdown()
        with open(output_path / 'dots_output.md', 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        # 保存原始JSON数据
        with open(output_path / 'dots_raw_data.json', 'w', encoding='utf-8') as f:
            json.dump(self.pages_data, f, ensure_ascii=False, indent=2)
        
        # 保存元素统计信息
        stats = {
            'total_elements': len(self.elements),
            'pages_count': len(set(e.page_number for e in self.elements)),
            'categories': {},
            'elements_summary': []
        }
        
        for element in self.elements:
            # 统计类别
            category = element.category
            if category not in stats['categories']:
                stats['categories'][category] = 0
            stats['categories'][category] += 1
            
            # 元素摘要
            stats['elements_summary'].append({
                'page': element.page_number,
                'category': element.category,
                'bbox': element.bbox,
                'text_preview': element.text[:100] if element.text else ''
            })
        
        with open(output_path / 'dots_stats.json', 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        
        logger.info(f"调试信息已保存到: {output_path}")

def process_dots_result(document_results: List[Dict[str, Any]], 
                       debug_output_dir: Optional[str] = None) -> Dict[str, Any]:
    """处理DOTS文档解析结果的便捷函数
    
    Args:
        document_results: DOTS适配器返回的文档解析结果
        debug_output_dir: 调试信息输出目录，可选
        
    Returns:
        dict: 包含处理结果的字典
    """
    processor = DOTSProcessor()
    
    # 处理解析结果
    elements = processor.process_document_results(document_results)
    
    # 生成Markdown和分块
    markdown_content = processor.to_markdown()
    chunks = processor.generate_chunks()
    
    # 保存调试信息（如果指定了输出目录）
    if debug_output_dir:
        processor.save_debug_info(debug_output_dir)
    
    return {
        'success': True,
        'elements_count': len(elements),
        'pages_count': len(set(e.page_number for e in elements)),
        'markdown_content': markdown_content,
        'chunks': chunks,
        'processor': processor  # 返回处理器实例以便进一步操作
    }