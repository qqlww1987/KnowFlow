# 父子分块映射关系查看器

这个工具帮助您直观地查看文档的父子分块映射关系，了解父分块和子分块之间的对应关系。

## 功能特性

- 📋 显示文档基本信息和分块配置
- 🔗 展示父子映射关系详情 
- 📊 提供详细的统计分析
- 📄 可选择显示分块内容预览
- 🎛️ 灵活的输出控制选项
- 🌐 **HTML可视化模式**: 现代化响应式网页界面
- 🔍 **实时搜索**: 支持分块内容搜索和高亮显示
- 📱 **移动适配**: 完全响应式设计，支持移动端浏览

## 使用方法

### 基本用法
```bash
# 查看文档的父子分块映射关系（显示前5对）
python parent_child_mapper_viewer.py <doc_id>

# 示例
python parent_child_mapper_viewer.py 8ebdf414815a11f0ba2766fc51ac58de
```

### 高级选项

#### 控制显示数量
```bash
# 显示前10个映射对
python parent_child_mapper_viewer.py <doc_id> --max-pairs 10
python parent_child_mapper_viewer.py <doc_id> -n 10
```

#### 仅显示映射关系，不显示内容
```bash
python parent_child_mapper_viewer.py <doc_id> --no-content
```

#### 仅显示统计信息
```bash
python parent_child_mapper_viewer.py <doc_id> --stats-only
python parent_child_mapper_viewer.py <doc_id> -s
```

#### HTML可视化模式
```bash
# 生成HTML可视化页面并在浏览器中自动打开
python parent_child_mapper_viewer.py <doc_id> --html

# 自定义HTML页面显示的映射对数量
python parent_child_mapper_viewer.py <doc_id> --html --html-pairs 20
```

#### AST预览模式
```bash
# 预览基于AST的父子分块效果（使用内置示例）
python parent_child_mapper_viewer.py fake_doc_id --ast-preview

# 使用外部Markdown文件进行预览
python parent_child_mapper_viewer.py fake_doc_id --ast-preview --markdown-file path/to/your.md

# 自定义分块参数
python parent_child_mapper_viewer.py fake_doc_id --ast-preview --parent-level 3 --child-size 128

# 生成AST分块HTML可视化页面
python parent_child_mapper_viewer.py fake_doc_id --ast-preview --ast-html

# 结合外部文件和HTML可视化
python parent_child_mapper_viewer.py fake_doc_id --ast-preview --ast-html --markdown-file path/to/your.md
```

### 输出示例

#### 标准输出
```
🔍 父子分块映射关系查看器
====================================================================================================
📋 文档信息:
   🆔 文档ID: 8ebdf414815a11f0ba2766fc51ac58de
   📄 文档名: 精简公路桥梁钢结构防腐涂装技术条件.pdf
   🎯 分块策略: parent_child
   👨‍👦 父分块配置:
      📏 父分块大小: 1024 tokens
      🔄 重叠大小: 100 tokens

📊 映射统计:
   📈 总映射数量: 94个
   👨 唯一父分块: 22个
   👶 子分块数量: 94个

🔗 映射关系详情:
   📌 映射对 1:
      🔗 子分块ID: 9f99e048-058a-4d79-b2e1-1524012da45a
      🔗 父分块ID: f7adc1eb-0dcf-4be6-9885-c4e18ac8b295
      👶 子分块内容: "涂层体系性能要求见表8..."
      👨 父分块内容: "配套编号|工况条件|涂层|涂料品种..."
```

#### 统计信息输出
```
📊 父子分块统计分析
📈 父子分块分布:
   👨 父分块总数: 22
   👶 子分块总数: 94
   📊 平均每个父分块包含: 4.27 个子分块

🔢 子分块数量分布:
   📉 最少: 1 个子分块
   📈 最多: 9 个子分块
   📊 中位数: 5 个子分块
```

#### HTML可视化界面
HTML模式会自动在浏览器中打开一个现代化的可视化页面，提供：
- **双栏布局**: 左侧显示子分块，右侧显示对应的父分块
- **搜索功能**: 页面顶部搜索框，输入关键词实时过滤和高亮显示
- **响应式设计**: 自动适配桌面和移动设备
- **美观界面**: 现代化渐变设计和卡片式布局
- **详细信息**: 显示分块ID、类型、顺序、长度等元数据

