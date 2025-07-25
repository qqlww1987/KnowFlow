#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接使用SQL设置超级管理员的脚本
"""

import sys
import os
import argparse
import logging
import pymysql

def setup_logging():
    """设置日志"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

def get_db_connection():
    """获取数据库连接"""
    try:
        connection = pymysql.connect(
            host=os.getenv('MYSQL_HOST', 'localhost'),
            port=int(os.getenv('MYSQL_PORT', '5455')),
            user=os.getenv('MYSQL_USER', 'root'),
            password=os.getenv('MYSQL_PASSWORD', 'infini_rag_flow'),
            database=os.getenv('MYSQL_DBNAME', 'rag_flow'),
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        logging.info("数据库连接成功")
        return connection
    except Exception as e:
        logging.error(f"数据库连接失败: {str(e)}")
        return None

def set_superuser(email=None, user_id=None):
    """设置用户为超级管理员"""
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        with connection.cursor() as cursor:
            # 查找用户
            if email:
                cursor.execute("SELECT id, email, nickname, is_superuser FROM user WHERE email = %s", (email,))
            elif user_id:
                cursor.execute("SELECT id, email, nickname, is_superuser FROM user WHERE id = %s", (user_id,))
            else:
                logging.error("必须提供邮箱或用户ID")
                return False
            
            user = cursor.fetchone()
            if not user:
                logging.error(f"未找到用户: {email or user_id}")
                return False
            
            logging.info(f"找到用户: {user['email']} (ID: {user['id']}, 昵称: {user['nickname']})")
            
            if user['is_superuser']:
                logging.info("用户已经是超级管理员")
                return True
            
            # 更新用户为超级管理员
            cursor.execute("UPDATE user SET is_superuser = 1 WHERE id = %s", (user['id'],))
            
            if cursor.rowcount > 0:
                connection.commit()
                logging.info(f"成功设置用户 {user['email']} 为超级管理员")
                return True
            else:
                logging.error("更新失败")
                return False
                
    except Exception as e:
        logging.error(f"设置超级管理员时发生错误: {str(e)}")
        connection.rollback()
        return False
    finally:
        connection.close()

def remove_superuser(email=None, user_id=None):
    """移除超级管理员权限"""
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        with connection.cursor() as cursor:
            # 查找用户
            if email:
                cursor.execute("SELECT id, email, nickname, is_superuser FROM user WHERE email = %s", (email,))
            elif user_id:
                cursor.execute("SELECT id, email, nickname, is_superuser FROM user WHERE id = %s", (user_id,))
            else:
                logging.error("必须提供邮箱或用户ID")
                return False
            
            user = cursor.fetchone()
            if not user:
                logging.error(f"未找到用户: {email or user_id}")
                return False
            
            logging.info(f"找到用户: {user['email']} (ID: {user['id']}, 昵称: {user['nickname']})")
            
            if not user['is_superuser']:
                logging.info("用户不是超级管理员")
                return True
            
            # 移除超级管理员权限
            cursor.execute("UPDATE user SET is_superuser = 0 WHERE id = %s", (user['id'],))
            
            if cursor.rowcount > 0:
                connection.commit()
                logging.info(f"成功移除用户 {user['email']} 的超级管理员权限")
                return True
            else:
                logging.error("更新失败")
                return False
                
    except Exception as e:
        logging.error(f"移除超级管理员权限时发生错误: {str(e)}")
        connection.rollback()
        return False
    finally:
        connection.close()

def list_superusers():
    """列出所有超级管理员"""
    connection = get_db_connection()
    if not connection:
        return
    
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT id, email, nickname, status, create_time 
                FROM user 
                WHERE is_superuser = 1 
                ORDER BY create_time DESC
            """)
            
            superusers = cursor.fetchall()
            
            if not superusers:
                logging.info("没有找到超级管理员用户")
                return
            
            logging.info("当前超级管理员列表:")
            logging.info("-" * 100)
            logging.info(f"{'ID':<32} {'邮箱':<30} {'昵称':<20} {'状态':<6} {'创建时间':<15}")
            logging.info("-" * 100)
            
            for user in superusers:
                status_text = "有效" if user['status'] == "1" else "无效"
                create_time = user['create_time'] or 0
                logging.info(f"{user['id']:<32} {user['email']:<30} {user['nickname']:<20} {status_text:<6} {create_time:<15}")
                
    except Exception as e:
        logging.error(f"查询超级管理员时发生错误: {str(e)}")
    finally:
        connection.close()

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='设置用户为超级管理员')
    parser.add_argument('--email', '-e', help='用户邮箱')
    parser.add_argument('--user-id', '-u', help='用户ID')
    parser.add_argument('--action', '-a', choices=['set', 'remove', 'list'], 
                       default='set', help='操作类型: set(设置), remove(移除), list(列出)')
    parser.add_argument('--host', default='localhost', help='MySQL主机地址')
    parser.add_argument('--port', default='5455', help='MySQL端口')
    parser.add_argument('--user', default='root', help='MySQL用户名')
    parser.add_argument('--password', default='infini_rag_flow', help='MySQL密码')
    parser.add_argument('--database', default='rag_flow', help='数据库名')
    
    args = parser.parse_args()
    
    # 设置环境变量
    os.environ['MYSQL_HOST'] = args.host
    os.environ['MYSQL_PORT'] = args.port
    os.environ['MYSQL_USER'] = args.user
    os.environ['MYSQL_PASSWORD'] = args.password
    os.environ['MYSQL_DBNAME'] = args.database
    
    setup_logging()
    
    if args.action == 'list':
        list_superusers()
    elif args.action == 'set':
        if not args.email and not args.user_id:
            logging.error("设置超级管理员时必须提供 --email 或 --user-id 参数")
            sys.exit(1)
        result = set_superuser(args.email, args.user_id)
        sys.exit(0 if result else 1)
    elif args.action == 'remove':
        if not args.email and not args.user_id:
            logging.error("移除超级管理员权限时必须提供 --email 或 --user-id 参数")
            sys.exit(1)
        result = remove_superuser(args.email, args.user_id)
        sys.exit(0 if result else 1)

if __name__ == '__main__':
    main()