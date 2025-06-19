from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    """应用主配置"""
    dev_mode: bool = Field(False, description="是否启用开发模式")
    cleanup_temp_files: bool = Field(True, description="是否清理临时文件")
    chunk_method: str = Field("smart", description="全局分块方法")


class ExcelConfig(BaseModel):
    """Excel处理配置"""
    default_strategy: str = Field("auto", description="默认分块策略")
    html_chunk_rows: int = Field(12, description="HTML分块的默认行数")
    enable_smart_chunk_size: bool = Field(True, description="是否启用智能分块大小计算")
    merge_adjacent_rows: int = Field(1, description="合并的相邻行数")
    preprocess_merged_cells: bool = Field(True, description="是否预处理合并的单元格")
    number_formatting: bool = Field(True, description="是否格式化数字")
    min_chunk_size: int = Field(50, description="最小分块字符数")
    max_chunk_size: int = Field(8000, description="最大分块字符数")
    preserve_table_structure: bool = Field(True, description="是否保持表格结构")


class RootConfig(BaseModel):
    """配置根模型"""
    app: AppConfig = Field(default_factory=AppConfig)
    excel: ExcelConfig = Field(default_factory=ExcelConfig) 