#### AST HTML可视化界面
AST预览的HTML模式提供更丰富的语义分析可视化：
- **三栏布局**: 原始文档、父分块、子分块并列显示
- **语义标记**: 显示分块中包含的标题、表格、代码、列表等语义元素
- **层级展示**: 清晰显示Markdown标题层级和AST结构信息
- **关联可视化**: 直观展示父子分块之间的语义关联关系
- **AST元数据**: 显示行号范围、节点类型、上下文层级等AST分析结果
- **实时搜索**: 支持跨所有分块内容的实时搜索和高亮

## 技术说明

### 数据来源
- **MySQL**: 存储父子映射关系 (`parent_child_mapping` 表)
- **Elasticsearch**: 存储分块内容和元数据

### 分块类型
- **父分块**: 较大的语义单元，提供完整上下文，用于LLM理解
- **子分块**: 较小的精确单元，用于向量化和精确匹配

### 检索原理
1. 🔍 用户查询 → 子分块向量匹配
2. 🔗 子分块ID → MySQL映射查询 → 父分块ID  
3. 📄 父分块ID → ES内容查询 → 完整上下文
4. 🤖 父分块内容 → LLM生成回答

## 错误处理

- ❌ 文档不存在：显示错误信息
- ❌ 无映射关系：提示没有父子分块数据
- ❌ ES连接失败：显示连接错误但继续显示ID关系
- ❌ 数据库连接失败：程序退出并显示错误信息

## 命令行参数

| 参数 | 简写 | 描述 |
|------|------|------|
| `doc_id` | - | 要查看的文档ID（必需） |
| `--max-pairs` | `-n` | 命令行模式显示的最大映射对数量（默认5） |
| `--no-content` | - | 不显示分块内容，仅显示ID和关系 |
| `--stats-only` | `-s` | 仅显示统计信息 |
| `--html` | - | 打开HTML可视化页面 |
| `--html-pairs` | - | HTML页面显示的最大映射对数量（默认20） |
| `--ast-preview` | - | 预览基于AST的父子分块效果 |
| `--ast-html` | - | AST预览模式下生成HTML可视化页面 |
| `--parent-level` | - | AST预览模式下的父分块分割层级（默认2） |
| `--child-size` | - | AST预览模式下的子分块大小（默认256） |
| `--markdown-file` | - | 用于AST预览的Markdown文件路径 |
| `--help` | `-h` | 显示帮助信息 |

## 依赖要求

- Python 3.7+
- KnowFlow项目环境
- MySQL数据库连接
- Elasticsearch连接

## 故障排除

### 模块导入错误
```bash
❌ 无法导入数据库模块: No module named 'database'
```
**解决方案**: 确保在KnowFlow项目根目录下运行脚本

### 数据库连接失败
**检查项目**:
1. MySQL服务是否运行
2. Elasticsearch服务是否运行  
3. 环境变量配置是否正确
4. 网络连接是否正常

### 文档无映射关系
**可能原因**:
1. 文档未使用父子分块策略
2. 文档处理过程中出现错误
3. 数据同步问题

### 浏览器无法打开HTML
**解决方案**:
1. 手动访问控制台显示的文件路径
2. 检查系统默认浏览器设置
3. 确保有足够权限创建临时文件

## 使用技巧

1. **快速检查**: 先使用 `--stats-only` 了解整体情况
2. **内容分析**: 使用默认设置查看具体映射内容
3. **批量查看**: 使用 `--max-pairs` 调整显示数量
4. **性能优化**: 大文档使用 `--no-content` 提高显示速度
5. **可视化查看**: 使用 `--html` 获得最佳的查看体验
6. **搜索定位**: HTML模式下使用搜索功能快速定位相关内容
7. **移动查看**: HTML页面支持在手机或平板上查看

## 最佳实践

### 推荐工作流程
1. **概览分析**: `python parent_child_mapper_viewer.py <doc_id> --stats-only`
2. **详细检查**: `python parent_child_mapper_viewer.py <doc_id> --html`
3. **问题排查**: `python parent_child_mapper_viewer.py <doc_id> --max-pairs 50 --no-content`

### 使用场景
- **开发调试**: 验证父子分块策略是否正确执行
- **质量评估**: 分析分块质量和映射关系合理性
- **问题排查**: 定位RAG检索效果不佳的原因
- **文档分析**: 理解文档结构和内容组织方式