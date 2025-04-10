<div align="center">
  <img src="assets/logo.png" width="108" height="124" alt="KnowFlow 企业知识库">
</div>

## 项目介绍

KnowFlow 是一个基于 RAGFlow 的开源项目，持续兼容 RAGFlow 官方版本，同时会将社区里做的比较好的最佳实践整合进来。
并在此基础上提供一些新的功能，以解决实际应用中的一些痛点。
KnowFlow 可以理解成 RAGFlow 官方开源产品真正落地企业场景的最后一公里服务。

## 新增功能介绍

### 一. 用户后台管理系统 [done]

参考 [ragflow-plus](https://github.com/zstar1003/ragflow-plus/)

移除原登陆页用户注册的通道，搭建用户后台管理系统，可对用户进行管理，包括用户管理、团队管理、用户模型配置管理等功能。

特点：新建用户时，新用户会自动加入创建时间最早用户的团队，并默认采取和最早用户相同的模型配置。

### 二. 支持回答结果图文混排 [doing]

能够回答结果图文混排，可将回答结果中的图片和文本进行混排，以增强回答的可读性。后续将持续支持表格、图标等格式，增强其结构化输出能力。

### 三. 文档预处理  [todo]

虽然 DeepDoc 很出色，但经过实践经验，文档经过预处理之后，对识别准确率有很大提升，我们将会持续支持文档预处理能力。

### 四. RAGFlow UI 重构 [doing]

虽然 DeepDoc 很出色，但经过实践经验，文档经过预处理之后，对识别准确率有很大提升，我们将会持续支持文档预处理能力。


## 使用方式

#### 1. 使用Docker Compose运行

和运行 ragflow 原始项目一样，项目根目录下执行

```bash
docker compose -f docker/docker-compose.yml up -d
```
访问地址：`服务器ip:80`，进入到ragflow原始界面

访问地址：`服务器ip:8888`，进入到管理界面


#### 2. 源码运行

也可以通过下面的方式单独运行管理系统

启动后端：

1.打开后端程序`management/server`，安装依赖

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2.启动后端

```bash
python app.py
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

<div align="center">
  <img src="assets/user-setting.png"  alt="用户后台管理系统">
</div>




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

