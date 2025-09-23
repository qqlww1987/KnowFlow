# KnowFlow API URL 配置说明

## 概述

`KNOWFLOW_API_URL` 环境变量用于配置 KnowFlow RBAC 系统的 API 端点地址。这个变量允许系统在不同的部署环境中正确访问 KnowFlow 后端服务。

## 配置方式

### 1. Docker Compose 环境

在 Docker Compose 环境中，该变量已经在以下文件中配置：

- `docker-compose.yml`
- `docker-compose-gpu.yml`
- `.env`

**默认配置：**
```bash
KNOWFLOW_API_URL=http://knowflow-backend:5000
```

### 2. 自定义配置

可以通过以下方式自定义 API URL：

#### 方法 1: 修改 .env 文件
```bash
# 编辑 docker/.env 文件
KNOWFLOW_API_URL=http://your-custom-host:5000
```

#### 方法 2: 环境变量覆盖
```bash
# 启动时设置环境变量
export KNOWFLOW_API_URL=http://your-custom-host:5000
docker-compose up -d
```

#### 方法 3: Docker Compose 命令行
```bash
# 直接在命令行中指定
KNOWFLOW_API_URL=http://your-custom-host:5000 docker-compose up -d
```

## 使用场景

### 1. 本地开发环境
```bash
# 连接到本地运行的 KnowFlow 服务
KNOWFLOW_API_URL=http://localhost:5000
```

### 2. 分布式部署
```bash
# 连接到远程 KnowFlow 服务
KNOWFLOW_API_URL=http://knowflow-server.example.com:5000
```

### 3. 负载均衡环境
```bash
# 连接到负载均衡器
KNOWFLOW_API_URL=http://knowflow-lb.internal:5000
```

### 4. HTTPS 环境
```bash
# 使用 HTTPS 连接
KNOWFLOW_API_URL=https://knowflow-api.example.com
```

## 影响的组件

该环境变量会影响以下组件：

1. **RAGFlow 容器** (`ragflow-server`)
   - 用于 RBAC 权限检查和集成
   - 通过 `/api/utils/rbac_utils.py` 模块调用 KnowFlow RBAC API

2. **RBAC 工具模块** (`/api/utils/rbac_utils.py`)
   - 构建 RBAC 服务 URL：`{KNOWFLOW_API_URL}/api/v1/rbac`
   - 在 RAGFlow 容器中运行

**注意：** `knowflow-backend` 容器本身不需要此环境变量，因为它是 RBAC 服务的提供者，而非消费者。

## 配置验证

### 检查配置是否生效

1. **查看容器环境变量：**
```bash
# 只有 ragflow-server 容器需要此环境变量
docker exec ragflow-server env | grep KNOWFLOW_API_URL
```

2. **检查服务连接：**
```bash
# 在 RAGFlow 容器内测试连接
docker exec ragflow-server curl -s "${KNOWFLOW_API_URL}/api/v1/rbac/health"
```

3. **查看日志：**
```bash
# 查看 RBAC 相关日志
docker logs ragflow-server | grep -i rbac
docker logs knowflow-backend | grep -i rbac
```

## 故障排除

### 常见问题

1. **连接超时或拒绝连接**
   - 检查 URL 格式是否正确
   - 确认目标服务是否正在运行
   - 验证网络连通性

2. **404 错误**
   - 确认 API 路径是否正确（应该指向 KnowFlow 根 URL，不包含 `/api/v1/rbac`）
   - 检查目标服务是否支持 RBAC API

3. **权限验证失败**
   - 检查 RBAC 服务是否正常启动
   - 确认数据库连接和初始化是否成功

### 调试命令

```bash
# 1. 检查容器网络
docker network ls
docker network inspect docker_ragflow

# 2. 测试容器间连通性
docker exec ragflow-server ping knowflow-backend

# 3. 手动测试 API 连接
docker exec ragflow-server curl -v "${KNOWFLOW_API_URL}/api/v1/rbac/health"

# 4. 查看详细日志
docker logs --tail 100 ragflow-server
docker logs --tail 100 knowflow-backend
```

## 安全注意事项

1. **内网部署：** 确保 RBAC API 仅在内网环境中可访问
2. **HTTPS：** 生产环境建议使用 HTTPS 连接
3. **防火墙：** 配置适当的防火墙规则限制访问
4. **认证：** 确保 API 调用具有适当的认证机制

## 示例配置

### 开发环境
```bash
# .env
KNOWFLOW_API_URL=http://localhost:5000
```

### 测试环境
```bash
# .env
KNOWFLOW_API_URL=http://knowflow-test.internal:5000
```

### 生产环境
```bash
# .env
KNOWFLOW_API_URL=https://knowflow-api.production.com
```

### Docker Swarm 环境
```bash
# .env
KNOWFLOW_API_URL=http://knowflow-backend:5000
```

### Kubernetes 环境
```bash
# .env
KNOWFLOW_API_URL=http://knowflow-backend-service.default.svc.cluster.local:5000
```