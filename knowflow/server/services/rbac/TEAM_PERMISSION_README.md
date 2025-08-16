# 团队权限管理功能实现

## 📋 功能概述

团队权限管理功能允许为整个团队授予知识库权限，团队成员将自动继承团队的权限。这大大简化了批量用户权限管理的复杂度。

## 🏗️ 系统架构

### 数据模型

#### 1. TeamRole 数据模型
```python
@dataclass
class TeamRole:
    """团队角色映射"""
    id: Optional[str] = None
    team_id: str = ""  # 团队ID (tenant_id)
    role_code: str = ""  # 角色代码
    resource_type: Optional[ResourceType] = None  # 资源类型
    resource_id: Optional[str] = None  # 资源ID
    tenant_id: str = "default"  # 租户ID
    granted_by: Optional[str] = None  # 授权者
    granted_at: Optional[str] = None  # 授权时间
    expires_at: Optional[str] = None  # 过期时间
    is_active: bool = True  # 是否激活
```

#### 2. 数据库表结构
```sql
CREATE TABLE rbac_team_roles (
    id VARCHAR(32) PRIMARY KEY,
    team_id VARCHAR(32) NOT NULL COMMENT '团队ID',
    role_code VARCHAR(50) NOT NULL COMMENT '角色代码', 
    resource_type ENUM('system', 'knowledgebase', 'document', 'team', 'user') DEFAULT NULL COMMENT '资源类型',
    resource_id VARCHAR(32) DEFAULT NULL COMMENT '资源ID',
    tenant_id VARCHAR(32) NOT NULL DEFAULT 'default' COMMENT '租户ID',
    granted_by VARCHAR(32) DEFAULT NULL COMMENT '授权者',
    granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '授权时间',
    expires_at TIMESTAMP NULL COMMENT '过期时间',
    is_active TINYINT(1) DEFAULT 1 COMMENT '是否激活',
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_team_resource (team_id, resource_type, resource_id),
    INDEX idx_role_code (role_code),
    INDEX idx_tenant_id (tenant_id),
    UNIQUE KEY uk_team_role_resource (team_id, role_code, resource_type, resource_id, tenant_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='团队角色映射表';
```

### 权限等级

| 权限级别 | 角色代码 | 权限说明 |
|---------|---------|----------|
| `read` | `viewer` | 可以查看知识库内的文档内容 |
| `write` | `editor` | 可以上传文件以及文件解析，编辑知识库内容 |
| `admin` | `admin` | 可以新增和删除知识库，管理知识库的所有内容和权限 |

## 🔧 核心功能

### 1. 权限服务方法

#### grant_team_role()
为团队授予特定资源的角色权限。

```python
permission_service.grant_team_role(
    team_id="team_001",
    role_code="viewer",
    resource_type=ResourceType.KNOWLEDGEBASE,
    resource_id="kb_001",
    tenant_id="default_tenant",
    granted_by="admin_user"
)
```

#### revoke_team_role()
撤销团队的资源权限。

```python
permission_service.revoke_team_role(
    team_id="team_001",
    resource_type=ResourceType.KNOWLEDGEBASE,
    resource_id="kb_001",
    tenant_id="default_tenant"
)
```

#### get_user_team_roles()
获取用户通过团队继承的所有角色。

```python
team_roles = permission_service.get_user_team_roles(
    user_id="user_001",
    tenant_id="default"
)
```

### 2. 权限检查机制

系统的权限检查流程已更新，包含以下步骤：

1. **超级管理员检查** - 检查用户是否为超级管理员
2. **直接权限检查** - 检查用户的直接资源权限
3. **角色权限检查** - 检查用户直接角色 + 团队角色权限
4. **资源所有者检查** - 检查用户是否为资源所有者

团队权限通过以下SQL查询实现：

```sql
SELECT DISTINCT r.code, r.name FROM rbac_team_roles tr
JOIN user_tenant ut ON tr.team_id = ut.tenant_id
JOIN rbac_roles r ON tr.role_code = r.code
JOIN rbac_role_permissions rp ON r.id = rp.role_id
JOIN rbac_permissions p ON rp.permission_id = p.id
WHERE ut.user_id = %s AND ut.status = 1 AND tr.is_active = 1
AND p.resource_type = %s AND p.permission_type = %s
AND (tr.expires_at IS NULL OR tr.expires_at > NOW())
AND (tr.resource_id IS NULL OR tr.resource_id = %s)
```

