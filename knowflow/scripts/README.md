# KnowFlow 安装和配置脚本

本目录包含 KnowFlow 的安装和配置脚本。

## 文件说明

- `install.sh` - 主安装脚本，自动完成环境配置和挂载
- `auto_mount.py` - 自动挂载脚本，用于在 RAGFlow 容器中添加 KnowFlow 扩展
- `test_auto_mount.py` - 测试脚本，验证自动挂载功能

## 快速安装

### 一键安装（推荐）

运行主安装脚本，它会自动完成所有配置：

```bash
./scripts/install.sh
```

这个脚本会：
1. 检查 Python 版本
2. 自动检测本机IP地址
3. 生成 `.env` 配置文件（使用检测到的IP）
4. 询问是否运行自动挂载脚本
5. 按需安装必要的Python依赖（PyYAML）

### 手动安装

如果你需要更精细的控制，可以分步执行：

1. **运行自动挂载**
   ```bash
   python3 scripts/auto_mount.py
   ```

2. **手动配置环境变量**
   ```bash
   # 编辑 .env 文件
   nano .env
   ```

## 自动挂载功能

`auto_mount.py` 脚本会自动：

1. **发现 RAGFlow 容器** - 扫描运行中的 Docker 容器
2. **定位 compose 文件** - 从容器标签中获取 docker-compose 配置位置
3. **备份原配置** - 自动备份原始的 docker-compose.yml 文件
4. **添加挂载点** - 将 KnowFlow 扩展文件挂载到 RAGFlow 容器
5. **自动重启服务** - 自动重启服务以应用新配置

### 挂载的扩展

- `enhanced_doc.py` → `/ragflow/api/apps/sdk/doc.py` - 增强版文档处理类

### 新增的 API 接口

挂载完成后，RAGFlow 将支持以下新接口：

```
POST /datasets/<dataset_id>/documents/<document_id>/chunks/batch
```

**请求示例：**
```bash
curl -X POST http://localhost:9380/datasets/DATASET_ID/documents/DOC_ID/chunks/batch \
     -H 'Content-Type: application/json' \
     -H 'Authorization: Bearer YOUR_TOKEN' \
     -d '{
       "chunks": [
         {"content": "第一个chunk内容", "important_keywords": ["关键词1"]},
         {"content": "第二个chunk内容", "important_keywords": ["关键词2"]}
       ],
       "batch_size": 5
     }'
```

## 环境配置

### .env 文件说明

安装脚本会自动生成 `.env` 文件，包含以下配置：

```bash
# RAGFlow 服务地址 (已自动检测IP)
RAGFLOW_BASE_URL=http://检测到的IP:请填入RAGFlow端口号

# 自动生成的配置
HOST_IP=检测到的IP
ES_HOST=检测到的IP
ES_PORT=1200
DB_HOST=检测到的IP
DB_PORT=5455
MINIO_HOST=检测到的IP
MINIO_PORT=9000
REDIS_HOST=检测到的IP
REDIS_PORT=6379
```

### 需要手动配置的项目

1. **RAGFLOW_BASE_URL** - 确认端口号是否正确

## 故障排除

### 常见问题

1. **找不到 RAGFlow 容器**
   - 确保 RAGFlow 服务正在运行
   - 检查 Docker 是否启动

2. **权限错误**
   - 确保有足够的权限访问 Docker
   - 检查文件权限

3. **挂载失败**
   - 检查 compose 文件格式
   - 确保服务名称正确

4. **IP 检测失败**
   - 脚本会尝试多种方法检测IP
   - 如果失败，会使用默认值 `your_server_ip`

### 恢复备份

如果挂载出现问题，可以恢复备份：

```bash
# 查找备份文件
find . -name "*.backup"

# 恢复配置
cp docker-compose.yml.backup docker-compose.yml
```

## 开发说明

### 脚本依赖

- Python 3.8+
- Docker
- Docker Compose
- PyYAML（自动安装）

### 目录结构

```
scripts/
├── install.sh          # 主安装脚本
├── auto_mount.py       # 自动挂载脚本
├── test_auto_mount.py  # 测试脚本
└── README.md          # 说明文档

extensions/
└── enhanced_doc.py    # KnowFlow 扩展文件
```

### 扩展开发

如需添加新的扩展文件：

1. 将文件放在 `extensions/` 目录
2. 在 `auto_mount.py` 的 `add_knowflow_mounts` 方法中添加挂载配置
3. 更新文档说明

### 测试功能

运行测试脚本验证功能：

```bash
python3 scripts/test_auto_mount.py
```

这个脚本会测试：
- 容器发现功能
- compose 文件查找
- 扩展文件检查
- 不会修改任何实际文件 