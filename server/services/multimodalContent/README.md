# RAGFlow图片服务方案 🖼️

<div align="center">
  <img src="images/ragflow_logo.png" alt="RAGFlow Logo" width="200">
  <br>
  <p><strong>增强文档问答体验的图片服务解决方案</strong></p>
</div>

## 📋 项目背景

在使用RAGFlow框架进行文档问答时，原始文档中通常包含大量图片。为了在问答结果中正确显示这些图片，我们需要一种机制来提供图片的网络访问。本项目通过独立的图片服务器容器解决这个问题，使RAGFlow容器能够通过Docker网络访问图片资源。

## 🏗️ 系统架构

系统包含两个主要容器：
1. **RAGFlow容器**：处理文档和提供问答功能
2. **图片服务器容器**：提供图片资源的HTTP访问

两个容器通过Docker自定义网络(`rag-network`)相互连接，使RAGFlow可以通过服务器IP地址引用图片：`http://192.168.x.x:8000/images/example.jpg`

```mermaid
graph LR
    User[用户] --> |1. 上传PDF| RAG[RAGFlow容器]
    RAG --> |2. 提取图片| Images[图片文件]
    RAG --> |3. 创建知识库| KB[知识库]
    Images --> |4. 存储| ImgServer[图片服务器容器]
    User --> |5. 提问| RAG
    RAG --> |6. 检索知识库| KB
    RAG --> |7. 生成回答| User
    RAG --> |8. 引用图片URL| ImgServer
    ImgServer --> |9. 提供图片访问| User
    
    subgraph Docker网络
        RAG
        ImgServer
    end
```

## 📁 项目文件说明

1. `image_server.py`: 图片服务器的主程序
2. `PyMuPDF_test.py`: PDF文档处理和图片提取的核心功能
3. `ragflow_build.py`: RAGFlow知识库和聊天助手创建的核心功能
4. `process_pdf.py`: 整合所有功能的启动脚本
5. `Dockerfile`: 图片服务器的容器配置文件
6. `requirements.txt`: Python依赖包列表

## 🛠️ 环境准备

### 虚拟环境配置

推荐使用虚拟环境以避免依赖冲突：

```bash
# 创建虚拟环境，注意 python < 3.13
python -m venv venv

# 激活虚拟环境
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# 安装依赖包
pip install -r requirements.txt
```

### Docker配置
确保已安装Docker并正常运行。

### 环境变量配置
**重要**: 创建`.env`文件并配置必要参数：
```
RAGFLOW_API_KEY=您的RAGFlow API密钥
RAGFLOW_SERVER_IP=您的服务器IP地址
```

查询您的IP地址方法：
- Windows: 在命令提示符中运行 `ipconfig`
- Mac/Linux: 在终端中运行 `ifconfig` 或 `ip addr`

**注意**: 请使用您机器在局域网中的实际 IPv4 地址，不要使用`localhost`或`127.0.0.1`

## 🚀 实现步骤

### 1. 构建并启动图片服务器

```bash
# 构建图片服务器镜像
docker build -t image-server .

# 创建本地图片存储目录
mkdir images

# 运行图片服务器容器（Windows PowerShell）
docker run -d -p 8000:8000 -v ${PWD}\/images:/app/images --name image-server image-server

# 如果使用CMD，请使用以下命令
# docker run -d -p 8000:8000 -v %cd%\/images:/app/images --name image-server image-server
```

### 2. 配置Docker网络

```bash
# 如果你是重新配置Docker服务，下述命令的前两行可以跳过

# 创建共享网络
docker network create rag-network

# 连接容器到网络
docker network connect rag-network ragflow-server
docker network connect rag-network image-server

# 验证网络连接
docker network inspect rag-network
```

### 3. 验证服务器状态

```bash
# 检查image-server是否正常运行
docker logs image-server

# 测试图片服务器访问
curl http://localhost:8000
# 或在浏览器访问 http://localhost:8000
```

### 4. 处理PDF文档

确保已经在`.env`文件中设置了必要的环境变量，然后运行PDF处理脚本：
```bash
python process_pdf.py demo.pdf
```

此脚本会自动执行以下操作：
1. 提取PDF中的图片
2. 将图片保存到图片服务器目录
3. 生成带有图片URL的增强文本
4. 创建RAGFlow知识库
5. 创建聊天助手

**参数说明**：
- 如果需要手动指定服务器IP，可以使用`--server_ip`参数：
  ```bash
  python process_pdf.py demo.pdf --server_ip 192.168.1.100
  ```

