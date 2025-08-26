import database
import jwt
import os
import logging
import time
import threading
from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime, timedelta
from routes import register_routes
from dotenv import load_dotenv
from rbac_init import initialize_rbac_system, RBACInitializer

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'docker', '.env'))

app = Flask(__name__)
# 启用CORS，允许前端访问
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

# 请求前钩子：确保RBAC已初始化
@app.before_request
def ensure_rbac_ready():
    """
    在处理需要RBAC的请求前确保RBAC已初始化
    排除不需要RBAC的路径
    """
    # 不需要RBAC检查的路径
    excluded_paths = [
        '/api/v1/auth/login',
        '/api/v1/admin/rbac/status',
        '/api/v1/admin/rbac/init',
        '/health',
        '/'
    ]
    
    # 如果是排除的路径，直接跳过
    if request.path in excluded_paths:
        return
    
    # 如果是静态文件或非API路径，跳过
    if not request.path.startswith('/api/'):
        return
    
    # 对于API路径，确保RBAC已初始化
    if not ensure_rbac_initialized():
        logger.warning(f"RBAC未初始化，拒绝请求: {request.path}")
        return jsonify({
            "code": 503,
            "message": "服务正在初始化中，请稍后再试",
            "data": {
                "suggestion": "请等待服务完成初始化或使用 /api/v1/admin/rbac/init 手动初始化"
            }
        }), 503

# 注册所有路由
register_routes(app)

# 延迟初始化标记
rbac_initialized = False
rbac_init_lock = threading.Lock()

def check_database_ready():
    """检查数据库是否准备就绪 - 检查所有RBAC初始化所需的表"""
    try:
        initializer = RBACInitializer()
        db = initializer._get_db_connection()
        cursor = db.cursor()
        
        # 定义RBAC初始化所需的所有表
        required_tables = ['user', 'tenant', 'user_tenant']
        missing_tables = []
        
        for table in required_tables:
            cursor.execute("""
                SELECT COUNT(*) FROM information_schema.tables 
                WHERE table_schema = DATABASE() AND table_name = %s
            """, (table,))
            table_exists = cursor.fetchone()[0] > 0
            
            if not table_exists:
                missing_tables.append(table)
                logger.debug(f"缺少表: {table}")
            else:
                logger.debug(f"表存在: {table}")
        
        cursor.close()
        db.close()
        
        if missing_tables:
            logger.info(f"等待以下表创建: {', '.join(missing_tables)}")
            return False
        
        logger.debug("所有必需表已存在")
        return True
        
    except Exception as e:
        logger.debug(f"数据库检查失败: {e}")
        return False

def delayed_rbac_init():
    """延迟RBAC初始化，带重试机制"""
    global rbac_initialized
    
    with rbac_init_lock:
        if rbac_initialized:
            return True
            
        max_retries = 30  # 最多重试30次
        retry_interval = 2  # 每次重试间隔2秒
        
        for attempt in range(max_retries):
            try:
                # 检查数据库是否准备就绪
                if not check_database_ready():
                    logger.info(f"等待数据库就绪... (尝试 {attempt + 1}/{max_retries})")
                    time.sleep(retry_interval)
                    continue
                
                # 执行RBAC初始化
                logger.info(f"开始RBAC初始化... (尝试 {attempt + 1}/{max_retries})")
                success = initialize_rbac_system()
                
                if success:
                    rbac_initialized = True
                    logger.info("✓ RBAC权限系统延迟初始化成功")
                    logger.info("默认管理员账户: admin@gmail.com / admin")
                    return True
                else:
                    logger.warning(f"RBAC初始化失败，将重试... (尝试 {attempt + 1}/{max_retries})")
                    
            except Exception as e:
                logger.warning(f"RBAC初始化异常，将重试: {e} (尝试 {attempt + 1}/{max_retries})")
            
            if attempt < max_retries - 1:
                time.sleep(retry_interval)
        
        logger.error("RBAC初始化最终失败，已达到最大重试次数")
        return False

def ensure_rbac_initialized():
    """确保RBAC已初始化的装饰器函数"""
    global rbac_initialized
    
    if rbac_initialized:
        return True
    
    return delayed_rbac_init()

# 后台初始化线程
def background_init():
    """后台初始化线程"""
    logger.info("启动后台RBAC初始化...")
    time.sleep(5)  # 等待5秒让其他服务启动
    delayed_rbac_init()

