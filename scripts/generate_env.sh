#!/bin/bash

# 设置日志函数
log_info() {
    echo "[INFO] $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_error() {
    echo "[ERROR] $(date '+%Y-%m-%d %H:%M:%S') - $1" >&2
}

# 获取脚本所在目录的父目录（项目根目录）
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"

# 检查 .env 文件是否存在
if [ ! -f "$ENV_FILE" ]; then
    log_error ".env 文件不存在，请先创建 .env 文件并添加 RAGFLOW_API_KEY 和 RAGFLOW_BASE_URL"
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
log_info "=== RAGFlow 配置生成器 ==="
log_info "宿主机 IP: $HOST_IP"
echo

# 设置默认 Elasticsearch 端口
ES_PORT=1200

# 创建临时文件
TEMP_FILE=$(mktemp)
log_info "创建临时文件: $TEMP_FILE"

# 定义需要更新的配置项
ES_HOST="$HOST_IP"
ES_PORT="$ES_PORT"
DB_HOST="$HOST_IP"
MINIO_HOST="$HOST_IP"
REDIS_HOST="$HOST_IP"

# 处理现有文件
while IFS= read -r line || [ -n "$line" ]; do
    # 跳过空行
    if [[ -z "$line" ]]; then
        echo "" >> "$TEMP_FILE"
        continue
    fi

    # 处理注释行
    if [[ "$line" =~ ^[[:space:]]*# ]]; then
        echo "$line" >> "$TEMP_FILE"
        continue
    fi

    # 处理键值对
    if [[ "$line" =~ ^([^=]+)=(.*)$ ]]; then
        key="${BASH_REMATCH[1]}"
        key=$(echo "$key" | xargs)  # 去除前后空格
        
        # 根据键名更新值
        case "$key" in
            "ES_HOST")
                echo "ES_HOST=$ES_HOST" >> "$TEMP_FILE"
                ES_HOST=""
                ;;
            "ES_PORT")
                echo "ES_PORT=$ES_PORT" >> "$TEMP_FILE"
                ES_PORT=""
                ;;
            "DB_HOST")
                echo "DB_HOST=$DB_HOST" >> "$TEMP_FILE"
                DB_HOST=""
                ;;
            "MINIO_HOST")
                echo "MINIO_HOST=$MINIO_HOST" >> "$TEMP_FILE"
                MINIO_HOST=""
                ;;
            "REDIS_HOST")
                echo "REDIS_HOST=$REDIS_HOST" >> "$TEMP_FILE"
                REDIS_HOST=""
                ;;
            *)
                # 保持原有值
                echo "$line" >> "$TEMP_FILE"
                ;;
        esac
    else
        # 保持非键值对的行不变
        echo "$line" >> "$TEMP_FILE"
    fi
done < "$ENV_FILE"

# 添加新的配置项
echo "" >> "$TEMP_FILE"
echo "# 自动生成的配置" >> "$TEMP_FILE"
echo "# 宿主机 IP: $HOST_IP" >> "$TEMP_FILE"
echo "" >> "$TEMP_FILE"

# 添加所有未处理的配置项
[ -n "$ES_HOST" ] && echo "ES_HOST=$ES_HOST" >> "$TEMP_FILE"
[ -n "$ES_PORT" ] && echo "ES_PORT=$ES_PORT" >> "$TEMP_FILE"
[ -n "$DB_HOST" ] && echo "DB_HOST=$DB_HOST" >> "$TEMP_FILE"
[ -n "$MINIO_HOST" ] && echo "MINIO_HOST=$MINIO_HOST" >> "$TEMP_FILE"
[ -n "$REDIS_HOST" ] && echo "REDIS_HOST=$REDIS_HOST" >> "$TEMP_FILE"

# 将临时文件内容写回 .env 文件
mv "$TEMP_FILE" "$ENV_FILE"
log_info "配置已更新: $ENV_FILE"

echo
log_info "配置已更新: $ENV_FILE"
echo "接下来您可以："
echo "1. 运行 'docker compose up -d' 启动服务"
echo "2. 访问 http://$HOST_IP:8081 进入管理界面"