# RBAC权限管理脚本集合

本目录包含了KnowFlow系统中所有与权限管理相关的脚本工具。

## 📁 脚本说明

### 🔧 核心管理脚本

#### `migrate_rbac.py`
**功能**：RBAC权限管理系统数据库迁移脚本  
**用途**：创建权限相关的数据表和初始数据  
**使用方法**：
```bash
cd /Users/zxwei/zhishi/KnowFlow/knowflow/scripts/role
python migrate_rbac.py
```

#### `user_management_guide.py`
**功能**：用户管理和角色授予操作指南  
**用途**：添加用户、授予角色、管理权限的交互式工具  
**使用方法**：
```bash
python user_management_guide.py
```
**特性**：
- 交互式用户界面
- 自动生成用户ID和密码
- 支持角色授予和撤销
- 查看用户角色和权限

### 🛠️ 维护工具脚本

#### `assign_super_admin.py`
**功能**：为用户分配超级管理员角色  
**用途**：快速为指定用户授予super_admin权限  
**使用方法**：
```bash
python assign_super_admin.py
```

#### `clean_duplicate_roles.py`
**功能**：清理重复的角色和用户角色分配记录  
**用途**：数据库维护，清理重复数据  
**使用方法**：
```bash
python clean_duplicate_roles.py
```

#### `check_user_roles.py`
**功能**：检查用户角色分配情况  
**用途**：查看和诊断用户权限配置  
**使用方法**：
```bash
python check_user_roles.py
```

### 🧪 测试脚本

#### `test_rbac.py`
**功能**：RBAC权限管理系统功能测试  
**用途**：验证权限系统的各项功能是否正常  
**使用方法**：
```bash
python test_rbac.py
```
**测试内容**：
- 用户登录功能
- 服务健康检查
- 角色和权限获取
- 权限检查功能
- 角色授予和撤销

#### `test_new_user.py`
**功能**：测试新创建用户的登录和权限功能  
**用途**：验证新用户的权限配置是否正确  
**使用方法**：
```bash
python test_new_user.py
```
**测试内容**：
- 新用户登录验证
- 角色获取测试
- 权限获取测试
- 权限检查测试

## 🚀 快速开始

### 1. 初始化权限系统
```bash
# 运行数据库迁移
python migrate_rbac.py
```

### 2. 添加用户和角色
```bash
# 使用交互式工具添加用户
python user_management_guide.py
```

### 3. 验证系统功能
```bash
# 运行完整测试
python test_rbac.py

# 测试新用户功能
python test_new_user.py
```

## 📋 可用角色类型

| 角色代码 | 角色名称 | 描述 | 权限范围 |
|---------|---------|------|----------|
| `super_admin` | 超级管理员 | 系统最高权限 | 所有权限 |
| `admin` | 管理员 | 租户管理权限 | 读取、写入、删除、分享 |
| `editor` | 编辑者 | 内容编辑权限 | 读取、写入、分享 |
| `viewer` | 查看者 | 只读权限 | 读取 |
| `guest` | 访客 | 受限访问 | 有限读取 |

## 🔧 环境要求

- Python 3.8+
- MySQL 5.7+
- Flask 2.0+
- 确保KnowFlow服务器正在运行（http://127.0.0.1:5000）

## 📝 注意事项

1. **运行环境**：所有脚本都需要在正确的Python环境中运行，确保已安装所需依赖
2. **数据库连接**：确保数据库连接配置正确
3. **服务状态**：测试脚本需要KnowFlow服务器处于运行状态
4. **权限要求**：某些操作需要管理员权限

## 🔍 故障排除

### 导入错误
如果遇到模块导入错误，请确保：
- 脚本在正确的目录中运行
- Python路径配置正确
- 所有依赖模块已安装

### 数据库连接错误
如果遇到数据库连接问题：
- 检查数据库服务是否启动
- 验证连接配置是否正确
- 确认数据库用户权限

### API调用失败
如果测试脚本中API调用失败：
- 确认KnowFlow服务器正在运行
- 检查API端点是否正确
- 验证认证token是否有效

---

**维护者**：KnowFlow开发团队  
**更新时间**：2024年12月