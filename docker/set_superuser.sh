#!/bin/bash

# RagFlow 用户管理脚本 - 无依赖版本
# 用法: ./simple_set_superuser.sh <action> [email] [options]
# 
# 动作:
#   list                    - 列出所有用户
#   show <email>           - 显示指定用户信息
#   set <email>            - 设置用户为超级用户
#   unset <email>          - 移除用户的超级用户权限
#   add <email> <password> - 添加新用户
#   delete <email>         - 删除用户
#   reset <email> <password> - 重置用户密码

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印函数
print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }

# 显示帮助信息
show_help() {
    echo "RagFlow 用户管理脚本"
    echo ""
    echo "用法: $0 <action> [email] [options]"
    echo ""
    echo "动作:"
    echo "  list                    - 列出所有用户"
    echo "  show <email>           - 显示指定用户信息"
    echo "  set <email>            - 设置用户为超级用户"
    echo "  unset <email>          - 移除用户的超级用户权限"
    echo "  add <email> <password> - 添加新用户"
    echo "  delete <email>         - 删除用户"
    echo "  reset <email> <password> - 重置用户密码"
    echo ""
    echo "示例:"
    echo "  $0 list"
    echo "  $0 show admin@example.com"
    echo "  $0 set admin@example.com"
    echo "  $0 unset admin@example.com"
    echo "  $0 add newuser@example.com mypassword"
    echo "  $0 delete olduser@example.com"
    echo "  $0 reset user@example.com newpassword"
    echo ""
}

