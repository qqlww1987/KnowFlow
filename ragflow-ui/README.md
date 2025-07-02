# RagFlow UI

一个用于替换 RagFlow 官方前端界面的现代化 React 项目，提供更美观和易用的用户体验。

## 项目介绍

本项目基于以下技术栈构建：
- **框架**: UMI 4.x + React 18
- **语言**: TypeScript
- **样式**: Tailwind CSS + Ant Design
- **状态管理**: Zustand
- **数据获取**: TanStack Query (React Query)
- **图标**: Ant Design Icons + Lucide React
- **图表**: Recharts + AntV G2/G6

## 环境要求

- Node.js >= 18.20.4
- npm 或 yarn

## 开发指南


### 集成到 RagFlow 开发

如果你想在 RagFlow 项目中进行集成开发：

1. **准备 RagFlow 项目**
   确保你已经克隆了 RagFlow 官方仓库：
   ```bash
   git clone https://github.com/infiniflow/ragflow.git
   ```

2. **备份原始前端**
   ```bash
   cd ragflow
   mv web web_backup  # 备份原始前端代码
   ```

3. **复制 ragflow-ui 到 RagFlow**
   ```bash
   cp -r /path/to/ragflow-ui ./web
   cd web
   ```

4. **安装依赖并启动开发**
   ```bash
   npm install
   npm run dev
   ```

5. **在 RagFlow 中启动后端服务**
   根据 RagFlow 官方文档启动后端服务，前端会自动代理 API 请求。

## 部署指南

### 构建生产版本

1. **构建项目**
   ```bash
   cd ragflow-ui
   npm install
   npm run build
   ```

   构建完成后，会在项目根目录生成 `dist` 文件夹，包含所有静态资源。

### Docker 部署集成

#### 方式一：修改 docker-compose.yml（推荐）

1. **准备构建产物**
   ```bash
   npm run build
   ```

2. **修改 RagFlow 的 docker-compose.yml**
   在 ragflow 服务的 volumes 配置中添加：
   ```yaml
   services:
     ragflow:
       # ... 其他配置
       volumes:
         # ... 其他挂载
         - /path/to/ragflow-ui/dist:/ragflow/web/dist:ro
   ```

3. **重启 RagFlow 服务**
   ```bash
   docker-compose down
   docker-compose up -d
   ```

#### 方式二：直接挂载到容器

如果 RagFlow 已经在运行，你可以直接挂载 dist 目录：

```bash
# 停止现有容器
docker stop ragflow_container_name

# 重新运行容器并挂载新的前端
docker run -d \
  --name ragflow_container_name \
  -v /path/to/ragflow-ui/dist:/ragflow/web/dist:ro \
  # ... 其他原有参数
  ragflow_image_name
```

#### 方式三：复制到容器内

```bash
# 构建前端
npm run build

# 复制到运行中的容器
docker cp ./dist/. ragflow_container_name:/ragflow/web/dist/

# 重启容器以确保更改生效
docker restart ragflow_container_name
```

### 验证部署

部署完成后，访问 RagFlow 的 Web 界面，你应该能看到新的 UI 界面。

## 开发注意事项

### API 代理配置

项目使用 UMI 的代理功能来转发 API 请求到 RagFlow 后端。代理配置位于 `.umirc.ts` 文件中：

```typescript
// 确保 API 请求能正确转发到 RagFlow 后端
proxy: {
  '/api': {
    target: 'http://localhost:9380', // RagFlow 后端地址
    changeOrigin: true,
  },
}
```

### 环境变量

根据需要，你可以创建 `.env` 文件来配置环境变量：

```bash
# RagFlow 后端地址
RAGFLOW_API_BASE_URL=http://localhost:9380
```

### 代码格式化

项目已配置 Prettier 和 ESLint：

```bash
# 格式化代码
npm run lint

# 运行测试
npm run test
```

## 项目结构

```
ragflow-ui/
├── src/
│   ├── components/     # 通用组件
│   ├── pages/         # 页面组件
│   ├── services/      # API 服务
│   ├── utils/         # 工具函数
│   ├── hooks/         # 自定义 Hooks
│   ├── stores/        # 状态管理
│   └── styles/        # 样式文件
├── public/            # 静态资源
├── dist/              # 构建产物（构建后生成）
├── .umirc.ts          # UMI 配置文件
├── tailwind.config.js # Tailwind CSS 配置
└── package.json       # 项目依赖配置
```

## 常见问题

### 1. 构建失败

确保 Node.js 版本 >= 18.20.4：
```bash
node --version
```

### 2. API 请求失败

检查 RagFlow 后端是否正常运行，以及代理配置是否正确。

### 3. 样式不生效

确保 Tailwind CSS 构建正常，检查 `tailwind.config.js` 配置。

### 4. Docker 挂载无效

确保：
- 构建产物路径正确
- Docker 容器有读取挂载目录的权限
- 挂载路径与 RagFlow 前端路径匹配

## 贡献指南

1. Fork 本项目
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request


## 支持

如有问题或建议，请创建 Issue 或联系项目维护者。 