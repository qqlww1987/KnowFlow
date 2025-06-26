# MinerU FastAPI 客户端配置指南

## 📖 配置说明

本配置用于 KnowFlow 中的 **MinerU HTTP 客户端适配器**，用于调用独立的 MinerU FastAPI 服务。

**重要说明**：
- 这里配置的是 **HTTP 客户端** 的请求参数
- **不是** MinerU FastAPI 服务本身的配置
- MinerU FastAPI 服务有自己独立的配置管理（位于 `web_api/` 目录）

## 🎯 配置范围

### 包含的配置项（客户端相关）
- **连接配置**：FastAPI 服务地址、超时时间
- **请求参数**：默认后端、Pipeline 参数、VLM 参数

### 不包含的配置项（服务端内部）
- ❌ Docker 部署配置（属于 web_api 服务）
- ❌ 模型下载和缓存配置（属于 web_api 服务）
- ❌ 性能优化配置（属于 web_api 服务）
- ❌ 日志和输出配置（属于 web_api 服务）

## ⚙️ 配置方法

### 方法1: 修改 settings.yaml

编辑 `server/services/config/settings.yaml`：

```yaml
mineru:
  # FastAPI 客户端配置
  fastapi:
    url: "http://localhost:8888"  # MinerU FastAPI 服务地址
    timeout: 300                  # 请求超时时间（秒）
  
  # 默认后端类型
  default_backend: "pipeline"
  
  # Pipeline 后端请求参数
  pipeline:
    parse_method: "auto"          # 解析方法: auto, txt, ocr
    lang: "ch"                    # 文档语言
    formula_enable: true          # 是否启用公式解析
    table_enable: true            # 是否启用表格解析
  
  # VLM 后端配置
  vlm:
    sglang:
      server_url: "http://localhost:30000"  # SGLang 服务器地址
```

### 方法2: 环境变量覆盖

```bash
# 连接配置
export MINERU_FASTAPI_URL="http://192.168.1.100:8888"
export MINERU_FASTAPI_TIMEOUT="600"

# 默认后端
export MINERU_FASTAPI_BACKEND="vlm-transformers"

# Pipeline 参数
export MINERU_PARSE_METHOD="ocr"
export MINERU_LANG="en"
export MINERU_FORMULA_ENABLE="false"
export MINERU_TABLE_ENABLE="true"

# VLM 参数
export MINERU_VLM_SERVER_URL="http://192.168.1.200:30000"
export SGLANG_SERVER_URL="http://192.168.1.200:30000"  # 兼容旧变量
```

### 方法3: KnowFlow 环境变量前缀

```bash
# 使用 KNOWFLOW_ 前缀（推荐用于生产环境）
export KNOWFLOW_MINERU__FASTAPI__URL="http://192.168.1.100:8888"
export KNOWFLOW_MINERU__DEFAULT_BACKEND="pipeline"
export KNOWFLOW_MINERU__VLM__SGLANG__SERVER_URL="http://localhost:30000"
```

## 📚 配置参考

### 连接配置

| 配置项 | 默认值 | 环境变量 | 说明 |
|--------|--------|----------|------|
| `fastapi.url` | `http://localhost:8888` | `MINERU_FASTAPI_URL` | MinerU FastAPI 服务地址 |
| `fastapi.timeout` | `300` | `MINERU_FASTAPI_TIMEOUT` | HTTP 请求超时时间（秒） |

### 后端配置

| 配置项 | 默认值 | 环境变量 | 说明 |
|--------|--------|----------|------|
| `default_backend` | `pipeline` | `MINERU_FASTAPI_BACKEND` | 默认后端类型 |

**支持的后端类型**：
- `pipeline` - 通用解析，兼容性最好
- `vlm-transformers` - 基于 Transformers 的 VLM
- `vlm-sglang-engine` - SGLang 引擎模式
- `vlm-sglang-client` - SGLang 客户端模式

### Pipeline 后端参数

| 配置项 | 默认值 | 环境变量 | 说明 |
|--------|--------|----------|------|
| `pipeline.parse_method` | `auto` | `MINERU_PARSE_METHOD` | 解析方法：auto, txt, ocr |
| `pipeline.lang` | `ch` | `MINERU_LANG` | 文档语言（OCR优化） |
| `pipeline.formula_enable` | `true` | `MINERU_FORMULA_ENABLE` | 是否解析公式 |
| `pipeline.table_enable` | `true` | `MINERU_TABLE_ENABLE` | 是否解析表格 |

### VLM 后端参数

| 配置项 | 默认值 | 环境变量 | 说明 |
|--------|--------|----------|------|
| `vlm.sglang.server_url` | `http://localhost:30000` | `MINERU_VLM_SERVER_URL`, `SGLANG_SERVER_URL` | SGLang 服务地址 |

## 🔧 使用示例

### 基础使用

```python
from server.services.knowledgebases.mineru_parse.process_pdf import process_pdf_entry

# 使用默认配置
result = process_pdf_entry(
    doc_id="doc_001",
    pdf_path="/path/to/document.pdf",
    kb_id="kb_001",
    update_progress=lambda p, m: print(f"{p*100:.1f}%: {m}")
)
```

### 指定后端

```python
from server.services.knowledgebases.mineru_parse.process_pdf import process_pdf_with_custom_backend

# 使用特定后端
result = process_pdf_with_custom_backend(
    doc_id="doc_002",
    pdf_path="/path/to/document.pdf",
    kb_id="kb_001",
    update_progress=lambda p, m: print(f"{p*100:.1f}%: {m}"),
    backend="vlm-transformers"  # 指定后端
)
```

### 动态配置

```python
from server.services.knowledgebases.mineru_parse.process_pdf import configure_fastapi

# 运行时更改配置
configure_fastapi(
    base_url="http://192.168.1.100:8888",
    backend="pipeline"
)
```

## 🧪 配置测试

### 测试连接

```python
from server.services.knowledgebases.mineru_parse.fastapi_adapter import test_adapter_connection

result = test_adapter_connection("http://localhost:8888")
print(f"连接状态: {result['status']}")
print(f"消息: {result['message']}")
```

### 查看当前配置

```python
from server.services.knowledgebases.mineru_parse.adapter_config import get_config

config = get_config()
config.print_config()
```

### 运行完整测试

```bash
cd server/services/knowledgebases/mineru_parse
python test_fastapi_adapter.py
```

## ⚠️ 注意事项

1. **服务依赖**：确保 MinerU FastAPI 服务正在运行且可访问
2. **网络配置**：注意防火墙和网络访问权限
3. **超时设置**：大文件处理时适当增加超时时间
4. **后端兼容性**：确保 FastAPI 服务支持所选择的后端
5. **配置优先级**：环境变量 > settings.yaml 配置

## 🔗 相关文档

- [MinerU FastAPI 适配器使用指南](README_FASTAPI.md)
- [web_api 服务配置](../../web_api/README.md)
- [KnowFlow 配置系统](../../services/config/README.md) 