# KnowFlow RBAC 权限管理系统完整手册

## 目录
1. [产品使用手册](#产品使用手册)
   - [概述](#概述)
   - [角色体系](#角色体系)
   - [权限模型](#权限模型)
   - [全局角色与资源角色关系](#全局角色与资源角色关系)
   - [用户界面操作指南](#用户界面操作指南)
   - [最佳实践](#最佳实践)
2. [技术实现原理介绍](#技术实现原理介绍)
   - [系统架构](#系统架构)
   - [数据模型](#数据模型)
   - [权限计算逻辑](#权限计算逻辑)
   - [缓存机制](#缓存机制)
   - [安全机制](#安全机制)
3. [对外API接口文档](#对外api接口文档)
   - [权限检查接口](#权限检查接口)
   - [用户角色管理接口](#用户角色管理接口)
   - [团队角色管理接口](#团队角色管理接口)
   - [权限查询接口](#权限查询接口)

---

# 产品使用手册

## 概述

KnowFlow RBAC（Role-Based Access Control）权限管理系统是一个基于角色的访问控制系统，用于管理用户对系统资源的访问权限。系统支持多租户架构，提供了细粒度的权限控制能力。

### 核心概念

- **用户（User）**: 系统中的个体用户
- **角色（Role）**: 权限的集合，用于归类相似的权限需求
- **权限（Permission）**: 对特定资源进行特定操作的授权
- **资源（Resource）**: 系统中需要保护的对象（如知识库、文档等）
- **租户（Tenant）**: 多租户环境中的独立组织单位
- **团队（Team）**: 用户的组织单位，可以批量分配权限

## 角色体系

### 1. 系统预定义角色

| 角色代码 | 角色名称 | 描述 | 权限范围 |
|---------|---------|------|---------|
| `super_admin` | 超级管理员 | 拥有系统所有权限 | 系统级全权限 |
| `admin` | 管理员 | 拥有租户内所有权限 | 租户级全权限 |
| `editor` | 编辑者 | 可以读取、编辑和分享资源 | 读取、写入、分享 |
| `viewer` | 查看者 | 只能查看资源 | 读取 |
| `user` | 普通用户 | 基础用户权限 | 读取 |
| `guest` | 访客 | 访客权限，只能查看公开资源 | 受限读取 |

### 2. 角色优先级

角色按优先级从高到低排序：
1. `super_admin` - 最高权限
2. `admin` - 管理权限
3. `editor` - 编辑权限
4. `viewer` - 查看权限
5. `user` - 基础权限
6. `guest` - 最低权限

系统遵循**单一角色语义**：同一作用域内用户只能拥有一个角色，新分配的角色会替换旧角色。

## 权限模型

### 1. 权限类型

| 权限类型 | 描述 | 应用场景 |
|---------|------|---------|
| `read` | 读取权限 | 查看资源内容 |
| `write` | 写入权限 | 编辑资源内容 |
| `delete` | 删除权限 | 删除资源 |
| `admin` | 管理权限 | 管理资源和权限 |
| `share` | 分享权限 | 分享资源给其他用户 |
| `export` | 导出权限 | 导出资源数据 |

### 2. 资源类型

| 资源类型 | 描述 | 示例 |
|---------|------|------|
| `knowledgebase` | 知识库 | 文档集合 |
| `document` | 文档 | 单个文档 |
| `team` | 团队 | 用户组织 |
| `system` | 系统 | 全局系统功能 |
| `user` | 用户 | 用户管理 |

### 3. 权限组合

权限通过"资源类型_权限类型"的格式命名：
- `kb_read`: 知识库读取权限
- `kb_write`: 知识库写入权限
- `kb_admin`: 知识库管理权限
- `doc_read`: 文档读取权限
- `team_admin`: 团队管理权限

## 全局角色与资源角色关系

### 1. 全局角色

全局角色作用于整个租户范围，不绑定特定资源：

```
用户 → 全局角色 → 租户权限
```

**特点：**
- 作用域：整个租户
- resource_id：NULL
- resource_type：NULL 或 system
- 继承性：全局角色的权限可以应用到所有资源

**应用场景：**
- 系统管理员：管理整个系统
- 租户管理员：管理整个租户
- 默认用户角色：新用户的基础权限

### 2. 资源角色

资源角色绑定到特定资源，提供细粒度的权限控制：

```
用户 → 资源角色 → 特定资源权限
```

**特点：**
- 作用域：特定资源
- resource_id：具体资源ID
- resource_type：资源类型
- 精确性：只对特定资源有效

**应用场景：**
- 知识库协作者：只能访问特定知识库
- 文档编辑者：只能编辑特定文档
- 项目团队成员：只能访问项目相关资源

### 3. 权限继承关系

权限检查按以下优先级：

1. **超级管理员检查**：最高优先级
2. **直接权限检查**：用户直接被授予的权限
3. **角色权限检查**：
   - 资源级角色权限（精确匹配）
   - 全局角色权限（继承到所有资源）
4. **资源所有者权限**：资源创建者的默认权限
5. **团队权限继承**：通过团队获得的权限

### 4. 权限计算示例

假设用户A对知识库KB001的权限计算：

```
步骤1: 检查超级管理员 → NO
步骤2: 检查直接权限 → NO  
步骤3: 检查角色权限
  - 资源角色：KB001的editor角色 → 有write权限 ✓
  - 全局角色：租户的viewer角色 → 有read权限
步骤4: 检查所有者权限 → NO
步骤5: 检查团队权限 → NO

结果：用户A对KB001有write权限（通过资源角色）
```

## 用户界面操作指南

### 1. 用户管理界面

#### 查看用户列表
1. 导航到"系统设置" → "用户管理"
2. 查看用户列表，包含用户名、邮箱、角色信息
3. 使用搜索功能过滤用户

#### 分配用户角色
1. 在用户列表中点击"分配角色"按钮
2. 选择要分配的角色
3. 确认分配

**注意：** 
- 新角色会替换用户当前的角色（单一角色语义）
- 未分配角色的用户显示为"用户"

#### 创建新用户
1. 点击"新建用户"按钮
2. 填写用户信息：用户名、邮箱、密码
3. 选择初始角色（可选）
4. 提交创建

### 2. 知识库权限管理

#### 查看知识库权限
1. 进入知识库详情页
2. 点击"权限管理"标签
3. 查看当前权限分配情况

#### 分配知识库权限
1. 在权限管理页面点击"添加成员"
2. 选择用户或团队
3. 选择角色（viewer、editor、admin）
4. 确认分配

#### 权限变更
1. 在权限列表中找到目标用户
2. 点击"修改权限"
3. 选择新角色
4. 确认变更

### 3. 团队管理

#### 创建团队
1. 导航到"团队管理"
2. 点击"创建团队"
3. 填写团队信息
4. 添加团队成员

#### 团队权限分配
1. 选择团队
2. 进入"权限管理"
3. 为团队分配对特定资源的角色
4. 团队成员自动继承团队权限

## 最佳实践

### 1. 角色设计原则

**最小权限原则**
- 用户只获得完成工作所需的最小权限
- 定期审查和调整权限分配

**角色分离原则**
- 管理员角色与普通用户角色分离
- 读写权限分离

**职责分离原则**
- 不同职责使用不同角色
- 避免权限过度集中

### 2. 权限分配策略

**全局角色使用场景**
- 系统管理员：使用 `super_admin` 全局角色
- 租户管理员：使用 `admin` 全局角色
- 默认用户：使用 `user` 全局角色

**资源角色使用场景**
- 项目协作：为特定知识库分配 `editor` 角色
- 内容审查：为特定文档分配 `viewer` 角色
- 临时权限：为特定资源分配临时角色

**团队权限使用场景**
- 部门权限：为部门团队分配相关资源权限
- 项目组权限：为项目团队分配项目资源权限
- 批量权限管理：通过团队统一管理多个用户权限

### 3. 安全建议

**密码安全**
- 强制使用强密码
- 定期更换密码
- 启用多因素认证（如支持）

**权限审计**
- 定期审查用户权限分配
- 监控异常权限使用
- 记录权限变更日志

**访问控制**
- 及时撤销离职员工权限
- 限制超级管理员数量
- 实施最小权限原则

---

# 技术实现原理介绍

## 系统架构

### 1. 整体架构

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   前端界面层     │    │   API接口层     │    │   服务层        │
│  (React/Vue)    │◄──►│  (Flask Routes) │◄──►│ (Business Logic)│
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                        │
                       ┌─────────────────┐    ┌─────────────────┐
                       │   缓存层        │    │   数据访问层     │
                       │   (Redis)       │◄──►│  (Database)     │
                       └─────────────────┘    └─────────────────┘
```

### 2. 核心组件

- **权限服务层** (`permission_service.py`): 核心业务逻辑
- **权限计算器** (`permission_calculator.py`): 权限计算算法
- **权限缓存** (`permission_cache.py`): 性能优化缓存
- **数据模型** (`rbac_models.py`): 数据结构定义
- **API路由** (`rbac_routes.py`): HTTP接口暴露

### 3. 模块关系

```
rbac_routes.py (API层)
    ↓
permission_service.py (服务层)
    ↓
permission_calculator.py (计算层)
    ↓
rbac_models.py (模型层)
    ↓
Database (数据层)
```

## 数据模型

### 1. 核心数据表

#### 角色表 (rbac_roles)
```sql
CREATE TABLE rbac_roles (
    id VARCHAR(32) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    code VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    role_type VARCHAR(20) NOT NULL,
    is_system BOOLEAN DEFAULT FALSE,
    tenant_id VARCHAR(32),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

#### 权限表 (rbac_permissions)
```sql
CREATE TABLE rbac_permissions (
    id VARCHAR(32) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    code VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    resource_type VARCHAR(20) NOT NULL,
    permission_type VARCHAR(20) NOT NULL,
    is_system BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

#### 用户角色关联表 (rbac_user_roles)
```sql
CREATE TABLE rbac_user_roles (
    id VARCHAR(32) PRIMARY KEY,
    user_id VARCHAR(32) NOT NULL,
    role_id VARCHAR(32) NOT NULL,
    resource_type VARCHAR(20),
    resource_id VARCHAR(32),
    tenant_id VARCHAR(32),
    granted_by VARCHAR(32),
    granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY unique_user_role_resource (user_id, tenant_id, resource_type, resource_id)
);
```

#### 角色权限关联表 (rbac_role_permissions)
```sql
CREATE TABLE rbac_role_permissions (
    id VARCHAR(32) PRIMARY KEY,
    role_id VARCHAR(32) NOT NULL,
    permission_id VARCHAR(32) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_role_permission (role_id, permission_id)
);
```

#### 团队角色表 (rbac_team_roles)
```sql
CREATE TABLE rbac_team_roles (
    id VARCHAR(32) PRIMARY KEY,
    team_id VARCHAR(32) NOT NULL,
    role_code VARCHAR(50) NOT NULL,
    resource_type VARCHAR(20),
    resource_id VARCHAR(32),
    tenant_id VARCHAR(32) NOT NULL,
    granted_by VARCHAR(32),
    granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NULL,
    is_active BOOLEAN DEFAULT TRUE
);
```

### 2. 数据关系

```
User ←→ UserRole ←→ Role ←→ RolePermission ←→ Permission
  │                                              ↑
  └── Team ←→ TeamRole ←─────────────────────────┘
```

### 3. 索引策略

**性能关键索引：**
```sql
-- 用户角色查询优化
CREATE INDEX idx_user_roles_user_active ON rbac_user_roles(user_id, is_active);
CREATE INDEX idx_user_roles_resource ON rbac_user_roles(resource_type, resource_id);

-- 团队角色查询优化
CREATE INDEX idx_team_roles_team_active ON rbac_team_roles(team_id, is_active);
CREATE INDEX idx_team_roles_resource ON rbac_team_roles(resource_type, resource_id);

-- 权限查询优化
CREATE INDEX idx_role_permissions_role ON rbac_role_permissions(role_id, is_active);
CREATE INDEX idx_permissions_resource ON rbac_permissions(resource_type, permission_type);
```

## 权限计算逻辑

### 1. 权限检查算法

```python
def check_permission(user_id, resource_type, resource_id, permission_type, tenant_id):
    """
    权限检查主流程
    """
    # 1. 超级管理员检查（最高优先级）
    if is_super_admin(user_id):
        return PermissionResult(True, "超级管理员权限")
    
    # 2. 直接权限检查
    if has_direct_permission(user_id, resource_type, resource_id, permission_type):
        return PermissionResult(True, "直接权限授权")
    
    # 3. 角色权限检查
    role_result = check_role_permission(user_id, resource_type, resource_id, permission_type)
    if role_result.has_permission:
        return role_result
    
    # 4. 资源所有者检查
    if is_resource_owner(user_id, resource_type, resource_id):
        return PermissionResult(True, "资源所有者权限")
    
    # 5. 默认拒绝
    return PermissionResult(False, "无相关权限")
```

### 2. 角色权限计算

```python
def check_role_permission(user_id, resource_type, resource_id, permission_type):
    """
    角色权限计算（包含用户角色和团队角色）
    """
    # 查询用户直接角色
    user_roles = get_user_direct_roles(user_id, resource_type, resource_id)
    
    # 查询用户团队角色
    team_roles = get_user_team_roles(user_id, resource_type, resource_id)
    
    # 合并所有角色
    all_roles = user_roles + team_roles
    
    # 检查角色权限
    for role in all_roles:
        if role_has_permission(role, permission_type):
            return PermissionResult(True, f"角色权限: {role.name}")
    
    return PermissionResult(False, "无角色权限")
```

### 3. 权限继承逻辑

```python
def check_permission_inheritance(user_id, resource_type, resource_id, permission_type):
    """
    权限继承检查：全局权限 → 资源权限
    """
    # 1. 检查资源级权限（精确匹配）
    resource_permission = check_resource_permission(user_id, resource_type, resource_id, permission_type)
    if resource_permission.has_permission:
        return resource_permission
    
    # 2. 检查全局权限（继承到所有资源）
    global_permission = check_global_permission(user_id, permission_type)
    if global_permission.has_permission:
        return PermissionResult(True, "全局权限继承")
    
    return PermissionResult(False, "无继承权限")
```

### 4. 团队权限计算

```python
def get_user_team_permissions(user_id, resource_type, resource_id):
    """
    计算用户通过团队获得的权限
    """
    # 1. 查询用户所属团队
    user_teams = get_user_teams(user_id)
    
    # 2. 查询团队权限
    team_permissions = []
    for team in user_teams:
        team_roles = get_team_roles(team.id, resource_type, resource_id)
        for role in team_roles:
            permissions = get_role_permissions(role.code)
            team_permissions.extend(permissions)
    
    return deduplicate_permissions(team_permissions)
```

## 缓存机制

### 1. 缓存架构

```
Application Layer
       ↓
Permission Cache Layer (Redis)
       ↓
Database Layer (MySQL)
```

### 2. 缓存策略

#### 缓存键设计
```python
# 用户权限缓存
CACHE_KEY_PATTERNS = {
    "user_permission": "rbac:perm:user:{user_id}:{resource_type}:{resource_id}:{permission_type}",
    "user_roles": "rbac:roles:user:{user_id}:{tenant_id}",
    "team_roles": "rbac:team_roles:team:{team_id}:{resource_type}:{resource_id}",
    "role_permissions": "rbac:role_perms:{role_code}"
}
```

#### 缓存过期策略
```python
CACHE_TTL = {
    "user_permission": 300,    # 5分钟
    "user_roles": 600,         # 10分钟
    "team_roles": 600,         # 10分钟
    "role_permissions": 3600   # 1小时
}
```

### 3. 缓存失效策略

#### 智能失效
```python
def invalidate_permission_cache(operation_type, **kwargs):
    """
    基于操作类型智能失效缓存
    """
    if operation_type == "user_role_changed":
        # 失效用户相关缓存
        invalidate_user_cache(kwargs["user_id"])
        
    elif operation_type == "team_role_changed":
        # 失效团队相关缓存
        invalidate_team_cache(kwargs["team_id"])
        
    elif operation_type == "resource_deleted":
        # 失效资源相关缓存
        invalidate_resource_cache(kwargs["resource_type"], kwargs["resource_id"])
```

#### 批量失效
```python
def batch_invalidate_cache(cache_keys):
    """
    批量失效缓存，提高性能
    """
    pipeline = redis_client.pipeline()
    for key in cache_keys:
        pipeline.delete(key)
    pipeline.execute()
```

### 4. 缓存预热

```python
def warmup_permission_cache(user_id):
    """
    权限缓存预热
    """
    # 预加载用户常用权限
    common_resources = get_user_common_resources(user_id)
    for resource in common_resources:
        for permission_type in ["read", "write"]:
            check_permission_with_cache(user_id, resource.type, resource.id, permission_type)
```

## 安全机制

### 1. 输入验证

```python
def validate_permission_request(data):
    """
    权限请求参数验证
    """
    # 参数存在性检查
    required_fields = ["user_id", "resource_type", "permission_type"]
    for field in required_fields:
        if field not in data:
            raise ValidationError(f"缺少必需参数: {field}")
    
    # 参数合法性检查
    if data["resource_type"] not in VALID_RESOURCE_TYPES:
        raise ValidationError(f"无效的资源类型: {data['resource_type']}")
    
    # SQL注入防护
    sanitize_input(data["user_id"])
    sanitize_input(data["resource_id"])
```

### 2. 权限提升防护

```python
def check_privilege_escalation(current_user, target_user, new_role):
    """
    检查权限提升攻击
    """
    # 防止用户给自己分配更高权限
    if current_user == target_user:
        current_role_level = get_role_level(get_user_role(current_user))
        new_role_level = get_role_level(new_role)
        if new_role_level < current_role_level:
            raise SecurityError("不能为自己分配更高权限")
    
    # 防止分配超出自己权限的角色
    if not has_permission(current_user, "admin", "system", None):
        raise SecurityError("权限不足，无法分配此角色")
```

### 3. 操作审计

```python
def audit_permission_operation(operation, user_id, target_user, details):
    """
    权限操作审计日志
    """
    audit_log = {
        "timestamp": datetime.now().isoformat(),
        "operation": operation,
        "operator": user_id,
        "target": target_user,
        "details": details,
        "ip_address": get_client_ip(),
        "user_agent": get_user_agent()
    }
    
    # 记录到审计日志
    logger.info(f"RBAC_AUDIT: {json.dumps(audit_log)}")
    
    # 存储到审计表
    save_audit_log(audit_log)
```

### 4. 会话管理

```python
def validate_session_permission(session_token, required_permission):
    """
    会话权限验证
    """
    # 验证会话有效性
    session = get_session(session_token)
    if not session or session.is_expired():
        raise AuthenticationError("会话已过期")
    
    # 验证权限
    if not has_permission(session.user_id, required_permission):
        raise AuthorizationError("权限不足")
    
    # 更新最后访问时间
    update_session_last_access(session_token)
```

---

# 对外API接口文档

## 权限检查接口

### 1. 检查用户权限

**接口地址:** `POST /api/v1/rbac/permissions/check`

**请求参数:**
```json
{
    "user_id": "user_123",
    "resource_type": "knowledgebase",
    "resource_id": "kb_456", 
    "permission_type": "read",
    "tenant_id": "tenant_789"
}
```

**响应数据:**
```json
{
    "has_permission": true,
    "user_id": "user_123",
    "resource_type": "knowledgebase",
    "resource_id": "kb_456",
    "permission_type": "read",
    "granted_roles": ["editor"],
    "reason": "角色权限授权"
}
```

**错误响应:**
```json
{
    "error": "权限检查失败",
    "message": "用户不存在",
    "code": 404
}
```

### 2. 检查全局权限

**接口地址:** `POST /api/v1/rbac/permissions/check-global`

**请求参数:**
```json
{
    "user_id": "user_123",
    "permission_type": "write",
    "tenant_id": "tenant_789"
}
```

**响应数据:**
```json
{
    "has_permission": true,
    "user_id": "user_123",
    "resource_type": "system",
    "resource_id": null,
    "permission_type": "write",
    "granted_roles": ["admin"],
    "reason": "全局角色权限授权"
}
```

### 3. 简化权限检查

**接口地址:** `POST /api/v1/rbac/permissions/simple-check`

**请求参数:**
```json
{
    "user_id": "user_123",
    "permission_code": "kb_read",
    "resource_id": "kb_456",
    "tenant_id": "tenant_789"
}
```

**响应数据:**
```json
{
    "has_permission": true,
    "user_id": "user_123",
    "permission_code": "kb_read",
    "resource_id": "kb_456",
    "tenant_id": "tenant_789"
}
```

## 用户角色管理接口

### 1. 获取用户角色

**接口地址:** `GET /api/v1/rbac/users/{user_id}/roles`

**查询参数:**
- `tenant_id`: 租户ID（可选，默认为default）

**响应数据:**
```json
{
    "user_id": "user_123",
    "roles": [
        {
            "id": "role_001",
            "name": "编辑者",
            "code": "editor",
            "description": "可以读取、编辑和分享资源",
            "role_type": "editor",
            "is_system": true,
            "tenant_id": "tenant_789",
            "created_at": "2024-01-01T10:00:00",
            "updated_at": "2024-01-01T10:00:00"
        }
    ],
    "total": 1
}
```

### 2. 为用户分配角色

**接口地址:** `POST /api/v1/rbac/users/{user_id}/roles`

**请求参数:**
```json
{
    "role_code": "editor",
    "tenant_id": "tenant_789",
    "resource_type": "knowledgebase",
    "resource_id": "kb_456",
    "expires_at": "2024-12-31T23:59:59"
}
```

**响应数据:**
```json
{
    "message": "成功为用户 user_123 授予角色 editor",
    "user_id": "user_123",
    "role_code": "editor",
    "granted_by": "system",
    "tenant_id": "tenant_789",
    "resource_type": "knowledgebase",
    "resource_id": "kb_456",
    "expires_at": "2024-12-31T23:59:59"
}
```

### 3. 撤销用户角色

**接口地址:** `DELETE /api/v1/rbac/users/{user_id}/roles/{role_code}`

**查询参数:**
- `tenant_id`: 租户ID
- `resource_id`: 资源ID（可选）

**响应数据:**
```json
{
    "message": "成功撤销用户 user_123 的角色 editor",
    "user_id": "user_123",
    "role_code": "editor",
    "tenant_id": "tenant_789",
    "resource_id": "kb_456"
}
```

### 4. 获取用户权限

**接口地址:** `GET /api/v1/rbac/users/{user_id}/permissions`

**查询参数:**
- `tenant_id`: 租户ID
- `resource_type`: 资源类型过滤（可选）

**响应数据:**
```json
{
    "user_id": "user_123",
    "permissions": [
        {
            "id": "perm_001",
            "name": "查看知识库",
            "code": "kb_read",
            "description": "可以查看知识库内容",
            "resource_type": "knowledgebase",
            "permission_type": "read",
            "created_at": "2024-01-01T10:00:00",
            "updated_at": "2024-01-01T10:00:00"
        }
    ],
    "total": 1,
    "resource_type_filter": "knowledgebase"
}
```

## 团队角色管理接口

### 1. 为团队分配角色

**接口地址:** `POST /api/v1/rbac/teams/{team_id}/roles`

**请求参数:**
```json
{
    "role_code": "editor",
    "resource_type": "knowledgebase",
    "resource_id": "kb_456",
    "tenant_id": "tenant_789",
    "granted_by": "admin_user"
}
```

**响应数据:**
```json
{
    "message": "团队角色授权成功",
    "team_id": "team_123",
    "role_code": "editor",
    "resource_type": "knowledgebase",
    "resource_id": "kb_456",
    "tenant_id": "tenant_789",
    "granted_by": "admin_user"
}
```

### 2. 撤销团队角色

**接口地址:** `DELETE /api/v1/rbac/teams/{team_id}/roles`

**查询参数:**
- `role_code`: 角色代码（可选）
- `resource_type`: 资源类型
- `resource_id`: 资源ID
- `tenant_id`: 租户ID

**响应数据:**
```json
{
    "message": "团队角色撤销成功",
    "team_id": "team_123",
    "affected_rows": 1
}
```

### 3. 获取团队角色

**接口地址:** `GET /api/v1/rbac/teams/{team_id}/roles`

**查询参数:**
- `resource_type`: 资源类型（可选）
- `resource_id`: 资源ID（可选）
- `tenant_id`: 租户ID

**响应数据:**
```json
{
    "team_id": "team_123",
    "roles": [
        {
            "id": "team_role_001",
            "team_id": "team_123",
            "role_code": "editor",
            "resource_type": "knowledgebase",
            "resource_id": "kb_456",
            "tenant_id": "tenant_789",
            "granted_by": "admin_user",
            "granted_at": "2024-01-01T10:00:00",
            "expires_at": null,
            "is_active": true
        }
    ],
    "total": 1
}
```

### 4. 获取用户团队角色

**接口地址:** `GET /api/v1/rbac/users/{user_id}/team-roles`

**查询参数:**
- `tenant_id`: 租户ID

**响应数据:**
```json
{
    "user_id": "user_123",
    "team_roles": [
        {
            "id": "team_role_001",
            "team_id": "team_456",
            "role_code": "editor",
            "resource_type": "knowledgebase",
            "resource_id": "kb_789",
            "tenant_id": "tenant_789",
            "granted_by": "admin_user",
            "granted_at": "2024-01-01T10:00:00",
            "expires_at": null,
            "is_active": true
        }
    ],
    "total": 1
}
```

## 权限查询接口

### 1. 获取所有角色

**接口地址:** `GET /api/v1/rbac/roles`

**响应数据:**
```json
{
    "success": true,
    "data": [
        {
            "id": "role_001",
            "name": "超级管理员",
            "code": "super_admin",
            "description": "拥有系统所有权限",
            "role_type": "super_admin",
            "is_system": true,
            "tenant_id": null,
            "created_at": "2024-01-01T10:00:00",
            "updated_at": "2024-01-01T10:00:00"
        }
    ],
    "total": 1
}
```

### 2. 获取所有权限

**接口地址:** `GET /api/v1/rbac/permissions`

**响应数据:**
```json
[
    {
        "id": "perm_001",
        "code": "kb_read",
        "name": "查看知识库",
        "description": "可以查看知识库内容",
        "resource_type": "knowledgebase",
        "permission_type": "read",
        "created_at": "2024-01-01T10:00:00",
        "updated_at": "2024-01-01T10:00:00"
    }
]
```

### 3. 获取角色权限映射

**接口地址:** `GET /api/v1/rbac/roles/{role_code}/permissions`

**响应数据:**
```json
[
    {
        "permission_id": "perm_001",
        "permission_code": "kb_read",
        "permission_name": "查看知识库",
        "description": "可以查看知识库内容",
        "resource_type": "knowledgebase",
        "permission_type": "read",
        "role_name": "编辑者",
        "granted_at": "2024-01-01T10:00:00"
    }
]
```

### 4. 健康检查

**接口地址:** `GET /api/v1/rbac/health`

**响应数据:**
```json
{
    "status": "healthy",
    "service": "RBAC权限管理系统",
    "version": "1.0.0",
    "timestamp": "2024-01-01T10:00:00"
}
```

## 错误码说明

| 错误码 | 说明 | 处理建议 |
|-------|------|---------|
| 400 | 请求参数错误 | 检查请求参数格式和内容 |
| 401 | 未授权访问 | 需要先进行身份认证 |
| 403 | 权限不足 | 用户没有执行此操作的权限 |
| 404 | 资源不存在 | 检查资源ID是否正确 |
| 409 | 资源冲突 | 资源已存在或状态冲突 |
| 500 | 服务器内部错误 | 联系系统管理员 |

## 接口调用示例

### Python示例

```python
import requests
import json

# 配置
API_BASE_URL = "http://localhost:5000/api/v1/rbac"
headers = {"Content-Type": "application/json"}

def check_user_permission(user_id, resource_type, resource_id, permission_type):
    """检查用户权限"""
    url = f"{API_BASE_URL}/permissions/check"
    data = {
        "user_id": user_id,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "permission_type": permission_type
    }
    
    response = requests.post(url, headers=headers, data=json.dumps(data))
    return response.json()

def assign_user_role(user_id, role_code, resource_type=None, resource_id=None):
    """为用户分配角色"""
    url = f"{API_BASE_URL}/users/{user_id}/roles"
    data = {
        "role_code": role_code
    }
    if resource_type:
        data["resource_type"] = resource_type
    if resource_id:
        data["resource_id"] = resource_id
    
    response = requests.post(url, headers=headers, data=json.dumps(data))
    return response.json()

# 使用示例
result = check_user_permission("user_123", "knowledgebase", "kb_456", "read")
print(f"用户权限检查结果: {result}")

result = assign_user_role("user_123", "editor", "knowledgebase", "kb_456")
print(f"角色分配结果: {result}")
```

### JavaScript示例

```javascript
const API_BASE_URL = "http://localhost:5000/api/v1/rbac";

async function checkUserPermission(userId, resourceType, resourceId, permissionType) {
    const response = await fetch(`${API_BASE_URL}/permissions/check`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            user_id: userId,
            resource_type: resourceType,
            resource_id: resourceId,
            permission_type: permissionType
        })
    });
    
    return await response.json();
}

async function assignUserRole(userId, roleCode, resourceType = null, resourceId = null) {
    const data = { role_code: roleCode };
    if (resourceType) data.resource_type = resourceType;
    if (resourceId) data.resource_id = resourceId;
    
    const response = await fetch(`${API_BASE_URL}/users/${userId}/roles`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    });
    
    return await response.json();
}

// 使用示例
checkUserPermission("user_123", "knowledgebase", "kb_456", "read")
    .then(result => console.log("权限检查结果:", result));

assignUserRole("user_123", "editor", "knowledgebase", "kb_456")
    .then(result => console.log("角色分配结果:", result));
```

---

## 总结

本手册详细介绍了KnowFlow RBAC权限管理系统的产品使用方法、技术实现原理和API接口文档。系统具有以下特点：

### 核心优势
1. **灵活的权限模型**: 支持全局角色和资源角色的层次化权限管理
2. **高性能设计**: 采用多级缓存和智能权限计算优化性能
3. **安全可靠**: 完善的输入验证、权限检查和审计机制
4. **易于扩展**: 模块化设计，便于添加新的资源类型和权限

### 使用建议
1. 遵循最小权限原则进行权限分配
2. 定期审查和清理不必要的权限
3. 合理使用全局角色和资源角色
4. 充分利用团队权限简化管理

### 技术特点
1. **单一角色语义**: 避免权限冲突和管理复杂性
2. **权限继承机制**: 全局权限自动继承到资源级别
3. **智能缓存策略**: 提高权限检查性能
4. **完善的API接口**: 支持各种权限管理操作

通过本手册，用户可以全面了解和有效使用KnowFlow RBAC权限管理系统，确保系统资源的安全访问和合理权限分配。