#!/bin/bash

# 获取脚本所在目录的父目录（项目根目录）
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"

# 检查 .env 文件是否存在
if [ ! -f "$ENV_FILE" ]; then
    echo "错误: .env 文件不存在，请先创建 .env 文件并添加 RAGFLOW_API_KEY 和 RAGFLOW_BASE_URL"
    exit 1
fi

# 获取宿主机 IP
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    HOST_IP=$(ipconfig getifaddr en0 || ipconfig getifaddr en1)
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    HOST_IP=$(hostname -I | awk '{print $1}')
elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    # Windows
    HOST_IP=$(ipconfig | findstr IPv4 | head -n 1 | awk '{print $NF}')
else
    # 使用 Docker 方式获取
    HOST_IP=$(docker run --rm alpine ip route | awk 'NR==1 {print $3}')
fi

# 如果上述方法都失败，使用 localhost
if [ -z "$HOST_IP" ]; then
    HOST_IP="localhost"
fi

# 提示用户输入必要信息
echo "=== RAGFlow 配置生成器 ==="
echo "宿主机 IP: $HOST_IP"
echo

read -p "请输入 Elasticsearch 端口 (默认: 9200): " ES_PORT
ES_PORT=${ES_PORT:-9200}

# 创建临时文件
TEMP_FILE=$(mktemp)

# 读取现有 .env 文件内容
cat "$ENV_FILE" > "$TEMP_FILE"

# 追加新配置
cat >> "$TEMP_FILE" << EOF

# 自动生成的配置
# 宿主机 IP: $HOST_IP

# Elasticsearch 配置
ES_HOST=$HOST_IP
ES_PORT=$ES_PORT

# 数据库配置（可选）
DB_HOST=$HOST_IP

# MinIO 配置（可选）
MINIO_HOST=$HOST_IP

# Redis 配置（可选）
REDIS_HOST=$HOST_IP

EOF

# 将临时文件内容写回 .env 文件
mv "$TEMP_FILE" "$ENV_FILE"

echo
echo "配置已添加到: $ENV_FILE"
echo "接下来您可以："
echo "1. 运行 'docker compose up -d' 启动服务"
echo "2. 访问 http://$HOST_IP:8888 进入管理界面"