# RBAC权限管理系统使用指南

## 📋 概述

本RBAC（基于角色的访问控制）权限管理系统为KnowFlow提供了完整的用户权限管理功能，支持角色管理、权限控制、资源访问控制等核心功能。

## 🚀 快速开始

### 1. 环境要求

- Python 3.8+
- MySQL 5.7+
- Flask 2.0+

### 2. 安装依赖

```bash
cd /path/to/knowflow/server
pip install -r requirements.txt
```

### 3. 数据库配置

确保MySQL数据库已启动，并配置好连接信息：

```python
# database.py
DATABASE_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': 'your_password',
    'database': 'rag_flow'
}
```

### 4. 初始化数据库

运行数据库迁移脚本：

```bash
cd /path/to/knowflow/scripts/role
python migrate_rbac.py
```

### 5. 启动服务

```bash
python app.py
```

服务将在 `http://localhost:5000` 启动。

## 🔧 系统配置

### RBAC配置

在 `config/rbac_config.py` 中配置RBAC相关设置：

```python
RBAC_CONFIG = {
    'enabled': True,  # 启用RBAC
    'default_role': 'user',  # 默认角色
    'admin_role': 'admin',  # 管理员角色
    'permission_cache_ttl': 300,  # 权限缓存时间（秒）
}
```

## 📚 核心概念

### 角色（Roles）
- **管理员（admin）**：拥有所有权限
- **编辑者（editor）**：可以创建和编辑内容
- **查看者（viewer）**：只能查看内容
- **用户（user）**：基础用户权限

### 权限（Permissions）
- **知识库权限**：`kb_read`, `kb_write`, `kb_delete`, `kb_share`
- **文档权限**：`doc_read`, `doc_write`, `doc_delete`
- **用户管理权限**：`user_manage`, `role_manage`

### 资源类型（Resource Types）
- **KNOWLEDGEBASE**：知识库资源
- **DOCUMENT**：文档资源
- **TEAM**：团队资源
- **SYSTEM**：系统资源

## 🔌 API使用指南

### 认证

所有API请求都需要在Header中包含JWT Token：

```bash
Authorization: Bearer <your_jwt_token>
```

### 获取用户角色

```bash
GET /api/rbac/users/{user_id}/roles
```

**响应示例：**
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "name": "管理员",
      "code": "admin",
      "role_type": "system"
    }
  ]
}
```

### 获取用户权限

```bash
GET /api/rbac/users/{user_id}/permissions
```

**响应示例：**
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "name": "查看知识库",
      "code": "kb_read",
      "resource_type": "knowledgebase",
      "permission_type": "read"
    }
  ]
}
```

### 检查权限

```bash
POST /api/rbac/check-permission
Content-Type: application/json

{
  "user_id": "admin_admin",
  "permission_code": "kb_read",
  "resource_type": "knowledgebase",
  "resource_id": "kb_001"
}
```

**响应示例：**
```json
{
  "success": true,
  "data": {
    "has_permission": true,
    "granted_roles": ["admin"],
    "reason": "通过角色 admin 获得权限"
  }
}
```

### 授予角色

```bash
POST /api/rbac/users/{user_id}/roles
Content-Type: application/json

{
  "role_code": "editor",
  "resource_type": "knowledgebase",
  "resource_id": "kb_001",
  "granted_by": "admin_user"
}
```

### 撤销角色

```bash
DELETE /api/rbac/users/{user_id}/roles/{role_code}
```

## 🧪 测试

### 运行测试脚本

```bash
cd /path/to/knowflow/scripts/role
python test_rbac.py
```

测试脚本将验证以下功能：
- 用户登录
- 服务健康检查
- 角色和权限获取
- 权限检查
- 角色授予和撤销

### 测试输出示例

```
=== RBAC权限管理系统测试 ===

1. 测试登录功能...
✓ 登录成功，获取到token

2. 测试健康检查...
✓ 服务状态: healthy
✓ RBAC启用状态: True

3. 测试RBAC API...
✓ 获取用户角色成功: 1 个角色
✓ 获取用户权限成功: 8 个权限

4. 测试权限检查功能...
✓ 权限检查结果: True

5. 测试角色授予功能...
✓ 角色授予成功

=== RBAC测试完成 ===
```

## 👥 用户管理和角色授予

### 添加用户的方法

#### 方法1：通过注册API添加用户

```bash
# 用户注册
curl -X POST http://localhost:5000/api/v1/user/register \
  -H "Content-Type: application/json" \
  -d '{
    "nickname": "新用户",
    "email": "newuser@example.com",
    "password": "your_password"
  }'
```

#### 方法2：直接在数据库中添加用户

使用提供的用户管理脚本：

```bash
# 运行交互式用户管理
python user_management_guide.py

# 或运行演示
python user_management_guide.py demo
```

#### 方法3：手动数据库操作

```sql
-- 添加用户
INSERT INTO user (
    id, nickname, email, password, 
    create_time, create_date, update_time, update_date,
    status, is_superuser, login_channel, last_login_time
) VALUES (
    'user_id_here', '用户昵称', 'user@example.com', MD5('password'),
    UNIX_TIMESTAMP(), CURDATE(), UNIX_TIMESTAMP(), CURDATE(),
    '1', 0, 'manual', NOW()
);
```

### 角色授予操作

#### 通过API授予角色

```bash
# 为用户授予角色
curl -X POST http://localhost:5000/api/v1/rbac/users/{user_id}/roles \
  -H "Authorization: Bearer {your_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "role_code": "editor",
    "resource_type": "knowledgebase",
    "resource_id": "kb_001"
  }'
```

