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
        <el-table-column label="处理进度" width="200">
          <template #default="scope">
            <el-progress 
              :percentage="scope.row.progress || 0"
              :status="scope.row.status === 'success' ? 'success' : scope.row.status === 'failed' ? 'exception' : ''"
            />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180">
          <template #default="scope">
            <el-button
              size="small"
              type="primary"
              @click="handleSubmit(scope.row)"
              :loading="scope.row.loading"  
              :disabled="scope.row.loading"
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
        <div v-if="currentLogs.length" class="logs-container" ref="logsContainer">
          <el-collapse :value="['logs']">
            <el-collapse-item title="处理日志" name="logs">
              <div class="log-item" v-for="(log, index) in currentLogs" :key="index">
                <span :class="{ 'error-log': log.includes('ERROR') }">{{ log }}</span>
              </div>
            </el-collapse-item>
          </el-collapse>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script lang="ts" setup>
import { ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { processPdfApi, getProcessStatus } from "@/common/apis/multimodal"

const fileList = ref<any[]>([])
const status = ref('')
const statusType = ref('info')
const result = ref('')
const currentLogs = ref<string[]>([])  // 定义 currentLogs 变量

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

const pollStatus = async (taskId: string, file: any) => {
  const timer = setInterval(async () => {
    try {
      const response = await getProcessStatus(taskId)

      // 更新文件状态
      file.progress = response.data.progress
      currentLogs.value = response.data.logs || []
      status.value = `正在处理: ${file.name}`

      // 检查处理状态
      if (response.data.status === 'completed') {
        clearInterval(timer)
        file.status = 'success'
        file.loading = false  // 处理完成，解除按钮禁用状态
        ElMessage.success('PDF处理完成')
      } else if (response.data.status === 'failed') {
        clearInterval(timer)
        file.status = 'failed'
        file.loading = false  // 处理失败，解除按钮禁用状态
        ElMessage.error('处理失败')
      }
    } catch (error) {
      clearInterval(timer)
      file.status = 'failed'
      file.loading = false  // 发生错误，解除按钮禁用状态
      ElMessage.error('状态查询失败')
      console.error('Error fetching status:', error)
    }
  }, 3000)

  file.statusTimer = timer
}

const handleSubmit = async (file: any) => {
  // 防止重复提交
  if (file.loading || file.status === 'processing') {
    ElMessage.warning('文件正在处理中')
    return
  }

  file.loading = true  // 启用加载动画
  file.status = 'processing'
  file.progress = 0
  currentLogs.value = []
  status.value = `正在处理: ${file.name}`

  try {
    const formData = new FormData()
    formData.append('file', file.raw)
    const response = await processPdfApi(file.raw)
    
    if (response.data.task_id) {
      status.value = `${file.name} 开始处理`
      statusType.value = 'info'
      pollStatus(response.data.task_id, file)
      ElMessage.success('开始处理PDF文件')
    } else {
      file.status = 'failed'
      file.loading = false  // 处理失败，解除按钮禁用状态
      status.value = `${file.name} 处理失败`
      statusType.value = 'error'
      ElMessage.error(response?.message || '处理失败')
    }
  } catch (error: any) {
    file.status = 'failed'
    file.loading = false  // 发生错误，解除按钮禁用状态
    status.value = `${file.name} 处理出错`
    statusType.value = 'error'
    ElMessage.error(error.message || '处理失败')
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

const logsContainer = ref<HTMLElement | null>(null)

// 监听日志变化并滚动到底部
watch(() => currentLogs.value, () => {
  if (logsContainer.value) {
    setTimeout(() => {
      logsContainer.value!.scrollTop = logsContainer.value!.scrollHeight
    }, 100)
  }
}, { deep: true })
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

.logs-container {
  margin-top: 15px;
  max-height: 300px;
  overflow-y: auto;
  scroll-behavior: smooth; /* 添加平滑滚动效果 */
}

.log-item {
  padding: 4px 0;
  font-family: monospace;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.error-log {
  color: #f56c6c;
}
</style>