# MinerU SGLang 全镜像部署指南

## 概述

本项目提供了基于 SGLang 的 MinerU 完全离线部署方案。镜像包含了所有必要的模型文件，无需在运行时下载任何模型，实现真正的离线部署。

## 特性

- ✅ **完全离线部署**: 所有模型文件已预下载并打包在镜像中
- ✅ **最新版本**: 使用 MinerU v2.1.10 最新版本
- ✅ **SGLang 集成**: 基于 SGLang v0.4.7-cu124 官方镜像
- ✅ **全功能支持**: 支持 Pipeline 和 VLM 两种模式
- ✅ **高性能**: GPU 加速推理，支持 CUDA 12.4
- ✅ **智能启动**: 默认支持环境变量配置，灵活的参数调优
- ✅ **易于部署**: 一键构建和运行，多种配置方式

## 镜像构建

### 方法一：使用构建脚本（推荐）

```bash
# 执行构建脚本
./build_mineru_sglang.sh
```

### 方法二：手动构建

```bash
# 使用 ModelScope 源（推荐，国内网络友好）
docker build \
    --build-arg MINERU_VERSION=2.1.10 \
    --build-arg MODEL_SOURCE=modelscope \
    -f Dockerfile.sglang \
    -t mineru-sglang:v2.1.10-offline \
    .

# 或使用 HuggingFace 源
docker build \
    --build-arg MINERU_VERSION=2.1.10 \
    --build-arg MODEL_SOURCE=huggingface \
    -f Dockerfile.sglang \
    -t mineru-sglang:v2.1.10-offline \
    .
```

## 运行部署

### 基础运行（使用默认配置）

```bash
docker run -d \
    -p 8888:8888 \
    -p 30000:30000 \
    --name mineru-sglang \
    mineru-sglang:v2.1.10-offline
```

> **注意**: 默认启动脚本为 `start_with_env.sh`，支持环境变量配置。如需使用简单模式，可以覆盖启动命令为 `./start_services.sh`。

### GPU 加速运行（推荐）

```bash
docker run -d \
    --gpus all \
    -p 8888:8888 \
    -p 30000:30000 \
    --name mineru-sglang \
    mineru-sglang:v2.1.10-offline
```

### 带数据卷挂载

```bash
docker run -d \
    --gpus all \
    -p 8888:8888 \
    -p 30000:30000 \
    -v $(pwd)/data:/app/data \
    -v $(pwd)/output:/app/output \
    --name mineru-sglang \
    mineru-sglang:v2.1.10-offline
```

### 配置文件挂载（推荐）

通过挂载配置文件，您可以在容器外部修改配置并实时生效：

#### 1. 挂载环境变量配置文件

```bash
# 创建本地 .env 文件
cp .env.example .env
# 编辑配置文件
vim .env

# 挂载 .env 文件启动容器
docker run -d \
    --gpus all \
    -p 8888:8888 \
    -p 30000:30000 \
    -v $(pwd)/.env:/app/.env \
    -v $(pwd)/data:/app/data \
    -v $(pwd)/output:/app/output \
    --name mineru-sglang \
    mineru-sglang:v2.1.10-offline
```

#### 2. 挂载 MinerU 配置文件

```bash
# 挂载 mineru.json 配置文件
docker run -d \
    --gpus all \
    -p 8888:8888 \
    -p 30000:30000 \
    -v $(pwd)/.env:/app/.env \
    -v $(pwd)/mineru.json:/root/mineru.json \
    -v $(pwd)/data:/app/data \
    -v $(pwd)/output:/app/output \
    --name mineru-sglang \
    mineru-sglang:v2.1.10-offline
```

#### 3. 完整配置挂载（生产环境推荐）

```bash
# 创建配置目录
mkdir -p config
cp .env config/
cp mineru.json config/

# 挂载整个配置目录
docker run -d \
    --gpus all \
    -p 8888:8888 \
    -p 30000:30000 \
    -v $(pwd)/config/.env:/app/.env \
    -v $(pwd)/config/mineru.json:/root/mineru.json \
    -v $(pwd)/data:/app/data \
    -v $(pwd)/output:/app/output \
    -v $(pwd)/models:/app/models \
    --name mineru-sglang \
    mineru-sglang:v2.1.10-offline
```

