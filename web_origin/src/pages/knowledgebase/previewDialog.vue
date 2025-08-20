<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="(value) => emit('update:visible', value)"
    title="文档预览"
    width="80%"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <div v-loading="loading" class="preview-container">
      <div v-if="content" class="preview-content">
        {{ content }}
      </div>
      <div v-else class="empty-state">
        暂无预览内容
      </div>
    </div>

    <template #footer>
      <span class="dialog-footer">
        <el-button @click="handleClose">关闭</el-button>
      </span>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

interface Props {
  visible: boolean
  documentId?: string
  content?: string
}

const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
}>()

const loading = ref(false)

// 监听对话框显示状态
watch(() => props.visible, async (newVal) => {
  if (newVal && props.documentId) {
    // 这里可以添加文档预览数据加载逻辑
    console.log('加载文档预览:', props.documentId)
  }
})

// 处理关闭
function handleClose() {
  emit('update:visible', false)
}
</script>

<style scoped>
.preview-container {
  min-height: 300px;
  max-height: 60vh;
  overflow-y: auto;
}

.preview-content {
  padding: 16px;
  white-space: pre-wrap;
  font-family: 'Courier New', monospace;
  font-size: 14px;
  line-height: 1.5;
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: #909399;
  font-size: 16px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
}
</style> 