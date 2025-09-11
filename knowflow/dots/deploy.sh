#!/bin/bash

# Dots OCR 一键部署脚本
set -e

echo "=== Dots OCR 一键部署脚本 ==="

# 检查是否在正确的目录
if [ ! -f "download_model.py" ] || [ ! -f "docker-compose.yml" ]; then
    echo "错误: 请在 knowflow/dots 目录下运行此脚本"
    exit 1
fi

echo "1. 检查 Python 环境..."
# 检查可用的 Python 命令
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "错误: 未找到 Python 命令，请安装 Python 3.8+"
    exit 1
fi
echo "   使用 Python 命令: $PYTHON_CMD"

echo "2. 创建虚拟环境并安装依赖..."
VENV_DIR="venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "   创建虚拟环境..."
    $PYTHON_CMD -m venv $VENV_DIR
fi

echo "   激活虚拟环境..."
source $VENV_DIR/bin/activate

echo "   安装 modelscope..."
pip install modelscope || {
    echo "   modelscope 安装失败，请检查网络连接"
    exit 1
}

echo "   依赖安装完成"

echo "3. 下载模型文件..."
echo "   使用 ModelScope 下载 rednote-hilab/dots.ocr 模型"
python download_model.py -t modelscope

if [ $? -ne 0 ]; then
    echo "   ModelScope 下载失败，安装 huggingface_hub 并尝试 HuggingFace..."
    pip install huggingface_hub
    python download_model.py -t huggingface
    if [ $? -ne 0 ]; then
        echo "错误: 模型下载失败，请检查网络连接"
        exit 1
    fi
fi

echo "4. 检查 GPU 可用性..."
if command -v nvidia-smi &> /dev/null; then
    nvidia-smi > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "   GPU 检查通过"
    else
        echo "   警告: GPU 不可用，服务可能无法正常启动"
    fi
else
    echo "   警告: nvidia-smi 未找到，请确保安装了 NVIDIA 驱动"
fi

echo "5. 启动 Dots OCR 服务..."
docker compose up -d

if [ $? -ne 0 ]; then
    echo "错误: 服务启动失败"
    exit 1
fi

echo "6. 等待服务启动..."
sleep 15

echo "7. 检查服务状态..."
docker compose ps

echo ""
echo "=== 部署完成 ==="
echo "服务地址: http://localhost:8000"
echo "模型名称: dotsocr-model"
echo ""
echo "测试命令:"
echo "curl -X GET http://localhost:8000/v1/models"
echo ""
echo "查看日志:"
echo "docker compose logs -f dots-ocr-server"
echo ""
echo "停止服务:"
echo "docker compose down"