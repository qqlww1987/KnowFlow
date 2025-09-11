# Dots OCR 部署指南

Dots OCR 是一个高性能的光学字符识别服务，基于 VLLM 和 OpenAI API 兼容接口。

## 前置要求

- Docker 和 Docker Compose
- NVIDIA GPU 和 NVIDIA Container Toolkit
- Python 3.8+ 以及以下依赖：
  ```bash
  pip install modelscope huggingface_hub
  ```

## 一键部署

### 快速开始

```bash
cd knowflow/dots
./deploy.sh
```

就这么简单！脚本会自动完成以下步骤：

1. 下载模型文件（约 10GB，首次需要较长时间）
2. 检查 GPU 可用性
3. 启动 OCR 服务
4. 验证服务状态

### 部署完成后

- **服务地址**: http://localhost:8000
- **模型名称**: dotsocr-model

### 常用命令

```bash
# 测试服务
curl -X GET http://localhost:8000/v1/models

# 查看服务状态
docker compose ps

# 查看日志
docker compose logs -f dots-ocr-server

# 停止服务
docker compose down

# 重启服务
docker compose restart
```

## API 使用

```bash
# OCR 识别示例
curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "dotsocr-model",
    "messages": [
      {
        "role": "user", 
        "content": [
          {
            "type": "text",
            "text": "请识别图片中的文字"
          },
          {
            "type": "image_url",
            "image_url": {
              "url": "data:image/jpeg;base64,YOUR_BASE64_IMAGE"
            }
          }
        ]
      }
    ]
  }'
```

## 故障排除

### 如果部署脚本失败

1. **模型下载失败**: 检查网络连接，脚本会自动重试 HuggingFace
2. **GPU 问题**: 运行 `nvidia-smi` 检查 GPU 状态
3. **Docker 问题**: 确保 Docker 和 Docker Compose 已正确安装
4. **权限问题**: 确保当前用户有 Docker 访问权限

### 手动部署

如果自动脚本有问题，可以手动执行：

```bash
# 1. 下载模型
python download_model.py -t modelscope

# 2. 启动服务
docker compose up -d
```

### 服务无法启动

查看详细日志：
```bash
docker compose logs dots-ocr-server
```

常见问题：
- GPU 内存不足：降低 `--gpu-memory-utilization` 参数
- 模型文件缺失：重新运行 `python download_model.py`
- 端口冲突：修改 docker-compose.yml 中的端口映射