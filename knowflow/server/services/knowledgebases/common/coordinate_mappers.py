#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
坐标映射器模块

提供统一的坐标映射接口，支持DOTS和MinerU两种不同的坐标系统：
- DOTS: 200 DPI 图像坐标，格式 [x1, y1, x2, y2]
- MinerU: 72 DPI PDF坐标，格式 [page_idx, x1, x2, y1, y2]
"""

import logging
import difflib
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Set

logger = logging.getLogger(__name__)

class CoordinateMapperInterface(ABC):
    """坐标映射器接口基类"""
    
    @abstractmethod
    def map_chunks_to_coordinates(self, chunks: List[str], elements_data: List[Dict]) -> List[List]:
        """
        将文本分块映射到坐标信息
        
        Args:
            chunks: 文本分块列表
            elements_data: 元素数据列表
            
        Returns:
            坐标列表，每个分块对应一个坐标列表
        """
        pass
    
    @abstractmethod 
    def transform_coordinates(self, coordinates: List) -> List:
        """
        转换坐标格式
        
        Args:
            coordinates: 原始坐标
            
        Returns:
            转换后的坐标
        """
        pass

class DOTSCoordinateMapper(CoordinateMapperInterface):
    """DOTS 坐标映射器"""
    
    def __init__(self):
        self.dpi_scale_factor = 72.0 / 200.0  # DOTS(200 DPI) -> PDF(72 DPI)
        
    def map_chunks_to_coordinates(self, chunks: List[str], dots_elements: List[Dict]) -> List[List]:
        """
        将 DOTS 元素映射到分块坐标
        
        关键差异处理：
        1. DOTS 使用 200 DPI 图像坐标 -> 转换为 72 DPI PDF坐标
        2. DOTS bbox格式: [x1, y1, x2, y2] -> MinerU格式: [page_idx, x1, x2, y1, y2]
        """
        logger.info(f"开始DOTS坐标映射: {len(chunks)}个分块, {len(dots_elements)}个元素")
        
        coordinates = []
        matched_indices: Set[int] = set()
        
        for i, chunk_content in enumerate(chunks):
            try:
                # 复用 DOTS 现有的匹配算法（difflib.SequenceMatcher）
                chunk_coords = self._find_matching_dots_elements(
                    chunk_content, dots_elements, matched_indices
                )
                
                # 转换坐标格式和DPI
                mineru_coords = self._convert_dots_to_mineru_format(chunk_coords)
                coordinates.append(mineru_coords)
                
                if mineru_coords:
                    logger.debug(f"分块{i} 匹配到 {len(mineru_coords)} 个DOTS坐标")
                else:
                    logger.debug(f"分块{i} 未找到匹配的DOTS坐标")
                    
            except Exception as e:
                logger.warning(f"分块{i} 坐标映射失败: {e}")
                coordinates.append([])
        
        coords_count = sum(1 for c in coordinates if c)
        logger.info(f"DOTS坐标映射完成: {coords_count}/{len(chunks)} 个分块有坐标")
        
        return coordinates
    
    def _find_matching_dots_elements(self, chunk_content: str, 
                                   dots_elements: List[Dict], 
                                   matched_indices: Set[int]) -> List[Dict]:
        """查找匹配的DOTS元素（复用原有算法）"""
        
        chunk_content_clean = chunk_content.strip()
        if not chunk_content_clean:
            return []
        
        # 检查chunk是否为HTML表格
        is_chunk_table = '<table>' in chunk_content_clean and '</table>' in chunk_content_clean
        
        # 用 difflib.SequenceMatcher 找最相似的元素（复用DOTS算法）
        best_idx = -1
        best_ratio = 0.0
        
        for i, element in enumerate(dots_elements):
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
            return []
        
        # 从锚点扩展（复用DOTS的扩展逻辑）
        matched_element_indices = [best_idx]
        
        # 向前扩展
        for i in range(best_idx - 1, -1, -1):
            if i in matched_indices:
                continue
            element_text = dots_elements[i].get('text', '').strip()
            if element_text and element_text in chunk_content_clean:
                matched_element_indices.insert(0, i)
            else:
                break
        
        # 向后扩展
        for i in range(best_idx + 1, len(dots_elements)):
            if i in matched_indices:
                continue
            element_text = dots_elements[i].get('text', '').strip()
            if element_text and element_text in chunk_content_clean:
                matched_element_indices.append(i)
            else:
                break
        
        # 记录已匹配的元素索引
        matched_indices.update(matched_element_indices)
        
        # 返回匹配的元素
        return [dots_elements[idx] for idx in matched_element_indices]
    
    def _convert_dots_to_mineru_format(self, dots_coords: List[Dict]) -> List[List]:
        """转换DOTS坐标到MinerU格式"""
        mineru_positions = []
        
        for coord in dots_coords:
            bbox = coord.get('bbox')
            page_number = coord.get('page_number')
            
            if not bbox or not page_number or len(bbox) != 4:
                logger.warning(f"无效的DOTS坐标数据: bbox={bbox}, page_number={page_number}")
                continue
            
            try:
                # DPI缩放: DOTS坐标 * (72/200) = PDF坐标
                pdf_x1 = bbox[0] * self.dpi_scale_factor
                pdf_y1 = bbox[1] * self.dpi_scale_factor  
                pdf_x2 = bbox[2] * self.dpi_scale_factor
                pdf_y2 = bbox[3] * self.dpi_scale_factor
                
                # 按照 MinerU 格式: [page_number, bbox[0], bbox[2], bbox[1], bbox[3]]
                mineru_position = [
                    page_number - 1,  # 转换为0开始的页面索引
                    int(pdf_x1),     # x1 (左边界) - DPI缩放后
                    int(pdf_x2),     # x2 (右边界) - DPI缩放后
                    int(pdf_y1),     # y1 (上边界) - DPI缩放后  
                    int(pdf_y2)      # y2 (下边界) - DPI缩放后
                ]
                mineru_positions.append(mineru_position)
                
                logger.debug(f"DOTS坐标转换: 原始={bbox} -> DPI缩放({self.dpi_scale_factor:.3f}) -> MinerU={mineru_position}")
                
            except (ValueError, IndexError) as e:
                logger.warning(f"坐标转换失败: {e}, bbox={bbox}")
                continue
        
        return mineru_positions
    
    def transform_coordinates(self, coordinates: List) -> List:
        """转换DOTS坐标格式"""
        # 在 _convert_dots_to_mineru_format 中已经处理了转换
        return coordinates

class MinerUCoordinateMapper(CoordinateMapperInterface):
    """MinerU 坐标映射器（保持原有逻辑）"""
    
    def map_chunks_to_coordinates(self, chunks: List[str], mineru_elements: List[Dict]) -> List[List]:
        """映射MinerU坐标（复用现有逻辑）"""
        logger.info(f"开始MinerU坐标映射: {len(chunks)}个分块")
        
        try:
            # 直接复用现有的 get_bbox_for_chunk 逻辑
            from ..mineru_parse.utils import get_bbox_for_chunk
            
            coordinates = []
            for i, chunk in enumerate(chunks):
                try:
                    chunk_coords = get_bbox_for_chunk(chunk, mineru_elements)
                    coordinates.append(chunk_coords)
                    
                    if chunk_coords:
                        logger.debug(f"分块{i} 获取到 {len(chunk_coords)} 个MinerU坐标")
                    else:
                        logger.debug(f"分块{i} 未获取到MinerU坐标")
                        
                except Exception as e:
                    logger.warning(f"分块{i} MinerU坐标获取失败: {e}")
                    coordinates.append([])
            
            coords_count = sum(1 for c in coordinates if c)
            logger.info(f"MinerU坐标映射完成: {coords_count}/{len(chunks)} 个分块有坐标")
            
            return coordinates
            
        except ImportError as e:
            logger.warning(f"无法导入MinerU坐标函数: {e}")
            return [[] for _ in chunks]
        except Exception as e:
            logger.error(f"MinerU坐标映射异常: {e}")
            return [[] for _ in chunks]
    
    def transform_coordinates(self, coordinates: List) -> List:
        """MinerU坐标无需转换"""
        return coordinates

class CoordinateMapperFactory:
    """坐标映射器工厂类"""
    
    @staticmethod
    def create_mapper(coordinate_source: str) -> CoordinateMapperInterface:
        """创建对应的坐标映射器"""
        if coordinate_source.lower() == 'dots':
            return DOTSCoordinateMapper()
        elif coordinate_source.lower() == 'mineru':
            return MinerUCoordinateMapper()
        else:
            raise ValueError(f"不支持的坐标来源: {coordinate_source}")

def convert_dots_to_mineru_coordinates(dots_bbox: List, page_number: int) -> List:
    """DOTS坐标转MinerU格式的独立函数（向后兼容）"""
    try:
        mapper = DOTSCoordinateMapper()
        
        # 构造DOTS元素格式
        dots_element = {
            'bbox': dots_bbox,
            'page_number': page_number
        }
        
        # 转换
        result = mapper._convert_dots_to_mineru_format([dots_element])
        return result[0] if result else []
        
    except Exception as e:
        logger.error(f"坐标转换失败: {e}")
        return []