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
      parent_separator?: string;
      child_separator?: string;
      retrieval_mode?: 'parent' | 'child' | 'hybrid';
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
      parent_separator: '\\n\\n',
      child_separator: '[。！？.!?]',
      retrieval_mode: 'parent',
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
            message="父子分块模式说明"
            description="采用双层分段结构，基于Smart AST分块 + LangChain ParentDocumentRetriever实现。先通过子分块进行精确检索，然后返回对应的父分块以提供完整上下文。"
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
                    'parent_separator',
                  ]}
                  label="父分块分隔符"
                  initialValue={
                    initialValues.parent_config?.parent_separator || '\\n\\n'
                  }
                  extra="正则表达式，按段落分割"
                >
                  <Input placeholder="\\n\\n" />
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
                  extra="分块大小配置，用于精确检索"
                >
                  <InputNumber
                    value={chunkTokenNum}
                    disabled
                    style={{ width: '100%' }}
                  />
                </Form.Item>

                <Form.Item
                  name={['chunking_config', 'parent_config', 'child_separator']}
                  label="子分块分隔符"
                  initialValue={
                    initialValues.parent_config?.child_separator ||
                    '[。！？.!?]'
                  }
                  extra="正则表达式，按句子分割"
                >
                  <Input placeholder="[。！？.!?]" />
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

          <Alert
            message="参数建议"
            description={
              <ul style={{ margin: 0, paddingLeft: 20 }}>
                <li>
                  <strong>长文档</strong>：父分块1536，子分块384
                </li>
                <li>
                  <strong>短文档</strong>：父分块512，子分块128
                </li>
                <li>
                  <strong>技术文档</strong>：父分块2048，子分块512
                </li>
                <li>
                  <strong>问答系统</strong>：使用父分块模式
                </li>
                <li>
                  <strong>精确搜索</strong>：使用子分块模式
                </li>
              </ul>
            }
            type="success"
            showIcon
          />
        </>
      )}
    </div>
  );
});

export default ChunkingConfig;
