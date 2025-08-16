import mysql.connector
from database import DB_CONFIG

try:
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    # 查看tenant表结构
    cursor.execute("DESCRIBE tenant")
    columns = cursor.fetchall()
    print("Tenant表结构:")
    for col in columns:
        print(f"字段: {col[0]}, 类型: {col[1]}")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"数据库错误: {e}")