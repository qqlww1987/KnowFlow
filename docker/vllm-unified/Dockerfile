# vLLM 统一服务 Dockerfile
# 支持 Chat、Embedding、Rerank 模型的统一部署

FROM nvidia/cuda:12.1.1-devel-ubuntu22.04

# 设置环境变量
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV CUDA_HOME=/usr/local/cuda
ENV PATH=${CUDA_HOME}/bin:${PATH}
ENV LD_LIBRARY_PATH=${CUDA_HOME}/lib64:${LD_LIBRARY_PATH}

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3.10-dev \
    python3-pip \
    git \
    wget \
    curl \
    vim \
    htop \
    build-essential \
    cmake \
    ninja-build \
    pkg-config \
    libssl-dev \
    libffi-dev \
    libjpeg-dev \
    libpng-dev \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 创建 python3 软链接
RUN ln -sf /usr/bin/python3.10 /usr/bin/python3 && \
    ln -sf /usr/bin/python3.10 /usr/bin/python

# 升级 pip
RUN python3 -m pip install --upgrade pip setuptools wheel

# 复制 requirements.txt
COPY requirements.txt /app/

# 先安装 torch (flash-attn 构建依赖)
RUN pip install --no-cache-dir torch>=2.1.0

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 安装额外的 CUDA 相关依赖
RUN pip install --no-cache-dir \
    nvidia-ml-py3 \
    pynvml

# 创建目录结构
RUN mkdir -p /app/models/chat && \
    mkdir -p /app/models/embedding && \
    mkdir -p /app/models/rerank && \
    mkdir -p /app/config && \
    mkdir -p /app/scripts && \
    mkdir -p /app/logs

# 复制配置文件
COPY config/ /app/config/

# 复制脚本文件
COPY scripts/ /app/scripts/

# 设置脚本执行权限
RUN chmod +x /app/scripts/*.py

# 设置 Hugging Face 缓存目录
ENV HF_HOME=/app/cache/huggingface
ENV TRANSFORMERS_CACHE=/app/cache/transformers
ENV HF_HUB_CACHE=/app/cache/hub

# 创建缓存目录
RUN mkdir -p /app/cache/huggingface && \
    mkdir -p /app/cache/transformers && \
    mkdir -p /app/cache/hub

# 预下载模型（构建时）
# 注意：这里需要网络连接，如果构建环境没有网络，可以注释掉这行
ARG DOWNLOAD_MODELS=true
RUN if [ "$DOWNLOAD_MODELS" = "true" ]; then \
        echo "开始下载模型..." && \
        python3 /app/scripts/download_models.py; \
    else \
        echo "跳过模型下载"; \
    fi

# 创建启动脚本
RUN cat > /app/start.sh <<EOF
#!/bin/bash
set -e

echo "=== vLLM 统一服务启动 ==="
echo "时间: \$(date)"
echo "GPU 信息:"
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader,nounits || echo "无法获取 GPU 信息"

# 检查模型文件
echo "检查模型文件..."
for model_dir in /app/models/*/; do
    if [ -d "\$model_dir" ]; then
        echo "模型目录: \$model_dir"
        ls -la "\$model_dir" | head -5
    fi
done

# 设置环境变量
export CUDA_VISIBLE_DEVICES=\${CUDA_VISIBLE_DEVICES:-"0,1"}
export VLLM_WORKER_MULTIPROC_METHOD=\${VLLM_WORKER_MULTIPROC_METHOD:-"spawn"}
export VLLM_LOGGING_LEVEL=\${VLLM_LOGGING_LEVEL:-"INFO"}

# 启动服务
echo "启动 vLLM 统一服务..."
cd /app
python3 /app/scripts/start_vllm.py
EOF

# 设置启动脚本权限
RUN chmod +x /app/start.sh

# 创建健康检查脚本
RUN cat > /app/healthcheck.sh <<EOF
#!/bin/bash
curl -f http://localhost:8000/health || exit 1
EOF

RUN chmod +x /app/healthcheck.sh

# 暴露端口
# 8000: 路由服务
# 8001: Chat 模型
# 8002: Embedding 模型
# 8003: Rerank 模型
EXPOSE 8000 8001 8002 8003

# 设置健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=300s --retries=3 \
    CMD /app/healthcheck.sh

# 设置卷挂载点
VOLUME ["/app/models", "/app/config", "/app/logs", "/app/cache"]

# 启动命令
CMD ["/app/start.sh"]