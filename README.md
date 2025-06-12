<div align="center">
  <img src="assets/logo.png" alt="KnowFlow 企业知识库" width="30%">
</div>

## 项目介绍

KnowFlow 是一个基于 RAGFlow 的开源项目，持续兼容 RAGFlow 官方版本，同时会将社区里做的比较好的最佳实践整合进来。
KnowFlow 可以理解成 RAGFlow 官方开源产品真正落地企业场景的最后一公里服务。

## 功能介绍

### 适配 RAGFlow 全新 UI 

基于 RAGFlow v0.18.0 二次开发全新 UI 页面。

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
2. 保持和官方 markdown **完全一致**的分块规则，保证分块和向量化检索效果，且具备开放性，后续可持续增强
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

### 1. 使用Docker Compose运行

1. 在宿主机器上下载 MinerU 模型文件

支持两种下载方式，任选其一：

**方式一：使用 ModelScope（推荐，国内用户速度更快）**
```bash
pip install modelscope
wget https://gcore.jsdelivr.net/gh/opendatalab/MinerU@master/scripts/download_models.py -O download_models.py
python3 download_models.py
```

**方式二：使用 HuggingFace**
```bash
pip install huggingface_hub
wget https://gcore.jsdelivr.net/gh/opendatalab/MinerU@master/scripts/download_models_hf.py -O download_models_hf.py
python3 download_models_hf.py
```

**智能检测说明：**
- 安装脚本会自动检测您系统中的模型缓存路径
- 优先使用 ModelScope 路径（如果存在且包含模型文件）
- 自动选择模型文件较多或目录较大的路径
- 支持的路径：`~/.cache/modelscope/hub` 和 `~/.cache/huggingface/hub`

2. 在项目根目录下新建 `.env` 文件，添加如下内容

```bash
#  从 RAGFlow API 页面后台获取 (必须)
RAGFLOW_API_KEY=
# 注意不支持 127.0.0.1、localhost，需要把 127.0.0.1 或 localhost 替换成部署机器的 IP 地址（）
RAGFLOW_BASE_URL=
```

3. 执行安装脚本，在 .env 里追加环境变量

```bash
./scripts/install.sh
```

4. 启动容器，开始愉快之旅
```bash
docker compose up -d
```
访问地址：`服务器ip:8888`，进入到管理界面


### 2. 源码运行

参照 Docker Compose 使用方式的前面 1、2、3 步骤，这是前提。


启动后端：

1.打开后端程序`management/server`，安装依赖

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```


2.开启文件格式转化服务（可选，支持 PDF 以外文件格式需要开启）

```bash
docker run -d -p 3000:3000 gotenberg/gotenberg:8
```

3.启动后端

```bash
python3 app.py
```


启动前端：

1.打开前端程序`management\web`，安装依赖
```bash
pnpm i
```

2.启动前端程序
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

### RAGFlow UI 

将开源的 `dist` 目录复制到 docker 内的 /ragflow/web/dist 目录下，覆盖原有的 dist 即可
```bash
docker cp -r dist {ragflow_container_name}:/ragflow/web/
```


## 编译 Docker

```bash
docker buildx build --platform linux/amd64 --target backend -t zxwei/knowflow-server:v0.3.0 --push .

docker buildx build --platform linux/amd64 --target frontend -t zxwei/knowflow-web:v0.3.0 --push .

```


## TODO
- [x] 支持更多文档格式的 MinerU 解析
- [x] 增强 MarkDown 文件的分块规则


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

1. 如何给 MinerU 进行 GPU 加速

   1） 安装 nvidia-container-toolkit

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


   2）修改 `magic-pdf.json`，把 `device-mode` 从 `cpu` 为 `cuda`：

      ```json
      "device-mode": "cuda"
      ```

      > 💡 ** magic-pdf.json **<br>
      > magic-pdf.json 文件在 MinerU 模型下载完成后会自动生成，路径可以在 .env 的 MINERU_MAGIC_PDF_JSON_PATH 查询。<br>

