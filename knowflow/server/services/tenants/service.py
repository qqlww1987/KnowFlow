import mysql.connector
from datetime import datetime
from database import DB_CONFIG

def get_tenants_with_pagination(current_page, page_size, username='', current_user_id=None, user_role=None):
    """查询租户信息，支持分页和条件筛选"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        
        # 构建WHERE子句和参数
        where_clauses = []
        params = []
        
        if username:
            where_clauses.append("""
            EXISTS (
                SELECT 1 FROM user_tenant ut 
                JOIN user u ON ut.user_id = u.id 
                WHERE ut.tenant_id = t.id AND u.nickname LIKE %s
            )
            """)
            params.append(f"%{username}%")
        
        # 添加基于角色的权限过滤
        if current_user_id and user_role:
            if user_role == 'admin':
                # 管理员只能看到自己创建的租户（其实就是自己的租户+自己创建的用户的租户）
                where_clauses.append("""
                EXISTS (
                    SELECT 1 FROM user_tenant ut 
                    JOIN user u ON ut.user_id = u.id 
                    WHERE ut.tenant_id = t.id AND ut.role = 'owner'
                    AND (u.id = %s OR u.created_by = %s)
                )
                """)
                params.extend([current_user_id, current_user_id])
            elif user_role == 'user':
                # 普通用户只能看到自己的租户
                where_clauses.append("""
                EXISTS (
                    SELECT 1 FROM user_tenant ut 
                    WHERE ut.tenant_id = t.id AND ut.user_id = %s AND ut.role = 'owner'
                )
                """)
                params.append(current_user_id)
            # super_admin 不添加过滤条件，可以看到所有租户
        
        # 组合WHERE子句
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        
        # 查询总记录数 - 每个用户只计算一次（优先个人租户）
        count_sql = f"""
        SELECT COUNT(*) as total
        FROM (
            SELECT
                t.id
            FROM
                tenant t
            JOIN user_tenant ut ON t.id = ut.tenant_id AND ut.role = 'owner'
            JOIN user u ON ut.user_id = u.id
            JOIN (
                SELECT
                    ut2.user_id,
                    COALESCE(
                        MAX(CASE WHEN ut2.user_id = t2.id THEN t2.id END),
                        MAX(t2.id)
                    ) as preferred_tenant_id
                FROM user_tenant ut2
                JOIN tenant t2 ON ut2.tenant_id = t2.id
                WHERE ut2.role = 'owner'
                GROUP BY ut2.user_id
            ) preferred ON t.id = preferred.preferred_tenant_id
            WHERE
                {where_sql}
        ) as unique_tenants
        """
        cursor.execute(count_sql, params)
        total = cursor.fetchone()['total']
        
        # 计算分页偏移量
        offset = (current_page - 1) * page_size
        
        # 执行分页查询 - 每个用户优先选择个人租户
        query = f"""
        SELECT
            t.id,
            u.nickname as username,
            t.llm_id as chat_model,
            t.embd_id as embedding_model,
            t.create_date,
            t.update_date
        FROM
            tenant t
        JOIN user_tenant ut ON t.id = ut.tenant_id AND ut.role = 'owner'
        JOIN user u ON ut.user_id = u.id
        JOIN (
            SELECT
                ut2.user_id,
                COALESCE(
                    MAX(CASE WHEN ut2.user_id = t2.id THEN t2.id END),
                    MAX(t2.id)
                ) as preferred_tenant_id
            FROM user_tenant ut2
            JOIN tenant t2 ON ut2.tenant_id = t2.id
            WHERE ut2.role = 'owner'
            GROUP BY ut2.user_id
        ) preferred ON t.id = preferred.preferred_tenant_id
        WHERE
            {where_sql}
        ORDER BY
            t.create_date DESC
        LIMIT %s OFFSET %s
        """
        cursor.execute(query, params + [page_size, offset])
        results = cursor.fetchall()
        
        # 关闭连接
        cursor.close()
        conn.close()
        
        # 格式化结果
        formatted_tenants = []
        for tenant in results:
            formatted_tenants.append({
                "id": tenant["id"],
                "username": tenant["username"] if tenant["username"] else "未指定",
                "chatModel": tenant["chat_model"] if tenant["chat_model"] else "",
                "embeddingModel": tenant["embedding_model"] if tenant["embedding_model"] else "",
                "createTime": tenant["create_date"].strftime("%Y-%m-%d %H:%M:%S") if tenant["create_date"] else "",
                "updateTime": tenant["update_date"].strftime("%Y-%m-%d %H:%M:%S") if tenant["update_date"] else ""
            })
        
        return formatted_tenants, total
        
    except mysql.connector.Error as err:
        print(f"数据库错误: {err}")
        return [], 0

def update_tenant(tenant_id, tenant_data):
    """更新租户信息"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # 更新租户表
        current_datetime = datetime.now()
        update_time = int(current_datetime.timestamp() * 1000)
        current_date = current_datetime.strftime("%Y-%m-%d %H:%M:%S")
        
        query = """
        UPDATE tenant 
        SET update_time = %s, 
            update_date = %s, 
            llm_id = %s, 
            embd_id = %s
        WHERE id = %s
        """
        
        cursor.execute(query, (
            update_time,
            current_date,
            tenant_data.get("chatModel", ""),
            tenant_data.get("embeddingModel", ""),
            tenant_id
        ))
        
        affected_rows = cursor.rowcount
        conn.commit()
        
        cursor.close()
        conn.close()
        
        return affected_rows > 0
        
    except mysql.connector.Error as err:
        print(f"更新租户错误: {err}")
        return False

