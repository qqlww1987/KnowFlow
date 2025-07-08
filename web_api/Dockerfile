# syntax=docker/dockerfile:1
FROM nvidia/cuda:11.8.0-runtime-ubuntu22.04

# 设置时区
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 设置构建参数
ARG INSTALL_TYPE=core
ARG http_proxy
ARG https_proxy
ARG TARGETARCH=amd64

# 设置代理环境变量（如果提供）
ENV http_proxy=${http_proxy}
ENV https_proxy=${https_proxy}

# 安装系统依赖（优化后的包列表）
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-dev \
    git \
    wget \
    curl \
    build-essential \
    pkg-config \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 设置pip镜像源和优化配置
RUN pip3 config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip3 config set global.trusted-host pypi.tuna.tsinghua.edu.cn && \
    pip3 config set global.timeout 60

# 安装uv包管理器（更快的pip替代品）
RUN --mount=type=cache,target=/root/.cache/pip \
    pip3 install --upgrade pip uv

# 设置工作目录
WORKDIR /app

# 复制依赖文件（分层复制以利用缓存）
COPY requirements*.txt ./

# 根据INSTALL_TYPE参数智能选择依赖文件
RUN if [ "$INSTALL_TYPE" = "core" ]; then \
        echo "Installing core dependencies for basic version..."; \
        if [ -f "requirements-core.txt" ]; then \
            cp requirements-core.txt requirements-active.txt; \
        else \
            echo "mineru[pipeline]==2.1.0" > requirements-active.txt; \
            echo "fastapi" >> requirements-active.txt; \
            echo "uvicorn" >> requirements-active.txt; \
            echo "python-multipart" >> requirements-active.txt; \
        fi \
    else \
        echo "Installing full dependencies..."; \
        cp requirements.txt requirements-active.txt; \
    fi

# 安装Python依赖（使用缓存挂载提升速度）
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=cache,target=/root/.cache/pip \
    uv pip install --system -r requirements-active.txt

# 复制应用代码（放在依赖安装之后以优化缓存）
COPY . .

# 设置启动脚本权限
RUN chmod +x start_services.sh

# 条件性模型预下载（仅在明确要求时进行）
ARG PREDOWNLOAD_MODELS=false
RUN if [ "$PREDOWNLOAD_MODELS" = "true" ] && [ "$INSTALL_TYPE" = "core" ]; then \
        echo "Pre-downloading pipeline models..."; \
        export MINERU_MODEL_SOURCE=modelscope; \
        mineru-models-download -s modelscope -m pipeline || \
        echo "Pipeline model download failed, will download on first use"; \
    else \
        echo "Skipping model pre-download for faster build. Models will be downloaded on first use."; \
    fi

# 设置运行时环境变量
ENV PYTHONPATH=/app
ENV MINERU_MODEL_SOURCE=modelscope
ENV INSTALL_TYPE=${INSTALL_TYPE}

# 清理构建缓存和临时文件
RUN rm -f requirements-active.txt && \
    apt-get clean && \
    python3 -c "import site; print(site.getsitepackages())" | xargs -I {} find {} -name "*.pyc" -delete 2>/dev/null || true

# 暴露端口
EXPOSE 8888

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8888/docs || exit 1

# 默认启动命令
CMD ["python3", "app.py"]
