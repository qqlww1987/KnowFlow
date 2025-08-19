import database
import jwt
import os
import logging
from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime, timedelta
from routes import register_routes
from dotenv import load_dotenv
from rbac_init import initialize_rbac_system

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

# 注册所有路由
register_routes(app)

# 初始化RBAC权限系统
def initialize_rbac():
    """应用启动时初始化RBAC权限系统"""
    try:
        logger.info("开始初始化RBAC权限系统...")
        success = initialize_rbac_system()
        if success:
            logger.info("✓ RBAC权限系统初始化成功")
            logger.info("默认管理员账户: admin@gmail.com / admin")
        else:
            logger.error("✗ RBAC权限系统初始化失败")
    except Exception as e:
        logger.error(f"RBAC系统初始化异常: {e}")

# 在应用上下文中初始化RBAC
with app.app_context():
    initialize_rbac()

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
    try:
        # 简单的认证（可以根据需要增强）
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return {"code": 1, "message": "需要认证"}, 401
        
        # 执行RBAC初始化
        logger.info("手动触发RBAC系统初始化...")
        success = initialize_rbac_system()
        
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
    try:
        from rbac_init import RBACInitializer
        initializer = RBACInitializer()
        
        # 检查RBAC是否已初始化
        is_initialized = initializer._is_rbac_initialized()
        
        status_info = {
            "rbac_initialized": is_initialized,
            "timestamp": datetime.now().isoformat()
        }
        
        if is_initialized:
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


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)