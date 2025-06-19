# Excel分块增强模块

本模块基于ragflow的Excel分块功能进行了增强，提供了更完善的Excel文件处理能力。

## 核心特性

### 1. **合并单元格预处理**
- 自动检测并处理合并单元格
- 将合并区域的值填充到每个单元格
- 避免分块时信息丢失

### 2. **灵活的分块策略**
- **HTML策略**: 保持表格结构，适合复杂表格
- **行策略**: 按行分块，适合结构化数据
- **自动策略**: 根据列数智能选择策略

### 3. **智能配置管理**
- 支持自定义分块行数（默认12行）
- 预设配置方案（default, high_precision, balanced等）
- 支持数字格式化和上下文增强

## 快速使用

### 基础用法

```python
from server.services.knowledgebases import quick_chunk_excel, quick_validate_excel

# 快速分块Excel文件
chunks = quick_chunk_excel("data.xlsx", strategy="html", chunk_rows=8)
print(f"分块数量: {len(chunks)}")

# 验证Excel文件
validation = quick_validate_excel("data.xlsx")
if validation['valid']:
    print("文件格式正确")
```

### 知识库集成

```python
from server.services.knowledgebases import chunk_excel_for_knowledge_base

# 知识库配置
kb_config = {
    'html4excel': True,              # 使用HTML分块
    'excel_chunk_rows': 10,         # 10行一块
    'excel_preset': 'balanced',     # 使用预设配置
    'preprocess_merged_cells': True # 预处理合并单元格
}

# 分块处理
result = chunk_excel_for_knowledge_base(
    file_input="data.xlsx",
    kb_config=kb_config,
    filename="data.xlsx"
)

print(f"分块数量: {result['chunk_count']}")
print(f"使用策略: {result['config_used']['strategy']}")
print(f"文件信息: {result['metadata']}")
```

### 高级配置

```python
from server.services.knowledgebases import (
    ExcelChunkingService, 
    ExcelConfigManager,
    create_excel_chunker
)

# 创建服务实例
service = ExcelChunkingService()

# 创建自定义配置
config = ExcelConfigManager.create_config(
    strategy="html",
    html_chunk_rows=15,
    preprocess_merged_cells=True,
    smart_chunk_size=True,
    number_formatting=True
)

# 使用自定义分块器
chunker = create_excel_chunker(config.to_dict())
chunks = chunker.chunk_excel("data.xlsx", "html")
```

## 配置选项

### 预设配置

| 配置名称 | 策略 | 行数 | 适用场景 |
|---------|------|------|----------|
| `default` | HTML | 12 | 通用场景 |
| `high_precision` | 行分块 | 1 | 需要精确控制 |
| `balanced` | 自动 | 8 | 平衡性能和质量 |
| `large_table` | HTML | 20 | 大型表格 |
| `simple_data` | 行分块 | 3 | 简单数据 |

### 配置参数

```python
{
    # 基础策略配置
    'strategy': 'html',                    # 分块策略: html/row/auto
    'html_chunk_rows': 12,                 # HTML分块行数
    
    # 预处理配置
    'preprocess_merged_cells': True,       # 是否预处理合并单元格
    'number_formatting': True,             # 是否格式化大数字
    
    # 质量优化
    'add_row_context': True,               # 是否添加行上下文
    'smart_chunk_size': True,              # 是否启用智能分块大小
    'preserve_table_structure': True,      # 是否保持表格结构
    
    # 大小限制
    'min_chunk_size': 50,                  # 最小分块字符数
    'max_chunk_size': 8000,                # 最大分块字符数
}
```

## API参考

### 主要类

#### `EnhancedExcelChunker`
核心分块器类，提供Excel文件的分块处理功能。

```python
chunker = EnhancedExcelChunker(config)
chunks = chunker.chunk_excel(file_input, strategy="html")
```

#### `ExcelChunkingService`
服务层接口，提供完整的Excel处理功能。

```python
service = ExcelChunkingService()
result = service.chunk_excel_for_kb(file_input, kb_config)
```

#### `ExcelConfigManager`
配置管理器，提供预设配置和配置创建功能。

```python
config = ExcelConfigManager.get_preset_config("balanced")
custom_config = ExcelConfigManager.create_config(strategy="html", html_chunk_rows=8)
```

### 便利函数

- `quick_chunk_excel()`: 快速分块Excel文件
- `quick_validate_excel()`: 快速验证Excel文件
- `chunk_excel_for_knowledge_base()`: 知识库分块接口
- `validate_excel_for_kb()`: 知识库验证接口
- `preview_excel_chunks()`: 分块预览功能

## 性能优化

### 1. **分块器缓存**
服务层自动缓存分块器实例，避免重复创建。

### 2. **智能分块大小**
根据表格复杂度自动调整分块大小：
- 简单表格（≤3列）：8-20行
- 中等复杂度（4-8列）：6-15行
- 复杂表格（>8列）：4-12行

### 3. **内存优化**
- 流式处理大文件
- 及时释放临时对象
- 支持字节流输入

## 错误处理

模块提供完善的错误处理机制：

```python
try:
    result = chunk_excel_for_knowledge_base(file_input, kb_config)
except Exception as e:
    print(f"处理失败: {e}")
    
    # 验证文件格式
    validation = validate_excel_for_kb(file_input)
    if not validation['valid']:
        print(f"文件格式错误: {validation['message']}")
```

## 示例场景

### 1. 功能清单表格处理
```python
# 适合有模块/子系统结构的功能清单
kb_config = {
    'excel_preset': 'high_precision',
    'add_row_context': True,
    'preprocess_merged_cells': True
}
```

### 2. 财务报表处理
```python
# 适合数字较多的财务数据
kb_config = {
    'excel_preset': 'balanced',
    'number_formatting': True,
    'html_chunk_rows': 15
}
```

### 3. 大型数据表处理
```python
# 适合行数很多的大表格
kb_config = {
    'excel_preset': 'large_table',
    'smart_chunk_size': True,
    'preserve_table_structure': True
}
```

## 注意事项

1. **依赖库**: 需要安装 `openpyxl` 和 `pandas`
2. **文件格式**: 支持 `.xlsx`, `.xls`, `.xlsm` 格式
3. **内存使用**: 大文件处理时注意内存占用
4. **编码问题**: 自动处理常见的编码问题

## 更新日志

### v1.0.0
- 初始版本发布
- 基于ragflow实现核心分块功能
- 添加合并单元格预处理
- 提供灵活的配置管理
- 完善的错误处理和日志记录 