# 启动后台初始化线程
background_thread = threading.Thread(target=background_init, daemon=True)
background_thread.start()

# 从环境变量获取配置
ADMIN_USERNAME = os.getenv('MANAGEMENT_ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.getenv('MANAGEMENT_ADMIN_PASSWORD', '12345678')
JWT_SECRET = os.getenv('MANAGEMENT_JWT_SECRET', 'your-secret-key')

# 生成token
def generate_token(username):
    # 设置令牌过期时间（例如1小时后过期）
    expire_time = datetime.utcnow() + timedelta(hours=1)
    
    # 生成令牌
    token = jwt.encode({
        'username': username,
        'exp': expire_time
    }, JWT_SECRET, algorithm='HS256') 
    
    return token

# 智能分块API端点 - 为RAGFlow提供HTTP接口
@app.route('/api/smart_chunk', methods=['POST'])
def smart_chunk():
    """智能分块API端点 - 供RAGFlow跨容器调用"""
    try:
        # 解析请求参数
        data = request.get_json()
        if not data:
            return {"code": 400, "message": "请求数据不能为空"}, 400
        
        text = data.get('text', '').strip()
        chunk_token_num = data.get('chunk_token_num', 128)
        min_chunk_tokens = data.get('min_chunk_tokens', 10)
        method = data.get('method', 'smart')
        
        if not text:
            return {"code": 400, "message": "文本内容不能为空"}, 400
        
        logger.info(f"🚀 [DEBUG] 智能分块API调用: 文本长度={len(text)} 字符, 分块大小={chunk_token_num}")
        
        # 导入智能分块函数
        from services.knowledgebases.mineru_parse.utils import split_markdown_to_chunks_smart
        
        # 执行智能分块
        chunks = split_markdown_to_chunks_smart(
            txt=text,
            chunk_token_num=chunk_token_num,
            min_chunk_tokens=min_chunk_tokens
        )
        
        logger.info(f"📊 [DEBUG] 智能分块结果: {len(chunks)} 个分块")
        
        # 返回结果
        return {
            "code": 0,
            "message": "智能分块成功",
            "data": {
                "chunks": chunks,
                "total_chunks": len(chunks),
                "method": method
            }
        }
        
    except Exception as e:
        logger.error(f"❌ [ERROR] 智能分块API失败: {e}")
        return {"code": 500, "message": f"智能分块失败: {str(e)}"}, 500


# AST父子分块API端点已移除 - 现在所有父子分块处理都在本地完成，不需要HTTP API

# 登录路由保留在主文件中
@app.route('/api/v1/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    # 创建用户名和密码的映射
    valid_users = {
        ADMIN_USERNAME: ADMIN_PASSWORD
    }
    
    # 验证用户名是否存在
    if not username or username not in valid_users:
        return {"code": 1, "message": "用户名不存在"}, 400
    
    # 验证密码是否正确
    if not password or password != valid_users[username]:
        return {"code": 1, "message": "密码错误"}, 400
    
    # 生成token
    token = generate_token(username)
    
    return {"code": 0, "data": {"token": token}, "message": "登录成功"}

# RBAC系统管理接口
@app.route('/api/v1/admin/rbac/init', methods=['POST'])
def admin_rbac_init():
    """手动初始化RBAC系统的管理接口"""
    global rbac_initialized
    
    try:
        # 简单的认证（可以根据需要增强）
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return {"code": 1, "message": "需要认证"}, 401
        
        # 执行RBAC初始化
        logger.info("手动触发RBAC系统初始化...")
        success = delayed_rbac_init()
        
        if success:
            logger.info("✓ RBAC权限系统手动初始化成功")
            return {
                "code": 0, 
                "message": "RBAC系统初始化成功",
                "data": {
                    "admin_account": "admin@gmail.com",
                    "admin_password": "admin"
                }
            }
        else:
            logger.error("✗ RBAC权限系统手动初始化失败")
            return {"code": 1, "message": "RBAC系统初始化失败"}, 500
            
    except Exception as e:
        logger.error(f"RBAC系统手动初始化异常: {e}")
        return {"code": 1, "message": f"初始化异常: {str(e)}"}, 500

@app.route('/api/v1/admin/rbac/status', methods=['GET'])
def admin_rbac_status():
    """检查RBAC系统状态"""
    global rbac_initialized
    
    try:
        from rbac_init import RBACInitializer
        initializer = RBACInitializer()
        
        # 检查数据库是否就绪
        db_ready = check_database_ready()
        
        # 检查RBAC是否已初始化
        is_initialized = rbac_initialized and initializer._is_rbac_initialized()
        
        table_status = get_detailed_database_status()
        
        status_info = {
            "database_ready": db_ready,
            "required_tables": table_status,
            "rbac_initialized": is_initialized,
            "background_init_status": rbac_initialized,
            "timestamp": datetime.now().isoformat()
        }
        
        # 添加缺少表的信息
        if table_status:
            missing_tables = [table for table, exists in table_status.items() if not exists]
            if missing_tables:
                status_info["missing_tables"] = missing_tables
                status_info["waiting_for"] = f"Waiting for tables: {', '.join(missing_tables)}"
        
        if is_initialized and db_ready:
            # 获取基本统计信息
            try:
                db = initializer._get_db_connection()
                cursor = db.cursor()
                
                # 统计角色数量
                cursor.execute("SELECT COUNT(*) FROM rbac_roles WHERE is_system = 1")
                system_roles_count = cursor.fetchone()[0]
                
                # 统计权限数量
                cursor.execute("SELECT COUNT(*) FROM rbac_permissions")
                permissions_count = cursor.fetchone()[0]
                
                # 检查默认管理员
                cursor.execute("""
                    SELECT COUNT(*) FROM user u
                    JOIN rbac_user_roles ur ON u.id = ur.user_id
                    JOIN rbac_roles r ON ur.role_id = r.id
                    WHERE u.email = 'admin@gmail.com' AND r.code = 'super_admin' AND ur.is_active = 1
                """)
                admin_exists = cursor.fetchone()[0] > 0
                
                status_info.update({
                    "system_roles_count": system_roles_count,
                    "permissions_count": permissions_count,
                    "default_admin_exists": admin_exists
                })
                
            except Exception as e:
                logger.warning(f"获取RBAC状态详情失败: {e}")
        
        return {"code": 0, "data": status_info, "message": "获取RBAC状态成功"}
        
    except Exception as e:
        logger.error(f"检查RBAC状态异常: {e}")
        return {"code": 1, "message": f"状态检查异常: {str(e)}"}, 500

def get_detailed_database_status():
    """获取详细的数据库状态信息"""
    try:
        initializer = RBACInitializer()
        db = initializer._get_db_connection()
        cursor = db.cursor()
        
        required_tables = ['user', 'tenant', 'user_tenant']
        table_status = {}
        
        for table in required_tables:
            cursor.execute("""
                SELECT COUNT(*) FROM information_schema.tables 
                WHERE table_schema = DATABASE() AND table_name = %s
            """, (table,))
            table_exists = cursor.fetchone()[0] > 0
            table_status[table] = table_exists
        
        cursor.close()
        db.close()
        
        return table_status
        
    except Exception as e:
        logger.debug(f"获取数据库状态失败: {e}")
        return {}

@app.route('/health', methods=['GET'])
def health_check():
    """
    健康检查接口 - 提供详细的服务状态信息
    """
    global rbac_initialized

    db_ready = check_database_ready()
    table_status = get_detailed_database_status()
    
    health_status = {
        "status": "healthy" if db_ready and rbac_initialized else "initializing",
        "database_ready": db_ready,
        "required_tables": table_status,
        "rbac_initialized": rbac_initialized,
        "timestamp": datetime.now().isoformat()
    }
    
    # 添加缺少表的信息
    if table_status:
        missing_tables = [table for table, exists in table_status.items() if not exists]
        if missing_tables:
            health_status["missing_tables"] = missing_tables
            health_status["waiting_for"] = f"Waiting for tables: {', '.join(missing_tables)}"
    
    status_code = 200 if (db_ready and rbac_initialized) else 503
    
    return jsonify({
        "code": 0 if status_code == 200 else 1,
        "data": health_status,
        "message": "服务运行正常" if status_code == 200 else "服务正在初始化"
    }), status_code


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    logger.info(f"KnowFlow Server 启动中... 端口: {port}")
    logger.info("RBAC将在后台自动初始化，或可通过 /api/v1/admin/rbac/init 手动初始化")
    app.run(host='0.0.0.0', port=port, debug=True)