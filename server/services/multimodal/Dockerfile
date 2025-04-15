FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY image_server.py .

# 确保images目录存在并设置正确的权限
RUN mkdir -p /app/images && chmod 777 /app/images

EXPOSE 8000

CMD ["python", "image_server.py"]