```mermaid
sequenceDiagram
    participant User as 用户
    participant Process as process_pdf.py
    participant PDF as PyMuPDF_test.py
    participant RAG as ragflow_build.py
    participant Server as 图片服务器
    participant KB as 知识库
    
    User->>Process: 运行 process_pdf.py
    Process->>PDF: 调用 extract_images_from_pdf()
    PDF-->>Process: 返回增强文本和图片列表
    Process->>Server: 复制图片到服务器目录
    Process->>RAG: 调用 create_ragflow_resources()
    RAG->>KB: 创建知识库
    RAG->>KB: 上传增强文本
    RAG->>KB: 创建聊天助手
    RAG-->>Process: 返回知识库和助手ID
    Process-->>User: 完成处理，返回结果
```

### 5. 测试问答功能

1. 访问RAGFlow Web界面（通常是 http://localhost:80）
2. 找到新创建的聊天助手（名称与PDF文件名相关）
3. 开始测试问答，验证回答中的图片是否正确显示

![RAGFlow问答截图](images/ragflow_chat_demo.png)

## 🖼️ 图片URL格式说明

本项目使用HTML的img标签格式来在RAGFlow中正确渲染图片。在最新版本中，图片URL使用服务器实际IP地址而不是localhost，这对于Docker容器间通信至关重要。

### 正确的图片格式示例:

```html
<img src="http://192.168.x.x:8000/images/page1_img1_abcd1234.png" alt="维修图片" width="300">
```

**注意**: 不要使用`localhost`或`127.0.0.1`作为图片URL中的主机地址，否则在RAGFlow容器中将无法正确解析。

### 效果对比:

| 使用IP地址的图片 | 使用localhost的图片 |
|------------------|---------------------|
| ![正确显示](images/correct_image_display.png) | ![不显示](images/incorrect_image_display.png) |

## 📊 代码运行流程说明

1. `process_pdf.py`是主要的入口文件，它会按顺序调用：
   - `PyMuPDF_test.py`中的函数处理PDF和提取图片
   - `ragflow_build.py`中的函数创建知识库和聊天助手

2. 详细流程图：

```mermaid
flowchart TD
    A[开始] --> B[加载环境变量]
    B --> C[接收命令行参数]
    C --> D[验证必要参数]
    D --> E[提取PDF中的图片]
    E --> F[构建增强文本]
    F --> G[保存图片到服务器目录]
    G --> H[保存增强文本]
    H --> I{是否跳过RAGFlow?}
    I -->|是| J[结束]
    I -->|否| K[创建知识库]
    K --> L[上传增强文本]
    L --> M[创建聊天助手]
    M --> N[配置提示词模板]
    N --> O[结束]
    
    style A fill:#f9f,stroke:#333,stroke-width:2px
    style O fill:#bbf,stroke:#333,stroke-width:2px
    style J fill:#bbf,stroke:#333,stroke-width:2px
```

## ⚠️ 注意事项

1. 确保图片服务器容器在RAGFlow容器之前启动
2. 图片名称会自动生成唯一标识，避免冲突
3. 图片会持久化存储在本地的`images`目录中
4. 请妥善保管RAGFlow API密钥
5. **重要**: 确保使用正确的服务器IP地址，否则图片将无法在RAGFlow聊天界面中显示

## 🔍 故障排除

如果遇到问题，请按以下顺序检查：

1. 容器状态：
   ```bash
   docker ps  # 检查两个容器是否都在运行
   ```

2. 网络连接：
   ```bash
   docker network inspect rag-network  # 检查网络连接状态
   ```

3. 图片服务器：
   ```bash
   docker logs image-server  # 检查服务器日志
   ls images  # 检查图片是否正确保存
   ```

4. 图片访问：
   - 通过浏览器访问 http://[您的IP]:8000 验证图片服务器
   - 检查生成的图片URL格式是否正确（应为 http://[您的IP]:8000/images/xxx.png）
   - 确认.env文件中的IP地址是否正确配置

5. RAGFlow API：
   - 确认API密钥设置正确
   - 检查RAGFlow服务是否正常运行

6. 图片显示问题：
   - 检查RAGFlow聊天界面网络请求，查看图片URL是否正确
   - 确认图片URL使用的是服务器IP而非localhost
   - 尝试手动在浏览器中访问图片URL验证图片是否可访问

如果仍然遇到问题，可以查看各个容器的日志：
```bash
docker logs ragflow-server
docker logs image-server
```