# MinerU Web API

基于 MinerU 官方 API 重新设计的 FastAPI 服务，完全兼容官方接口规范。

## 特性

- ✅ **完全兼容官方 API**: 基于 MinerU 2.1.10+ 官方 `aio_do_parse` 函数
- ✅ **多文件支持**: 支持批量上传和处理多个文件
- ✅ **多后端支持**: pipeline, vlm-transformers, vlm-sglang-engine, vlm-sglang-client
- ✅ **灵活输出**: 支持 Markdown、中间 JSON、模型输出、内容列表、图片等
- ✅ **健康检查**: 自动检查 SGLang 服务器状态
- ✅ **错误处理**: 完善的错误处理和用户友好的错误信息

## 安装

```bash
# 安装依赖
pip install -r requirements.txt

# 或者手动安装核心依赖
pip install "mineru[pipeline]>=2.1.10" fastapi uvicorn python-multipart requests loguru
```

## 运行

```bash
# 启动 API 服务
python app.py

# 或使用 uvicorn
uvicorn app:app --host 0.0.0.0 --port 8888
```

服务将在 `http://localhost:8888` 启动，API 文档可通过 `http://localhost:8888/docs` 访问。

## API 接口

### POST /file_parse

解析文件（PDF、图片）并返回结构化结果。

**参数:**

- `files`: 要解析的文件列表（支持 PDF、PNG、JPG、JPEG、BMP、TIFF）
- `output_dir`: 输出目录（默认: `./output`）
- `lang_list`: 语言列表（默认: `["ch"]`）
- `backend`: 解析后端（默认: `pipeline`）
  - `pipeline`: 标准管道模式
  - `vlm-transformers`: VLM Transformers 模式
  - `vlm-sglang-engine`: VLM SGLang 引擎模式
  - `vlm-sglang-client`: VLM SGLang 客户端模式
- `parse_method`: 解析方法（默认: `auto`）
- `formula_enable`: 是否启用公式解析（默认: `true`）
- `table_enable`: 是否启用表格解析（默认: `true`）
- `server_url`: SGLang 服务器地址（vlm-sglang-client 模式必需）
- `return_md`: 是否返回 Markdown 内容（默认: `true`）
- `return_middle_json`: 是否返回中间 JSON（默认: `false`）
- `return_model_output`: 是否返回模型输出（默认: `false`）
- `return_content_list`: 是否返回内容列表（默认: `false`）
- `return_images`: 是否返回图片（默认: `false`）
- `start_page_id`: 起始页码（默认: `0`）
- `end_page_id`: 结束页码（默认: `99999`）

**示例请求:**

```bash
# 基础用法 - Pipeline 模式
curl -X POST "http://localhost:8888/file_parse" \
  -F "files=@document.pdf" \
  -F "backend=pipeline" \
  -F "return_md=true"

# VLM SGLang 客户端模式
curl -X POST "http://localhost:8888/file_parse" \
  -F "files=@document.pdf" \
  -F "backend=vlm-sglang-client" \
  -F "server_url=http://localhost:30000" \
  -F "return_md=true" \
  -F "return_content_list=true"

# 多文件批量处理
curl -X POST "http://localhost:8888/file_parse" \
  -F "files=@doc1.pdf" \
  -F "files=@doc2.pdf" \
  -F "files=@image.png" \
  -F "backend=pipeline" \
  -F "return_md=true" \
  -F "return_images=true"
```

**响应格式:**

```json
{
  "results": [
    {
      "filename": "document.pdf",
      "md_content": "# 文档标题\n\n文档内容...",
      "content_list": [...],
      "images": {...},
      "backend": "pipeline"
    }
  ],
  "total_files": 1,
  "successful_files": 1
}
```

## 环境变量

- `SGLANG_SERVER_URL`: SGLang 服务器默认地址
- `MINERU_VLM_SERVER_URL`: MinerU VLM 服务器地址（备用）
- `MINERU_MODEL_SOURCE`: 模型源（modelscope/huggingface）

## 与官方 API 的兼容性

本 API 完全基于 MinerU 官方的 `aio_do_parse` 函数构建，确保：

1. **接口兼容**: 参数名称和行为与官方 API 一致
2. **功能完整**: 支持所有官方后端和解析选项
3. **结果一致**: 输出格式与官方 API 保持一致
4. **性能优化**: 利用官方优化的解析逻辑

## 故障排除

### SGLang 服务器连接问题

如果使用 `vlm-sglang-client` 后端时遇到连接问题：

1. 确保 SGLang 服务正在运行：
   ```bash
   curl http://localhost:30000/health
   ```

2. 检查防火墙和端口设置

3. 如果使用 Docker，确保使用完整版镜像：
   ```bash
   docker run -p 30000:30000 -p 8888:8888 your-mineru-image
   ```

### 模型下载问题

如果遇到模型下载问题，可以设置模型源：

```bash
export MINERU_MODEL_SOURCE=modelscope  # 或 huggingface
```

## 更新日志

### v2.1.10+
- 基于 MinerU 官方 API 重新设计
- 完全兼容官方接口规范
- 支持多文件批量处理
- 改进错误处理和用户体验
- 添加 SGLang 服务器健康检查
- 优化依赖管理