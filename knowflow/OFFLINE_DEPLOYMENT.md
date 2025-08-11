# KnowFlow 离线部署指南

本文档介绍如何在离线环境中部署 KnowFlow 系统，包括服务器、MinerU 服务和本地大模型的配置。

## 系统要求

### 硬件要求
- **CPU**: 8 核以上
- **内存**: 16GB 以上（推荐 32GB）
- **存储**: 100GB 以上可用空间
- **GPU**: NVIDIA GPU（推荐，用于模型推理加速）

### 软件要求
- Docker 20.10+
- Docker Compose 2.0+
- NVIDIA Container Toolkit（GPU 环境）

## 部署步骤

### 1. 部署 MinerU 服务

使用 `zxwei/mineru-api-full:v2.1.11` 以上版本：

```bash
# 拉取镜像
docker pull zxwei/mineru-api-full:v2.1.11

# 启动 MinerU 服务（GPU 版本）
docker run -d \
    --gpus all \
    -p 8888:8888 \
    --name mineru-pipeline \
    -e MINERU_MODEL_SOURCE=local \
    -e INSTALL_TYPE=core \
    zxwei/mineru-api-full:v2.1.11
```

#### CPU 版本（无 GPU 环境）

```bash
# 启动 MinerU 服务（CPU 版本）
docker run -d \
    -p 8888:8888 \
    --name mineru-pipeline \
    -e MINERU_MODEL_SOURCE=local \
    -e INSTALL_TYPE=core \
    zxwei/mineru-api-full:v2.1.11
```

### 2. 配置 MinerU 服务地址

在 KnowFlow 配置中设置 MinerU 服务地址：

```json
{
  "mineru_api_url": "http://localhost:8888",
  "timeout": 30000
}
```

### 3. 部署 KnowFlow 服务器

使用 `zxwei/knowflow-server:v2.0.3` 以上版本：

```bash
# 拉取镜像
docker pull zxwei/knowflow-server:v2.0.3

# 启动服务
docker run -d \
    --name knowflow-server \
    -p 9380:9380 \
    -v knowflow-data:/data \
    zxwei/knowflow-server:v2.0.3
```

### 4. 本地大模型下载

参照 [模型下载指南](./scripts/models/README.md) 进行本地大模型的下载和配置。

#### 快速开始

```bash
# 进入模型脚本目录
cd knowflow/scripts/models/

# 使用一体化脚本下载所有模型
./download_models_all_in_one.sh --all

# 或下载指定模型
./download_models_all_in_one.sh qwen3-14b
```

#### 支持的模型

**Qwen 系列模型**
- **qwen3-14b**: Qwen2.5 14B 指令微调模型（约 28GB）
- **qwen3-32b**: Qwen2.5 32B 指令微调模型（约 65GB）
- **qwen3-32b-q8**: Qwen2.5 32B 8位量化模型（约 36GB）
- **qwen3-32b-q6**: Qwen2.5 32B 6位量化模型（约 28GB）
- **qwen3-30b-a3b**: Qwen2.5 30B A3B 模型（约 24GB）

**嵌入和重排序模型**
- **bge-reranker-v2-m3**: BGE Reranker v2 M3 模型（约 2GB）
- **bge-m3**: BGE M3 嵌入模型（约 2GB）

### 5. 验证服务状态

```bash
# 检查 KnowFlow 服务
curl http://localhost:9380/health

# 检查 MinerU 服务
curl http://localhost:8888/health
```

## 离线环境配置

### 镜像导出和导入

#### 导出镜像

```bash
# 导出 KnowFlow 服务镜像
docker save zxwei/knowflow-server:v2.0.3 -o knowflow-server-v2.0.3.tar

# 导出 MinerU 服务镜像
docker save zxwei/mineru-api-full:v2.1.11 -o mineru-api-full-v2.1.11.tar
```

#### 导入镜像

```bash
# 导入 KnowFlow 服务镜像
docker load -i knowflow-server-v2.0.3.tar

# 导入 MinerU 服务镜像
docker load -i mineru-api-full-v2.1.11.tar
```

### 模型文件离线传输

#### 1. 在线环境准备模型文件

**使用下载脚本获取模型**
```bash
# 进入模型脚本目录
cd knowflow/scripts/models/

# 下载所有模型到默认路径
python download_models.py --all

# 或下载指定模型
python download_models.py qwen3-30b-a3b bge-m3 bge-reranker-v2-m3
```

