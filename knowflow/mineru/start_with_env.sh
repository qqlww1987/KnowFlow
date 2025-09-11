#!/bin/bash
set -euo pipefail

# 加载环境变量文件（如果存在）
if [ -f "/app/.env" ]; then
    echo "Loading environment variables from .env file..."
    export $(grep -v '^#' /app/.env | xargs)
fi

# 设置默认值
export PYTHONPATH=/app
export MINERU_MODEL_SOURCE=${MINERU_MODEL_SOURCE:-modelscope}
export INSTALL_TYPE=${INSTALL_TYPE:-all}
export API_PORT=${API_PORT:-8888}
export SGLANG_PORT=${SGLANG_PORT:-30000}
export SGLANG_HOST=${SGLANG_HOST:-0.0.0.0}
export SGLANG_TP_SIZE=${SGLANG_TP_SIZE:-1}
export SGLANG_DP_SIZE=${SGLANG_DP_SIZE:-1}
export SGLANG_MEM_FRACTION_STATIC=${SGLANG_MEM_FRACTION_STATIC:-0.9}
export SGLANG_ENABLE_TORCH_COMPILE=${SGLANG_ENABLE_TORCH_COMPILE:-false}
export SGLANG_MAX_SEQ_LEN=${SGLANG_MAX_SEQ_LEN:-8192}
export SGLANG_BATCH_SIZE=${SGLANG_BATCH_SIZE:-32}
export STARTUP_WAIT_TIME=${STARTUP_WAIT_TIME:-15}
export LOG_LEVEL=${LOG_LEVEL:-INFO}
export VERBOSE=${VERBOSE:-false}

echo "=== MinerU SGLang Docker Container ==="
echo "Install Type: $INSTALL_TYPE"
echo "Model Source: $MINERU_MODEL_SOURCE"
echo "API Port: $API_PORT"
echo "SGLang Port: $SGLANG_PORT"
echo "Log Level: $LOG_LEVEL"
echo "======================================"

# 构建 SGLang 服务器命令
build_sglang_command() {
    local cmd="mineru-sglang-server"
    cmd="$cmd --port $SGLANG_PORT"
    cmd="$cmd --host $SGLANG_HOST"
    
    if [ "$SGLANG_TP_SIZE" != "1" ]; then
        cmd="$cmd --tp-size $SGLANG_TP_SIZE"
    fi
    
    if [ "$SGLANG_DP_SIZE" != "1" ]; then
        cmd="$cmd --dp-size $SGLANG_DP_SIZE"
    fi
    
    if [ "$SGLANG_MEM_FRACTION_STATIC" != "0.9" ]; then
        cmd="$cmd --mem-fraction-static $SGLANG_MEM_FRACTION_STATIC"
    fi
    
    if [ "$SGLANG_ENABLE_TORCH_COMPILE" = "true" ]; then
        cmd="$cmd --enable-torch-compile"
    fi
    
    if [ "$SGLANG_MAX_SEQ_LEN" != "8192" ]; then
        cmd="$cmd --max-seq-len $SGLANG_MAX_SEQ_LEN"
    fi
    
    if [ "$SGLANG_BATCH_SIZE" != "32" ]; then
        cmd="$cmd --batch-size $SGLANG_BATCH_SIZE"
    fi
    
    if [ "$VERBOSE" = "true" ]; then
        cmd="$cmd --verbose"
    fi
    
    echo "$cmd"
}

# 检查INSTALL_TYPE环境变量，决定是否启动SGLang server
if [ "$INSTALL_TYPE" = "all" ]; then
    echo "Starting SGLang server with custom parameters..."
    SGLANG_CMD=$(build_sglang_command)
    echo "Command: $SGLANG_CMD"
    
    # 在后台启动 SGLang 服务器
    eval "$SGLANG_CMD" &
    SGLANG_PID=$!
    echo "SGLang server started with PID: $SGLANG_PID on port $SGLANG_PORT"
    
    # 等待SGLang server启动
    echo "Waiting $STARTUP_WAIT_TIME seconds for SGLang server to be ready..."
    sleep $STARTUP_WAIT_TIME
    
    # 检查SGLang server是否正常运行
    echo "Checking SGLang server health..."
    for i in {1..5}; do
        if curl -f http://localhost:$SGLANG_PORT/health >/dev/null 2>&1; then
            echo "✓ SGLang server is healthy"
            break
        else
            echo "⚠ Attempt $i/5: SGLang server not ready yet, waiting..."
            sleep 5
        fi
        
        if [ $i -eq 5 ]; then
            echo "❌ Warning: SGLang server may not be ready after $((STARTUP_WAIT_TIME + 25)) seconds"
        fi
    done
else
    echo "INSTALL_TYPE is '$INSTALL_TYPE', skipping SGLang server startup"
fi

# 启动主应用
echo "Starting MinerU Web API on port $API_PORT..."
echo "API Documentation: http://localhost:$API_PORT/docs"
echo "Health Check: http://localhost:$API_PORT/health"
if [ "$INSTALL_TYPE" = "all" ]; then
    echo "SGLang Server: http://localhost:$SGLANG_PORT"
fi
echo "======================================"

# 启动 API 服务
cd /app
python3 app.py