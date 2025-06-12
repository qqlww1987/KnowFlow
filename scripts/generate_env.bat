@echo off
setlocal enabledelayedexpansion

:: 设置日志函数
call :log_info "=== RAGFlow 配置生成器 ==="

:: 获取项目根目录
set "PROJECT_ROOT=%~dp0.."
set "ENV_FILE=%PROJECT_ROOT%\.env"

:: 检查 .env 文件是否存在
if not exist "%ENV_FILE%" (
    call :log_error ".env 文件不存在，请先创建 .env 文件并添加 RAGFLOW_API_KEY 和 RAGFLOW_BASE_URL"
    exit /b 1
)

:: 获取宿主机 IP
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4"') do (
    set "HOST_IP=%%a"
    set "HOST_IP=!HOST_IP: =!"
    goto :found_ip
)
:found_ip

:: 如果上述方法都失败，使用 localhost
if "%HOST_IP%"=="" set "HOST_IP=localhost"

:: 提示用户输入必要信息
call :log_info "宿主机 IP: %HOST_IP%"
echo.

:: 设置默认 Elasticsearch 端口
set "ES_PORT=1200"

:: 创建临时文件
set "TEMP_FILE=%TEMP%\ragflow_env_%RANDOM%.tmp"
call :log_info "创建临时文件: %TEMP_FILE%"

:: 定义需要更新的配置项
set "ES_HOST=%HOST_IP%"
set "ES_PORT=%ES_PORT%"
set "DB_HOST=%HOST_IP%"
set "MINIO_HOST=%HOST_IP%"
set "REDIS_HOST=%HOST_IP%"

:: 处理现有文件
for /f "usebackq delims=" %%a in ("%ENV_FILE%") do (
    set "line=%%a"
    
    :: 跳过空行
    if "!line!"=="" (
        echo. >> "%TEMP_FILE%"
        goto :next_line
    )
    
    :: 处理注释行
    if "!line:~0,1!"=="#" (
        echo !line! >> "%TEMP_FILE%"
        goto :next_line
    )
    
    :: 处理键值对
    for /f "tokens=1,* delims==" %%b in ("!line!") do (
        set "key=%%b"
        set "key=!key: =!"
        
        :: 根据键名更新值
        if /i "!key!"=="ES_HOST" (
            echo ES_HOST=!ES_HOST! >> "%TEMP_FILE%"
            set "ES_HOST="
        ) else if /i "!key!"=="ES_PORT" (
            echo ES_PORT=!ES_PORT! >> "%TEMP_FILE%"
            set "ES_PORT="
        ) else if /i "!key!"=="DB_HOST" (
            echo DB_HOST=!DB_HOST! >> "%TEMP_FILE%"
            set "DB_HOST="
        ) else if /i "!key!"=="MINIO_HOST" (
            echo MINIO_HOST=!MINIO_HOST! >> "%TEMP_FILE%"
            set "MINIO_HOST="
        ) else if /i "!key!"=="REDIS_HOST" (
            echo REDIS_HOST=!REDIS_HOST! >> "%TEMP_FILE%"
            set "REDIS_HOST="
        ) else (
            :: 保持原有值
            echo !line! >> "%TEMP_FILE%"
        )
    )
    :next_line
)

:: 添加新的配置项
echo. >> "%TEMP_FILE%"
echo # 自动生成的配置 >> "%TEMP_FILE%"
echo # 宿主机 IP: %HOST_IP% >> "%TEMP_FILE%"
echo. >> "%TEMP_FILE%"

:: 添加所有未处理的配置项
if defined ES_HOST echo ES_HOST=!ES_HOST! >> "%TEMP_FILE%"
if defined ES_PORT echo ES_PORT=!ES_PORT! >> "%TEMP_FILE%"
if defined DB_HOST echo DB_HOST=!DB_HOST! >> "%TEMP_FILE%"
if defined MINIO_HOST echo MINIO_HOST=!MINIO_HOST! >> "%TEMP_FILE%"
if defined REDIS_HOST echo REDIS_HOST=!REDIS_HOST! >> "%TEMP_FILE%"

:: 将临时文件内容写回 .env 文件
move /y "%TEMP_FILE%" "%ENV_FILE%" > nul
call :log_info "配置已更新: %ENV_FILE%"

echo.
call :log_info "配置已更新: %ENV_FILE%"
echo 接下来您可以：
echo 1. 运行 'docker compose up -d' 启动服务
echo 2. 访问 http://%HOST_IP%:8888 进入管理界面

goto :eof

:log_info
echo [INFO] %date% %time% - %~1
goto :eof

:log_error
echo [ERROR] %date% %time% - %~1 >&2
goto :eof 