# 检查参数
if [ $# -eq 0 ]; then
    show_help
    exit 1
fi

ACTION="$1"
EMAIL="$2"
PASSWORD="$3"

# 从环境变量或配置文件读取MySQL密码
if [ -f "docker/.env" ]; then
    source docker/.env
elif [ -f ".env" ]; then
    source .env
fi

# 默认密码（如果环境变量未设置）
MYSQL_PASSWORD=${MYSQL_PASSWORD:-infini_rag_flow}
MYSQL_USER=${MYSQL_USER:-root}
MYSQL_CONTAINER=${MYSQL_CONTAINER:-ragflow-mysql}
MYSQL_DATABASE=${MYSQL_DATABASE:-rag_flow}

# 检查MySQL容器是否运行
check_mysql_container() {
    if ! sudo docker ps | grep -q "$MYSQL_CONTAINER"; then
        print_error "MySQL容器 '$MYSQL_CONTAINER' 未运行"
        print_info "请先启动RagFlow服务: sudo docker compose -f docker/docker-compose.yml up -d"
        exit 1
    fi
}

# 执行MySQL命令
execute_mysql() {
    local sql="$1"
    local silent="$2"
    
    if [ "$silent" = "true" ]; then
        sudo docker exec "$MYSQL_CONTAINER" mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE" -e "$sql" 2>/dev/null
    else
        sudo docker exec "$MYSQL_CONTAINER" mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE" -e "$sql"
    fi
}

# 检查邮箱格式
validate_email() {
    local email="$1"
    if [[ ! "$email" =~ ^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ ]]; then
        print_error "邮箱格式无效: $email"
        exit 1
    fi
}

# 检查用户是否存在
user_exists() {
    local email="$1"
    local count=$(execute_mysql "SELECT COUNT(*) FROM user WHERE email='$email';" true 2>/dev/null | tail -n1)
    [ "$count" -gt 0 ]
}

# 生成密码哈希（简单MD5，实际应该使用更安全的方法）
hash_password() {
    local password="$1"
    echo -n "$password" | md5sum | cut -d' ' -f1
}

# 列出所有用户
list_users() {
    print_info "获取用户列表..."
    echo ""
    execute_mysql "
    SELECT 
        CONCAT('邮箱: ', email) as '用户信息',
        CASE WHEN is_superuser=1 THEN '是' ELSE '否' END as '超级用户',
        DATE_FORMAT(create_time, '%Y-%m-%d %H:%i') as '创建时间',
        DATE_FORMAT(update_time, '%Y-%m-%d %H:%i') as '更新时间'
    FROM user 
    ORDER BY create_time DESC;
    "
}

# 显示用户信息
show_user() {
    local email="$1"
    validate_email "$email"
    
    if ! user_exists "$email"; then
        print_error "用户不存在: $email"
        exit 1
    fi
    
    print_info "用户信息: $email"
    echo ""
    execute_mysql "
    SELECT 
        email as '邮箱',
        CASE WHEN is_superuser=1 THEN '是' ELSE '否' END as '超级用户',
        status as '状态',
        DATE_FORMAT(create_time, '%Y-%m-%d %H:%i:%s') as '创建时间',
        DATE_FORMAT(update_time, '%Y-%m-%d %H:%i:%s') as '更新时间'
    FROM user 
    WHERE email='$email';
    "
}

# 设置超级用户
set_superuser() {
    local email="$1"
    validate_email "$email"
    
    if ! user_exists "$email"; then
        print_error "用户不存在: $email"
        exit 1
    fi
    
    print_info "设置用户 $email 为超级用户..."
    execute_mysql "UPDATE user SET is_superuser=1, update_time=NOW() WHERE email='$email';"
    
    if [ $? -eq 0 ]; then
        print_success "成功设置用户 $email 为超级用户"
        show_user "$email"
    else
        print_error "设置失败"
        exit 1
    fi
}

# 移除超级用户权限
unset_superuser() {
    local email="$1"
    validate_email "$email"
    
    if ! user_exists "$email"; then
        print_error "用户不存在: $email"
        exit 1
    fi
    
    print_info "移除用户 $email 的超级用户权限..."
    execute_mysql "UPDATE user SET is_superuser=0, update_time=NOW() WHERE email='$email';"
    
    if [ $? -eq 0 ]; then
        print_success "成功移除用户 $email 的超级用户权限"
        show_user "$email"
    else
        print_error "移除失败"
        exit 1
    fi
}

# 添加新用户
add_user() {
    local email="$1"
    local password="$2"
    
    validate_email "$email"
    
    if [ -z "$password" ]; then
        print_error "请提供密码"
        echo "用法: $0 add <email> <password>"
        exit 1
    fi
    
    if user_exists "$email"; then
        print_error "用户已存在: $email"
        exit 1
    fi
    
    local hashed_password=$(hash_password "$password")
    local user_id=$(uuidgen | tr -d '-' | head -c 32)
    
    print_info "添加新用户: $email"
    execute_mysql "
    INSERT INTO user (id, email, password, create_time, update_time, is_superuser, status) 
    VALUES ('$user_id', '$email', '$hashed_password', NOW(), NOW(), 0, 1);
    "
    
    if [ $? -eq 0 ]; then
        print_success "成功添加用户: $email"
        show_user "$email"
    else
        print_error "添加用户失败"
        exit 1
    fi
}

# 删除用户
delete_user() {
    local email="$1"
    validate_email "$email"
    
    if ! user_exists "$email"; then
        print_error "用户不存在: $email"
        exit 1
    fi
    
    print_warning "确定要删除用户 $email 吗？此操作不可恢复！"
    read -p "请输入 'yes' 确认删除: " confirm
    
    if [ "$confirm" != "yes" ]; then
        print_info "取消删除操作"
        exit 0
    fi
    
    print_info "删除用户: $email"
    execute_mysql "DELETE FROM user WHERE email='$email';"
    
    if [ $? -eq 0 ]; then
        print_success "成功删除用户: $email"
    else
        print_error "删除用户失败"
        exit 1
    fi
}

# 重置用户密码
reset_password() {
    local email="$1"
    local password="$2"
    
    validate_email "$email"
    
    if [ -z "$password" ]; then
        print_error "请提供新密码"
        echo "用法: $0 reset <email> <password>"
        exit 1
    fi
    
    if ! user_exists "$email"; then
        print_error "用户不存在: $email"
        exit 1
    fi
    
    local hashed_password=$(hash_password "$password")
    
    print_info "重置用户 $email 的密码..."
    execute_mysql "UPDATE user SET password='$hashed_password', update_time=NOW() WHERE email='$email';"
    
    if [ $? -eq 0 ]; then
        print_success "成功重置用户 $email 的密码"
        show_user "$email"
    else
        print_error "重置密码失败"
        exit 1
    fi
}

# 主逻辑
main() {
    check_mysql_container
    
    case "$ACTION" in
        "list")
            list_users
            ;;
        "show")
            if [ -z "$EMAIL" ]; then
                print_error "请提供邮箱地址"
                echo "用法: $0 show <email>"
                exit 1
            fi
            show_user "$EMAIL"
            ;;
        "set")
            if [ -z "$EMAIL" ]; then
                print_error "请提供邮箱地址"
                echo "用法: $0 set <email>"
                exit 1
            fi
            set_superuser "$EMAIL"
            ;;
        "unset")
            if [ -z "$EMAIL" ]; then
                print_error "请提供邮箱地址"
                echo "用法: $0 unset <email>"
                exit 1
            fi
            unset_superuser "$EMAIL"
            ;;
        "add")
            if [ -z "$EMAIL" ] || [ -z "$PASSWORD" ]; then
                print_error "请提供邮箱地址和密码"
                echo "用法: $0 add <email> <password>"
                exit 1
            fi
            add_user "$EMAIL" "$PASSWORD"
            ;;
        "delete")
            if [ -z "$EMAIL" ]; then
                print_error "请提供邮箱地址"
                echo "用法: $0 delete <email>"
                exit 1
            fi
            delete_user "$EMAIL"
            ;;
        "reset")
            if [ -z "$EMAIL" ] || [ -z "$PASSWORD" ]; then
                print_error "请提供邮箱地址和新密码"
                echo "用法: $0 reset <email> <password>"
                exit 1
            fi
            reset_password "$EMAIL" "$PASSWORD"
            ;;
        "help"|"-h"|"--help")
            show_help
            ;;
        *)
            print_error "未知动作: $ACTION"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

# 检查依赖
check_dependencies() {
    if ! command -v uuidgen &> /dev/null; then
        print_warning "uuidgen 未找到，将使用随机字符串生成ID"
    fi
    
    if ! command -v md5sum &> /dev/null; then
        print_error "md5sum 未找到，请安装 coreutils"
        exit 1
    fi
}

# 运行主程序
check_dependencies
main