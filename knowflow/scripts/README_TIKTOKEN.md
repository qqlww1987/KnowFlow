# TikToken 离线支持配置

## 📖 概述

本文档说明如何配置 KnowFlow 以支持 tiktoken 的离线使用，避免在离线环境中因无法下载 BPE 编码文件而导致的启动失败。

## 🔧 解决方案

### 1. 预下载 tiktoken 缓存文件

在 Docker 构建阶段，我们会自动下载常用的 tiktoken 编码文件：

- `cl100k_base` - GPT-4, GPT-3.5-turbo
- `p50k_base` - GPT-3 models like text-davinci-003
- `r50k_base` - GPT-3 models like text-davinci-002
- `gpt2` - GPT-2 models
- `o200k_base` - GPT-4o models

### 2. Dockerfile 修改

在 `knowflow/Dockerfile` 中添加了以下配置：

```dockerfile
# 下载tiktoken缓存文件用于离线环境
COPY scripts/download_tiktoken.py /app/scripts/
RUN pip install tiktoken && \
    mkdir -p /opt/tiktoken_cache && \
    python3 /app/scripts/download_tiktoken.py

# 设置tiktoken缓存目录环境变量
ENV TIKTOKEN_CACHE_DIR=/opt/tiktoken_cache
```

### 3. 代码修改

修改了 `server/services/knowledgebases/mineru_parse/utils.py`，使其：

- 优先使用环境变量 `TIKTOKEN_CACHE_DIR` 指定的缓存目录
- 如果环境变量未设置，则使用默认路径 `/opt/tiktoken_cache`
- 自动创建缓存目录（如果不存在）

## 🚀 使用方法

### 构建 Docker 镜像

```bash
cd knowflow
docker build -t knowflow:latest .
```

构建过程中会自动下载 tiktoken 缓存文件。

### 测试离线功能

可以使用提供的测试脚本验证 tiktoken 离线功能：

```bash
# 在容器内运行测试
docker run --rm knowflow:latest python3 /app/scripts/test_tiktoken_offline.py
```

### 环境变量配置

如果需要自定义缓存目录，可以设置环境变量：

```bash
# 自定义缓存目录
export TIKTOKEN_CACHE_DIR=/custom/path/to/tiktoken/cache

# 或在 docker-compose.yml 中设置
environment:
  - TIKTOKEN_CACHE_DIR=/opt/tiktoken_cache
```

## 📁 文件说明

- `download_tiktoken.py` - 下载 tiktoken 编码文件的脚本
- `test_tiktoken_offline.py` - 测试 tiktoken 离线功能的脚本
- `README_TIKTOKEN.md` - 本说明文档

## ✅ 验证步骤

1. **构建镜像时检查**：
   ```bash
   docker build -t knowflow:latest . | grep tiktoken
   ```

2. **运行时检查缓存文件**：
   ```bash
   docker run --rm knowflow:latest ls -la /opt/tiktoken_cache/
   ```

3. **测试编码功能**：
   ```bash
   docker run --rm knowflow:latest python3 /app/scripts/test_tiktoken_offline.py
   ```

## 🔍 故障排除

### 问题：构建时下载失败

**解决方案**：
- 确保构建环境有网络连接
- 检查防火墙设置
- 尝试使用代理：
  ```bash
  docker build --build-arg HTTP_PROXY=http://proxy:port -t knowflow:latest .
  ```

### 问题：运行时找不到缓存文件

**解决方案**：
- 检查环境变量 `TIKTOKEN_CACHE_DIR` 是否正确设置
- 确保缓存目录存在且有读取权限
- 重新构建镜像

### 问题：编码器初始化失败

**解决方案**：
- 运行测试脚本检查具体错误
- 检查缓存文件是否完整
- 确认 tiktoken 版本兼容性

## 📝 注意事项

1. **缓存文件大小**：所有编码文件总计约几MB，不会显著增加镜像大小
2. **版本兼容性**：确保 tiktoken 版本与缓存文件兼容
3. **网络依赖**：只在构建阶段需要网络，运行时完全离线
4. **更新策略**：如需更新编码文件，重新构建镜像即可

## 🎯 效果

配置完成后，KnowFlow 将能够：

- ✅ 在完全离线环境中启动
- ✅ 正常使用 tiktoken 进行文本编码/解码
- ✅ 避免因网络问题导致的启动失败
- ✅ 提高启动速度（无需在线下载）