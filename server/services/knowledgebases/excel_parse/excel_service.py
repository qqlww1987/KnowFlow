import logging
from typing import List, Dict, Any, Optional, Union
from io import BytesIO

from .excel_chunker import EnhancedExcelChunker
from .excel_config import get_excel_config_for_kb, GlobalExcelConfig


logger = logging.getLogger(__name__)


class ExcelChunkingService:
    """Excel分块服务 - 知识库系统的Excel处理统一接口"""
    
    def __init__(self):
        self._chunker_cache = {}  # 缓存分块器实例
    
    def _get_chunker(self, config: GlobalExcelConfig) -> EnhancedExcelChunker:
        """
        获取分块器实例（带缓存）
        
        Args:
            config: Excel配置 (新的Pydantic模型)
            
        Returns:
            EnhancedExcelChunker实例
        """
        config_key = str(hash(frozenset(config.model_dump().items())))
        
        if config_key not in self._chunker_cache:
            self._chunker_cache[config_key] = EnhancedExcelChunker(config.model_dump())
        
        return self._chunker_cache[config_key]
    
    def chunk_excel_for_kb(self, 
                          file_input: Union[str, bytes, BytesIO],
                          kb_config: Dict[str, Any],
                          filename: Optional[str] = None) -> Dict[str, Any]:
        """
        为知识库系统分块Excel文件
        
        Args:
            file_input: Excel文件输入（路径、字节流或BytesIO）
            kb_config: 知识库配置
            filename: 文件名（用于日志和错误报告）
            
        Returns:
            包含分块结果和元数据的字典 {
                'chunks': List[str],
                'metadata': Dict[str, Any],
                'config_used': Dict[str, Any]
            }
        """
        try:
            # 从知识库配置创建Excel配置
            excel_config = get_excel_config_for_kb(kb_config)
            
            # 获取分块器
            chunker = self._get_chunker(excel_config)
            
            # 执行分块
            chunks = chunker.chunk_excel(file_input, excel_config.default_strategy)
            
            # 获取文件元数据
            metadata = self._extract_metadata(file_input, filename, excel_config)
            
            return {
                'chunks': chunks,
                'metadata': metadata,
                'config_used': excel_config.model_dump(),
                'chunk_count': len(chunks),
                'total_characters': sum(len(chunk) for chunk in chunks)
            }
            
        except Exception as e:
            logger.error(f"Excel分块失败 - 文件: {filename or 'unknown'}, 错误: {e}")
            raise
    
    def _extract_metadata(self, file_input: Union[str, bytes, BytesIO], 
                         filename: Optional[str], 
                         config: GlobalExcelConfig) -> Dict[str, Any]:
        """
        提取文件元数据
        
        Args:
            file_input: 文件输入
            filename: 文件名
            config: Excel配置
            
        Returns:
            元数据字典
        """
        metadata = {
            'filename': filename or 'unknown',
            'file_type': 'excel',
            'chunking_strategy': config.default_strategy,
            'preprocessed_merged_cells': config.preprocess_merged_cells
        }
        
        try:
            # 获取总行数
            total_rows = EnhancedExcelChunker.get_row_count(file_input)
            metadata['total_rows'] = total_rows
            
            # 获取工作表信息
            chunker = EnhancedExcelChunker(config.model_dump())
            wb = chunker._load_excel_to_workbook(file_input)
            
            sheets_info = []
            for sheetname in wb.sheetnames:
                ws = wb[sheetname]
                rows = list(ws.rows)
                if rows:
                    sheet_info = {
                        'name': sheetname,
                        'rows': len(rows),
                        'cols': len([c for c in rows[0] if c.value]) if rows else 0
                    }
                    sheets_info.append(sheet_info)
            
            metadata['sheets'] = sheets_info
            metadata['sheet_count'] = len(sheets_info)
            
        except Exception as e:
            logger.warning(f"元数据提取失败: {e}")
        
        return metadata
    
    def validate_excel_file(self, file_input: Union[str, bytes, BytesIO]) -> Dict[str, Any]:
        """
        验证Excel文件格式和可读性
        
        Args:
            file_input: 文件输入
            
        Returns:
            验证结果字典 {
                'valid': bool,
                'message': str,
                'file_info': Dict[str, Any]
            }
        """
        try:
            # 尝试加载文件
            chunker = EnhancedExcelChunker()
            wb = chunker._load_excel_to_workbook(file_input)
            
            # 检查基本信息
            sheet_count = len(wb.sheetnames)
            total_rows = 0
            has_data = False
            
            for sheetname in wb.sheetnames:
                ws = wb[sheetname]
                rows = list(ws.rows)
                if rows:
                    total_rows += len(rows)
                    if len(rows) > 1:  # 有数据行
                        has_data = True
            
            if not has_data:
                return {
                    'valid': False,
                    'message': '文件中没有发现有效数据',
                    'file_info': {
                        'sheet_count': sheet_count,
                        'total_rows': total_rows
                    }
                }
            
            return {
                'valid': True,
                'message': '文件格式正确，可以处理',
                'file_info': {
                    'sheet_count': sheet_count,
                    'total_rows': total_rows,
                    'sheets': wb.sheetnames
                }
            }
            
        except Exception as e:
            return {
                'valid': False,
                'message': f'文件格式错误或无法读取: {str(e)}',
                'file_info': {}
            }
    
    def get_chunking_preview(self, 
                           file_input: Union[str, bytes, BytesIO],
                           kb_config: Dict[str, Any],
                           max_preview_chunks: int = 3) -> Dict[str, Any]:
        """
        获取分块预览
        
        Args:
            file_input: 文件输入
            kb_config: 知识库配置
            max_preview_chunks: 最大预览分块数
            
        Returns:
            预览结果字典
        """
        try:
            result = self.chunk_excel_for_kb(file_input, kb_config)
            
            preview_chunks = result['chunks'][:max_preview_chunks]
            
            return {
                'preview_chunks': preview_chunks,
                'total_chunks': result['chunk_count'],
                'metadata': result['metadata'],
                'config_used': result['config_used'],
                'estimated_tokens': self._estimate_tokens(result['chunks'])
            }
            
        except Exception as e:
            logger.error(f"分块预览失败: {e}")
            raise
    
    def _estimate_tokens(self, chunks: List[str]) -> int:
        """
        估算token数量（简单估算：中文1个字符≈1个token，英文4个字符≈1个token）
        
        Args:
            chunks: 分块列表
            
        Returns:
            估算的token数量
        """
        total_chars = sum(len(chunk) for chunk in chunks)
        # 简单的混合估算
        estimated_tokens = int(total_chars * 0.8)  # 保守估算
        return estimated_tokens
    
    def get_available_configs(self) -> Dict[str, Any]:
        """
        获取可用的配置选项（用于UI）
        
        注意：此方法现在返回全局配置，预设功能已简化。
        """
        # 直接从全局配置获取默认值
        default_config = get_excel_config_for_kb({})
        
        return {
            'strategies': ['html', 'row', 'auto'],
            'default_config': default_config.model_dump()
        }


