# MinerU FastAPI 适配器使用指南

本适配器将原有的 MinerU Python API 调用方式完全改造为通过 FastAPI 服务访问，提供更高的性能和更好的可扩展性。

## 📋 功能特性

- ✅ **纯 FastAPI 模式**：完全基于 FastAPI 服务，不依赖原生 Python API
- ✅ **多后端支持**：支持 pipeline、vlm-transformers、vlm-sglang-engine、vlm-sglang-client
- ✅ **自动配置管理**：支持环境变量和配置文件
- ✅ **完整参数兼容**：保持与原有接口相同的参数结构
- ✅ **进度回调支持**：保持原有的进度更新机制
- ✅ **错误处理**：完善的错误处理和日志记录

## 🚀 快速开始

### 1. 启动 FastAPI 服务

首先确保 MinerU FastAPI 服务正在运行：

```bash
# 方式1：直接启动
cd web_api
python app.py

# 方式2：Docker 启动
docker run -p 8888:8888 mineru-api-full

# 方式3：使用已有的测试服务
python web_api/test_backends.py --base-url http://localhost:8888
```

### 2. 配置环境变量

```bash
# 基础配置
export MINERU_FASTAPI_URL="http://localhost:8888"
export MINERU_FASTAPI_BACKEND="pipeline"
export MINERU_FASTAPI_TIMEOUT="300"

# Pipeline 后端配置
export MINERU_PARSE_METHOD="auto"
export MINERU_LANG="ch"
export MINERU_FORMULA_ENABLE="true"
export MINERU_TABLE_ENABLE="true"

# VLM 后端配置 (如果使用 vlm-sglang-client)
export MINERU_VLM_SERVER_URL="http://localhost:30000"
```

### 3. 使用适配器

```python
from server.services.knowledgebases.mineru_parse.process_pdf import (
    process_pdf_entry,
    process_pdf_with_custom_backend,
    configure_fastapi
)

# 方式1：使用默认配置
def progress_callback(progress, message):
    print(f"进度 {progress*100:.1f}%: {message}")

result = process_pdf_entry(
    doc_id="doc_001",
    pdf_path="/path/to/document.pdf",
    kb_id="kb_001",
    update_progress=progress_callback
)

# 方式2：指定特定后端
result = process_pdf_with_custom_backend(
    doc_id="doc_002", 
    pdf_path="/path/to/document.pdf",
    kb_id="kb_001",
    update_progress=progress_callback,
    backend="vlm-transformers"  # 指定后端
)

# 方式3：动态配置
configure_fastapi(
    base_url="http://192.168.1.100:8888",
    backend="pipeline"
)
```

## ⚙️ 配置管理

### 环境变量配置

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| `MINERU_FASTAPI_URL` | `http://localhost:8888` | FastAPI 服务地址 |
| `MINERU_FASTAPI_BACKEND` | `pipeline` | 默认后端类型 |
| `MINERU_FASTAPI_TIMEOUT` | `300` | 请求超时时间（秒） |
| `MINERU_PARSE_METHOD` | `auto` | 解析方法 (pipeline) |
| `MINERU_LANG` | `ch` | 语言设置 (pipeline) |
| `MINERU_FORMULA_ENABLE` | `true` | 公式解析开关 (pipeline) |
| `MINERU_TABLE_ENABLE` | `true` | 表格解析开关 (pipeline) |
| `MINERU_VLM_SERVER_URL` | `None` | VLM 服务地址 (vlm-sglang-client) |

### 代码配置

```python
from server.services.knowledgebases.mineru_parse.adapter_config import (
    get_config, 
    configure_fastapi,
    set_backend
)

# 获取当前配置
config = get_config()
config.print_config()

# 更新配置
configure_fastapi(
    base_url="http://localhost:8888",
    backend="vlm-transformers"
)

# 设置后端
set_backend("pipeline")
```

## 🔧 支持的后端

