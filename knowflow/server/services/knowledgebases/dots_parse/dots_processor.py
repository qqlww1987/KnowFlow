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
import difflib

# 不直接导入Mineru函数，而是复用其算法逻辑

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
        self.page_number = element_data.get('page_number', 1)  # 添加页面编号
        
        # 计算元素面积和位置信息
        if len(self.bbox) == 4 and all(isinstance(coord, (int, float)) for coord in self.bbox):
            # 确保坐标是数值类型
            self.x1, self.y1, self.x2, self.y2 = [float(coord) for coord in self.bbox]
            self.width = abs(self.x2 - self.x1)
            self.height = abs(self.y2 - self.y1)
            self.area = self.width * self.height
            self.center_x = (self.x1 + self.x2) / 2
            self.center_y = (self.y1 + self.y2) / 2
            
            # 确保坐标顺序正确 (x1 <= x2, y1 <= y2)
            if self.x1 > self.x2:
                self.x1, self.x2 = self.x2, self.x1
            if self.y1 > self.y2:
                self.y1, self.y2 = self.y2, self.y1
            
            # 更新bbox以保持一致性
            self.bbox = [self.x1, self.y1, self.x2, self.y2]
        else:
            logger.warning(f"无效的DOTS bbox数据: {self.bbox}")
            self.width = self.height = self.area = 0
            self.center_x = self.center_y = 0
            self.x1 = self.y1 = self.x2 = self.y2 = 0
    
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
    
    def generate_chunks(self, chunk_token_num: int = 256, min_chunk_tokens: int = 10, 
                       chunking_strategy: str = 'smart', 
                       enable_coordinates: bool = True) -> List[Dict[str, Any]]:
        """生成用于RAGFlow的文本分块（基于完整Markdown，使用DOTS坐标数据+Mineru算法）
        
        Args:
            chunk_token_num: 分块大小（token数）
            min_chunk_tokens: 最小分块大小（token数）
            chunking_strategy: 分块策略 ('smart', 'advanced', 'basic')
            enable_coordinates: 是否启用坐标映射
            
        Returns:
            list: 分块数据列表
        """
        if not self.elements:
            return []
        
        # 1. 生成完整的Markdown文档
        complete_markdown = self.to_markdown()
        if not complete_markdown.strip():
            logger.warning("完整Markdown内容为空")
            return []
        
        logger.info(f"基于完整Markdown进行分块，文档长度: {len(complete_markdown)} 字符")
        
        # 2. 使用类似Mineru的智能分块方法
        try:
            # 调用智能分块函数（类似Mineru的实现）
            chunk_contents = self._split_markdown_smart(
                complete_markdown, 
                chunk_token_num=chunk_token_num,
                min_chunk_tokens=min_chunk_tokens,
                strategy=chunking_strategy
            )
            
            # 3. 准备DOTS元素列表用于坐标映射
            dots_elements_list = None
            if enable_coordinates:
                dots_elements_list = self._prepare_dots_elements_for_coordinate_mapping()
            
            # 4. 转换为RAGFlow格式的分块
            chunks = []
            matched_global_indices = set()  # 跟踪已匹配的元素索引
            
            for i, content in enumerate(chunk_contents):
                if content.strip():
                    # 基本信息
                    page_number = self._extract_page_number(content)
                    chunk_data = {
                        'id': i,
                        'content': content.strip(),
                        'page_number': page_number,
                        'start_pos': 0,  # 基于完整markdown的分块，位置信息简化
                        'end_pos': len(content),
                        'element_count': self._count_elements_in_chunk(content),
                        'chunking_strategy': chunking_strategy
                    }
                    
                    # 5. 获取坐标信息（使用DOTS数据+Mineru算法）
                    if enable_coordinates and dots_elements_list:
                        try:
                            positions = self._get_chunk_coordinates_from_dots(
                                content.strip(), 
                                dots_elements_list,
                                matched_global_indices
                            )
                            if positions:
                                chunk_data['positions'] = positions
                                chunk_data['has_coordinates'] = True
                                logger.debug(f"分块 {i} 获取到 {len(positions)} 个DOTS坐标")
                            else:
                                chunk_data['has_coordinates'] = False
                        except Exception as coord_e:
                            logger.warning(f"分块 {i} 坐标获取失败: {coord_e}")
                            chunk_data['has_coordinates'] = False
                    
                    chunks.append(chunk_data)
            
            logger.info(f"使用{chunking_strategy}策略生成 {len(chunks)} 个文本分块")
            if enable_coordinates:
                coords_count = sum(1 for c in chunks if c.get('has_coordinates', False))
                logger.info(f"成功为 {coords_count}/{len(chunks)} 个分块获取了坐标信息")
            
            return chunks
            
        except Exception as e:
            logger.error(f"智能分块失败: {e}，回退到简单分块")
            return self._generate_chunks_fallback(complete_markdown, chunk_token_num)
    
    def _split_markdown_smart(self, markdown_text: str, chunk_token_num: int = 256, 
                             min_chunk_tokens: int = 10, strategy: str = 'smart') -> List[str]:
        """智能Markdown分块（复用Mineru的分块逻辑）
        
        Args:
            markdown_text: 完整的Markdown文本
            chunk_token_num: 目标分块大小
            min_chunk_tokens: 最小分块大小
            strategy: 分块策略
            
        Returns:
            分块内容列表
        """
        try:
            # 复用mineru的分块函数
            from ..mineru_parse.utils import (
                split_markdown_to_chunks_smart,
                split_markdown_to_chunks_advanced,
                split_markdown_to_chunks
            )
            
            if strategy == 'smart':
                chunks = split_markdown_to_chunks_smart(
                    markdown_text, 
                    chunk_token_num=chunk_token_num,
                    min_chunk_tokens=min_chunk_tokens
                )
            elif strategy == 'advanced':
                chunks = split_markdown_to_chunks_advanced(
                    markdown_text,
                    chunk_token_num=chunk_token_num,
                    min_chunk_tokens=min_chunk_tokens
                )
            else:  # basic
                chunks = split_markdown_to_chunks(
                    markdown_text,
                    chunk_token_num=chunk_token_num
                )
            
            logger.info(f"使用{strategy}策略分块完成，生成 {len(chunks)} 个分块")
            return chunks
            
        except ImportError as e:
            logger.warning(f"无法导入Mineru分块函数: {e}")
            return self._simple_markdown_chunking(markdown_text, chunk_token_num)
        except Exception as e:
            logger.error(f"分块处理异常: {e}")
            return self._simple_markdown_chunking(markdown_text, chunk_token_num)
    
    def _simple_markdown_chunking(self, text: str, chunk_size: int) -> List[str]:
        """简单的Markdown分块（后备方案）"""
        if not text:
            return []
            
        # 按段落分割
        paragraphs = text.split('\n\n')
        chunks = []
        current_chunk = []
        current_size = 0
        
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
                
            para_size = len(paragraph)
            
            if current_size + para_size > chunk_size and current_chunk:
                # 完成当前分块
                chunks.append('\n\n'.join(current_chunk))
                current_chunk = [paragraph]
                current_size = para_size
            else:
                current_chunk.append(paragraph)
                current_size += para_size
        
        # 添加最后一个分块
        if current_chunk:
            chunks.append('\n\n'.join(current_chunk))
        
        return chunks
    
    def _extract_page_number(self, content: str) -> int:
        """从分块内容中提取页面编号"""
        import re
        # 查找页面标记 <!-- Page N -->
        page_match = re.search(r'<!-- Page (\d+) -->', content)
        if page_match:
            return int(page_match.group(1))
        
        # 如果没有找到页面标记，返回默认页面
        return 1
    
    def _count_elements_in_chunk(self, content: str) -> int:
        """统计分块中的元素数量（粗略估计）"""
        # 统计标题、列表项、表格等结构的数量
        import re
        
        count = 0
        # 标题
        count += len(re.findall(r'^#+\s', content, re.MULTILINE))
        # 列表项
        count += len(re.findall(r'^[-*+]\s', content, re.MULTILINE))
        # 表格行
        count += len(re.findall(r'\|.*\|', content))
        # 公式
        count += len(re.findall(r'\$\$.*?\$\$', content, re.DOTALL))
        
        # 如果没有明显结构，按段落计算
        if count == 0:
            count = len([p for p in content.split('\n\n') if p.strip()])
        
        return max(1, count)
    
    def _generate_chunks_fallback(self, markdown_text: str, chunk_size: int) -> List[Dict[str, Any]]:
        """后备分块方案"""
        simple_chunks = self._simple_markdown_chunking(markdown_text, chunk_size)
        
        chunks = []
        for i, content in enumerate(simple_chunks):
            if content.strip():
                chunks.append({
                    'id': i,
                    'content': content.strip(),
                    'page_number': self._extract_page_number(content),
                    'start_pos': 0,
                    'end_pos': len(content),
                    'element_count': self._count_elements_in_chunk(content),
                    'chunking_strategy': 'fallback'
                })
        
        return chunks
    
    def _prepare_dots_elements_for_coordinate_mapping(self) -> List[Dict[str, Any]]:
        """准备DOTS元素列表用于坐标映射（保持DOTS原始格式）
        
        Returns:
            元素列表，保持DOTS的原始坐标格式
        """
        elements_list = []
        
        # 按页面和位置排序元素
        sorted_elements = sorted(self.elements, key=lambda e: (e.page_number, e.center_y, e.center_x))
        
        for i, element in enumerate(sorted_elements):
            # 验证坐标数据有效性
            if element.bbox and len(element.bbox) == 4:
                element_data = {
                    'bbox': element.bbox,  # DOTS格式 [x1, y1, x2, y2] 
                    'category': element.category,
                    'text': element.text,
                    'page_number': element.page_number,  # 保持1开始的页面编号
                    'index': i
                }
                elements_list.append(element_data)
                logger.debug(f"DOTS元素 {i}: bbox={element.bbox}, page={element.page_number}, text='{element.text[:50]}...'")
            else:
                logger.warning(f"跳过无效DOTS元素 {i}: bbox={element.bbox}")
        
        logger.info(f"准备了 {len(elements_list)} 个有效DOTS元素用于坐标映射")
        return elements_list
    
    def _get_chunk_coordinates_from_dots(self, chunk_content: str, elements_list: List[Dict[str, Any]], 
                                        matched_indices: set) -> Optional[List[List[int]]]:
        """从DOTS元素中获取分块对应的坐标信息（复用Mineru匹配算法+DOTS坐标格式）
        
        Args:
            chunk_content: 分块内容
            elements_list: DOTS元素列表
            matched_indices: 已匹配的元素索引
            
        Returns:
            坐标列表，Mineru格式 [[page_idx, x1, x2, y1, y2], ...]
        """
        try:
            chunk_content_clean = chunk_content.strip()
            if not chunk_content_clean:
                return None
            
            # 检查chunk是否为HTML表格
            is_chunk_table = '<table>' in chunk_content_clean and '</table>' in chunk_content_clean
            
            # 用 difflib.SequenceMatcher 找最相似的元素（复用Mineru算法）
            best_idx = -1
            best_ratio = 0.0
            
            for i, element in enumerate(elements_list):
                if i in matched_indices:
                    continue
                    
                element_text = element.get('text', '').strip()
                if not element_text:
                    continue
                
                if is_chunk_table:
                    # 对于表格chunk，检查元素是否也是表格
                    if element.get('category') == 'Table':
                        # 对于表格，可能需要特殊处理HTML内容
                        if '<table>' in element_text and '</table>' in element_text:
                            import re
                            table_match = re.search(r'<table>.*?</table>', element_text, re.DOTALL)
                            if table_match:
                                element_html = table_match.group(0)
                                ratio = difflib.SequenceMatcher(None, chunk_content_clean, element_html).ratio()
                            else:
                                ratio = difflib.SequenceMatcher(None, chunk_content_clean, element_text).ratio()
                        else:
                            ratio = difflib.SequenceMatcher(None, chunk_content_clean, element_text).ratio()
                    else:
                        ratio = 0.0
                else:
                    # 对于非表格chunk，直接比较文本内容
                    ratio = difflib.SequenceMatcher(None, chunk_content_clean, element_text).ratio()
                
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_idx = i
            
            if best_idx == -1 or best_ratio < 0.1:  # 阈值可调整
                logger.debug(f"未找到足够相似的DOTS元素 (最高相似度: {best_ratio:.3f})")
                return None
            
            # 从锚点扩展（复用Mineru的扩展逻辑）
            matched_element_indices = [best_idx]
            
            # 向前扩展
            for i in range(best_idx - 1, -1, -1):
                if i in matched_indices:
                    continue
                element_text = elements_list[i].get('text', '').strip()
                if element_text and element_text in chunk_content_clean:
                    matched_element_indices.insert(0, i)
                else:
                    break
            
            # 向后扩展
            for i in range(best_idx + 1, len(elements_list)):
                if i in matched_indices:
                    continue
                element_text = elements_list[i].get('text', '').strip()
                if element_text and element_text in chunk_content_clean:
                    matched_element_indices.append(i)
                else:
                    break
            
            # 提取位置信息并转换为Mineru格式
            positions = []
            for idx in matched_element_indices:
                element = elements_list[idx]
                bbox = element.get('bbox')  # DOTS格式 [x1, y1, x2, y2]
                page_number = element.get('page_number')
                
                if bbox and page_number is not None and len(bbox) == 4:
                    # 转换为Mineru格式：[page_idx, x1, x2, y1, y2]
                    # DOTS page_number是1开始，需要转换为0开始的页面索引
                    # DOTS bbox: [x1, y1, x2, y2] -> Mineru: [page_idx, x1, x2, y1, y2]
                    mineru_position = [
                        page_number - 1,  # 转换为0开始的页面索引
                        int(bbox[0]),     # x1 (左边界)
                        int(bbox[2]),     # x2 (右边界)  
                        int(bbox[1]),     # y1 (上边界)
                        int(bbox[3])      # y2 (下边界)
                    ]
                    positions.append(mineru_position)
                    
                    logger.debug(f"DOTS坐标转换: DOTS={bbox} page={page_number} -> Mineru={mineru_position}")
                else:
                    logger.warning(f"无效的DOTS坐标数据: bbox={bbox}, page_number={page_number}")
            
            # 记录已匹配的元素索引
            matched_indices.update(matched_element_indices)
            
            if positions:
                logger.debug(f"为chunk找到 {len(positions)} 个DOTS位置（相似度: {best_ratio:.3f}）")
                return positions
            else:
                logger.debug("未能从DOTS元素提取到有效的位置信息")
                return None
                
        except Exception as e:
            logger.error(f"从DOTS获取chunk坐标失败: {e}")
            return None
    
    
    
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
                       debug_output_dir: Optional[str] = None,
                       chunk_token_num: int = 256,
                       min_chunk_tokens: int = 10,
                       chunking_strategy: str = 'smart') -> Dict[str, Any]:
    """处理DOTS文档解析结果的便捷函数
    
    Args:
        document_results: DOTS适配器返回的文档解析结果
        debug_output_dir: 调试信息输出目录，可选
        chunk_token_num: 分块大小（token数）
        min_chunk_tokens: 最小分块大小（token数）
        chunking_strategy: 分块策略 ('smart', 'advanced', 'basic')
        
    Returns:
        dict: 包含处理结果的字典
    """
    processor = DOTSProcessor()
    
    # 处理解析结果
    elements = processor.process_document_results(document_results)
    
    # 生成Markdown和分块（使用新的智能分块方法，包含坐标映射）
    markdown_content = processor.to_markdown()
    chunks = processor.generate_chunks(
        chunk_token_num=chunk_token_num,
        min_chunk_tokens=min_chunk_tokens,
        chunking_strategy=chunking_strategy,
        enable_coordinates=True  # 启用坐标映射
    )
    
    # 保存调试信息（如果指定了输出目录）
    if debug_output_dir:
        processor.save_debug_info(debug_output_dir)
    
    logger.info(f"DOTS处理完成: {len(elements)}个元素, {len(chunks)}个分块, 策略={chunking_strategy}")
    
    return {
        'success': True,
        'elements_count': len(elements),
        'pages_count': len(set(e.page_number for e in elements)),
        'markdown_content': markdown_content,
        'chunks': chunks,
        'chunking_strategy': chunking_strategy,
        'processor': processor  # 返回处理器实例以便进一步操作
    }