import { request } from "@/http/axios"

// PDF处理接口
export function processPdfApi(file: File) {
  const formData = new FormData()
  formData.append('file', file)
  
  return request({
    url: 'api/v1/multimodal/process_pdf',
    method: 'post',
    data: formData,
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
}

// Export as named export
export default {
    processPdfApi
}