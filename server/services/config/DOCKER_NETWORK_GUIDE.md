# Docker容器网络通信配置指南

当KnowFlow server容器化后，访问MinerU服务需要正确配置网络地址。

## 🚫 问题
```yaml
# ❌ 错误配置 - 容器内无法访问
mineru:
  fastapi:
    url: "http://localhost:8888"
```

## ✅ 解决方案

### 方案1：使用宿主机网络地址（推荐）

#### 1.1 获取宿主机IP
```bash
# Linux/macOS
hostname -I | awk '{print $1}'
# 或
ip route get 1 | awk '{print $7}'
# Windows
ipconfig | findstr IPv4
```

#### 1.2 配置settings.yaml
```yaml
mineru:
  fastapi:
    url: "http://192.168.1.100:8888"  # 替换为实际宿主机IP
  vlm:
    sglang:
      server_url: "http://192.168.1.100:30000"
```

#### 1.3 环境变量覆盖
```bash
export KNOWFLOW_MINERU__FASTAPI__URL="http://192.168.1.100:8888"
export KNOWFLOW_MINERU__VLM__SGLANG__SERVER_URL="http://192.168.1.100:30000"
```

### 方案2：使用host.docker.internal（Docker Desktop）

#### 2.1 配置settings.yaml
```yaml
mineru:
  fastapi:
    url: "http://host.docker.internal:8888"
  vlm:
    sglang:
      server_url: "http://host.docker.internal:30000"
```

#### 2.2 启动KnowFlow容器
```bash
docker run -d \
  --name knowflow-server \
  -p 8000:8000 \
  -v $(pwd)/server/services/config:/app/config \
  knowflow-server
```

### 方案3：使用Docker网络（推荐生产环境）

#### 3.1 创建自定义网络
```bash
docker network create knowflow-network
```

#### 3.2 启动MinerU（加入网络）
```bash
docker run --rm -d --gpus=all \
  --shm-size=32g \
  --network knowflow-network \
  -p 8888:8888 -p 30000:30000 \
  --name mineru-api \
  mineru-api-full
```

#### 3.3 配置settings.yaml
```yaml
mineru:
  fastapi:
    url: "http://mineru-api:8888"
  vlm:
    sglang:
      server_url: "http://mineru-api:30000"
```

#### 3.4 启动KnowFlow（加入同一网络）
```bash
docker run -d \
  --network knowflow-network \
  --name knowflow-server \
  -p 8000:8000 \
  knowflow-server
```

### 方案4：使用Docker Compose（最佳实践）

#### 4.1 创建docker-compose.yml
```yaml
version: '3.8'

services:
  mineru-api:
    image: mineru-api-full
    ports:
      - "8888:8888"
      - "30000:30000"
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    shm_size: 32gb
    networks:
      - knowflow-network

  knowflow-server:
    image: knowflow-server
    ports:
      - "8000:8000"
    environment:
      - KNOWFLOW_MINERU__FASTAPI__URL=http://mineru-api:8888
      - KNOWFLOW_MINERU__VLM__SGLANG__SERVER_URL=http://mineru-api:30000
    depends_on:
      - mineru-api
    networks:
      - knowflow-network

networks:
  knowflow-network:
    driver: bridge
```

#### 4.2 启动服务
```bash
docker-compose up -d
```

## 🔧 配置验证

### 检查网络连通性
```bash
# 进入KnowFlow容器
docker exec -it knowflow-server bash

# 测试MinerU连接
curl http://mineru-api:8888/docs  # Docker网络
curl http://host.docker.internal:8888/docs  # Docker Desktop
curl http://192.168.1.100:8888/docs  # 宿主机IP
```

### 动态配置检测
```python
# 在KnowFlow中添加自动检测逻辑
import requests
import os

def detect_mineru_url():
    """自动检测MinerU服务地址"""
    possible_urls = [
        "http://mineru-api:8888",
        "http://host.docker.internal:8888",
        f"http://{os.environ.get('HOST_IP', '192.168.1.100')}:8888"
    ]
    
    for url in possible_urls:
        try:
            response = requests.get(f"{url}/docs", timeout=5)
            if response.status_code == 200:
                return url
        except:
            continue
    
    return None
```

## 📋 配置优先级

1. **环境变量** (最高优先级)
2. **settings.yaml配置文件**
3. **自动检测逻辑**
4. **默认值** (localhost - 仅适用于开发环境)

## ⚠️ 注意事项

1. **防火墙设置**：确保端口8888和30000在宿主机上开放
2. **网络延迟**：容器间通信可能比localhost稍慢
3. **健康检查**：建议添加服务健康检查逻辑
4. **SSL证书**：生产环境建议使用HTTPS

## 🎯 推荐配置

- **开发环境**：方案2 (host.docker.internal)
- **测试环境**：方案1 (宿主机IP)
- **生产环境**：方案4 (Docker Compose) 