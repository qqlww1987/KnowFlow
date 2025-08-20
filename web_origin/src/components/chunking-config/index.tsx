import { useTranslate } from '@/hooks/common-hooks';
import { Form, Input, InputNumber, Select } from 'antd';
import { memo } from 'react';

interface ChunkingConfigProps {
  className?: string;
  initialValues?: {
    strategy?: 'basic' | 'smart' | 'advanced' | 'strict_regex';
    chunk_token_num?: number;
    min_chunk_tokens?: number;
    regex_pattern?: string;
  };
}

export const ChunkingConfig = memo(function ChunkingConfig({
  className,
  initialValues = {
    strategy: 'smart',
    chunk_token_num: 256,
    min_chunk_tokens: 10,
    regex_pattern: '',
  },
}: ChunkingConfigProps) {
  const { t } = useTranslate('knowledgeConfiguration');
  const strategy = Form.useWatch(['chunking_config', 'strategy']);

  const strategyOptions = [
    { value: 'basic', label: '基础分块' },
    { value: 'smart', label: '智能分块' },
    { value: 'advanced', label: '按标题分块' },
    { value: 'strict_regex', label: '正则分块' },
  ];

  return (
    <div className={className}>
      <Form.Item
        name={['chunking_config', 'strategy']}
        label="分块策略"
        initialValue={initialValues.strategy}
        rules={[{ required: true, message: '请选择分块策略' }]}
      >
        <Select placeholder="请选择分块策略" options={strategyOptions} />
      </Form.Item>

      <Form.Item
        name={['chunking_config', 'chunk_token_num']}
        label="分块大小"
        initialValue={initialValues.chunk_token_num}
        rules={[
          { required: true, message: '请输入分块大小' },
          {
            validator: (_, value) => {
              if (value < 50 || value > 2048) {
                return Promise.reject(new Error('分块大小必须在50-2048之间'));
              }
              return Promise.resolve();
            },
          },
        ]}
        extra="单位：tokens，范围：50-2048"
      >
        <InputNumber
          min={50}
          max={2048}
          placeholder="256"
          style={{ width: '100%' }}
        />
      </Form.Item>

      <Form.Item
        name={['chunking_config', 'min_chunk_tokens']}
        label="最小分块大小"
        initialValue={initialValues.min_chunk_tokens}
        rules={[
          { required: true, message: '请输入最小分块大小' },
          {
            validator: (_, value) => {
              if (value < 10 || value > 500) {
                return Promise.reject(
                  new Error('最小分块大小必须在10-500之间'),
                );
              }
              return Promise.resolve();
            },
          },
        ]}
        extra="单位：tokens，范围：10-500"
      >
        <InputNumber
          min={10}
          max={500}
          placeholder="10"
          style={{ width: '100%' }}
        />
      </Form.Item>

      {strategy === 'strict_regex' && (
        <Form.Item
          name={['chunking_config', 'regex_pattern']}
          label="正则表达式"
          initialValue={initialValues.regex_pattern}
          rules={[
            {
              validator: (_, value) => {
                if (strategy === 'strict_regex') {
                  if (!value || !value.trim()) {
                    return Promise.reject(
                      new Error('正则分块策略需要输入正则表达式'),
                    );
                  }
                  try {
                    new RegExp(value);
                    return Promise.resolve();
                  } catch (e) {
                    return Promise.reject(new Error('请输入有效的正则表达式'));
                  }
                }
                return Promise.resolve();
              },
            },
          ]}
          extra="用于匹配条文等结构化内容"
        >
          <Input placeholder="第[零一二三四五六七八九十百千万\\d]+条" />
        </Form.Item>
      )}
    </div>
  );
});

export default ChunkingConfig;
