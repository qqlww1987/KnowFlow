import database
import jwt
import os
import logging
import time
import threading
import mysql.connector
from flask import Flask, jsonify, request, g
from flask_cors import CORS
from datetime import datetime, timedelta
from routes import register_routes
from dotenv import load_dotenv
from rbac_init import initialize_rbac_system, RBACInitializer
from database import DB_CONFIG

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

# ==================== 用户身份识别机制 ====================

def get_current_user():
    """
    获取当前请求的用户信息
    返回: (user_id, role) 或 None
    """
    try:
        user_id = None
        
        # 1. 从 X-User-ID header 获取（管理页面专用）
        if request.headers.get('X-User-ID'):
            user_id = request.headers.get('X-User-ID')
        
        # 2. 从 RAGFlow session cookie 获取当前用户
        elif request.cookies.get('user_id'):
            user_id = request.cookies.get('user_id')
            
        # 3. 从 RAGFlow session 获取 (_ragflow_user_session_)
        elif request.cookies.get('_ragflow_user_session_'):
            user_id = get_user_id_from_ragflow_session()
        
        # 4. 从 Authorization header 获取
        elif request.headers.get('Authorization'):
            auth_header = request.headers.get('Authorization')
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
                user_id = get_user_id_from_token(token)
        
        # 5. 默认使用3@qq.com用户（管理员测试用户）
        if not user_id:
            user_id = get_user_id_by_email('3@qq.com')
        
        if not user_id:
            return None
            
        # 从数据库获取用户角色信息
        return get_user_info_from_db(user_id)
        
    except Exception as e:
        logger.warning(f"获取用户信息失败: {e}")
        return None

def get_user_id_from_token(token):
    """从token获取用户ID（简化实现）"""
    # TODO: 实现JWT解析或token验证
    return None

def get_user_id_from_ragflow_session():
    """从RAGFlow session获取用户ID"""
    # TODO: 解析RAGFlow session cookie获取用户信息
    return None

def get_user_id_by_email(email):
    """根据邮箱获取用户ID"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        cursor.execute("SELECT id FROM user WHERE email = %s LIMIT 1", (email,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return result[0] if result else None
    except Exception as e:
        logger.warning(f"根据邮箱获取用户ID失败: {e}")
        return None

def get_default_admin_user_id():
    """获取默认管理员用户ID"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # 获取最早创建的超级管理员
        cursor.execute("""
            SELECT id FROM user 
            WHERE is_superuser = 1 OR email = 'admin@gmail.com'
            ORDER BY create_time ASC
            LIMIT 1
        """)
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return result[0] if result else None
    except Exception as e:
        logger.warning(f"获取默认admin用户失败: {e}")
        return None

def get_user_info_from_db(user_id):
    """从数据库获取用户信息"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        
        # 检查是否为超级管理员
        cursor.execute("""
            SELECT 
                u.id, u.nickname, u.email, u.is_superuser,
                COUNT(CASE WHEN r.code = 'super_admin' THEN 1 END) as is_super_admin_role,
                COUNT(CASE WHEN r.code = 'admin' THEN 1 END) as is_admin_role
            FROM user u
            LEFT JOIN rbac_user_roles ur ON u.id = ur.user_id AND ur.is_active = 1
            LEFT JOIN rbac_roles r ON ur.role_id = r.id
            WHERE u.id = %s
            GROUP BY u.id, u.nickname, u.email, u.is_superuser
        """, (user_id,))
        
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not user:
            return None
            
        # 确定用户角色
        if user['is_superuser'] == 1 or user['is_super_admin_role'] > 0:
            role = 'super_admin'
        elif user['is_admin_role'] > 0:
            role = 'admin'
        else:
            role = 'user'
            
        return user_id, role, user['nickname'], user['email']
        
    except Exception as e:
        logger.warning(f"从数据库获取用户信息失败: {e}")
        return None

def get_manageable_user_ids(current_user_id, role):
    """
    获取当前用户可管理的用户ID列表
    返回: list of user_ids 或 None（表示所有用户）
    """
    if role == 'super_admin':
        return None  # 超级管理员可以看所有用户
    
    if role == 'admin':
        try:
            conn = mysql.connector.connect(**DB_CONFIG)
            cursor = conn.cursor()
            
            # 获取当前用户创建的所有用户 + 用户自己
            cursor.execute("""
                SELECT id FROM user 
                WHERE created_by = %s OR id = %s
            """, (current_user_id, current_user_id))
            
            results = cursor.fetchall()
            cursor.close()
            conn.close()
            
            return [row[0] for row in results]
            
        except Exception as e:
            logger.warning(f"获取可管理用户列表失败: {e}")
            return [current_user_id]  # 至少返回自己
    
    return [current_user_id]  # 普通用户只能看自己

# 在Flask的g对象中存储用户信息
@app.before_request
def load_user_info():
    """在每个请求前加载用户信息"""
    # 跳过不需要用户信息的路径
    excluded_paths = ['/health', '/api/v1/auth/login', '/']
    if request.path in excluded_paths or not request.path.startswith('/api/'):
        return
        
    user_info = get_current_user()
    if user_info:
        g.current_user_id, g.current_user_role, g.current_user_name, g.current_user_email = user_info
        g.manageable_user_ids = get_manageable_user_ids(g.current_user_id, g.current_user_role)
    else:
        g.current_user_id = None
        g.current_user_role = None
        g.current_user_name = None
        g.current_user_email = None
        g.manageable_user_ids = None

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

# 启动后台初始化线程（仅在主工作进程中执行，避免debug模式重复）
if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
    logger.info("主工作进程启动后台RBAC初始化线程")
    background_thread = threading.Thread(target=background_init, daemon=True)
    background_thread.start()
elif os.environ.get("WERKZEUG_RUN_MAIN") is None:
    # 非debug模式或直接运行
    logger.info("直接启动后台RBAC初始化线程")
    background_thread = threading.Thread(target=background_init, daemon=True)
    background_thread.start()
else:
    logger.info("Werkzeug监控进程，跳过后台初始化线程")

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
    
    # 检查是否是werkzeug reloader进程
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        logger.info("主工作进程启动 - RBAC将在后台自动初始化")
    else:
        logger.info("监控进程启动 - 等待主工作进程")
    
    app.run(host='0.0.0.0', port=port, debug=True)