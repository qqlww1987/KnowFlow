export interface ProcessPdfResponse {
    code: number;  // 状态码，通常0表示成功
    message?: string;  // 可选的消息
    data?: any;  // 实际返回的数据
    // 可能包含其他服务端返回的字段
  }

