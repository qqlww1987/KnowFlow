import kbService from '@/services/knowledge-service';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { message } from 'antd';
import { get } from 'lodash';
import { useFetchKnowledgeBaseConfiguration } from './knowledge-hooks';

// KnowFlow API 调用接口
interface KnowFlowApiConfig {
  parse_method?: string;
  language?: string;
  chunking_config?: {
    strategy?: 'basic' | 'smart' | 'advanced' | 'strict_regex';
    chunk_token_num?: number;
    min_chunk_tokens?: number;
    regex_pattern?: string;
  };
}

// 调用 KnowFlow 取消解析 API (通过nginx代理)
const callKnowFlowCancelApi = async (documentId: string) => {
  try {
    // 通过统一的API服务调用knowflow取消解析接口
    const response = await kbService.knowflow_parse_cancel(
      {}, // 空请求体
      `${documentId}/parse/cancel`,
    );

    // 因为 request 设置了 getResponse: true，响应数据在 response.data 中
    return response.data;
  } catch (error: any) {
    console.error('KnowFlow 取消解析 API 调用失败:', error);
    throw new Error(
      error.response?.data?.message ||
        error.message ||
        'KnowFlow 取消解析 API 调用失败',
    );
  }
};
const callKnowFlowParseApi = async (
  documentId: string,
  config: KnowFlowApiConfig,
) => {
  const { parse_method = 'auto', language = 'ch', chunking_config } = config;

  // 准备请求体
  const requestBody: any = {
    parse_method,
    language,
  };

  // 如果有分块配置，添加到请求体中
  if (chunking_config) {
    requestBody.chunking_config = chunking_config;
  }

  try {
    // 通过统一的API服务调用knowflow解析接口
    const response = await kbService.knowflow_document_parse(
      requestBody,
      `${documentId}/parse`,
    );

    // 因为 request 设置了 getResponse: true，响应数据在 response.data 中
    return response.data;
  } catch (error: any) {
    console.error('KnowFlow API 调用失败:', error);
    throw new Error(
      error.response?.data?.message || error.message || 'KnowFlow API 调用失败',
    );
  }
};

// 获取 KnowFlow 解析进度 (通过nginx代理)
const getKnowFlowParseProgress = async (documentId: string) => {
  try {
    const response = await kbService.knowflow_parse_progress(
      undefined,
      `${documentId}/parse/progress`,
    );

    // 因为 request 设置了 getResponse: true，响应数据在 response.data 中
    return response.data;
  } catch (error: any) {
    console.error('获取 KnowFlow 解析进度失败:', error);
    throw new Error(
      error.response?.data?.message || error.message || '获取解析进度失败',
    );
  }
};

// 使用 MinerU 解析器运行文档的 Hook
export const useRunMinerUDocument = () => {
  const queryClient = useQueryClient();
  const { data: knowledgeDetail } = useFetchKnowledgeBaseConfiguration();

  const {
    data,
    isPending: loading,
    mutateAsync,
  } = useMutation({
    mutationKey: ['runMinerUDocument'],
    mutationFn: async ({
      doc_ids,
      run,
      delete: shouldDelete,
    }: {
      doc_ids: string[];
      run: number;
      delete: boolean;
    }) => {
      // 获取 KnowFlow API 配置
      const knowflowConfig = get(
        knowledgeDetail,
        'parser_config',
        {},
      ) as KnowFlowApiConfig;

      // 根据 run 参数决定操作类型
      if (run === 1) {
        // 获取每个文档的详细信息，包括分块配置
        const { data: docInfoResponse } = await kbService.document_infos({
          doc_ids,
        });
        if (docInfoResponse.code !== 0) {
          throw new Error('无法获取文档信息');
        }

        const documentInfos = docInfoResponse.data;

        // 开始解析
        const results = [];
        for (const docInfo of documentInfos) {
          try {
            // 为每个文档准备单独的配置，包含其分块配置
            const docConfig: KnowFlowApiConfig = {
              ...knowflowConfig,
              // 使用文档自己的分块配置，如果存在的话
              chunking_config:
                docInfo.parser_config?.chunking_config ||
                knowflowConfig.chunking_config,
            };

            const result = await callKnowFlowParseApi(docInfo.id, docConfig);
            results.push(result);

            // 每调用一次KnowFlow API后立即刷新文档列表
            queryClient.invalidateQueries({ queryKey: ['fetchDocumentList'] });
          } catch (error: any) {
            console.error(`文档 ${docInfo.id} 解析失败:`, error);
            results.push({ code: -1, message: error.message });
          }
        }

        // 检查是否有成功的解析
        const successCount = results.filter((r) => r.code === 0).length;
        if (successCount > 0) {
          message.success(
            `已成功提交 ${successCount} 个文档到 KnowFlow 进行解析`,
          );
        }
        if (successCount < doc_ids.length) {
          message.warning(`${doc_ids.length - successCount} 个文档提交失败`);
        }

        return { code: successCount > 0 ? 0 : -1 };
      } else if (run === 2) {
        // 取消解析 - 调用 KnowFlow 取消解析 API
        const results = [];
        for (const docId of doc_ids) {
          try {
            const result = await callKnowFlowCancelApi(docId);
            results.push(result);

            // 每调用一次KnowFlow取消API后立即刷新文档列表
            queryClient.invalidateQueries({ queryKey: ['fetchDocumentList'] });
          } catch (error: any) {
            console.error(`文档 ${docId} 取消解析失败:`, error);
            results.push({ code: -1, message: error.message });
          }
        }

        // 检查是否有成功的取消操作
        const successCount = results.filter((r) => r.code === 0).length;
        if (successCount > 0) {
          message.success(`已成功取消 ${successCount} 个文档的解析`);
        }
        if (successCount < doc_ids.length) {
          message.warning(`${doc_ids.length - successCount} 个文档取消失败`);
        }

        return { code: successCount > 0 ? 0 : -1 };
      }

      return { code: 0 };
    },
    onError: (error: any) => {
      message.error(`MinerU 解析失败: ${error.message}`);
    },
  });

  return { runMinerUDocument: mutateAsync, loading, data };
};

// 获取 MinerU 解析进度的 Hook
export const useFetchMinerUProgress = () => {
  const {
    data,
    isPending: loading,
    mutateAsync,
  } = useMutation({
    mutationKey: ['fetchMinerUProgress'],
    mutationFn: async ({ documentId }: { documentId: string }) => {
      const result = await getKnowFlowParseProgress(documentId);
      return result;
    },
    onError: (error: any) => {
      console.error('获取 MinerU 解析进度失败:', error.message);
    },
  });

  return { fetchMinerUProgress: mutateAsync, loading, data };
};

// 批量运行 MinerU 文档解析的 Hook
export const useBatchRunMinerUDocuments = () => {
  const queryClient = useQueryClient();
  const { runMinerUDocument } = useRunMinerUDocument();

  const {
    data,
    isPending: loading,
    mutateAsync,
  } = useMutation({
    mutationKey: ['batchRunMinerUDocuments'],
    mutationFn: async ({
      doc_ids,
      run = 1,
    }: {
      doc_ids: string[];
      run?: number;
    }) => {
      const result = await runMinerUDocument({
        doc_ids,
        run,
        delete: false,
      });

      queryClient.invalidateQueries({ queryKey: ['fetchDocumentList'] });

      return result;
    },
    onError: (error: any) => {
      console.error('批量运行 MinerU 文档解析失败:', error);
      message.error(`批量解析失败: ${error.message}`);
    },
  });

  return { batchRunMinerUDocuments: mutateAsync, loading, data };
};
