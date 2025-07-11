# KnowFlow 批量 API 测试脚本

## 📁 文件说明

```
knowflow_extensions/
├── enhanced_doc.py      # 核心：增强版 doc.py (包含 batch_add_chunk 方法)
├── auto_mount.py        # 自动挂载脚本
├── test_batch_api.py    # 完整测试套件 (推荐)
├── quick_test.py        # 快速测试脚本
└── requirements.txt     # 依赖包
```

## 🚀 测试新增的批量接口

### 新增API接口
```
POST /api/v1/datasets/{dataset_id}/documents/{document_id}/chunks/batch
```

### 请求格式
```json
{
  "chunks": [
    {
      "content": "chunk内容",
      "important_keywords": ["关键词1", "关键词2"],
      "questions": ["问题1？", "问题2？"]
    }
  ],
  "batch_size": 5  // 可选，默认5，最大20
}
```

## 🧪 测试脚本使用

### 1. 完整测试套件 (推荐)

```bash
python3 knowflow_extensions/test_batch_api.py
```

**功能特点：**
- ✅ 三种规模测试：小批量(5)、中等(20)、大批量(50)
- ✅ 性能统计和错误报告
- ✅ 交互式配置选项
- ✅ 详细的结果分析

**配置步骤：**
1. 修改脚本中的配置：
   ```python
   DATASET_ID = "your_actual_dataset_id"
   DOCUMENT_ID = "your_actual_document_id"
   BASE_URL = "http://localhost:9380"
   API_KEY = "your_api_key"  # 如果需要
   ```

### 2. 快速测试脚本

```bash
python3 knowflow_extensions/quick_test.py
```

**功能特点：**
- ✅ 简单快速测试
- ✅ 固定3个测试chunks
- ✅ 基础结果验证

## 📋 测试前准备

### 1. 获取必要的ID

**方式1：通过Web界面**
- 打开 RAGFlow Web界面
- 从URL中获取 dataset_id 和 document_id

**方式2：通过API**
```bash
# 获取数据集列表
curl -H "Authorization: Bearer YOUR_TOKEN" \
     http://localhost:9380/api/v1/datasets

# 获取文档列表
curl -H "Authorization: Bearer YOUR_TOKEN" \
     http://localhost:9380/api/v1/datasets/{dataset_id}/documents
```

### 2. 确保服务运行

```bash
# 检查RAGFlow服务状态
curl http://localhost:9380/api/v1/health

# 或者检查docker容器
docker ps | grep ragflow
```

### 3. 安装依赖

```bash
pip install requests
```

## 📊 测试示例输出

### 成功示例
```
🚀 发送批量请求到: http://localhost:9380/api/v1/datasets/abc123/documents/def456/chunks/batch
📊 批量大小: 20 chunks
🔧 处理分片: 5
⏱️  请求耗时: 2.34 秒
📤 HTTP状态码: 200
✅ 批量添加成功!
   ✅ 成功添加: 20 chunks
   ❌ 失败数量: 0 chunks
📊 处理统计:
   📥 请求总数: 20
   🔄 分片大小: 5
   📦 处理批次: 4
   💰 嵌入成本: 1240
```

### 错误示例
```
❌ 请求失败:
   状态码: 404
   响应: Dataset not found
```

## 🔧 高级配置

### 批量大小调优
- **小批量(≤10)**: `batch_size: 2-5`
- **中等批量(11-50)**: `batch_size: 5-10`  
- **大批量(>50)**: `batch_size: 10-20`

### 性能限制
- 单次最大chunks: 100
- 单个chunk最大长度: 1000字符
- 最大批量大小: 20

## ⚠️ 注意事项

1. **确保RAGFlow服务已启用KnowFlow扩展**
   ```bash
   # 检查挂载是否生效
   docker exec ragflow-server ls -la /ragflow/api/apps/sdk/doc.py
   ```

2. **API令牌认证**
   - 如果RAGFlow启用了认证，需要配置`API_KEY`

3. **网络超时**
   - 大批量测试可能需要较长时间，脚本默认60秒超时

## 🐛 故障排除

### 常见错误

1. **Dataset/Document not found**
   - 检查ID是否正确
   - 确认有访问权限

2. **Connection refused**
   - 检查RAGFlow服务是否运行
   - 确认端口配置(默认9380)

3. **Timeout**
   - 增加超时时间
   - 减少批量大小

4. **Authentication failed**
   - 检查API_KEY配置
   - 确认令牌有效性

## 🎯 测试建议

1. **先用快速测试验证连通性**
2. **然后用完整测试套件评估性能**
3. **根据实际需求调整批量大小**
4. **监控内存和CPU使用情况** 