import mysql.connector
from database import DB_CONFIG

try:
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    # 先查看user表结构
    cursor.execute("DESCRIBE user")
    columns = cursor.fetchall()
    print("User表结构:")
    for col in columns:
        print(f"字段: {col[0]}, 类型: {col[1]}")
    
    # 查询所有用户
    cursor.execute("SELECT id, nickname FROM user LIMIT 10")
    users = cursor.fetchall()
    
    print("\n现有用户:")
    for user in users:
        print(f"ID: {user[0]}, Nickname: {user[1]}")
    
    # 检查是否存在system用户
    cursor.execute("SELECT id, nickname FROM user WHERE id = 'system' OR nickname = 'system'")
    system_users = cursor.fetchall()
    
    print("\nSystem用户:")
    if system_users:
        for user in system_users:
            print(f"ID: {user[0]}, Nickname: {user[1]}")
    else:
        print("未找到system用户")
        # 创建system用户
        print("\n创建system用户...")
        from datetime import datetime
        from utils import generate_uuid
        
        current_datetime = datetime.now()
        create_time = int(current_datetime.timestamp() * 1000)
        current_date = current_datetime.strftime("%Y-%m-%d %H:%M:%S")
        
        insert_query = """
        INSERT INTO user (
            id, create_time, create_date, update_time, update_date,
            nickname, email, password, status, is_superuser,
            is_authenticated, is_active, is_anonymous
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        """
        
        user_data = (
            'system', create_time, current_date, create_time, current_date,
            'System User', 'system@knowflow.com', 'system_password', '1', 1,
            '1', '1', '0'
        )
        
        cursor.execute(insert_query, user_data)
        conn.commit()
        print("System用户创建成功！")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"数据库错误: {e}")