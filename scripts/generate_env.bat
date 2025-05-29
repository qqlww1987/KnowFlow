@echo off
setlocal enabledelayedexpansion

:: 获取脚本所在目录的父目录（项目根目录）
for %%i in ("%~dp0..") do set "PROJECT_ROOT=%%~fi"
set "ENV_FILE=%PROJECT_ROOT%\.env"

:: 检查 .env 文件是否存在
if not exist "%ENV_FILE%" (
    echo 错误: .env 文件不存在，请先创建 .env 文件并添加 RAGFLOW_API_KEY 和 RAGFLOW_BASE_URL
    exit /b 1
)

:: 获取宿主机 IP
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4"') do (
    set HOST_IP=%%a
    set HOST_IP=!HOST_IP:~1!
    goto :found_ip
)

:found_ip
if "%HOST_IP%"=="" (
    set HOST_IP=localhost
)

:: 提示用户输入必要信息
echo === RAGFlow 配置生成器 ===
echo 宿主机 IP: %HOST_IP%
echo.

set /p ES_PORT="请输入 Elasticsearch 端口 (默认: 9200): "
if "%ES_PORT%"=="" set ES_PORT=9200

:: 创建临时文件
set "TEMP_FILE=%TEMP%\ragflow_env.tmp"

:: 读取现有 .env 文件内容
type "%ENV_FILE%" > "%TEMP_FILE%"

:: 追加新配置
echo. >> "%TEMP_FILE%"
echo # 自动生成的配置 >> "%TEMP_FILE%"
echo # 宿主机 IP: %HOST_IP% >> "%TEMP_FILE%"
echo. >> "%TEMP_FILE%"
echo # Elasticsearch 配置 >> "%TEMP_FILE%"
echo ES_HOST=%HOST_IP% >> "%TEMP_FILE%"
echo ES_PORT=%ES_PORT% >> "%TEMP_FILE%"
echo. >> "%TEMP_FILE%"
echo # 数据库配置（可选）>> "%TEMP_FILE%"
echo DB_HOST=%HOST_IP% >> "%TEMP_FILE%"
echo. >> "%TEMP_FILE%"
echo # MinIO 配置（可选）>> "%TEMP_FILE%"
echo MINIO_HOST=%HOST_IP% >> "%TEMP_FILE%"
echo. >> "%TEMP_FILE%"
echo # Redis 配置（可选）>> "%TEMP_FILE%"
echo REDIS_HOST=%HOST_IP% >> "%TEMP_FILE%"
echo. >> "%TEMP_FILE%"
echo # 时区配置 >> "%TEMP_FILE%"
echo TIMEZONE=Asia/Shanghai >> "%TEMP_FILE%"

:: 将临时文件内容写回 .env 文件
move /y "%TEMP_FILE%" "%ENV_FILE%" > nul

echo.
echo 配置已添加到: %ENV_FILE%
echo 接下来您可以：
echo 1. 运行 'docker compose up -d' 启动服务
echo 2. 访问 http://%HOST_IP%:8888 进入管理界面 