#### 通过脚本授予角色

```python
# 使用用户管理脚本
from user_management_guide import grant_role_to_user_db

# 授予角色
success = grant_role_to_user_db(
    user_id="user_id_here",
    role_code="admin",
    granted_by="admin_user_id"
)
```

#### 直接数据库操作

```sql
-- 获取角色ID
SELECT id FROM rbac_roles WHERE code = 'admin';

-- 授予角色
INSERT INTO rbac_user_roles (
    user_id, role_id, granted_by, is_active, created_at, updated_at
) VALUES (
    'user_id_here', role_id_here, 'admin_user_id', 1, NOW(), NOW()
);
```

### 可用角色类型

| 角色代码 | 角色名称 | 描述 | 权限范围 |
|---------|---------|------|----------|
| `super_admin` | 超级管理员 | 系统最高权限 | 所有权限 |
| `admin` | 管理员 | 租户管理权限 | 读取、写入、删除、分享 |
| `editor` | 编辑者 | 内容编辑权限 | 读取、写入、分享 |
| `viewer` | 查看者 | 只读权限 | 读取 |
| `guest` | 访客 | 受限访问 | 有限读取 |

### 权限检查和验证

```bash
# 检查用户权限
curl -X POST http://localhost:5000/api/v1/rbac/check-permission \
  -H "Authorization: Bearer {your_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_id_here",
    "permission_code": "kb_read",
    "resource_type": "knowledgebase",
    "resource_id": "kb_001"
  }'
```

### 撤销角色

```bash
# 撤销用户角色
curl -X DELETE http://localhost:5000/api/v1/rbac/users/{user_id}/roles/{role_code} \
  -H "Authorization: Bearer {your_token}"
```

### 查看用户角色和权限

```bash
# 获取用户角色
curl -X GET http://localhost:5000/api/v1/rbac/users/{user_id}/roles \
  -H "Authorization: Bearer {your_token}"

# 获取用户权限
curl -X GET http://localhost:5000/api/v1/rbac/users/{user_id}/permissions \
  -H "Authorization: Bearer {your_token}"

# 获取当前用户角色
curl -X GET http://localhost:5000/api/v1/rbac/my/roles \
  -H "Authorization: Bearer {your_token}"
```

## 🔍 故障排除

### 常见问题

1. **表不存在错误**
   ```
   Table 'rag_flow.knowledgebases' doesn't exist
   ```
   **解决方案**：确保数据库表名正确，应使用单数形式（`knowledgebase`而非`knowledgebases`）

2. **游标错误**
   ```
   Unread result found
   ```
   **解决方案**：确保数据库连接配置了`buffered=True`和`autocommit=True`

3. **权限检查失败**
   - 检查用户是否有相应角色
   - 检查角色是否有相应权限
   - 检查资源所有者关系

4. **用户登录失败**
   - 检查用户是否存在于数据库中
   - 验证密码是否正确
   - 确认用户状态是否为激活状态

### 日志查看

```bash
# 查看应用日志
tail -f logs/app.log

# 查看RBAC相关日志
grep "RBAC" logs/app.log
```

### 数据库检查

```sql
-- 检查用户角色
SELECT u.nickname, r.name, r.code 
FROM user u 
JOIN rbac_user_roles ur ON u.id = ur.user_id 
JOIN rbac_roles r ON ur.role_id = r.id 
WHERE u.nickname = 'your_username';

-- 检查角色权限
SELECT r.name, p.name, p.code 
FROM rbac_roles r 
JOIN rbac_role_permissions rp ON r.id = rp.role_id 
JOIN rbac_permissions p ON rp.permission_id = p.id 
WHERE r.code = 'admin';

-- 检查用户是否存在
SELECT id, nickname, email, status FROM user WHERE email = 'user@example.com';

-- 查看所有角色
SELECT id, name, code, description FROM rbac_roles ORDER BY id;
```

## 📁 项目结构

```
knowflow/
├── server/
│   ├── services/rbac/
│   │   ├── __init__.py
│   │   ├── permission_service.py    # 权限服务核心逻辑
│   │   └── rbac_service.py         # RBAC服务主入口
│   ├── routes/rbac/
│   │   ├── __init__.py
│   │   └── rbac_routes.py          # RBAC API路由
│   ├── middleware/
│   │   └── auth_middleware.py      # 认证中间件
│   └── config/
│       ├── database.py             # 数据库配置
│       └── rbac_config.py          # RBAC配置
└── scripts/role/
    ├── migrate_rbac.py             # 数据库迁移脚本
    ├── test_rbac.py                # RBAC测试脚本
    ├── user_management_guide.py    # 用户管理指南
    ├── assign_super_admin.py       # 超级管理员分配
    ├── check_user_roles.py         # 用户角色检查
    ├── clean_duplicate_roles.py    # 重复角色清理
    ├── test_new_user.py            # 新用户测试
    └── README.md                   # 脚本使用说明
```

## 🔒 安全注意事项

1. **JWT密钥管理**：确保JWT密钥安全存储，定期轮换
2. **数据库权限**：使用最小权限原则配置数据库用户
3. **HTTPS**：生产环境必须使用HTTPS
4. **权限审计**：定期审查用户权限分配
5. **日志监控**：监控异常的权限访问行为

## 📞 支持

如有问题，请：
1. 查看本文档的故障排除部分
2. 运行测试脚本验证系统状态
3. 检查应用日志获取详细错误信息
4. 联系开发团队获取技术支持

---

**版本**：1.0.0  
**更新时间**：2024年12月  
**维护者**：KnowFlow开发团队