#!/bin/bash

# 获取脚本所在目录的父目录（项目根目录）
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=== RAGFlow 插件安装程序 ==="
echo "项目根目录: $PROJECT_ROOT"
echo

# 检查 .env 文件是否存在
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    echo "错误: .env 文件不存在，请先创建 .env 文件并添加 RAGFLOW_API_KEY 和 RAGFLOW_BASE_URL"
    exit 1
fi

# 生成环境配置
echo "生成环境配置..."
chmod +x "$PROJECT_ROOT/scripts/generate_env.sh"
"$PROJECT_ROOT/scripts/generate_env.sh"

# 准备 Docker 挂载
echo "准备 Docker 挂载..."
python3 "$PROJECT_ROOT/mineru_volumes.py"


echo
echo "=== 安装完成！==="