**模型存储路径**
- 默认下载路径：`/var/lib/docker/volumes/gpustack-data/_data/models`
- 模型目录结构：
  ```
  /var/lib/docker/volumes/gpustack-data/_data/models/
  ├── qwen3-30b-a3b/          # Qwen2.5 30B A3B 模型
  ├── bge-reranker-v2-m3/     # BGE Reranker v2 M3
  ├── bge-m3/                 # BGE M3 嵌入模型
  └── ...
  ```

#### 2. 打包模型文件

**方法一：打包整个模型目录**
```bash
# 进入 Docker 数据卷目录
cd /var/lib/docker/volumes/gpustack-data/_data/

# 打包所有模型（推荐使用 pigz 加速压缩）
tar -I pigz -cf knowflow-models-all.tar.gz models/

# 或使用标准 gzip（较慢但兼容性好）
tar -czf knowflow-models-all.tar.gz models/
```

**方法二：按需打包指定模型**
```bash
# 只打包核心模型
cd /var/lib/docker/volumes/gpustack-data/_data/
tar -czf knowflow-models-core.tar.gz \
    models/qwen3-30b-a3b/ \
    models/bge-reranker-v2-m3/ \
    models/bge-m3/

# 打包大语言模型
tar -czf knowflow-llm-models.tar.gz \
    models/qwen3-30b-a3b/ \
    models/qwen3-32b/ \
    models/qwen3-32b-q8/
```

**检查打包文件**
```bash
# 查看压缩包内容
tar -tzf knowflow-models-all.tar.gz | head -20

# 检查文件大小
ls -lh *.tar.gz
```

#### 3. 传输到离线环境

**使用 scp 传输**
```bash
# 传输到目标服务器
scp knowflow-models-all.tar.gz user@target-server:/tmp/
```

**使用 rsync 传输（支持断点续传）**
```bash
# 传输大文件，支持断点续传
rsync -avz --progress knowflow-models-all.tar.gz user@target-server:/tmp/
```

#### 4. 离线环境部署模型

**解压模型文件**
```bash
# 在目标服务器上解压
cd /tmp
tar -xzf knowflow-models-all.tar.gz

# 创建 Docker 数据卷目录（如果不存在）
sudo mkdir -p /var/lib/docker/volumes/gpustack-data/_data/

# 移动模型文件到正确位置
sudo mv models/* /var/lib/docker/volumes/gpustack-data/_data/models/

# 设置正确的权限
sudo chown -R 1000:1000 /var/lib/docker/volumes/gpustack-data/_data/models/
```

**验证模型文件**
```bash
# 检查模型目录结构
ls -la /var/lib/docker/volumes/gpustack-data/_data/models/

# 验证模型信息文件
cat /var/lib/docker/volumes/gpustack-data/_data/models/qwen3-30b-a3b/model_info.json
```

#### 5. 配置模型路径

**GPUStack 配置**
```bash
# 使用下载脚本生成配置信息
cd knowflow/scripts/models/
python download_models.py --config
```

**手动配置模型路径**
- 确保模型文件路径与 GPUStack 配置一致
- 模型路径格式：`/var/lib/docker/volumes/gpustack-data/_data/models/{model_name}/`
- 在 GPUStack 界面中添加本地模型，指向对应路径

#### 6. 离线传输注意事项

**存储空间要求**
- 完整模型包：约 150-200GB
- 核心模型包：约 30-50GB
- 确保目标环境有足够存储空间

**网络传输优化**
- 大文件建议分片传输
- 使用支持断点续传的工具
- 可考虑使用移动存储设备传输

**文件完整性验证**
```bash
# 生成校验和
sha256sum knowflow-models-all.tar.gz > models.sha256

# 在目标环境验证
sha256sum -c models.sha256
```


## GPUStack 迁移指南

如果您之前使用旧安装脚本安装了 GPUStack，请按照以下说明迁移到支持的 Docker 部署方法。

### 迁移前准备

**重要提示**：在进行迁移之前，强烈建议备份数据库。对于默认安装，请停止 GPUStack 服务器并创建位于 `/var/lib/gpustack/database.db` 的文件备份。

```bash
# 停止现有 GPUStack 服务
sudo systemctl stop gpustack

# 备份数据库
sudo cp /var/lib/gpustack/database.db /var/lib/gpustack/database.db.backup

# 备份整个数据目录（推荐）
sudo tar -czf gpustack-backup-$(date +%Y%m%d).tar.gz /var/lib/gpustack/
```

