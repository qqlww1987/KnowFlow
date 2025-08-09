
# GPUStack 模型部署和下载

本目录包含用于 GPUStack 模型部署的脚本和配置文件，支持自动下载和配置 AI 模型。

## 快速开始

### 一体化脚本（推荐）

使用一体化脚本，自动完成虚拟环境创建、依赖安装和模型下载：

```bash
# 下载所有模型
./download_models_all_in_one.sh --all

# 下载指定模型
./download_models_all_in_one.sh qwen3-14b

# 查看帮助
./download_models_all_in_one.sh --help
```

### 手动设置 GPUStack（可选）

如果需要启动 GPUStack 容器：

```bash
docker run -d --name gpustack \
    --restart=unless-stopped \
    --gpus all \
    --network=host \
    --ipc=host \
    -v gpustack-data:/var/lib/gpustack \
    gpustack/gpustack \
    --port 9000
```

## 模型下载

### 支持的模型

- **qwen3-14b**: Qwen2.5 14B 指令微调模型（约 28GB）
- **bge-reranker-v2-m3**: BGE Reranker v2 M3 模型（约 2GB）
- **bge-m3**: BGE M3 嵌入模型（约 2GB）

### 使用方法

#### 列出所有支持的模型

```bash
./download_models_all_in_one.sh --list
```

#### 下载所有模型

```bash
./download_models_all_in_one.sh --all
```

#### 下载指定模型

```bash
# 下载单个模型
./download_models_all_in_one.sh qwen3-14b

# 下载多个模型
./download_models_all_in_one.sh bge-m3 bge-reranker-v2-m3
```

#### 其他选项

```bash
# 强制重新下载
./download_models_all_in_one.sh --all --force

# 自定义下载目录
./download_models_all_in_one.sh --base-dir /path/to/models qwen3-14b

# 使用 Hugging Face Token（用于私有模型）
./download_models_all_in_one.sh --hf-token your_token_here qwen3-14b

# 显示帮助信息
./download_models_all_in_one.sh --help
```

#### 高级用法（直接使用 Python 脚本）

如果您已经有虚拟环境，也可以直接使用 Python 脚本：

```bash
# 激活虚拟环境
source ./venv/bin/activate

# 使用 Python 脚本
python download_models.py --all
python download_models.py --config  # 查看 GPUStack 配置信息
```

## 在 GPUStack 中添加模型

1. 访问 GPUStack Web 界面：http://localhost:9000
2. 在界面中选择「添加模型」
3. 选择「本地模型」
4. 指向下载的模型路径（默认为 `./models/模型名称/`）
5. 配置模型参数并启动

## 本地模型配置说明

### Docker 环境下的路径配置

在 Docker 环境中，模型文件的路径映射关系如下：

- **宿主机路径**: `/var/lib/docker/volumes/gpustack-data/_data/models/`
- **容器内路径**: `/var/lib/gpustack/models/`

### 模型路径示例

以 BGE-M3 模型为例：

```bash
# 宿主机上的实际路径
/var/lib/docker/volumes/gpustack-data/_data/models/bge-m3/

# GPUStack 容器内的路径（在 Web 界面中使用）
/var/lib/gpustack/models/bge-m3
```

### 配置步骤

1. **确认模型文件位置**
   ```bash
   # 检查模型是否存在
   ls -la /var/lib/docker/volumes/gpustack-data/_data/models/bge-m3/
   ```

2. **在 GPUStack 中配置模型路径**
   - 在 GPUStack Web 界面中添加模型时
   - 使用容器内路径：`/var/lib/gpustack/models/bge-m3`
   - **注意**：不要使用宿主机路径

3. **验证模型文件结构**
   ```bash
   # 模型目录应包含以下文件
   config.json
   pytorch_model.bin
   tokenizer.json
   # 其他相关文件...
   ```

### 支持的模型格式

- **PyTorch 格式**: `pytorch_model.bin`
- **Safetensors 格式**: `model.safetensors`
- **GGUF 格式**: `*.gguf`

### 路径配置注意事项

1. **路径一致性**: 确保在 GPUStack 中使用容器内路径
2. **权限设置**: 确保 Docker 容器有读取模型文件的权限
3. **文件完整性**: 确认所有模型文件都已正确下载
4. **目录结构**: 模型文件应位于以模型名命名的子目录中

## 配置文件

### models_config.json

模型配置文件，可以自定义：
- 模型仓库 ID
- 模型描述
- 下载设置
- GPUStack 设置

## 故障排除

### 常见问题

1. **下载速度慢**
   - 使用国内镜像：`export HF_ENDPOINT=https://hf-mirror.com`
   - 使用代理：`export https_proxy=your_proxy`

2. **磁盘空间不足**
   - 检查可用空间：`df -h`
   - 清理不需要的模型：`rm -rf ./models/model_name`

3. **权限问题**
   - 确保脚本有执行权限：`chmod +x setup_models.sh`
   - 确保 Docker 权限正确

## 文件说明

- `download_models_all_in_one.sh`: 一体化模型下载脚本（推荐使用）
- `download_models.py`: 底层的 Python 模型下载脚本
- `models_config.json`: 模型配置文件
- `requirements.txt`: Python 依赖列表
- `example_custom_config.json`: 自定义配置示例
- `README.md`: 本说明文件