> **配置文件说明**:
> - `.env`: 环境变量配置，控制 SGLang 服务器参数
> - `mineru.json`: MinerU 核心配置，包含模型路径、LaTeX 分隔符、LLM 辅助等设置
> - 配置文件修改后重启容器即可生效

### 自定义 Command 参数

您可以通过在 docker run 命令末尾添加自定义参数来覆盖默认的启动行为：

#### 1. 仅启动 API 服务（不启动 SGLang 服务器）

```bash
docker run -d \
    -p 8888:8888 \
    --name mineru-api-only \
    -e INSTALL_TYPE=core \
    mineru-sglang:v2.1.10-offline
```

#### 2. 自定义 SGLang 服务器参数

```bash
docker run -d \
    --gpus all \
    -p 8888:8888 \
    -p 30000:30000 \
    --name mineru-sglang-custom \
    mineru-sglang:v2.1.10-offline \
    bash -c "mineru-sglang-server --port 30000 --host 0.0.0.0 --tp-size 2 --mem-fraction-static 0.8 & python /app/app.py"
```

#### 3. 交互式运行（调试模式）

```bash
docker run -it \
    --gpus all \
    -p 8888:8888 \
    -p 30000:30000 \
    --name mineru-debug \
    mineru-sglang:v2.1.10-offline \
    bash
```

#### 4. 自定义启动脚本

```bash
# 创建自定义启动脚本
cat > custom_start.sh << 'EOF'
#!/bin/bash
set -euo pipefail

# 设置环境变量
export PYTHONPATH=/app
export MINERU_MODEL_SOURCE=modelscope

# 启动 SGLang 服务器（自定义参数）
echo "Starting SGLang server with custom parameters..."
mineru-sglang-server \
    --port 30000 \
    --host 0.0.0.0 \
    --tp-size 1 \
    --mem-fraction-static 0.9 \
    --enable-torch-compile \
    &

# 等待服务启动
sleep 15

# 启动 API 服务
echo "Starting MinerU Web API..."
python /app/app.py
EOF

# 使用自定义脚本运行
docker run -d \
    --gpus all \
    -p 8888:8888 \
    -p 30000:30000 \
    -v $(pwd)/custom_start.sh:/app/custom_start.sh \
    --name mineru-custom \
    mineru-sglang:v2.1.10-offline \
    bash /app/custom_start.sh
```

#### 5. 环境变量配置（推荐）

使用环境变量文件来配置 SGLang 参数，这是最灵活和方便的方法：

```bash
# 1. 创建环境变量配置文件
cp .env.example .env

# 2. 编辑配置文件（根据需要修改参数）
vim .env

# 3. 使用配置文件启动容器（默认启动方式）
docker run -d \
    --gpus all \
    -p 8888:8888 \
    -p 30000:30000 \
    -v $(pwd)/.env:/app/.env \
    --name mineru-env-config \
    mineru-sglang:v2.1.10-offline
```

> **提示**: 由于默认启动脚本已更改为 `start_with_env.sh`，无需显式指定启动命令。

**环境变量配置示例** (`.env` 文件):

```bash
# 基础配置
INSTALL_TYPE=all
MINERU_MODEL_SOURCE=modelscope
API_PORT=8888
SGLANG_PORT=30000

# SGLang 性能参数
SGLANG_TP_SIZE=2                    # 张量并行大小
SGLANG_DP_SIZE=1                    # 数据并行大小
SGLANG_MEM_FRACTION_STATIC=0.8      # 内存分配比例
SGLANG_ENABLE_TORCH_COMPILE=true    # 启用编译优化
SGLANG_MAX_SEQ_LEN=8192             # 最大序列长度
SGLANG_BATCH_SIZE=64                # 批处理大小

# 高级配置
STARTUP_WAIT_TIME=20                # 启动等待时间
LOG_LEVEL=INFO                      # 日志级别
VERBOSE=true                        # 详细日志
```

### 常见配置场景

#### 高性能配置（多 GPU）
```bash
# 适用于多 GPU 环境的高性能配置
SGLANG_TP_SIZE=4
SGLANG_MEM_FRACTION_STATIC=0.85
SGLANG_ENABLE_TORCH_COMPILE=true
SGLANG_MAX_SEQ_LEN=16384
SGLANG_BATCH_SIZE=128
```

#### 内存受限环境
```bash
# 适用于内存较小的环境
SGLANG_TP_SIZE=1
SGLANG_MEM_FRACTION_STATIC=0.7
SGLANG_MAX_SEQ_LEN=4096
SGLANG_BATCH_SIZE=32
```

