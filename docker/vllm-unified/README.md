# vLLM 统一服务部署指南

## 概述

vLLM 统一服务是 KnowFlow 项目的核心组件，提供了 Chat、Embedding 和 Rerank 三种大模型服务的统一部署方案。通过 Docker 容器化技术，实现了大模型的离线部署和统一管理。

## 功能特性

- **多模型统一管理**: 同时支持对话、嵌入和重排序模型
- **离线部署**: 支持完全离线环境下的模型部署
- **GPU 加速**: 充分利用 NVIDIA GPU 资源
- **高可用性**: 内置健康检查和故障恢复机制
- **监控支持**: 集成 Prometheus 和 Grafana 监控
- **负载均衡**: 支持 Nginx 反向代理

## 系统要求

### 硬件要求
- **GPU**: NVIDIA GPU (推荐 RTX 4090 或更高)
- **显存**: 至少 24GB (推荐 48GB+)
- **内存**: 至少 32GB
- **存储**: 至少 100GB 可用空间

### 软件要求
- Docker 20.10+
- Docker Compose 2.0+
- NVIDIA Docker Runtime
- Linux 操作系统 (推荐 Ubuntu 20.04+)

## 快速开始

### 1. 环境准备

```bash
# 检查 Docker 安装
docker --version
docker-compose --version

# 检查 NVIDIA Docker 支持
docker run --rm --gpus all nvidia/cuda:12.1-base-ubuntu22.04 nvidia-smi
```

### 2. 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑环境变量
vim .env
```

主要配置项：
```bash
# Hugging Face Token (可选，用于下载私有模型)
HF_TOKEN=your_huggingface_token

# GPU 设备
CUDA_VISIBLE_DEVICES=0,1

# 服务端口
VLLM_ROUTER_PORT=8000
VLLM_CHAT_PORT=8001
VLLM_EMBEDDING_PORT=8002
VLLM_RERANK_PORT=8003
```

### 3. 构建镜像

#### 方式一：使用构建脚本（推荐）

```bash
# 默认构建（包含模型下载）
./build.sh

# 自定义构建
./build.sh --tag v1.0.0 --skip-models

# 查看构建选项
./build.sh --help
```

#### 方式二：手动构建

```bash
# 构建镜像（包含模型下载）
docker build --build-arg DOWNLOAD_MODELS=true -t knowflow/vllm-unified:latest .

# 构建镜像（不下载模型）
docker build --build-arg DOWNLOAD_MODELS=false -t knowflow/vllm-unified:latest .
```

### 4. 启动服务

#### 方式一：使用部署脚本（推荐）

```bash
# 启动服务
./deploy.sh start

# 查看服务状态
./deploy.sh status

# 查看服务日志
./deploy.sh logs

# 停止服务
./deploy.sh stop
```

#### 方式二：使用 Docker Compose

```bash
# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f vllm-unified

# 停止服务
docker-compose down
```

### 5. 验证服务

```bash
# 检查服务健康状态
curl http://localhost:8000/health

# 测试 Chat 模型
curl -X POST http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer token-abc123" \
  -d '{
    "model": "Qwen2.5-32B-Instruct",
    "messages": [
      {"role": "user", "content": "你好"}
    ]
  }'

# 测试 Embedding 模型
curl -X POST http://localhost:8002/v1/embeddings \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer token-abc123" \
  -d '{
    "model": "bge-m3",
    "input": "测试文本"
  }'
```

## 配置说明

### 模型配置 (config/models.json)

```json
{
  "models": {
    "chat": {
      "name": "Qwen2.5-32B-Instruct",
      "path": "/app/models/chat",
      "type": "chat",
      "port": 8001,
      "gpu_memory_utilization": 0.8,
      "max_model_len": 32768,
      "tensor_parallel_size": 2,
      "dtype": "auto"
    },
    "embedding": {
      "name": "bge-m3",
      "path": "/app/models/embedding",
      "type": "embedding",
      "port": 8002,
      "gpu_memory_utilization": 0.3,
      "max_model_len": 8192,
      "tensor_parallel_size": 1,
      "dtype": "auto"
    },
    "rerank": {
      "name": "bge-reranker-v2-m3",
      "path": "/app/models/rerank",
      "type": "rerank",
      "port": 8003,
      "gpu_memory_utilization": 0.2,
      "max_model_len": 8192,
      "tensor_parallel_size": 1,
      "dtype": "auto"
    }
  }
}
```

### vLLM 引擎配置 (config/vllm_config.yaml)

详细的 vLLM 引擎参数配置，包括：
- 服务器设置
- 模型并行配置
- 调度器参数
- 缓存配置
- 日志设置

## 高级用法

### 自定义模型

1. 修改 `config/models.json` 配置文件
2. 将模型文件放置到对应路径
3. 重新构建镜像或挂载模型目录

```bash
# 挂载本地模型目录
docker run -d \
  --name vllm-unified \
  --gpus all \
  -p 8000-8003:8000-8003 \
  -v /path/to/your/models:/app/models \
  zxwei/vllm-unified:latest
