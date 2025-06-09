# KnowFlow .env 配置文件示例 (包含 DEV 模式)
# =======================================================

# RAGFlow API 配置
RAGFLOW_API_KEY=your_ragflow_api_key_here
RAGFLOW_BASE_URL=http://your_ragflow_server_ip

# 数据库和存储配置
ES_HOST='your_elasticsearch_host'
ES_PORT='1200'
DB_HOST='your_database_host'
MINIO_HOST='your_minio_host'
REDIS_HOST='your_redis_host'

# MinerU 配置
MINERU_MODLES_DIR='/path/to/your/huggingface/cache'
MINERU_MAGIC_PDF_JSON_PATH='/path/to/your/magic-pdf.json'

# =======================================================
# 开发模式和环境配置
# =======================================================

# 开发模式配置
# - DEV=true: 启用开发模式，跳过MinerU处理，使用现有markdown文件测试
# - DEV=false 或不设置: 生产模式，执行完整的文档处理流程
DEV=true

# 临时文件清理配置
# - 开发模式下默认不清理 (CLEANUP_TEMP_FILES=false)
# - 生产模式下默认清理 (CLEANUP_TEMP_FILES=true)
# - 可以手动设置来覆盖默认行为
CLEANUP_TEMP_FILES=false

# 分块方法配置
# - advanced: 高级分块方法，混合策略+动态阈值调整
# - smart: 智能分块方法，基于AST的语义分块（默认推荐）
# - basic: 基础分块方法，简单的文本分割
CHUNK_METHOD=smart

# =======================================================
# 不同环境的推荐配置组合
# =======================================================

# 🔸 开发环境 (推荐)
# DEV=true
# CLEANUP_TEMP_FILES=false  # 可选，dev模式下默认为false
# CHUNK_METHOD=smart

# 🔸 测试环境
# DEV=true
# CLEANUP_TEMP_FILES=false
# CHUNK_METHOD=advanced

# 🔸 生产环境 - 质量优先
# DEV=false
# CLEANUP_TEMP_FILES=true  # 可选，生产模式下默认为true
# CHUNK_METHOD=advanced

# 🔸 生产环境 - 性能优先
# DEV=false
# CLEANUP_TEMP_FILES=true
# CHUNK_METHOD=smart

# 🔸 调试环境 (完整流程但保留文件)
# DEV=false
# CLEANUP_TEMP_FILES=false
# CHUNK_METHOD=advanced

# =======================================================
# 配置说明
# =======================================================

# 1. 开发模式特性：
#    - 跳过耗时的 MinerU 文档处理
#    - 直接使用现有 markdown 文件进行分块测试
#    - 便于快速验证分块算法效果
#    - 自动保留临时文件便于调试

# 2. 临时文件管理：
#    - 开发模式：优先保留文件（便于调试）
#    - 生产模式：优先清理文件（节省存储空间）
#    - 支持手动覆盖默认行为

# 3. 分块方法选择：
#    - basic: 最快，质量一般，无依赖
#    - smart: 平衡，质量好，需要 markdown-it-py
#    - advanced: 最好质量，最慢，需要 markdown-it-py

# 4. 注意事项：
#    - 修改配置后需要重启服务
#    - 生产环境建议设置 DEV=false
#    - smart 和 advanced 方法需要安装 markdown-it-py
#    - 无效配置会自动回退到 smart 方法 