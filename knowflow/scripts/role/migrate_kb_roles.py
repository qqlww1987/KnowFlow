#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识库角色简化迁移脚本
将知识库专用角色(kb_admin, kb_writer, kb_reader)迁移到基本角色(admin, editor, viewer)
"""

import sys
import os
import logging
from datetime import datetime

# 添加server目录到Python路径
script_dir = os.path.dirname(os.path.abspath(__file__))
knowflow_dir = os.path.dirname(os.path.dirname(script_dir))
server_dir = os.path.join(knowflow_dir, 'server')
sys.path.append(server_dir)

from database import get_db_connection

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('kb_role_migration.log')
    ]
)
logger = logging.getLogger(__name__)

class KBRoleMigrator:
    def __init__(self):
        self.db = None
        self.cursor = None
        
        # 角色映射关系
        self.role_mapping = {
            'kb_admin': 'admin',
            'kb_writer': 'editor', 
            'kb_reader': 'viewer'
        }
    
    def connect_db(self):
        """连接数据库"""
        try:
            self.db = get_db_connection()
            self.cursor = self.db.cursor(dictionary=True)
            logger.info("数据库连接成功")
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            raise
    
    def close_db(self):
        """关闭数据库连接"""
        if self.cursor:
            self.cursor.close()
        if self.db:
            self.db.close()
        logger.info("数据库连接已关闭")
    
    def check_existing_roles(self):
        """检查现有角色"""
        logger.info("检查现有角色...")
        
        # 检查知识库专用角色
        kb_roles = list(self.role_mapping.keys())
        placeholders = ','.join(['%s'] * len(kb_roles))
        
        self.cursor.execute(f"""
            SELECT code, name, COUNT(*) as count
            FROM rbac_roles 
            WHERE code IN ({placeholders})
            GROUP BY code, name
        """, kb_roles)
        
        existing_kb_roles = self.cursor.fetchall()
        
        if existing_kb_roles:
            logger.info("发现以下知识库专用角色:")
            for role in existing_kb_roles:
                logger.info(f"  - {role['name']} ({role['code']})")
        else:
            logger.info("未发现知识库专用角色")
        
        # 检查基本角色
        basic_roles = list(self.role_mapping.values())
        placeholders = ','.join(['%s'] * len(basic_roles))
        
        self.cursor.execute(f"""
            SELECT code, name
            FROM rbac_roles 
            WHERE code IN ({placeholders})
        """, basic_roles)
        
        existing_basic_roles = self.cursor.fetchall()
        
        if existing_basic_roles:
            logger.info("发现以下基本角色:")
            for role in existing_basic_roles:
                logger.info(f"  - {role['name']} ({role['code']})")
        else:
            logger.warning("未发现基本角色，请先运行migrate_rbac.py")
        
        return len(existing_kb_roles) > 0
    
    def migrate_user_roles(self):
        """迁移用户角色分配"""
        logger.info("迁移用户角色分配...")
        
        for old_role, new_role in self.role_mapping.items():
            try:
                # 获取旧角色ID
                self.cursor.execute(
                    "SELECT id FROM rbac_roles WHERE code = %s", 
                    (old_role,)
                )
                old_role_result = self.cursor.fetchone()
                if not old_role_result:
                    logger.info(f"角色 {old_role} 不存在，跳过")
                    continue
                
                old_role_id = old_role_result['id']
                
                # 获取新角色ID
                self.cursor.execute(
                    "SELECT id FROM rbac_roles WHERE code = %s", 
                    (new_role,)
                )
                new_role_result = self.cursor.fetchone()
                if not new_role_result:
                    logger.error(f"目标角色 {new_role} 不存在")
                    continue
                
                new_role_id = new_role_result['id']
                
                # 查找使用旧角色的用户
                self.cursor.execute("""
                    SELECT user_id, resource_type, resource_id, granted_by, 
                           granted_at, expires_at, tenant_id
                    FROM rbac_user_roles 
                    WHERE role_id = %s AND is_active = 1
                """, (old_role_id,))
                
                user_roles = self.cursor.fetchall()
                
                if not user_roles:
                    logger.info(f"没有用户使用角色 {old_role}")
                    continue
                
                logger.info(f"发现 {len(user_roles)} 个用户使用角色 {old_role}")
                
                # 为每个用户分配新角色
                for user_role in user_roles:
                    # 检查用户是否已有新角色
                    self.cursor.execute("""
                        SELECT id FROM rbac_user_roles 
                        WHERE user_id = %s AND role_id = %s 
                        AND resource_type = %s AND resource_id = %s 
                        AND is_active = 1
                    """, (
                        user_role['user_id'], new_role_id,
                        user_role['resource_type'], user_role['resource_id']
                    ))
                    
                    if self.cursor.fetchone():
                        logger.info(f"用户 {user_role['user_id']} 已有角色 {new_role}，跳过")
                        continue
                    
                    # 插入新角色
                    self.cursor.execute("""
                        INSERT INTO rbac_user_roles (
                            user_id, role_id, resource_type, resource_id,
                            granted_by, granted_at, expires_at, tenant_id,
                            is_active, created_at, updated_at
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, 1, NOW(), NOW()
                        )
                    """, (
                        user_role['user_id'], new_role_id,
                        user_role['resource_type'], user_role['resource_id'],
                        user_role['granted_by'], user_role['granted_at'],
                        user_role['expires_at'], user_role['tenant_id']
                    ))
                    
                    logger.info(f"为用户 {user_role['user_id']} 分配新角色 {new_role}")
                
                # 禁用旧角色分配
                self.cursor.execute("""
                    UPDATE rbac_user_roles 
                    SET is_active = 0, updated_at = NOW()
                    WHERE role_id = %s
                """, (old_role_id,))
                
                logger.info(f"已禁用角色 {old_role} 的所有分配")
                
            except Exception as e:
                logger.error(f"迁移用户角色 {old_role} -> {new_role} 失败: {e}")
                self.db.rollback()
                raise
        
        self.db.commit()
        logger.info("用户角色迁移完成")
    
    def migrate_team_roles(self):
        """迁移团队角色分配"""
        logger.info("迁移团队角色分配...")
        
        for old_role, new_role in self.role_mapping.items():
            try:
                # 查找使用旧角色的团队
                self.cursor.execute("""
                    SELECT team_id, resource_type, resource_id, granted_by,
                           granted_at, expires_at, tenant_id
                    FROM rbac_team_roles 
                    WHERE role_code = %s AND is_active = 1
                """, (old_role,))
                
                team_roles = self.cursor.fetchall()
                
                if not team_roles:
                    logger.info(f"没有团队使用角色 {old_role}")
                    continue
                
                logger.info(f"发现 {len(team_roles)} 个团队使用角色 {old_role}")
                
                # 为每个团队分配新角色
                for team_role in team_roles:
                    # 检查团队是否已有新角色
                    self.cursor.execute("""
                        SELECT id FROM rbac_team_roles 
                        WHERE team_id = %s AND role_code = %s 
                        AND resource_type = %s AND resource_id = %s 
                        AND is_active = 1
                    """, (
                        team_role['team_id'], new_role,
                        team_role['resource_type'], team_role['resource_id']
                    ))
                    
                    if self.cursor.fetchone():
                        logger.info(f"团队 {team_role['team_id']} 已有角色 {new_role}，跳过")
                        continue
                    
                    # 插入新角色
                    self.cursor.execute("""
                        INSERT INTO rbac_team_roles (
                            team_id, role_code, resource_type, resource_id,
                            granted_by, granted_at, expires_at, tenant_id,
                            is_active, create_time, update_time
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, 1, NOW(), NOW()
                        )
                    """, (
                        team_role['team_id'], new_role,
                        team_role['resource_type'], team_role['resource_id'],
                        team_role['granted_by'], team_role['granted_at'],
                        team_role['expires_at'], team_role['tenant_id']
                    ))
                    
                    logger.info(f"为团队 {team_role['team_id']} 分配新角色 {new_role}")
                
                # 禁用旧角色分配
                self.cursor.execute("""
                    UPDATE rbac_team_roles 
                    SET is_active = 0, update_time = NOW()
                    WHERE role_code = %s
                """, (old_role,))
                
                logger.info(f"已禁用团队角色 {old_role} 的所有分配")
                
            except Exception as e:
                logger.error(f"迁移团队角色 {old_role} -> {new_role} 失败: {e}")
                self.db.rollback()
                raise
        
        self.db.commit()
        logger.info("团队角色迁移完成")
    
    def cleanup_old_roles(self):
        """清理旧角色（可选）"""
        logger.info("清理旧角色...")
        
        kb_roles = list(self.role_mapping.keys())
        placeholders = ','.join(['%s'] * len(kb_roles))
        
        # 删除角色权限关联
        self.cursor.execute(f"""
            DELETE rp FROM rbac_role_permissions rp
            JOIN rbac_roles r ON rp.role_id = r.id
            WHERE r.code IN ({placeholders})
        """, kb_roles)
        
        # 删除角色
        self.cursor.execute(f"""
            DELETE FROM rbac_roles 
            WHERE code IN ({placeholders})
        """, kb_roles)
        
        self.db.commit()
        logger.info("旧角色清理完成")
    
    def run_migration(self, cleanup=False):
        """运行完整迁移"""
        try:
            self.connect_db()
            
            # 检查现有角色
            has_kb_roles = self.check_existing_roles()
            
            if not has_kb_roles:
                logger.info("没有发现知识库专用角色，无需迁移")
                return
            
            # 迁移用户角色
            self.migrate_user_roles()
            
            # 迁移团队角色
            self.migrate_team_roles()
            
            # 可选：清理旧角色
            if cleanup:
                self.cleanup_old_roles()
            
            logger.info("知识库角色迁移完成！")
            
        except Exception as e:
            logger.error(f"迁移失败: {e}")
            if self.db:
                self.db.rollback()
            raise
        finally:
            self.close_db()

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='知识库角色简化迁移脚本')
    parser.add_argument('--cleanup', action='store_true', 
                       help='迁移完成后删除旧角色（谨慎使用）')
    
    args = parser.parse_args()
    
    migrator = KBRoleMigrator()
    migrator.run_migration(cleanup=args.cleanup)

if __name__ == '__main__':
    main()