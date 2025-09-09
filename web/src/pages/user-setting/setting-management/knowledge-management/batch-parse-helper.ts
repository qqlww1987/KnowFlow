// 批量解析助手 - 专门处理批量解析逻辑的独立模块

export interface BatchParsingState {
  isActive: boolean;
  totalDocuments: number;
  completedDocuments: number;
  currentDocumentName: string | null;
  message: string;
  error: string | null;
  startTime: number | null;
}

export interface DocumentProgress {
  id: string;
  name: string;
  progress: number;
  chunk_num: number;
  run: string; // '0': 未解析, '1': 解析中, '3': 完成
  status: string;
  message?: string;
}

export class BatchParseMonitor {
  private pollingTimer: NodeJS.Timeout | null = null;
  private onStateChange: (state: BatchParsingState) => void;
  private onDocumentsUpdate: (documents: DocumentProgress[]) => void;
  private kbId: string;
  private request: any;
  private pagination: { current: number; pageSize: number };

  constructor(
    kbId: string,
    request: any,
    onStateChange: (state: BatchParsingState) => void,
    onDocumentsUpdate: (documents: DocumentProgress[]) => void,
    pagination: { current: number; pageSize: number } = {
      current: 1,
      pageSize: 10,
    },
  ) {
    this.kbId = kbId;
    this.request = request;
    this.onStateChange = onStateChange;
    this.onDocumentsUpdate = onDocumentsUpdate;
    this.pagination = pagination;
  }

  // 启动监控
  start() {
    this.stop(); // 确保清理旧的定时器

    // 初始化状态
    this.onStateChange({
      isActive: true,
      totalDocuments: 0,
      completedDocuments: 0,
      currentDocumentName: null,
      message: '正在启动批量解析...',
      error: null,
      startTime: Date.now(),
    });

    // 立即检查一次
    this.checkProgress();

    // 每3秒检查一次
    this.pollingTimer = setInterval(() => {
      this.checkProgress();
    }, 3000);
  }

  // 停止监控
  stop() {
    if (this.pollingTimer) {
      clearInterval(this.pollingTimer);
      this.pollingTimer = null;
    }
  }

  // 更新分页参数
  updatePagination(pagination: { current: number; pageSize: number }) {
    this.pagination = pagination;
    console.log('[BatchMonitor] 分页参数已更新:', this.pagination);
  }

  // 检查进度
  private async checkProgress() {
    try {
      // 同时获取批量进度和文档列表状态
      const [batchRes, documentsRes] = await Promise.all([
        this.request.get(
          `/api/knowflow/v1/knowledgebases/${this.kbId}/batch_parse_sequential/progress`,
        ),
        this.request.get(
          `/api/knowflow/v1/knowledgebases/${this.kbId}/documents`,
          {
            params: {
              current_page: this.pagination.current,
              size: this.pagination.pageSize,
            },
          },
        ),
      ]);

      // 处理批量解析进度
      if (batchRes?.data?.code === 0 && batchRes.data.data) {
        const data = batchRes.data.data;

        this.onStateChange({
          isActive: true,
          totalDocuments: data.total || 0,
          completedDocuments: data.current || 0,
          currentDocumentName: this.extractDocumentName(data.message),
          message: data.message || '批量解析进行中...',
          error: null,
          startTime: data.start_time
            ? Math.floor(data.start_time * 1000)
            : Date.now(),
        });

        // 检查是否完成
        if (data.status === 'completed' || data.status === 'failed') {
          this.onStateChange({
            isActive: false,
            totalDocuments: data.total || 0,
            completedDocuments: data.current || 0,
            currentDocumentName: null,
            message:
              data.message ||
              (data.status === 'completed'
                ? '批量解析完成！'
                : '批量解析失败！'),
            error: data.status === 'failed' ? data.message || '解析失败' : null,
            startTime: data.start_time
              ? Math.floor(data.start_time * 1000)
              : Date.now(),
          });

          this.stop();
          return { completed: true, success: data.status === 'completed' };
        }
      } else {
        this.onStateChange({
          isActive: true,
          totalDocuments: 0,
          completedDocuments: 0,
          currentDocumentName: null,
          message: '获取进度时出现错误',
          error: batchRes?.data?.message || '获取进度失败',
          startTime: Date.now(),
        });
      }

      // 处理文档列表状态更新
      if (documentsRes?.data?.code === 0) {
        console.log('[BatchMonitor] 文档API响应结构:', documentsRes.data);

        // 适配不同的API响应结构
        let documentsData = null;
        if (documentsRes.data.data?.list) {
          // 如果是分页格式: { data: { list: [...], total: x } }
          documentsData = documentsRes.data.data.list;
        } else if (documentsRes.data.data?.data) {
          // 如果是分页格式: { data: { data: [...], total: x } }
          documentsData = documentsRes.data.data.data;
        } else if (
          documentsRes.data.data &&
          Array.isArray(documentsRes.data.data)
        ) {
          // 如果是直接数组格式: { data: [...] }
          documentsData = documentsRes.data.data;
        }

        if (documentsData && Array.isArray(documentsData)) {
          console.log(
            '[BatchMonitor] 处理文档数据，数量:',
            documentsData.length,
          );

          const documents: DocumentProgress[] = documentsData.map(
            (doc: any) => {
              console.log('[BatchMonitor] 文档数据:', {
                id: doc.id,
                name: doc.name,
                progress: doc.progress,
                chunk_num: doc.chunk_num,
                run: doc.run,
                status: doc.status,
              });

              return {
                id: doc.id,
                name: doc.name,
                progress: doc.progress || 0,
                chunk_num: doc.chunk_num || 0,
                run: doc.run || '0',
                status: doc.status || '1',
                message: doc.message || '',
              };
            },
          );

          console.log(
            '[BatchMonitor] 调用文档更新回调，文档数量:',
            documents.length,
          );
          // 更新文档状态
          this.onDocumentsUpdate(documents);
        } else {
          console.log('[BatchMonitor] 文档数据格式不正确:', documentsRes.data);
        }
      }
    } catch (error: any) {
      this.onStateChange({
        isActive: true,
        totalDocuments: 0,
        completedDocuments: 0,
        currentDocumentName: null,
        message: '无法连接到服务器',
        error: error.message || '网络错误',
        startTime: Date.now(),
      });
    }

    return { completed: false };
  }

  // 从消息中提取文档名
  private extractDocumentName(message: string): string | null {
    if (!message) return null;

    const match = message.match(/正在解析:\s*(.+?)\s*\(/);
    return match ? match[1].trim() : null;
  }
}

// 启动批量解析的工具函数
export async function startBatchParsing(
  kbId: string,
  request: any,
): Promise<boolean> {
  try {
    const res = await request.post(
      `/api/knowflow/v1/knowledgebases/${kbId}/batch_parse_sequential/start`,
    );

    return res?.data?.code === 0;
  } catch (error) {
    console.error('启动批量解析失败:', error);
    return false;
  }
}