def get_all_configured_models():
    """获取所有租户已配置的模型列表，去重后返回"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        
        # 获取所有租户的模型配置
        query = """
        SELECT DISTINCT 
            llm_id as chat_model,
            embd_id as embedding_model
        FROM tenant 
        WHERE (llm_id IS NOT NULL AND llm_id != '') 
           OR (embd_id IS NOT NULL AND embd_id != '')
        """
        cursor.execute(query)
        results = cursor.fetchall()
        
        # 关闭连接
        cursor.close()
        conn.close()
        
        # 提取去重的模型列表
        chat_models = set()
        embedding_models = set()
        
        for row in results:
            if row['chat_model']:
                chat_models.add(row['chat_model'])
            if row['embedding_model']:
                embedding_models.add(row['embedding_model'])
        
        return {
            'chat_models': sorted(list(chat_models)),
            'embedding_models': sorted(list(embedding_models))
        }
        
    except mysql.connector.Error as err:
        print(f"获取已配置模型错误: {err}")
        return {
            'chat_models': [],
            'embedding_models': []
        }

def get_admin_tenant_config():
    """获取超级管理员租户的配置作为默认值"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        
        # 查询超级管理员用户
        admin_query = """
        SELECT id FROM user 
        WHERE email = 'admin@gmail.com' 
        ORDER BY create_time ASC 
        LIMIT 1
        """
        cursor.execute(admin_query)
        admin_user = cursor.fetchone()
        
        if not admin_user:
            cursor.close()
            conn.close()
            return {'chat_model': '', 'embedding_model': ''}
        
        # 查询管理员租户配置
        tenant_query = """
        SELECT llm_id as chat_model, embd_id as embedding_model
        FROM tenant 
        WHERE id = %s
        """
        cursor.execute(tenant_query, (admin_user['id'],))
        tenant_config = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if tenant_config:
            return {
                'chat_model': tenant_config['chat_model'] or '',
                'embedding_model': tenant_config['embedding_model'] or ''
            }
        else:
            return {'chat_model': '', 'embedding_model': ''}
            
    except mysql.connector.Error as err:
        print(f"获取管理员租户配置错误: {err}")
        return {'chat_model': '', 'embedding_model': ''}