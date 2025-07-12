# KnowFlow 配置说明

## 环境变量配置

### 必需配置

| 变量名 | 说明 | 示例值 |
|--------|------|--------|
| `RAGFLOW_BASE_URL` | RAGFlow服务地址 | `http://localhost:9380` |

### 可选配置

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `MYSQL_PASSWORD` | MySQL密码 | `infini_rag_flow` |
| `MINIO_USER` | MinIO用户名 | `rag_flow` |
| `MINIO_PASSWORD` | MinIO密码 | `infini_rag_flow` |
| `ELASTIC_PASSWORD` | Elasticsearch密码 | `infini_rag_flow` |
| `DEV_MODE` | 开发模式 | `true` |
| `SKIP_MINERU_PROCESSING` | 跳过MinerU处理 | `true` |

## 配置示例

### .env 文件
```bash
# RAGFlow 配置
RAGFLOW_BASE_URL=http://localhost:9380

# 数据库配置
MYSQL_PASSWORD=infini_rag_flow
MINIO_USER=rag_flow
MINIO_PASSWORD=infini_rag_flow
ELASTIC_PASSWORD=infini_rag_flow

# 开发模式配置
DEV_MODE=true
SKIP_MINERU_PROCESSING=true
```

### Docker Compose 环境变量
```yaml
environment:
  - RAGFLOW_BASE_URL=${RAGFLOW_BASE_URL}
  - DB_HOST=${DB_HOST}
  - MYSQL_PORT=3306
  - MINIO_HOST=${MINIO_HOST}
  - ES_HOST=${ES_HOST}
  - ES_PORT=${ES_PORT}
```

## 权限管理

KnowFlow 现在使用动态权限管理：

1. **自动获取权限**：根据知识库ID自动获取对应的tenant_id和API key
2. **多用户支持**：每个用户/tenant使用自己的API key
3. **权限隔离**：用户只能访问自己创建的知识库
4. **安全性提升**：不再依赖全局的API key

## 开发模式

开发模式下，系统会：
- 跳过 MinerU 文档解析，直接使用现有的 markdown 文件
- 启用详细的调试日志
- 使用测试数据

## 故障排除

### 常见问题

1. **权限错误**
   - 检查知识库是否属于当前用户
   - 确认用户有对应的API key
   - 查看调试日志中的权限获取信息

2. **连接失败**
   - 检查 `RAGFLOW_BASE_URL` 配置
   - 确认 RAGFlow 服务已启动
   - 验证网络连接

3. **数据库错误**
   - 检查数据库服务状态
   - 验证数据库密码配置
   - 确认数据库表结构正确