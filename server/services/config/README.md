# KnowFlow 业务配置系统

这个配置系统将业务逻辑配置与环境部署配置分离，提供统一的配置管理。

## 配置文件结构

```
server/
├── config/
│   ├── __init__.py              # 配置模块导出
│   ├── business_config.py       # 配置管理器
│   ├── settings.yaml            # 业务配置文件
│   └── docker-settings.yaml    # Docker环境配置覆盖
├── .env                         # 环境部署配置（数据库连接等）
└── docker-compose.yml
```

## 配置层次

1. **默认配置**: 代码中的默认值
2. **YAML配置文件**: `settings.yaml` 或 `docker-settings.yaml`
3. **环境变量覆盖**: 特定的环境变量可以覆盖配置文件中的设置

## 使用方法

### 基本使用

```python
from config import get_business_config, get_document_config, get_excel_config

# 获取完整配置
config = get_business_config()
print(config.environment)  # development 或 production

# 获取特定模块配置
doc_config = get_document_config()
print(doc_config.chunk_method)  # smart

excel_config = get_excel_config()
print(excel_config.default_strategy)  # html
```

### 在Excel处理中使用

```python
from services.knowledgebases.excel_parse import ExcelChunkConfig

# 自动从全局配置获取
config = ExcelChunkConfig.from_global_config()

# 仍支持传统方式
config = ExcelConfigManager.get_default_config()
```

### 在文档处理中使用

```python
from config import get_document_config

config = get_document_config()

# 检查是否为开发模式
if config.dev_mode:
    # 跳过MinerU处理
    pass

# 获取分块配置
chunk_size = config.default_chunk_size
cleanup_files = config.cleanup_temp_files
```

## 环境变量映射

以下环境变量可以覆盖配置文件中的设置：

### 文档处理
- `CHUNK_METHOD` → `document_processing.chunk_method`
- `CLEANUP_TEMP_FILES` → `document_processing.cleanup_temp_files`
- `DEV_MODE` → `document_processing.dev_mode`
- `MINERU_CACHE_TYPE` → `document_processing.mineru_cache_type`
- `DEFAULT_CHUNK_SIZE` → `document_processing.default_chunk_size`

### Excel处理
- `EXCEL_DEFAULT_STRATEGY` → `excel_processing.default_strategy`
- `EXCEL_HTML_CHUNK_ROWS` → `excel_processing.html_chunk_rows`
- `EXCEL_PREPROCESS_MERGED` → `excel_processing.preprocess_merged_cells`
- `EXCEL_NUMBER_FORMATTING` → `excel_processing.number_formatting`
- `EXCEL_ADD_ROW_CONTEXT` → `excel_processing.add_row_context`

### 全局配置
- `ENVIRONMENT` → `environment`
- `DEBUG` → `debug`

## Docker 部署

### Docker Compose 示例

```yaml
version: '3.8'
services:
  knowflow-server:
    build: .
    environment:
      # 环境部署配置
      - RAGFLOW_API_KEY=${RAGFLOW_API_KEY}
      - DATABASE_HOST=${DATABASE_HOST}
      
      # 标识Docker环境
      - DOCKER_MODE=true
      
      # 业务配置覆盖
      - CHUNK_METHOD=advanced
      - EXCEL_DEFAULT_STRATEGY=auto
      - CLEANUP_TEMP_FILES=true
    volumes:
      # 可选：挂载配置文件以支持动态修改
      - ./config:/app/config
```

### 自动配置选择

- `DOCKER_MODE=true`: 自动加载 `docker-settings.yaml`
- `DOCKER_MODE=false` 或未设置: 加载 `settings.yaml`

## 配置验证

配置系统包含自动验证：

```python
config = get_business_config()
if config.validate():
    print("配置有效")
else:
    print("配置存在问题")
```

## 迁移指南

### 从环境变量迁移

**原来 (.env)**:
```bash
CHUNK_METHOD=smart
CLEANUP_TEMP_FILES=true
EXCEL_HTML_CHUNK_ROWS=15
```

**现在 (settings.yaml)**:
```yaml
document_processing:
  chunk_method: "smart"
  cleanup_temp_files: true

excel_processing:
  html_chunk_rows: 15
```

### 向后兼容性

现有的环境变量仍然有效，可以覆盖YAML配置：

```bash
# 这样仍然工作
export CHUNK_METHOD=advanced
export EXCEL_DEFAULT_STRATEGY=row
```

## 配置最佳实践

1. **开发环境**: 修改 `settings.yaml`
2. **生产环境**: 使用 `docker-settings.yaml` + 环境变量覆盖
3. **敏感信息**: 仍然使用 `.env` 文件（数据库密码等）
4. **业务逻辑**: 使用 YAML 配置文件

## 故障排除

### 配置加载失败

```python
# 检查配置文件是否存在
import os
from pathlib import Path

config_file = Path("config/settings.yaml")
if not config_file.exists():
    print(f"配置文件不存在: {config_file}")

# 检查导入
try:
    from config import get_business_config
    config = get_business_config()
    print("配置加载成功")
except ImportError as e:
    print(f"配置模块导入失败: {e}")
```

### 环境变量不生效

确保环境变量名称正确，参考上面的映射表。

### Docker 环境配置

确保设置了 `DOCKER_MODE=true` 以自动加载 Docker 专用配置。

# 配置系统说明

本目录 (`server/config`) 是 KnowFlow 服务端的统一业务配置中心。

## 核心文件

- `settings.yaml`: 系统的核心配置文件，包含所有业务逻辑的默认参数。
- `config_loader.py`: 配置加载器，负责读取、合并和验证配置。
- `business_config.py`: 使用 Pydantic 定义的配置模型，确保配置的类型安全和结构正确。

## 配置加载流程

1.  **加载YAML文件**: 程序启动时，`config_loader` 会首先加载 `settings.yaml` 作为基础配置。
2.  **环境变量覆盖**: 加载器会检查特定前缀的环境变量（如 `KNOWFLOW_`），并用它们的值覆盖YAML中的默认配置。这为在 Docker 或其他生产环境中动态调整配置提供了灵活性。
3.  **Pydantic验证**: 加载并合并后的配置会通过 `business_config.py` 中定义的Pydantic模型进行验证。任何类型不匹配或缺失的必需字段都会导致程序启动失败，从而避免了因配置错误引发的运行时问题。
4.  **全局访问**: 验证后的配置对象（如 `APP_CONFIG`, `EXCEL_CONFIG`）会作为单例在整个应用中提供，任何需要配置的模块都可以直接从 `server.config` 导入使用。

## 环境变量覆盖规则

- **前缀**: `KNOWFLOW_`
- **分隔符**: 使用双下划线 `__` 来表示层级关系。

### 示例

要覆盖 `settings.yaml` 中的 `app.dev_mode`，你需要设置以下环境变量：

```bash
export KNOWFLOW_APP__DEV_MODE=true
```

要覆盖 `excel.html_chunk_rows`，你需要设置：

```bash
export KNOWFLOW_EXCEL__HTML_CHUNK_ROWS=12
```

这种设计将业务配置与环境部署（如数据库密码、API Key等，它们应存在于 `.env` 文件中）清晰地分离开来，使得配置管理更加结构化和安全。