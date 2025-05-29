# 临时文件清理控制

## 环境变量说明

### CLEANUP_TEMP_FILES

控制系统是否自动清理处理过程中生成的临时文件。

**默认值**: `true`

**可选值**:
- `true`, `1`, `yes`, `on` - 启用自动清理（默认）
- `false`, `0`, `no`, `off` - 禁用自动清理

## 使用方法

在你的 `.env` 文件中添加：

```bash
# 启用自动清理（默认行为）
CLEANUP_TEMP_FILES=true

# 或者禁用自动清理（用于调试）
CLEANUP_TEMP_FILES=false
```

## 影响的功能

当 `CLEANUP_TEMP_FILES=false` 时，以下临时文件将被保留：

1. **文档解析临时文件** (`document_parser.py`)
   - 临时 PDF 文件
   - 临时图片目录

2. **MinIO 图片上传** (`minio_server.py`)
   - 处理后的图片文件

3. **RAGFlow 资源创建** (`ragflow_build.py`)
   - Markdown 文件及其目录

## 使用场景

### 生产环境
```bash
CLEANUP_TEMP_FILES=true
```
- 自动清理临时文件，节省磁盘空间
- 避免临时文件积累

### 开发/调试环境
```bash
CLEANUP_TEMP_FILES=false
```
- 保留临时文件用于调试
- 可以检查中间处理结果
- 便于问题排查

## 注意事项

1. **磁盘空间**: 禁用清理可能导致临时文件积累，注意监控磁盘使用情况
2. **调试完成**: 调试完成后建议重新启用自动清理
3. **权限**: 确保应用有权限删除临时文件目录

## 日志信息

启用清理时的日志：
```
[INFO] 已清理临时文件目录: /tmp/some_temp_dir
[INFO] 已删除临时图片文件: /tmp/image.jpg
```

禁用清理时的日志：
```
[INFO] 环境变量 CLEANUP_TEMP_FILES 设置为 false，保留临时文件: /tmp/some_temp_dir
[INFO] 保留临时图片文件: /tmp/image.jpg
``` 