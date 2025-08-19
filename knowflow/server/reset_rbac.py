#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RBAC表清理和重置脚本
用于测试时清除所有RBAC相关表，确保可以重新初始化
"""

import logging
from database import get_db_connection

logger = logging.getLogger(__name__)

def reset_rbac_tables():
    """
    删除所有RBAC相关表，用于测试重新初始化
    
    Returns:
        bool: 是否成功重置
    """
    db = None
    cursor = None
    
    try:
        logger.info("开始重置RBAC表...")
        
        # 获取数据库连接
        db = get_db_connection()
        db.autocommit = True
        cursor = db.cursor()
        
        # 要删除的表列表（按依赖关系排序）
        tables_to_drop = [
            'rbac_team_roles',          # 团队角色表
            'rbac_resource_permissions', # 资源权限表
            'rbac_role_permissions',     # 角色权限关联表
            'rbac_user_roles',          # 用户角色关联表
            'rbac_roles',               # 角色表
            'rbac_permissions'          # 权限表
        ]
        
        # 删除表
        for table_name in tables_to_drop:
            try:
                # 检查表是否存在
                cursor.execute("""
                    SELECT COUNT(*) FROM information_schema.tables 
                    WHERE table_schema = DATABASE() AND table_name = %s
                """, (table_name,))
                
                if cursor.fetchone()[0] > 0:
                    cursor.execute(f"DROP TABLE {table_name}")
                    logger.info(f"✓ 删除表: {table_name}")
                else:
                    logger.info(f"- 表不存在: {table_name}")
                    
            except Exception as e:
                logger.warning(f"删除表 {table_name} 时出错: {e}")
        
        # 删除默认管理员用户（可选）
        try:
            cursor.execute("SELECT id FROM user WHERE email = 'admin@gmail.com'")
            admin_user = cursor.fetchone()
            if admin_user:
                cursor.execute("DELETE FROM user WHERE email = 'admin@gmail.com'")
                logger.info("✓ 删除默认管理员用户")
            else:
                logger.info("- 默认管理员用户不存在")
        except Exception as e:
            logger.warning(f"删除默认管理员用户时出错: {e}")
        
        logger.info("✓ RBAC表重置完成")
        return True
        
    except Exception as e:
        logger.error(f"重置RBAC表失败: {e}")
        return False
        
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()

def verify_reset():
    """
    验证重置结果
    """
    db = None
    cursor = None
    
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        # 检查RBAC表是否都已删除
        rbac_tables = [
            'rbac_permissions', 'rbac_roles', 'rbac_user_roles', 
            'rbac_role_permissions', 'rbac_resource_permissions', 'rbac_team_roles'
        ]
        
        existing_tables = []
        for table in rbac_tables:
            cursor.execute("""
                SELECT COUNT(*) FROM information_schema.tables 
                WHERE table_schema = DATABASE() AND table_name = %s
            """, (table,))
            
            if cursor.fetchone()[0] > 0:
                existing_tables.append(table)
        
        if existing_tables:
            logger.warning(f"以下表未删除: {existing_tables}")
            return False
        else:
            logger.info("✓ 所有RBAC表已删除")
            return True
            
    except Exception as e:
        logger.error(f"验证重置结果失败: {e}")
        return False
        
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()

if __name__ == '__main__':
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    import sys
    
    # 支持命令行参数强制执行
    if len(sys.argv) > 1 and sys.argv[1] == '--force':
        print("⚠️  强制执行RBAC表重置...")
        confirmation = 'YES'
    else:
        print("⚠️  这将删除所有RBAC相关表和数据！")
        try:
            confirmation = input("确认要重置RBAC表吗？输入 'YES' 确认: ")
        except EOFError:
            print("无法获取用户输入，请使用 --force 参数强制执行")
            sys.exit(1)
    
    if confirmation == 'YES':
        # 执行重置
        success = reset_rbac_tables()
        
        if success:
            print("✓ RBAC表重置成功")
            
            # 验证重置结果
            if verify_reset():
                print("✓ 重置验证通过")
                print("\n现在可以重新运行RBAC初始化:")
                print("python rbac_init.py")
            else:
                print("⚠️  重置验证失败")
        else:
            print("✗ RBAC表重置失败")
    else:
        print("操作已取消")