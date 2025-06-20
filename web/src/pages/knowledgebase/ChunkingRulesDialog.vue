<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="(value) => emit('update:visible', value)"
    title="编辑分块规则"
    width="500px"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-width="120px"
      v-loading="loading"
    >
      <el-form-item label="分块策略" prop="strategy">
        <el-select v-model="form.strategy" placeholder="请选择分块策略" style="width: 100%">
          <el-option
            v-for="option in strategyOptions"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="分块大小" prop="chunk_token_num">
        <el-input-number
          v-model="form.chunk_token_num"
          :min="50"
          :max="2048"
          placeholder="256"
          style="width: 100%"
        />
        <div class="form-tip">单位：tokens，范围：50-2048</div>
      </el-form-item>

      <el-form-item label="最小分块大小" prop="min_chunk_tokens">
        <el-input-number
          v-model="form.min_chunk_tokens"
          :min="10"
          :max="500"
          placeholder="10"
          style="width: 100%"
        />
        <div class="form-tip">单位：tokens，范围：10-500</div>
      </el-form-item>

      <el-form-item 
        v-if="form.strategy === 'strict_regex'"
        label="正则表达式" 
        prop="regex_pattern"
      >
        <el-input
          v-model="form.regex_pattern"
          placeholder="第[零一二三四五六七八九十百千万\\d]+条"
          style="width: 100%"
        />
        <div class="form-tip">用于匹配条文等结构化内容</div>
      </el-form-item>
    </el-form>

    <template #footer>
      <span class="dialog-footer">
        <el-button @click="handleClose">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleSubmit">
          保存
        </el-button>
      </span>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, watch, nextTick } from 'vue'
import { ElMessage, type FormInstance } from 'element-plus'
import { 
  updateDocumentChunkingConfigApi, 
  getDocumentChunkingConfigApi 
} from '@@/apis/kbs/document'

interface ChunkingConfig {
  strategy: 'basic' | 'smart' | 'advanced' | 'strict_regex'
  chunk_token_num: number
  min_chunk_tokens: number
  regex_pattern?: string
}

interface Props {
  visible: boolean
  documentId: string
  documentName?: string
}

const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'success'): void
}>()

const formRef = ref<FormInstance>()
const loading = ref(false)
const submitLoading = ref(false)

const form = reactive<ChunkingConfig>({
  strategy: 'smart',
  chunk_token_num: 256,
  min_chunk_tokens: 10,
  regex_pattern: ''
})

const strategyOptions = [
  { value: 'basic', label: '基础分块' },
  { value: 'smart', label: '智能分块' },
  { value: 'advanced', label: '按标题分块' },
  { value: 'strict_regex', label: '正则分块' }
]

const rules = {
  strategy: [
    { required: true, message: '请选择分块策略', trigger: 'change' }
  ],
  chunk_token_num: [
    { required: true, message: '请输入分块大小', trigger: 'blur' },
    { type: 'number', min: 50, max: 2048, message: '分块大小必须在50-2048之间', trigger: 'blur' }
  ],
  min_chunk_tokens: [
    { required: true, message: '请输入最小分块大小', trigger: 'blur' },
    { type: 'number', min: 10, max: 500, message: '最小分块大小必须在10-500之间', trigger: 'blur' }
  ],
  regex_pattern: [
    { 
      validator: (rule: any, value: string, callback: any) => {
        if (form.strategy === 'strict_regex') {
          if (!value || !value.trim()) {
            callback(new Error('正则分块策略需要输入正则表达式'))
          } else {
            try {
              new RegExp(value)
              callback()
            } catch (e) {
              callback(new Error('请输入有效的正则表达式'))
            }
          }
        } else {
          callback()
        }
      }, 
      trigger: 'blur' 
    }
  ]
}

// 监听对话框显示状态
watch(() => props.visible, async (newVal) => {
  if (newVal && props.documentId) {
    await loadChunkingConfig()
  }
})

// 加载分块配置
async function loadChunkingConfig() {
  if (!props.documentId) return
  
  loading.value = true
  try {
    const response = await getDocumentChunkingConfigApi(props.documentId)
    const config = response?.data?.chunking_config
    
    if (config) {
      Object.assign(form, {
        strategy: config.strategy || 'smart',
        chunk_token_num: config.chunk_token_num || 256,
        min_chunk_tokens: config.min_chunk_tokens || 10,
        regex_pattern: config.regex_pattern || ''
      })
    }
  } catch (error: any) {
    ElMessage.error(`加载分块配置失败: ${error?.message || '未知错误'}`)
  } finally {
    loading.value = false
  }
}

// 处理提交
async function handleSubmit() {
  if (!formRef.value || !props.documentId) return
  
  try {
    const valid = await formRef.value.validate()
    if (!valid) return
    
    submitLoading.value = true
    
    const config: ChunkingConfig = {
      strategy: form.strategy,
      chunk_token_num: form.chunk_token_num,
      min_chunk_tokens: form.min_chunk_tokens
    }
    
    // 只在正则分块时包含正则表达式
    if (form.strategy === 'strict_regex' && form.regex_pattern) {
      config.regex_pattern = form.regex_pattern
    }
    
    await updateDocumentChunkingConfigApi({
      doc_id: props.documentId,
      chunking_config: config
    })
    
    ElMessage.success('分块配置保存成功')
    emit('success')
    handleClose()
  } catch (error: any) {
    ElMessage.error(`保存分块配置失败: ${error?.message || '未知错误'}`)
  } finally {
    submitLoading.value = false
  }
}

// 处理关闭
function handleClose() {
  emit('update:visible', false)
  // 重置表单验证状态
  nextTick(() => {
    formRef.value?.resetFields()
  })
}
</script>

<style scoped>
.form-tip {
  color: #909399;
  font-size: 12px;
  line-height: 1.5;
  margin-top: 4px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
</style> 