## 🌐 API 接口

### 知识库团队权限管理

#### 1. 获取知识库权限列表
```http
GET /api/v1/knowledgebases/{kb_id}/permissions
```

**响应示例：**
```json
{
  "success": true,
  "data": {
    "total": 3,
    "user_permissions": [
      {
        "user_id": "user_001",
        "username": "张三",
        "permission_level": "admin",
        "granted_at": "2024-01-01T10:00:00",
        "permission_source": "user"
      }
    ],
    "team_permissions": [
      {
        "team_id": "team_001", 
        "team_name": "开发团队",
        "permission_level": "write",
        "granted_at": "2024-01-01T10:00:00",
        "permission_source": "team"
      }
    ]
  }
}
```

#### 2. 为团队授予权限
```http
POST /api/v1/knowledgebases/{kb_id}/permissions/teams
```

**请求参数：**
```json
{
  "team_id": "team_001",
  "permission_level": "write"
}
```

#### 3. 撤销团队权限
```http
DELETE /api/v1/knowledgebases/{kb_id}/permissions/teams/{team_id}
```

## 💻 前端实现

### 权限管理模态框

前端提供了完整的团队权限管理界面：

1. **双标签页设计** - 分别管理用户权限和团队权限
2. **团队选择器** - 支持搜索和筛选团队
3. **权限级别选择** - 读取、写入、管理三种级别
4. **实时权限列表** - 显示当前所有权限分配
5. **权限撤销** - 一键撤销团队或用户权限

### 核心组件

#### PermissionModal.tsx
```typescript
interface TeamPermission {
  team_id: string;
  team_name: string;
  permission_level: string;
  granted_at?: string;
  permission_source: 'team';
}
```

## 🔄 工作流程

### 团队权限授予流程

1. **管理员选择团队** - 从团队列表中选择目标团队
2. **选择权限级别** - 读取、写入或管理权限
3. **系统记录权限** - 在 `rbac_team_roles` 表中创建记录
4. **成员自动继承** - 团队所有成员自动获得相应权限
5. **权限检查生效** - 下次权限检查时团队权限生效

### 团队权限继承机制

```
团队权限 (rbac_team_roles)
    ↓
用户-团队关系 (user_tenant)
    ↓
用户继承权限 (权限检查时动态计算)
```

## 🚀 部署和配置

### 1. 数据库迁移

首先创建团队角色表：

```bash
cd knowflow/server
source venv/bin/activate
python scripts/init_kb_rbac.py
```

### 2. 验证功能

运行测试脚本验证功能：

```python
# 测试团队权限服务
from services.rbac.permission_service import permission_service
from models.rbac_models import ResourceType

# 为团队授予权限
success = permission_service.grant_team_role(
    team_id="test_team",
    role_code="kb_reader", 
    resource_type=ResourceType.KNOWLEDGEBASE,
    resource_id="test_kb"
)
```

## ⚠️ 注意事项

1. **数据库表依赖** - 需要先创建 `rbac_team_roles` 表
2. **团队成员管理** - 依赖现有的 `user_tenant` 表关系
3. **权限缓存** - 团队权限变更后立即生效，无需重启
4. **权限优先级** - 用户直接权限优先于团队继承权限
5. **团队删除** - 删除团队时应同时清理相关权限记录

## 🎯 功能优势

1. **批量管理** - 一次设置团队权限，所有成员自动获得
2. **动态继承** - 新加入团队的成员自动继承团队权限
3. **精细控制** - 支持资源级别的细粒度权限控制
4. **易于维护** - 减少单独为每个用户设置权限的工作量
5. **权限透明** - 前端清晰显示权限来源（用户直接权限 vs 团队继承权限）

## 🔮 扩展方向

1. **权限继承层级** - 支持多级团队权限继承
2. **权限模板** - 预定义常用的团队权限组合
3. **权限审计** - 记录团队权限变更历史
4. **批量操作** - 支持批量授予/撤销多个团队权限
5. **权限报告** - 生成团队权限分析报告