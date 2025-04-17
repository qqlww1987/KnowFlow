import { request } from "@/http/axios"
import type * as mul from "./type"

// PDF处理接口``
export function processPdfApi(raw: File) {
  const formData = new FormData()
  formData.append('file', raw)
  
  return request<mul.ProcessPdfResponse>({
    url: 'api/v1/multimodal/process_pdf',
    method: 'post',
    data: formData,
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
}

export function getProcessStatus(taskId: string) {
  return request<mul.ProcessPdfResponse>({
    url: `api/v1/multimodal/process_status/${taskId}`,
    method: "get"
  })
}

// Export as named export
export default {
    processPdfApi
}