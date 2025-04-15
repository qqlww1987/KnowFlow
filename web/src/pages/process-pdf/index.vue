<template>
  <div class="app-container">
    <el-card shadow="never" class="search-wrapper">
      <el-upload
        class="upload-demo"
        :auto-upload="false"
        :on-change="handleFileChange"
        :file-list="fileList"
        
        accept=".pdf"
        multiple
      >
        <el-button type="primary">选择PDF文件</el-button>
        <template #tip>
          <div class="el-upload__tip">请上传PDF格式文档</div>
        </template>
      </el-upload>

      <el-table :data="fileList" style="width: 100%; margin-top: 20px">
        <el-table-column prop="name" label="文件名" />
        <el-table-column prop="size" label="大小" :formatter="formatFileSize" />
        <el-table-column label="解析状态" width="120">
          <template #default="scope">
            <el-tag :type="getStatusTagType(scope.row.status)">
              {{ getStatusText(scope.row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180">
          <template #default="scope">
            <el-button
              size="small"
              type="primary"
              @click="handleSubmit(scope.row)"
              :loading="scope.row.loading"
            >
              解析
            </el-button>
            <el-button
              size="small"
              type="danger"
              @click="handleRemove(scope.row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="status" class="status-container">
        <el-alert :title="status"  show-icon />
        <div v-if="result" class="result-container">
          <el-collapse>
            <el-collapse-item title="处理结果">
              <pre>{{ result }}</pre>
            </el-collapse-item>
          </el-collapse>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script lang="ts" setup>
import { ref } from 'vue'

import { ElMessage, ElMessageBox } from 'element-plus'

const fileList = ref<any[]>([])
const status = ref('')
const statusType = ref('info')
const result = ref('')

const handleFileChange = (file: any) => {
  fileList.value.push({
    ...file,
    loading: false
  })
}

const beforeRemove = (file: any) => {
  return ElMessageBox.confirm(`确定移除 ${file.name}？`, '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  })
}

const handleRemove = (file: any) => {
  fileList.value = fileList.value.filter(f => f.uid !== file.uid)
  ElMessage.success('文件已移除')
}

const formatFileSize = (row: any) => {
  const bytes = row.size
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}
import { processPdfApi } from "@/common/apis/multimodal"
const handleSubmit = async (file: any) => {
  file.loading = true
  file.status = 'processing' // 设置解析中状态
  
  try {
    const response = await processPdfApi(file.raw)
    
    if (response?.code === 0) {
      file.status = 'success' // 解析成功
      status.value = `${file.name} 处理成功`
      statusType.value = 'success'
      result.value = JSON.stringify(response, null, 2)
      ElMessage.success('PDF处理完成')
    } else {
      file.status = 'failed' // 解析失败
      ElMessage.error('解析失败')
    }
  } catch (error: any) {
    file.status = 'failed' // 解析失败
    // ... 错误处理代码保持不变 ...
  } finally {
    file.loading = false
  }
}

// 新增状态显示方法
const getStatusTagType = (status: string) => {
  switch(status) {
    case 'success': return 'success'
    case 'failed': return 'danger'
    case 'processing': return 'warning'
    default: return 'info'
  }
}

const getStatusText = (status: string) => {
  switch(status) {
    case 'success': return '解析完成'
    case 'failed': return '解析失败'
    case 'processing': return '解析中'
    default: return '待解析'
  }
}
</script>

<style scoped>
.app-container {
  padding: 20px;
}

.upload-demo {
  margin-bottom: 10px;
}

.status-container {
  margin-top: 20px;
}

.result-container {
  margin-top: 15px;
}

pre {
  white-space: pre-wrap;
  word-wrap: break-word;
  background-color: #f5f7fa;
  padding: 12px;
  border-radius: 4px;
  font-family: monospace;
}
</style>