### Linux 迁移步骤

#### 步骤 1：找到现有数据目录

找到旧版安装使用的现有数据目录路径，默认路径为：

```
/var/lib/gpustack
```

我们将在下一步中将其引用为 `${your-data-dir}`。

#### 步骤 2：通过 Docker 重新安装 GPUStack

**NVIDIA GPU 环境**

如果您使用的是 NVIDIA GPU，请运行以下 Docker 命令来迁移您的 GPUStack 服务器，并用您的数据目录位置替换卷挂载路径：

```bash
docker run -d --name gpustack \
    --restart=unless-stopped \
    --gpus all \
    --network=host \
    --ipc=host \
    -v /var/lib/gpustack:/var/lib/gpustack \
    gpustack/gpustack
```

**CPU 环境或其他 GPU**

对于 CPU 环境或其他 GPU 硬件平台：

```bash
docker run -d --name gpustack \
    --restart=unless-stopped \
    --network=host \
    --ipc=host \
    -v /var/lib/gpustack:/var/lib/gpustack \
    gpustack/gpustack
```

#### 步骤 3：验证迁移结果

```bash
# 检查容器状态
docker ps | grep gpustack

# 查看容器日志
docker logs gpustack

# 验证 GPUStack 服务
curl http://localhost:80/health
```

#### 步骤 4：清理旧安装（可选）

迁移成功后，可以清理旧的安装文件：

```bash
# 卸载旧版本（如果通过包管理器安装）
sudo apt remove gpustack  # Ubuntu/Debian
sudo yum remove gpustack   # CentOS/RHEL

# 或删除手动安装的文件
sudo rm -rf /usr/local/bin/gpustack
sudo rm -rf /etc/systemd/system/gpustack.service
sudo systemctl daemon-reload
```

### 迁移注意事项

1. **数据完整性**：迁移过程会保留您现有的模型、配置和数据
2. **端口配置**：Docker 版本默认使用 host 网络模式，端口配置保持不变
3. **权限设置**：确保 Docker 有权限访问数据目录
4. **服务依赖**：如果有其他服务依赖 GPUStack，请相应更新配置

### 故障排除

**迁移失败处理**

```bash
# 如果迁移失败，可以恢复备份
sudo systemctl start gpustack  # 启动旧服务
sudo cp /var/lib/gpustack/database.db.backup /var/lib/gpustack/database.db
```

**权限问题**

```bash
# 修复数据目录权限
sudo chown -R 1000:1000 /var/lib/gpustack/
sudo chmod -R 755 /var/lib/gpustack/
```

## 访问系统

部署完成后，可以通过以下地址访问系统：

- **KnowFlow 主界面**: http://localhost:9380
- **MinerU API**: http://localhost:8888
- **GPUStack 管理界面**: http://localhost:80
- **API 文档**: http://localhost:8888/docs

## 故障排除

### 常见问题

1. **服务无法启动**
   ```bash
   # 检查容器日志
   docker logs knowflow-server
   docker logs mineru-pipeline
   ```

2. **GPU 不可用**
   ```bash
   # 检查 NVIDIA 驱动
   nvidia-smi
   
   # 检查 Docker GPU 支持
   docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi
   ```

3. **端口冲突**
   ```bash
   # 检查端口占用
   netstat -tlnp | grep :9380
   netstat -tlnp | grep :8888
   ```

4. **内存不足**
   ```bash
   # 检查系统资源
   free -h
   df -h
   ```

### 性能优化

1. **GPU 内存优化**
   - 根据 GPU 显存调整模型配置
   - 使用量化模型减少内存占用

2. **存储优化**
   - 使用 SSD 存储提升 I/O 性能
   - 定期清理临时文件

3. **网络优化**
   - 使用 Docker 内部网络减少延迟
   - 配置合适的超时时间

## 版本说明

- **KnowFlow Server**: v2.0.3+
- **MinerU API**: v2.1.11+
- **Docker**: 20.10+
- **Docker Compose**: 2.0+

## 获取帮助

如果在部署过程中遇到问题，请：

1. 查看 [常见问题文档](./docs/faq.mdx)
2. 检查 [GitHub Issues](https://github.com/your-repo/issues)
3. 联系技术支持团队

---

**注意**: 离线部署需要提前准备所有必要的镜像和模型文件。建议在有网络的环境中先完成镜像拉取和模型下载，然后打包传输到离线环境。