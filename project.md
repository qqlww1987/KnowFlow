# 背景
1. 本项目是一个 RAG 系统，/Users/zxwei/zhishi/KnowFlow/knowflow 是独立的微服务，提供 rbac http server 端实现给到主项目使用，如果需要用到该目录下的服务，需要通过  source /Users/zxwei/zhishi/KnowFlow/knowflow/server/venv/bin/activate ，然后 python3.10 来执行脚本。


2. 主项目前端在 /Users/zxwei/zhishi/KnowFlow/web 下面，其他目录都是主项目后端服务。
后端项目可以通过 uv run python3.10 执行脚本。


3. 主项目提供了一个管理页面，只允许超级管理员可见和操作。


4. RBAC 服务端端口是 5000，主项目端口是 9380，主项目的数据库端口是 5545。



