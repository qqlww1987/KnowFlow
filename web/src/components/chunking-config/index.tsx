import { useTranslate } from '@/hooks/common-hooks';
import { InfoCircleOutlined } from '@ant-design/icons';
import { Alert, Card, Col, Form, Input, InputNumber, Row, Select } from 'antd';
import { memo } from 'react';

interface ChunkingConfigProps {
  className?: string;
  initialValues?: {
    strategy?: 'basic' | 'smart' | 'advanced' | 'strict_regex' | 'parent_child';
    chunk_token_num?: number;
    min_chunk_tokens?: number;
    regex_pattern?: string;
    parent_config?: {
      parent_chunk_size?: number;
      parent_chunk_overlap?: number;
      retrieval_mode?: 'parent' | 'child' | 'hybrid';
      parent_split_level?: number; // AST语义分块：按照标题层级分割父分块
    };
  };
}

export const ChunkingConfig = memo(function ChunkingConfig({
  className,
  initialValues = {
    strategy: 'smart',
    chunk_token_num: 256,
    min_chunk_tokens: 10,
    regex_pattern: '',
    parent_config: {
      parent_chunk_size: 1024,
      parent_chunk_overlap: 100,
      retrieval_mode: 'parent',
      parent_split_level: 2, // 默认按H2标题分割
    },
  },
}: ChunkingConfigProps) {
  const { t } = useTranslate('knowledgeConfiguration');
  const strategy = Form.useWatch(['chunking_config', 'strategy']);
  const chunkTokenNum = Form.useWatch(['chunking_config', 'chunk_token_num']);

  const strategyOptions = [
    { value: 'basic', label: '基础分块' },
    { value: 'smart', label: '智能分块' },
    { value: 'advanced', label: '按标题分块' },
    { value: 'strict_regex', label: '正则分块' },
    { value: 'parent_child', label: '父子分块' },
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

      {strategy === 'parent_child' && (
        <>
          <Alert
            message="AST父子分块模式说明"
            description="采用基于AST语义分析的双层分块结构。父分块按照Markdown标题层级（H1、H2、H3等）进行语义边界分割，确保语义完整性；子分块使用智能AST分块，保持语义连贯。检索时先通过子分块精确匹配，再返回对应的父分块提供完整上下文。"
            type="info"
            showIcon
            icon={<InfoCircleOutlined />}
            style={{ marginBottom: 16 }}
          />

          <Row gutter={16}>
            <Col span={12}>
              <Card
                title="父分块配置"
                size="small"
                style={{ marginBottom: 16 }}
              >
                <Form.Item
                  name={[
                    'chunking_config',
                    'parent_config',
                    'parent_chunk_size',
                  ]}
                  label="父分块大小"
                  initialValue={
                    initialValues.parent_config?.parent_chunk_size || 1024
                  }
                  rules={[
                    { required: true, message: '请输入父分块大小' },
                    {
                      validator: (_, value) => {
                        if (value < 200 || value > 4000) {
                          return Promise.reject(
                            new Error('父分块大小必须在200-4000之间'),
                          );
                        }
                        return Promise.resolve();
                      },
                    },
                  ]}
                  extra="单位：tokens，提供丰富上下文"
                >
                  <InputNumber
                    min={200}
                    max={4000}
                    placeholder="1024"
                    style={{ width: '100%' }}
                  />
                </Form.Item>

                <Form.Item
                  name={[
                    'chunking_config',
                    'parent_config',
                    'parent_chunk_overlap',
                  ]}
                  label="父分块重叠"
                  initialValue={
                    initialValues.parent_config?.parent_chunk_overlap || 100
                  }
                  rules={[
                    {
                      validator: (_, value) => {
                        if (value < 0 || value > 500) {
                          return Promise.reject(
                            new Error('重叠大小必须在0-500之间'),
                          );
                        }
                        return Promise.resolve();
                      },
                    },
                  ]}
                  extra="单位：tokens，相邻父分块重叠"
                >
                  <InputNumber
                    min={0}
                    max={500}
                    placeholder="100"
                    style={{ width: '100%' }}
                  />
                </Form.Item>

                <Form.Item
                  name={[
                    'chunking_config',
                    'parent_config',
                    'parent_split_level',
                  ]}
                  label="AST分割层级"
                  initialValue={
                    initialValues.parent_config?.parent_split_level || 2
                  }
                  rules={[
                    {
                      validator: (_, value) => {
                        if (value < 1 || value > 6) {
                          return Promise.reject(
                            new Error('标题层级必须在1-6之间'),
                          );
                        }
                        return Promise.resolve();
                      },
                    },
                  ]}
                  extra="按H1(1), H2(2), H3(3)等标题层级分割父分块"
                >
                  <Select placeholder="选择标题层级">
                    <Select.Option value={1}>H1 - 最大章节</Select.Option>
                    <Select.Option value={2}>
                      H2 - 主要章节（推荐）
                    </Select.Option>
                    <Select.Option value={3}>H3 - 子章节</Select.Option>
                    <Select.Option value={4}>H4 - 小节</Select.Option>
                    <Select.Option value={5}>H5 - 段落级</Select.Option>
                    <Select.Option value={6}>H6 - 细粒度</Select.Option>
                  </Select>
                </Form.Item>
              </Card>
            </Col>

            <Col span={12}>
              <Card
                title="子分块配置"
                size="small"
                style={{ marginBottom: 16 }}
              >
                <Form.Item
                  label="子分块大小"
                  extra="基于AST智能分块，自动保持语义完整性"
                >
                  <InputNumber
                    value={chunkTokenNum}
                    disabled
                    style={{ width: '100%' }}
                  />
                </Form.Item>

                <Form.Item
                  name={['chunking_config', 'parent_config', 'retrieval_mode']}
                  label="检索模式"
                  initialValue={
                    initialValues.parent_config?.retrieval_mode || 'parent'
                  }
                  rules={[{ required: true, message: '请选择检索模式' }]}
                >
                  <Select placeholder="选择检索模式">
                    <Select.Option value="parent">
                      父分块模式（推荐）
                    </Select.Option>
                    <Select.Option value="child">子分块模式</Select.Option>
                    <Select.Option value="hybrid">混合模式</Select.Option>
                  </Select>
                </Form.Item>
              </Card>
            </Col>
          </Row>
        </>
      )}
    </div>
  );
});

export default ChunkingConfig;