### 1. Pipeline 模式 (推荐)
```python
# 使用 pipeline 后端
result = process_pdf_with_custom_backend(
    doc_id="test",
    pdf_path="document.pdf", 
    kb_id="kb001",
    update_progress=callback,
    backend="pipeline",
    parse_method="auto",
    lang="ch",
    formula_enable=True,
    table_enable=True
)
```

### 2. VLM-Transformers 模式
```python
# 使用 vlm-transformers 后端
result = process_pdf_with_custom_backend(
    doc_id="test",
    pdf_path="document.pdf",
    kb_id="kb001", 
    update_progress=callback,
    backend="vlm-transformers"
)
```

### 3. VLM-SGLang 模式
```python
# Engine 模式
result = process_pdf_with_custom_backend(
    doc_id="test",
    pdf_path="document.pdf",
    kb_id="kb001",
    update_progress=callback,
    backend="vlm-sglang-engine"
)

# Client 模式 (需要 server_url)
result = process_pdf_with_custom_backend(
    doc_id="test", 
    pdf_path="document.pdf",
    kb_id="kb001",
    update_progress=callback,
    backend="vlm-sglang-client",
    server_url="http://localhost:30000"
)
```

## 🧪 测试和调试

### 1. 运行测试脚本

```bash
cd server/services/knowledgebases/mineru_parse
python test_fastapi_adapter.py
```

### 2. 测试连接

```python
from server.services.knowledgebases.mineru_parse.fastapi_adapter import test_adapter_connection

# 测试连接
result = test_adapter_connection("http://localhost:8888")
print(f"连接状态: {result['status']}")
print(f"消息: {result['message']}")
```

### 3. 调试信息

```python
from server.services.knowledgebases.mineru_parse.process_pdf import get_processing_info

# 获取处理信息
info = get_processing_info()
print(f"处理模式: {info['mode']}")
print(f"服务地址: {info['url']}")
print(f"后端类型: {info['backend']}")
```

## 📊 返回结果格式

```python
# 成功返回的结果格式
{
    "success": True,
    "chunk_count": 42,
    "fastapi_result": {
        "md_content": "# 文档标题\n\n文档内容...",
        "content_list": [...],
        "info": {...},
        "_adapter_info": {
            "backend_used": "pipeline",
            "file_processed": "document.pdf",
            "adapter_version": "2.0.0",
            "processing_mode": "fastapi_only"
        }
    },
    "backend_used": "pipeline"
}
```

## ⚠️ 注意事项

1. **服务依赖**：确保 FastAPI 服务正在运行且可访问
2. **超时设置**：大文件处理时适当增加超时时间
3. **后端选择**：根据硬件配置选择合适的后端
4. **错误处理**：处理过程中的错误会通过异常抛出

## 🔄 迁移指南

### 从原生 Python API 迁移

**原有代码：**
```python
from server.services.knowledgebases.mineru_parse.mineru_test import process_pdf_with_minerU

result = process_pdf_with_minerU(pdf_path, update_progress)
```

**新代码：**
```python
from server.services.knowledgebases.mineru_parse.process_pdf import process_pdf_entry

result = process_pdf_entry(doc_id, pdf_path, kb_id, update_progress)
```

### 配置迁移

**原有环境变量：**
```bash
MINERU_USE_FASTAPI=true
MINERU_DEFAULT_BACKEND=pipeline
```

**新环境变量：**
```bash
MINERU_FASTAPI_URL=http://localhost:8888
MINERU_FASTAPI_BACKEND=pipeline
```

## 🐛 故障排除

### 1. 连接失败
- 检查 FastAPI 服务是否启动
- 验证服务地址和端口
- 检查防火墙设置

### 2. 处理超时
- 增加 `MINERU_FASTAPI_TIMEOUT` 值
- 检查网络连接稳定性
- 确认文件大小是否合理

### 3. 后端错误
- 检查后端类型是否支持
- 确认后端服务正常运行
- 查看 FastAPI 服务日志

## 📞 技术支持

如果遇到问题，请：

1. 查看 FastAPI 服务日志
2. 运行测试脚本进行诊断
3. 检查配置是否正确
4. 提供详细的错误信息和日志 