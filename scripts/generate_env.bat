@echo off
setlocal enabledelayedexpansion

REM 颜色定义
set "RED=[91m"
set "GREEN=[92m"
set "YELLOW=[93m"
set "BLUE=[94m"
set "NC=[0m"

REM 项目根目录
set "PROJECT_ROOT=%~dp0.."
set "ENV_FILE=%PROJECT_ROOT%\.env"

REM 日志函数
:log_info
echo %BLUE%[INFO]%NC% %~1
goto :eof

:log_success
echo %GREEN%[SUCCESS]%NC% %~1
goto :eof

:log_warning
echo %YELLOW%[WARNING]%NC% %~1
goto :eof

:log_error
echo %RED%[ERROR]%NC% %~1
goto :eof

REM 检查.env文件是否存在
if not exist "%ENV_FILE%" (
    call :log_error ".env 文件不存在，请先创建 .env 文件并添加 RAGFLOW_BASE_URL"
    exit /b 1
)

call :log_info "开始生成环境配置..."

REM 读取现有的.env文件
for /f "tokens=1,* delims==" %%a in (%ENV_FILE%) do (
    if "%%a"=="RAGFLOW_BASE_URL" set "RAGFLOW_BASE_URL=%%b"
)

REM 检查必要的环境变量
if "%RAGFLOW_BASE_URL%"=="" (
    call :log_error "RAGFLOW_BASE_URL 未设置，请在 .env 文件中添加"
    exit /b 1
)

call :log_success "环境配置生成完成！"
call :log_info "请确保以下服务已启动："
echo   - RAGFlow: %RAGFLOW_BASE_URL%
echo   - MySQL: localhost:5455
echo   - MinIO: localhost:9000
echo   - Elasticsearch: localhost:9200 