#### 仅 API 服务（不启动 SGLang）
```bash
# 仅启动 MinerU API，不启动 SGLang 服务器
INSTALL_TYPE=core
```

#### 6. 直接传递环境变量

```bash
docker run -d \
    --gpus all \
    -p 8888:8888 \
    -p 30000:30000 \
    -e INSTALL_TYPE=all \
    -e MINERU_MODEL_SOURCE=huggingface \
    -e SGLANG_TP_SIZE=2 \
    -e SGLANG_MEM_FRACTION_STATIC=0.8 \
    -e SGLANG_ENABLE_TORCH_COMPILE=true \
    --name mineru-direct-env \
    mineru-sglang:v2.1.10-offline
```

> **提示**: 环境变量会被默认的 `start_with_env.sh` 脚本自动读取和应用。

## 服务端口

- **8888**: MinerU Web API 服务端口
- **30000**: SGLang 推理服务端口

## API 使用

### 健康检查

```bash
curl http://localhost:8888/health
```

### 文档解析 API

```bash
# 上传文档进行解析
curl -X POST "http://localhost:8888/parse" \
     -F "file=@document.pdf" \
     -F "mode=pipeline"
```

## 配置文件详解

### .env 环境变量配置文件

`.env` 文件用于配置 SGLang 服务器和系统运行参数，支持以下配置项：

#### 基础配置

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `INSTALL_TYPE` | `all` | 安装类型（all/core） |
| `MINERU_MODEL_SOURCE` | `modelscope` | 模型源（modelscope/huggingface） |
| `API_PORT` | `8888` | MinerU Web API 端口 |
| `SGLANG_PORT` | `30000` | SGLang 服务器端口 |

### SGLang 性能参数

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `SGLANG_HOST` | `0.0.0.0` | SGLang 服务器主机地址 |
| `SGLANG_TP_SIZE` | `1` | 张量并行大小 |
| `SGLANG_DP_SIZE` | `1` | 数据并行大小 |
| `SGLANG_MEM_FRACTION_STATIC` | `0.9` | 静态内存分配比例 |
| `SGLANG_ENABLE_TORCH_COMPILE` | `false` | 启用 torch.compile 优化 |
| `SGLANG_MAX_SEQ_LEN` | `8192` | 最大序列长度 |
| `SGLANG_BATCH_SIZE` | `64` | 批处理大小 |

### 系统配置

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `STARTUP_WAIT_TIME` | `15` | 启动等待时间（秒） |
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `VERBOSE` | `false` | 详细日志输出 |
| `MINERU_MODELS_DIR` | `/app/models` | 模型文件存储目录 |
| `HF_HUB_CACHE` | `/app/models/huggingface` | HuggingFace 缓存目录 |
| `MODELSCOPE_CACHE` | `/app/models/modelscope` | ModelScope 缓存目录 |

### mineru.json 配置文件

`mineru.json` 是 MinerU 的核心配置文件，位于 `/root/mineru.json`，包含以下配置项：

#### 配置结构

```json
{
  "bucket_info": {
    "bucket_name": "",
    "access_key": "",
    "secret_key": "",
    "endpoint": ""
  },
  "latex-delimiter-config": {
    "inline": ["$", "$"],
    "display": ["$$", "$$"]
  },
  "llm-aided-config": {
    "title_aided": {
      "api_key": "",
      "base_url": "",
      "model": "",
      "enabled": false
    }
  },
  "models-dir": {
    "pipeline": "/app/models/pipeline",
    "vlm": "/app/models/vlm"
  },
  "config_version": "1.3.0"
}
```

#### 配置项说明

| 配置项 | 说明 | 用途 |
|--------|------|------|
| `bucket_info` | S3 存储桶配置 | 用于文档存储和访问 |
| `latex-delimiter-config` | LaTeX 公式分隔符 | 控制数学公式的识别和解析 |
| `llm-aided-config` | LLM 辅助功能配置 | 启用标题辅助等 AI 增强功能 |
| `models-dir` | 模型文件路径 | 指定 Pipeline 和 VLM 模型位置 |
| `config_version` | 配置文件版本 | 用于兼容性检查和升级 |

#### 常用配置示例

