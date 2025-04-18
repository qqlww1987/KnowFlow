# 前端构建阶段
FROM node:18 AS frontend-builder
WORKDIR /app/frontend
COPY web /app/frontend
# 安装 pnpm
RUN npm install -g pnpm
# 设置环境变量禁用交互式提示
ENV CI=true
# 安装依赖并构建
RUN pnpm i && pnpm build

# 前端服务阶段
FROM nginx:alpine AS frontend
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=frontend-builder /app/frontend/dist /usr/share/nginx/html
# 暴露前端端口
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]

# 后端构建阶段
FROM python:3.10.16 AS backend
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

COPY server/requirements.txt /app/
# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple \
    && rm -rf ~/.cache/pip
# 复制后端代码
COPY server /app

# /root/.cache/huggingface/hub/models--opendatalab--PDF-Extract-Kit-1.0/snapshots/95817b4b2321769155f05c8d7e2f5a6b6da9e662/models
RUN python3.10 services/multimodal/download_models_hf.py 

# 暴露后端端口
EXPOSE 5000
CMD ["python3.10", "app.py"]