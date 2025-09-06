#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DOTS OCR 结果处理器

使用 DOTS 官方方法将 OCR 结果转换为 RAGFlow 兼容的格式，支持:
- 布局元素提取和分类
- 官方 Markdown 转换（自动去除页眉页脚）
- 智能分块生成和坐标映射
"""

import json
import logging
import os
import difflib
import tempfile
from typing import Dict, List, Any, Optional, Callable
from pathlib import Path
from PIL import Image

# 导入 DOTS 官方的 markdown 转换方法
try:
    from .format_transformer import layoutjson2md
    DOTS_FORMATTER_AVAILABLE = True
except ImportError:
    DOTS_FORMATTER_AVAILABLE = False
    logger.warning("DOTS format_transformer not available")

# 复用 Mineru 分块算法

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
    
    def to_markdown(self, output_dir: str = None) -> tuple:
        """将所有元素转换为Markdown格式的文档（使用DOTS官方方法）
        
        Args:
            output_dir: 图片输出目录，可选
            
        Returns:
            tuple: (markdown_text, extracted_images_list)
        """
        if not self.elements or not self.pages_data:
            return "", []
        
        if not DOTS_FORMATTER_AVAILABLE:
            logger.error("DOTS format_transformer 不可用，无法生成 markdown")
            return "", []
        
        try:
            # 使用 DOTS 官方方法生成 markdown
            markdown_parts = []
            all_extracted_images = []
            
            for page_idx, page_data in enumerate(self.pages_data):
                # 检查页面是否有有效的布局元素
                layout_elements = page_data.get('layout_elements', [])
                if not layout_elements:
                    continue
                
                # 构造符合 DOTS 格式的 cells 数据
                cells = []
                for element_data in layout_elements:
                    cell = {
                        'bbox': element_data.get('bbox', [0, 0, 0, 0]),
                        'category': element_data.get('category', 'Text'),
                        'text': element_data.get('text', '')
                    }
                    cells.append(cell)
                
                # 获取页面图像对象
                page_image = page_data.get('page_image')
                if page_image is None:
                    # 如果没有页面图像，创建虚拟图像
                    image_dims = page_data.get('image_dimensions', {'width': 1240, 'height': 1754})
                    page_image = Image.new('RGB', (image_dims['width'], image_dims['height']), 'white')
                
                # 使用官方方法生成 markdown（no_page_hf=True 去除页眉页脚）
                page_markdown, page_images = layoutjson2md(
                    page_image, cells, text_key='text', no_page_hf=True, output_dir=output_dir
                )
                
                if page_markdown.strip():
                    markdown_parts.append(page_markdown.strip())
                
                # 收集提取的图片
                if page_images:
                    all_extracted_images.extend(page_images)
            
            final_markdown = '\n\n'.join(markdown_parts)
            return final_markdown, all_extracted_images
            
        except Exception as e:
            logger.error(f"DOTS 官方 markdown 转换失败: {e}")
            return "", []
    
    def generate_chunks(self, chunk_token_num: int = 256, min_chunk_tokens: int = 10, 
                       chunking_strategy: str = 'smart', 
                       enable_coordinates: bool = True, 
                       output_dir: str = None,
                       chunking_config: Optional[dict] = None) -> Dict[str, Any]:
        """生成用于RAGFlow的文本分块（基于完整Markdown，使用DOTS坐标数据+Mineru算法）
        
        Args:
            chunk_token_num: 分块大小（token数）
            min_chunk_tokens: 最小分块大小（token数）
            chunking_strategy: 分块策略 ('smart', 'advanced', 'basic')
            enable_coordinates: 是否启用坐标映射
            output_dir: 图片输出目录（可选）
            chunking_config: 完整分块配置（用于复杂分块策略）
            
        Returns:
            dict: 包含分块数据和提取图片的字典
        """
        if not self.elements:
            return {'chunks': [], 'extracted_images': []}
        
        # 1. 生成完整的Markdown文档
        complete_markdown, extracted_images = self.to_markdown(output_dir=output_dir)
        if not complete_markdown.strip():
            logger.warning("完整Markdown内容为空")
            return {'chunks': [], 'extracted_images': []}
        
        logger.info(f"基于完整Markdown进行分块，文档长度: {len(complete_markdown)} 字符")
        
        # 2. 使用类似Mineru的智能分块方法
        try:
            # 调用智能分块函数（类似Mineru的实现）
            chunk_contents = self._split_markdown_smart(
                complete_markdown, 
                chunk_token_num=chunk_token_num,
                min_chunk_tokens=min_chunk_tokens,
                strategy=chunking_strategy,
                chunking_config=chunking_config
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
                    else:
                        chunk_data['has_coordinates'] = False
                    
                    chunks.append(chunk_data)
            
            logger.info(f"使用{chunking_strategy}策略生成 {len(chunks)} 个文本分块")
            if enable_coordinates:
                coords_count = sum(1 for c in chunks if c.get('has_coordinates', False))
                logger.info(f"成功为 {coords_count}/{len(chunks)} 个分块获取了坐标信息")
            
            return {'chunks': chunks, 'extracted_images': extracted_images}
            
        except Exception as e:
            logger.error(f"智能分块失败: {e}，回退到简单分块")
            fallback_chunks = self._generate_chunks_fallback(complete_markdown, chunk_token_num)
            return {'chunks': fallback_chunks, 'extracted_images': extracted_images}
    
    def generate_chunks_from_markdown(self, markdown_content: str, chunk_token_num: int = 256, 
                                     min_chunk_tokens: int = 10, chunking_strategy: str = 'smart', 
                                     enable_coordinates: bool = True, 
                                     chunking_config: Optional[dict] = None) -> Dict[str, Any]:
        """基于已处理的markdown内容生成分块（用于图片URL已更新后的情况）
        
        Args:
            markdown_content: 已处理的markdown内容（图片URL已更新）
            chunk_token_num: 分块大小（token数）
            min_chunk_tokens: 最小分块大小（token数）
            chunking_strategy: 分块策略 ('smart', 'advanced', 'basic')
            enable_coordinates: 是否启用坐标映射
            
        Returns:
            dict: 包含分块数据的字典
        """
        if not self.elements or not markdown_content.strip():
            return {'chunks': []}
        
        logger.info(f"基于已处理markdown进行分块，文档长度: {len(markdown_content)} 字符")
        
        try:
            # 调用智能分块函数（类似原来的实现）
            chunk_contents = self._split_markdown_smart(
                markdown_content, 
                chunk_token_num=chunk_token_num,
                min_chunk_tokens=min_chunk_tokens,
                strategy=chunking_strategy,
                chunking_config=chunking_config
            )
            
            # 准备DOTS元素列表用于坐标映射
            dots_elements_list = None
            if enable_coordinates:
                dots_elements_list = self._prepare_dots_elements_for_coordinate_mapping()
            
            # 转换为RAGFlow格式的分块
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
                    
                    # 获取坐标信息（使用DOTS数据+Mineru算法）
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
                    else:
                        chunk_data['has_coordinates'] = False
                    
                    chunks.append(chunk_data)
            
            logger.info(f"使用{chunking_strategy}策略生成 {len(chunks)} 个文本分块")
            if enable_coordinates:
                coords_count = sum(1 for c in chunks if c.get('has_coordinates', False))
                logger.info(f"成功为 {coords_count}/{len(chunks)} 个分块获取了坐标信息")
            
            return {'chunks': chunks}
            
        except Exception as e:
            logger.error(f"智能分块失败: {e}，回退到简单分块")
            fallback_chunks = self._generate_chunks_fallback(markdown_content, chunk_token_num)
            return {'chunks': fallback_chunks}
    
    def _split_markdown_smart(self, markdown_text: str, chunk_token_num: int = 256, 
                             min_chunk_tokens: int = 10, strategy: str = 'smart',
                             chunking_config: Optional[dict] = None) -> List[str]:
        """智能Markdown分块（复用Mineru的分块逻辑）
        
        Args:
            markdown_text: 完整的Markdown文本
            chunk_token_num: 目标分块大小
            min_chunk_tokens: 最小分块大小
            strategy: 分块策略
            chunking_config: 完整分块配置（用于复杂策略）
            
        Returns:
            分块内容列表
        """
        try:
            # 复用mineru的统一分块接口，支持完整配置
            from ..mineru_parse.utils import split_markdown_to_chunks_configured
            
            # 传递完整的分块配置给Mineru函数
            chunks = split_markdown_to_chunks_configured(
                markdown_text,
                chunk_token_num=chunk_token_num,
                min_chunk_tokens=min_chunk_tokens,
                chunking_config=chunking_config  # 传递完整配置
            )
            
            logger.info(f"使用{strategy}策略分块完成，生成 {len(chunks)} 个分块")
            return chunks
            
        except ImportError as e:
            logger.warning(f"无法导入Mineru分块函数: {e}")
            return self._simple_markdown_chunking(markdown_text, chunk_token_num)
        except Exception as e:
            logger.error(f"分块处理异常: {e}")
            logger.debug(f"chunking_config: {chunking_config}")
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
                    # 关键修复：DPI 缩放问题
                    # DOTS 使用 pdf2image 200 DPI 转换，而 MinerU 使用 PDF 原生坐标 72 DPI
                    # 需要进行 DPI 缩放转换: DOTS坐标 * (72/200) = PDF坐标
                    
                    dpi_scale_factor = 72.0 / 200.0  # PDF标准 72 DPI / DOTS图像 200 DPI
                    
                    # 缩放 DOTS 图像坐标到 PDF 坐标
                    pdf_x1 = bbox[0] * dpi_scale_factor
                    pdf_y1 = bbox[1] * dpi_scale_factor  
                    pdf_x2 = bbox[2] * dpi_scale_factor
                    pdf_y2 = bbox[3] * dpi_scale_factor
                    
                    # 按照 MinerU utils.py:621 的格式: [page_number, bbox[0], bbox[2], bbox[1], bbox[3]]
                    mineru_position = [
                        page_number - 1,  # 转换为0开始的页面索引
                        int(pdf_x1),     # x1 (左边界) - DPI缩放后
                        int(pdf_x2),     # x2 (右边界) - DPI缩放后
                        int(pdf_y1),     # y1 (上边界) - DPI缩放后  
                        int(pdf_y2)      # y2 (下边界) - DPI缩放后
                    ]
                    positions.append(mineru_position)
                    
                    logger.debug(f"DOTS坐标转换: 原始={bbox} -> DPI缩放({dpi_scale_factor:.3f}) -> PDF={mineru_position}")
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
        markdown_content, _ = self.to_markdown()
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
                       chunking_strategy: str = 'smart',
                       kb_id: str = None,
                       temp_dir: str = None,
                       chunking_config: Optional[dict] = None) -> Dict[str, Any]:
    """处理DOTS文档解析结果的便捷函数
    
    Args:
        document_results: DOTS适配器返回的文档解析结果
        debug_output_dir: 调试信息输出目录，可选
        chunk_token_num: 分块大小（token数）
        min_chunk_tokens: 最小分块大小（token数）
        chunking_strategy: 分块策略 ('smart', 'advanced', 'basic')
        kb_id: 知识库ID
        temp_dir: 临时目录
        chunking_config: 完整的分块配置（包含策略和参数）
        
    Returns:
        dict: 包含处理结果的字典
    """
    processor = DOTSProcessor()
    
    # 处理解析结果
    elements = processor.process_document_results(document_results)
    
    # 第一步：生成包含相对路径图片的markdown和提取图片
    image_output_dir = None
    if temp_dir and kb_id:
        image_output_dir = os.path.join(temp_dir, 'images')
    
    # 生成markdown并提取图片
    if image_output_dir:
        markdown_content, extracted_images = processor.to_markdown(output_dir=image_output_dir)
    else:
        markdown_content, extracted_images = processor.to_markdown()
    
    # 第二步：如果有图片，先处理图片上传和URL更新，然后再进行分块
    if extracted_images and kb_id and temp_dir:
        try:
            # 复用MinerU的图片处理逻辑
            from ..mineru_parse.minio_server import upload_directory_to_minio
            from ..mineru_parse.mineru_test import update_markdown_image_urls
            
            # 检查图片目录是否存在
            if os.path.exists(image_output_dir):
                # 上传图片到MinIO
                success = upload_directory_to_minio(kb_id, image_output_dir)
                
                if success:
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as tmp_file:
                        tmp_file.write(markdown_content)
                        tmp_md_path = tmp_file.name
                    
                    # 更新markdown中的图片URL
                    updated_markdown = update_markdown_image_urls(tmp_md_path, kb_id)
                    
                    if updated_markdown:
                        markdown_content = updated_markdown
                        logger.info(f"已更新 {len(extracted_images)} 个图片URL为MinIO格式")
                    
                    # 清理临时文件
                    os.unlink(tmp_md_path)
                else:
                    logger.warning("图片上传失败，使用原始markdown")
            else:
                logger.warning(f"图片输出目录不存在: {image_output_dir}")
                
        except Exception as e:
            logger.warning(f"图片处理失败，使用原始markdown: {e}")
            import traceback
            logger.debug(f"图片处理异常详情: {traceback.format_exc()}")
    
    # 第三步：基于处理后的markdown（已包含正确的图片URL）进行分块
    result = processor.generate_chunks_from_markdown(
        markdown_content=markdown_content,
        chunk_token_num=chunk_token_num,
        min_chunk_tokens=min_chunk_tokens,
        chunking_strategy=chunking_strategy,
        enable_coordinates=True,  # 启用坐标映射
        chunking_config=chunking_config  # 传递完整分块配置
    )
    chunks = result['chunks']
    
    # 图片处理已在分块之前完成，这里只记录结果
    logger.info(f"分块生成完成: {len(chunks)} 个分块, 包含图片: {len(extracted_images)} 个")
    
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
        'extracted_images': extracted_images,
        'chunking_strategy': chunking_strategy,
        'processor': processor  # 返回处理器实例以便进一步操作
    }