**启用 LLM 标题辅助**:
```json
{
  "llm-aided-config": {
    "title_aided": {
      "api_key": "your-api-key",
      "base_url": "https://api.openai.com/v1",
      "model": "gpt-3.5-turbo",
      "enabled": true
    }
  }
}
```

**自定义 LaTeX 分隔符**:
```json
{
  "latex-delimiter-config": {
    "inline": ["\\(", "\\)"],
    "display": ["\\[", "\\]"]
  }
}
```

**自定义模型路径**:
```json
{
  "models-dir": {
    "pipeline": "/custom/models/pipeline",
    "vlm": "/custom/models/vlm"
  }
}
```

## 镜像优化说明

### 相比原版的改进

1. **版本升级**: 从 MinerU 2.1.0 升级到 2.1.10
2. **完全离线**: 所有模型文件预下载，无需运行时下载
3. **智能启动**: 默认使用 `start_with_env.sh`，支持环境变量配置
4. **构建参数化**: 支持通过构建参数自定义版本和模型源
5. **环境优化**: 完整的环境变量配置系统和缓存管理
6. **构建优化**: 优化 Docker 层缓存，提升构建效率
7. **依赖完整**: 添加了 git、wget、curl 等必要工具
8. **配置灵活**: 支持 `.env` 文件配置和运行时环境变量

### 模型文件说明

镜像包含以下预下载的模型：

**Pipeline 模型**:
- doclayout_yolo: 文档布局检测
- yolo_v8_mfd: 数学公式检测
- unimernet_small: 公式识别
- pytorch_paddle: OCR 引擎
- layout_reader: 布局阅读
- slanet_plus: 表格识别

**VLM 模型**:
- 视觉语言模型相关文件

## 故障排除

### 常见问题

1. **构建时间过长**
   - 模型下载需要时间，请耐心等待
   - 建议使用 ModelScope 源（国内网络更快）

2. **内存不足**
   - 确保 Docker 有足够内存（建议 8GB+）
   - 调整 `SGLANG_MEM_FRACTION_STATIC` 参数
   - 可以分阶段构建或使用更大的机器

3. **GPU 不可用**
   - 确保安装了 nvidia-docker2
   - 检查 CUDA 驱动版本兼容性

4. **SGLang 服务启动失败**
   - 检查 GPU 内存是否足够
   - 调整 `SGLANG_TP_SIZE` 和 `SGLANG_MEM_FRACTION_STATIC`
   - 增加 `STARTUP_WAIT_TIME` 等待时间

5. **环境变量不生效**
   - 确保 `.env` 文件格式正确（无空格、正确的键值对）
   - 检查文件挂载路径是否正确
   - 使用 `docker exec` 进入容器检查环境变量

6. **端口冲突**
   - 修改 `API_PORT` 和 `SGLANG_PORT` 环境变量
   - 确保宿主机端口未被占用

7. **配置文件挂载问题**
   - 确保配置文件路径正确且文件存在
   - 检查文件权限（建议 644 权限）
   - 验证 JSON 格式是否正确（使用 `jq` 工具验证）
   - 确保挂载路径与容器内路径匹配

8. **模型路径配置错误**
   - 检查 `mineru.json` 中的 `models-dir` 配置
   - 确保模型文件在指定路径存在
   - 验证模型文件完整性

### 日志查看

```bash
# 查看容器日志
docker logs mineru-sglang

# 实时查看日志
docker logs -f mineru-sglang

# 进入容器检查配置
docker exec -it mineru-sglang bash

# 检查环境变量
docker exec mineru-sglang env | grep -E "(SGLANG|API|MINERU)"

# 验证配置文件
docker exec mineru-sglang cat /app/.env
docker exec mineru-sglang cat /root/mineru.json

# 检查模型文件
docker exec mineru-sglang ls -la /app/models/

# 验证 JSON 配置格式
docker exec mineru-sglang jq . /root/mineru.json
```

## 性能优化建议

1. **使用 GPU**: 启用 GPU 加速可显著提升处理速度
2. **内存配置**: 为容器分配足够内存（推荐 8GB+）
3. **存储优化**: 使用 SSD 存储可提升 I/O 性能
4. **网络配置**: 如需外网访问，配置适当的防火墙规则

## 更新说明

- 删除了基础版 Dockerfile（根据用户需求保留）
- 优化了 Dockerfile.sglang 为完全离线部署版本
- 添加了构建脚本和详细文档
- 升级到 MinerU 最新版本 2.1.10