```

### 监控部署

启用监控服务：

```bash
# 启动包含监控的完整服务
docker-compose --profile monitoring up -d

# 访问监控界面
# Prometheus: http://localhost:9090
# Grafana: http://localhost:3000 (admin/admin123)
```

### 负载均衡

启用 Nginx 反向代理：

```bash
# 启动包含 Nginx 的服务
docker-compose --profile nginx up -d

# 通过 Nginx 访问服务
curl http://localhost/v1/chat/completions
```

## 离线部署

### 构建离线包

```bash
# 构建完整离线包
./build_offline_package.sh

# 自定义离线包
./build_offline_package.sh --version v1.0.0 --output /tmp/offline
```

### 部署离线包

1. 将离线包传输到目标服务器
2. 解压离线包
3. 加载 Docker 镜像
4. 启动服务

```bash
# 解压离线包
tar -xzf knowflow-offline-*.tar.gz
cd knowflow-offline

# 加载镜像
./scripts/load_images.sh

# 启动服务
./scripts/deploy.sh start
```

## 故障排除

### 常见问题

1. **GPU 内存不足**
   - 调整 `gpu_memory_utilization` 参数
   - 减少 `tensor_parallel_size`
   - 使用更小的模型

2. **服务启动失败**
   - 检查 GPU 驱动和 NVIDIA Docker
   - 查看容器日志：`docker logs vllm-unified`
   - 验证模型文件完整性

3. **推理速度慢**
   - 增加 GPU 数量
   - 调整批处理大小
   - 优化模型量化

### 日志查看

```bash
# 查看服务日志
docker-compose logs -f vllm-unified

# 查看特定时间段日志
docker-compose logs --since="1h" vllm-unified

# 查看错误日志
docker-compose logs vllm-unified | grep ERROR
```

### 性能调优

1. **GPU 配置优化**
   ```bash
   # 设置 GPU 性能模式
   nvidia-smi -pm 1
   nvidia-smi -ac 1215,1410
   ```

2. **内存优化**
   ```yaml
   # docker-compose.yml
   deploy:
     resources:
       limits:
         memory: 32G
       reservations:
         memory: 16G
   ```

3. **网络优化**
   ```yaml
   # 使用主机网络模式
   network_mode: host
   ```

## API 文档

### Chat API

```bash
POST http://localhost:8001/v1/chat/completions
Content-Type: application/json
Authorization: Bearer token-abc123

{
  "model": "Qwen2.5-32B-Instruct",
  "messages": [
    {"role": "user", "content": "你好"}
  ],
  "temperature": 0.7,
  "max_tokens": 1000
}
```

### Embedding API

```bash
POST http://localhost:8002/v1/embeddings
Content-Type: application/json
Authorization: Bearer token-abc123

{
  "model": "bge-m3",
  "input": "要嵌入的文本"
}
```

### Rerank API

```bash
POST http://localhost:8003/v1/rerank
Content-Type: application/json
Authorization: Bearer token-abc123

{
  "model": "bge-reranker-v2-m3",
  "query": "查询文本",
  "documents": ["文档1", "文档2", "文档3"]
}
```

## 更新和维护

### 更新服务

```bash
# 拉取最新镜像
docker pull knowflow/vllm-unified:latest

# 重启服务
./deploy.sh restart
```

### 备份数据

```bash
# 备份模型数据
docker run --rm -v vllm_models:/data -v $(pwd):/backup alpine tar czf /backup/models-backup.tar.gz -C /data .

# 备份配置文件
tar czf config-backup.tar.gz config/
```

### 清理资源

```bash
# 清理未使用的镜像
docker image prune -f

# 清理未使用的卷
docker volume prune -f

# 完全清理
./deploy.sh clean --force
```

## 许可证

本项目基于 Apache 2.0 许可证开源。

## 支持

如有问题或建议，请提交 Issue 或联系开发团队。

---

**注意**: 首次启动可能需要较长时间来下载和加载模型，请耐心等待。建议在生产环境中使用离线部署方式以提高稳定性。