# 全局服务实例
_excel_service = None


def get_excel_service() -> ExcelChunkingService:
    """获取Excel分块服务实例（单例）"""
    global _excel_service
    if _excel_service is None:
        _excel_service = ExcelChunkingService()
    return _excel_service


# 便利函数
def chunk_excel_for_knowledge_base(file_input: Union[str, bytes, BytesIO],
                                 kb_config: Dict[str, Any],
                                 filename: Optional[str] = None) -> Dict[str, Any]:
    """
    为知识库分块Excel文件的便利函数
    
    Args:
        file_input: 文件输入
        kb_config: 知识库配置
        filename: 文件名
        
    Returns:
        分块结果
    """
    service = get_excel_service()
    return service.chunk_excel_for_kb(file_input, kb_config, filename)


def validate_excel_for_kb(file_input: Union[str, bytes, BytesIO]) -> Dict[str, Any]:
    """验证Excel文件的便利函数"""
    service = get_excel_service()
    return service.validate_excel_file(file_input)


def preview_excel_chunks(file_input: Union[str, bytes, BytesIO],
                        kb_config: Dict[str, Any]) -> Dict[str, Any]:
    """预览Excel分块的便利函数"""
    service = get_excel_service()
    return service.get_chunking_preview(file_input, kb_config)


if __name__ == "__main__":
    # 测试代码
    import sys
    
    def test_excel_service():
        import os
        
        service = get_excel_service()
        
        # 准备测试文件路径
        # 确保项目根目录下有 test_data/test.xlsx
        script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        test_file = os.path.join(script_dir, "test_data", "test.xlsx")
        
        if not os.path.exists(test_file):
            print(f"测试文件未找到: {test_file}")
            return

        print(f"--- 使用 'row' 策略测试 ---")
        kb_config_row = {"excel_strategy": "row"}
        result_row = service.chunk_excel_for_kb(test_file, kb_config=kb_config_row, filename="test.xlsx")
        
        if result_row:
            print(f"分块数量: {result_row['chunk_count']}")
            print(f"总字符数: {result_row['total_characters']}")
            print(f"使用配置: {result_row['config_used']['default_strategy']}")
            
            # 显示前两个分块的预览
            for i, chunk in enumerate(result_row['chunks'][:2]):
                print(f"  块 {i+1}: {chunk[:100]}...")

        print(f"\n--- 使用 'html' 策略测试 ---")
        kb_config_html = {"excel_strategy": "html", "html_chunk_rows": 5}
        result_html = service.chunk_excel_for_kb(test_file, kb_config=kb_config_html, filename="test.xlsx")

        if result_html:
            print(f"分块数量: {result_html['chunk_count']}")
            print(f"总字符数: {result_html['total_characters']}")
            print(f"使用配置: {result_html['config_used']['default_strategy']}")
            # 显示第一个分块预览
            if result_html['chunks']:
                print(f"  块 1: {result_html['chunks'][0][:200]}...")
    
    test_excel_service() 