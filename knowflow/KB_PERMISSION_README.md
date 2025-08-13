# 知识库权限管理系统

## 概述

基于 RBAC (Role-Based Access Control) 实现的知识库权限管理系统，支持针对知识库为用户和团队分配不同级别的访问权限。

## 权限级别

### 三种权限级别

1. **管理员 (Admin)**
   - 🔴 可以新增和删除知识库
   - 📝 可以上传文件以及文件解析
   - 👀 可以查看知识库内的文档内容
   - ⚙️ 可以管理知识库权限
   - 🔗 可以分享知识库

2. **编辑者 (Writer)**
   - 📝 可以上传文件以及文件解析
   - 👀 可以查看知识库内的文档内容
   - 🔗 可以分享知识库

3. **查看者 (Reader)**
   - 👀 可以查看知识库内的文档内容

## 系统架构

### 后端实现

#### RBAC 模型
- **角色 (Roles)**: `kb_admin`, `kb_writer`, `kb_reader`
- **权限 (Permissions)**: `kb_read`, `kb_write`, `kb_delete`, `kb_admin`, `kb_share`
- **资源类型 (Resource Types)**: `knowledgebase`, `document`

#### 核心服务
- `PermissionService`: 权限检查和管理
- `KnowledgebaseService`: 知识库权限管理扩展
- `permission_decorator`: 权限验证装饰器

#### API 接口

##### 权限管理接口
```
GET    /api/v1/knowledgebases/{kb_id}/permissions        # 获取知识库权限列表
POST   /api/v1/knowledgebases/{kb_id}/permissions/users  # 为用户授予权限
DELETE /api/v1/knowledgebases/{kb_id}/permissions/users/{user_id}  # 撤销用户权限
POST   /api/v1/knowledgebases/{kb_id}/permissions/teams  # 为团队授予权限
DELETE /api/v1/knowledgebases/{kb_id}/permissions/teams/{team_id}  # 撤销团队权限
POST   /api/v1/knowledgebases/{kb_id}/permissions/check  # 检查用户权限
```

##### RBAC 核心接口
```
POST   /api/v1/rbac/permissions/check           # 权限检查
GET    /api/v1/rbac/users/{user_id}/roles       # 获取用户角色
GET    /api/v1/rbac/users/{user_id}/permissions # 获取用户权限
POST   /api/v1/rbac/users/{user_id}/roles       # 授予用户角色
DELETE /api/v1/rbac/users/{user_id}/roles/{role_code}  # 撤销用户角色
```

### 前端实现

#### 权限管理组件
- `PermissionModal`: 权限管理模态框
- 集成到知识库管理页面的权限按钮

#### 功能特性
- 用户权限管理：查看、添加、撤销用户权限
- 团队权限管理：为团队批量授权
- 权限级别可视化：使用不同颜色标签区分权限级别
- 实时权限验证：基于权限控制按钮和功能可见性

## 部署和配置

### 1. 数据库初始化

运行 RBAC 数据库迁移脚本：
```bash
cd knowflow/scripts/role
python migrate_rbac.py
```

### 2. 知识库权限初始化

运行知识库权限初始化脚本：
```bash
cd knowflow/scripts
python init_kb_rbac.py
```

### 3. 服务启动

确保以下服务已启动：
- RBAC 权限服务路由已注册
- 知识库服务权限验证已集成

## 使用指南

### 管理员操作

1. **查看权限列表**
   - 在知识库管理页面，点击知识库对应的"权限"按钮
   - 查看当前知识库的所有用户权限

2. **授予用户权限**
   - 在权限管理弹窗中，选择用户和权限级别
   - 点击"添加权限"按钮完成授权

3. **撤销用户权限**
   - 在权限列表中，点击对应用户的"撤销"按钮
   - 确认后即可撤销该用户的所有知识库权限

4. **团队权限管理**
   - 选择团队和权限级别
   - 系统会为团队中的所有成员授予相应权限

### 权限验证

系统会在以下操作时自动进行权限验证：

- **知识库查看**: 需要 `read` 权限
- **文档上传/解析**: 需要 `write` 权限
- **知识库编辑**: 需要 `write` 权限
- **知识库删除**: 需要 `admin` 权限
- **权限管理**: 需要 `admin` 权限

## API 使用示例

### 检查用户权限
```bash
curl -X POST http://localhost:5000/api/v1/rbac/permissions/check \
  -H "Content-Type: application/json" \
  -d '{
    "resource_type": "knowledgebase",
    "resource_id": "kb_123",
    "permission_type": "read",
    "user_id": "user_456"
  }'
```

### 为用户授予权限
```bash
curl -X POST http://localhost:5000/api/v1/knowledgebases/kb_123/permissions/users \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_456",
    "permission_level": "write"
  }'
```

### 获取知识库权限列表
```bash
curl -X GET http://localhost:5000/api/v1/knowledgebases/kb_123/permissions
```

## 注意事项

1. **权限继承**: 高级权限自动包含低级权限 (`admin` > `write` > `read`)
2. **资源级权限**: 权限是基于具体知识库的，不同知识库的权限相互独立
3. **团队权限**: 团队权限变更会影响团队中的所有成员
4. **系统角色**: 超级管理员拥有所有知识库的完整权限

## 故障排除

### 常见问题

1. **权限检查失败**
   - 检查用户是否已登录
   - 确认用户拥有相应的角色和权限
   - 验证资源ID是否正确

2. **权限授予失败**
   - 确认操作用户拥有 `admin` 权限
   - 检查目标用户是否存在
   - 验证权限级别参数是否正确

3. **前端权限按钮不显示**
   - 检查当前用户的权限级别
   - 确认权限验证逻辑是否正确实现
   - 查看浏览器控制台是否有错误信息

### 日志查看

权限相关的日志通常位于：
- 服务端日志: 包含权限检查和操作记录
- 数据库日志: 记录角色和权限的变更

## 扩展开发

### 添加新的权限类型

1. 在 `rbac_models.py` 中添加新的权限定义
2. 更新初始化脚本 `init_kb_rbac.py`
3. 在相应的服务中添加权限验证
4. 更新前端权限管理界面

### 集成到其他模块

1. 导入权限装饰器: `from services.rbac.permission_decorator import require_permission`
2. 在需要权限验证的路由上添加装饰器
3. 根据业务需求定义相应的权限代码 