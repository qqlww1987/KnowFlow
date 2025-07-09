<div align="center">
  <img src="assets/logo.png" alt="KnowFlow 企业知识库" width="30%">
</div>

## 项目介绍

KnowFlow 是一个基于 RAGFlow 的开源项目，持续兼容 RAGFlow 官方版本，同时会将社区里做的比较好的最佳实践整合进来。
KnowFlow 可以理解成 RAGFlow 官方开源产品真正落地企业场景的最后一公里服务。

## 功能介绍

### 适配 RAGFlow 全新 UI

基于 RAGFlow v0.18.0 二次开发全新 UI 页面，目前已适配 v0.19.0。

<div align="center">
  <img src="assets/ui_1.png" alt="KnowFlow 企业知识库">
</div>

<div align="center">
  <img src="assets/ui_2.png" alt="KnowFlow 企业知识库">
</div>

### 用户后台管理系统

参考 [ragflow-plus](https://github.com/zstar1003/ragflow-plus/)

<div align="center">
  <img src="assets/user-setting.png"  alt="用户后台管理系统">
</div>

移除原登陆页用户注册的通道，搭建用户后台管理系统，可对用户进行管理，包括用户管理、团队管理、用户模型配置管理等功能。

特点：新建用户时，新用户会自动加入创建时间最早用户的团队，并默认采取和最早用户相同的模型配置。

### 图文混排输出

1. 支持市面上常见的文件格式，如 ppt/png/word/doc/excel/...等等
2. 保持和官方 markdown **完全一致**的分块规则，共提供了三种分块策略，保证分块和向量化检索效果，且具备开放性，后续可持续增强
3. 无缝对接 RAGFlow 知识库系统，文档自动解析和分块

<div align="center">
  <img src="assets/mulcontent.png"  alt="图文混排">
</div>

### 支持企业微信应用

支持企业微信应用，可将企业微信应用作为聊天机器人，使用企业微信应用进行聊天。具体使用方式参照  `server/services/knowflow/README.md` 中的说明。

<div align="center">
  <img src="assets/wecom.jpg" style="height: 400px;" alt="企业微信应用">
</div>

## 使用方式

### 0. MinerU 本地调试（开发环境）

如果您需要在本地环境进行开发调试，可以直接运行 MinerU 服务：

```bash
# 1. 安装 Python 依赖（注意：zsh 需要用引号包围方括号）
pip install "mineru[core]" fastapi uvicorn python-multipart

# 2. 设置环境变量
export MINERU_DEVICE_MODE=cpu
export MINERU_MODEL_SOURCE=modelscope

# 3. 进入项目目录
cd web_api

# 4. 启动本地服务
python app.py
```

**配置 settings.yaml：**

使用本地 MinerU 服务时，需要修改 `server/services/config/settings.yaml` 中的服务地址：

```yaml
mineru:
  fastapi:
    # 本地开发服务地址
    url: "http://localhost:8888"
  
  vlm:
    sglang:
      # 本地SGLang服务地址（如果使用vlm-sglang-client后端）
      server_url: "http://localhost:30000"
```

> 💡 **提示：** 本地调试模式适合开发环境，生产环境建议使用Docker方式部署

### 1. 使用 Docker Compose 运行

1. 启动 MinerU 服务

   选择以下两种镜像之一：

   **完整版（推荐）- 包含所有功能**
   ```bash
   docker run --rm -d --gpus=all \
     --shm-size=32g \
     -p 8888:8888 -p 30000:30000 \
     --name mineru-api \
     zxwei/mineru-api-full:2.1.0
   ```

   **基础版 - 仅包含基础功能**
   ```bash
   docker run --rm -d --gpus=all \
     --shm-size=32g \
     -p 8888:8888 \
     --name mineru-api \
     zxwei/mineru-api:2.1.0
   ```

   > 💡 **镜像说明：**
   > - `zxwei/mineru-api-full`：包含完整的 VLM 功能，支持所有后端类型
   > - `zxwei/mineru-api`：基础版本，主要支持 pipeline 后端
   > - `server/services/config/settings.yaml` 可以配置选择 MinerU 模式、配置服务地址
   > - 如需 GPU 加速，请确保已安装 nvidia-container-toolkit


2. 执行安装脚本，自动生成配置

   ```bash
   ./scripts/install.sh
   ```

   > 💡 **自动配置功能：**
   > - 脚本会自动检测本机IP地址
   > - 自动创建 `.env` 配置文件（如果不存在）
   > - 如果 `.env` 文件已存在，会提供选项：保留现有配置或重新生成

3. 完善 `.env` 文件配置

   安装脚本会自动创建 `.env` 文件模板，您只需要填写两个必要信息：

   ```bash
   # 从 RAGFlow API 页面后台获取 (必须手动填写)
   RAGFLOW_API_KEY=你的实际API密钥

   # 确认端口号并替换 (通常RAGFlow默认端口是80或8080)
   RAGFLOW_BASE_URL=http://检测到的IP:实际端口号
   ```

   > 💡 **提示：** 其他配置项（如HOST_IP、ES_HOST等）已由脚本自动填写

4. 启动容器，开始愉快之旅

   ```bash
   docker compose up -d
   ```

   访问地址：`服务器ip:8081`，进入到管理界面

### 2. 源码运行

参照 Docker Compose 使用方式的前面步骤，确保 MinerU 服务已启动。

**启动后端：**

1. 打开后端程序 `management/server`，安装依赖

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. 开启文件格式转化服务（可选，支持 PDF 以外文件格式需要开启）

   ```bash
   docker run -d -p 3000:3000 gotenberg/gotenberg:8
   ```

3. 启动后端

   ```bash
   python3 app.py
   ```

**启动前端：**

1. 打开前端程序 `management\web`，安装依赖

   ```bash
   pnpm i
   ```

2. 启动前端程序

   ```bash
   pnpm dev
   ```

浏览器访问启动后的地址，即可进入系统。

> 💡 **提示：** **图文混排功能**，聊天助手的提示词很重要，配置不正确会无法显示图片。模板如下：<br>

> 请参考{knowledge}内容回答用户问题。<br>
> 如果知识库内容包含图片，请在回答中包含图片URL。<br>
> 注意这个 html 格式的 URL 是来自知识库本身，URL 不能做任何改动。<br>
> 请确保回答简洁、专业，将图片自然地融入回答内容中。

---

### RAGFlow UI（无 RAGFlow UI 更新需要可忽略）

参照 `ragflow-ui/README.md`


## 编译 Docker（无编译需要可忽略）

```bash
docker buildx build --platform linux/amd64 --target backend -t zxwei/knowflow-server:v0.3.0 --push .

docker buildx build --platform linux/amd64 --target frontend -t zxwei/knowflow-web:v0.3.0 --push .
```

## TODO

- [x] 支持更多文档格式的 MinerU 解析
- [x] 增强 MarkDown 文件的分块规则
- [x] 优化 Excel 文件分块
- [x] MinerU 2.0 接入
- [x] RAGFlow 前端 UI 源码开源


## 交流群

如果有其它需求或问题建议，可加入交流群进行讨论。

如需加群，加我微信 skycode007，备注"加群"即可。

## 鸣谢

本项目基于以下开源项目开发：

- [ragflow](https://github.com/infiniflow/ragflow)
- [v3-admin-vite](https://github.com/un-pany/v3-admin-vite)
- [ragflow-plus](https://github.com/zstar1003/ragflow-plus/)

## 更新信息获取

目前该项目仍在持续更新中，更新日志会在我的微信公众号[KnowFlow 企业知识库]上发布，欢迎关注。

## 常见问题

### 1. 如何选择 MinerU 镜像版本

**zxwei/mineru-api-full（推荐）：**
- 包含完整的 VLM 功能
- 支持所有后端类型：pipeline, vlm-transformers, vlm-sglang-engine, vlm-sglang-client
- 镜像较大，但功能最全

**zxwei/mineru-api：**
- 基础版本，镜像较小
- 主要支持 pipeline 后端
- 适合基础文档解析需求

### 2. 如何给 MinerU 进行 GPU 加速

1）安装 nvidia-container-toolkit

```bash
# 添加源
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/libnvidia-container/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

# 安装组件
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# 重启 Docker
sudo systemctl restart docker
```

2）启动 MinerU 容器时确保包含 `--gpus=all` 参数（如上面的示例命令）

3）在 settings.yaml 中配置使用 GPU 后端：

```yaml
mineru:
  default_backend: "vlm-sglang-client"  # 使用 VLM 后端
```

### 3. 容器网络配置

如果 KnowFlow server 也运行在容器中，需要正确配置网络地址：

- **Docker Desktop**：使用 `http://host.docker.internal:8888`
- **Linux Docker**：使用宿主机IP，如 `http://192.168.1.100:8888`
- **Docker Compose**：使用服务名，如 `http://mineru-api:8888`

详细配置参考 `DOCKER_NETWORK_GUIDE.md`

### 4. 常见错误处理

1）**端口冲突**：
   - MinerU 服务使用端口 8888 和 30000
   - KnowFlow 前端使用端口 8081
   - 后端服务使用端口 5000
   - 确保这些端口未被其他服务占用

2）**内存不足**：增加 Docker 内存限制或调整 `--shm-size` 参数

3）**GPU 不可用**：检查 nvidia-container-toolkit 安装和 GPU 驱动

4）**网络连接问题**：检查防火墙设置和容器网络配置





