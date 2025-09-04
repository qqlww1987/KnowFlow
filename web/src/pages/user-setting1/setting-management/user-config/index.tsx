import { useTranslate } from '@/hooks/common-hooks';
import request from '@/utils/request';
import {
  ApiOutlined,
  DeleteOutlined,
  EditOutlined,
  ReloadOutlined,
  RobotOutlined,
  SearchOutlined,
  UserOutlined,
} from '@ant-design/icons';
import {
  Button,
  Card,
  Form,
  Input,
  Modal,
  Pagination,
  Select,
  Space,
  Table,
  Tag,
  message,
} from 'antd';
import React, { useEffect, useState } from 'react';
import styles from './index.less';

const { Option } = Select;

interface UserConfigData {
  id: string;
  username: string;
  chatModel: string;
  embeddingModel: string;
  updateTime: string;
}

const UserConfigPage = () => {
  const { t } = useTranslate('setting');
  const [loading, setLoading] = useState(false);
  const [configData, setConfigData] = useState<UserConfigData[]>([]);
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [currentConfig, setCurrentConfig] = useState<UserConfigData | null>(
    null,
  );
  const [selectedRowKeys, setSelectedRowKeys] = useState<string[]>([]);
  const [searchValue, setSearchValue] = useState('');

  const [editForm] = Form.useForm();
  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: 10,
    total: 0,
  });

  // 模拟可用的模型选项
  const chatModelOptions = [
    'gpt-4o',
    'gpt-4o-mini',
    'gpt-3.5-turbo',
    'claude-3-opus',
    'claude-3-sonnet',
    'claude-3-haiku',
    'gemini-pro',
    'gemini-1.5-pro',
  ];

  const embeddingModelOptions = [
    'text-embedding-3-large',
    'text-embedding-3-small',
    'text-embedding-ada-002',
    'sentence-transformers',
    'bge-large-zh-v1.5',
    'bge-small-zh-v1.5',
  ];

  useEffect(() => {
    loadConfigData();
  }, [pagination.current, pagination.pageSize, searchValue]);

  const loadConfigData = async () => {
    setLoading(true);
    try {
      const res = await request.get('/api/knowflow/v1/tenants', {
        params: {
          currentPage: pagination.current,
          size: pagination.pageSize,
          username: searchValue,
        },
      });
      const data = res?.data?.data || {};
      setConfigData(data.list || []);
      setPagination((prev) => ({ ...prev, total: data.total || 0 }));
    } catch (error) {
      message.error('加载用户配置数据失败');
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = () => {
    setPagination((prev) => ({ ...prev, current: 1 }));
    loadConfigData();
  };

  const handleReset = () => {
    setSearchValue('');
    setPagination((prev) => ({ ...prev, current: 1 }));
    loadConfigData();
  };

  const handleEdit = (record: UserConfigData) => {
    setCurrentConfig(record);
    editForm.setFieldsValue({
      username: record.username,
      chatModel: record.chatModel,
      embeddingModel: record.embeddingModel,
    });
    setEditModalVisible(true);
  };

  const handleEditSubmit = async () => {
    try {
      const values = await editForm.validateFields();
      setLoading(true);
      if (currentConfig) {
        await request.put(`/api/knowflow/v1/tenants/${currentConfig.id}`, {
          data: values,
        });
        message.success('修改配置成功');
        setEditModalVisible(false);
        loadConfigData();
      }
    } catch (error) {
      message.error('修改配置失败');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = () => {
    message.info('如需删除租户配置，可直接删除负责人账号');
  };

  const getModelDisplayName = (model: string): string => {
    const modelMap: { [key: string]: string } = {
      'gpt-4o': 'GPT-4o',
      'gpt-4o-mini': 'GPT-4o Mini',
      'gpt-3.5-turbo': 'GPT-3.5 Turbo',
      'claude-3-opus': 'Claude-3 Opus',
      'claude-3-sonnet': 'Claude-3 Sonnet',
      'claude-3-haiku': 'Claude-3 Haiku',
      'gemini-pro': 'Gemini Pro',
      'gemini-1.5-pro': 'Gemini 1.5 Pro',
      'text-embedding-3-large': 'Text Embedding 3 Large',
      'text-embedding-3-small': 'Text Embedding 3 Small',
      'text-embedding-ada-002': 'Ada 002',
      'sentence-transformers': 'Sentence Transformers',
      'bge-large-zh-v1.5': 'BGE Large ZH v1.5',
      'bge-small-zh-v1.5': 'BGE Small ZH v1.5',
    };
    return modelMap[model] || model;
  };

  const getModelColor = (model: string): string => {
    if (model.includes('gpt')) return 'green';
    if (model.includes('claude')) return 'blue';
    if (model.includes('gemini')) return 'purple';
    if (model.includes('embedding') || model.includes('bge')) return 'orange';
    return 'default';
  };

  const columns = [
    {
      title: '用户名',
      dataIndex: 'username',
      key: 'username',
      render: (text: string) => (
        <Space>
          <UserOutlined />
          {text}
        </Space>
      ),
    },
    {
      title: '聊天模型',
      dataIndex: 'chatModel',
      key: 'chatModel',
      width: 180,
      ellipsis: {
        showTitle: false,
      },
      render: (model: string) => (
        <Tag
          color={getModelColor(model)}
          icon={<RobotOutlined />}
          style={{ maxWidth: '160px' }}
        >
          <span
            title={getModelDisplayName(model)}
            style={{
              display: 'inline-block',
              maxWidth: '120px',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              verticalAlign: 'top',
            }}
          >
            {getModelDisplayName(model)}
          </span>
        </Tag>
      ),
    },
    {
      title: '嵌入模型',
      dataIndex: 'embeddingModel',
      key: 'embeddingModel',
      width: 180,
      ellipsis: {
        showTitle: false,
      },
      render: (model: string) => (
        <Tag
          color={getModelColor(model)}
          icon={<ApiOutlined />}
          style={{ maxWidth: '160px' }}
        >
          <span
            title={getModelDisplayName(model)}
            style={{
              display: 'inline-block',
              maxWidth: '120px',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              verticalAlign: 'top',
            }}
          >
            {getModelDisplayName(model)}
          </span>
        </Tag>
      ),
    },
    {
      title: '更新时间',
      dataIndex: 'updateTime',
      key: 'updateTime',
    },
    {
      title: '操作',
      key: 'action',
      fixed: 'right' as const,
      width: 150,
      render: (_: any, record: UserConfigData) => (
        <Space size="small">
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          >
            修改
          </Button>
          <Button
            type="link"
            size="small"
            danger
            icon={<DeleteOutlined />}
            onClick={handleDelete}
          >
            删除
          </Button>
        </Space>
      ),
    },
  ];

  const handleTableChange = (page: number, pageSize: number) => {
    setPagination((prev) => ({ ...prev, current: page, pageSize }));
  };

  return (
    <div className={styles.userConfigWrapper}>
      {/* 搜索区域 */}
      <Card className={styles.searchCard} size="small">
        <Space>
          <Input
            placeholder="请输入用户名搜索"
            value={searchValue}
            onChange={(e) => setSearchValue(e.target.value)}
            style={{ width: 250 }}
            allowClear
          />
          <Button
            type="primary"
            icon={<SearchOutlined />}
            onClick={handleSearch}
            loading={loading}
          >
            搜索
          </Button>
          <Button icon={<ReloadOutlined />} onClick={handleReset}>
            重置
          </Button>
        </Space>
      </Card>

      {/* 配置列表 */}
      <Card className={styles.tableCard}>
        <div className={styles.tableHeader}>
          <Button icon={<ReloadOutlined />} onClick={loadConfigData}>
            刷新
          </Button>
        </div>

        <Table
          columns={columns}
          dataSource={configData}
          rowKey="id"
          loading={loading}
          pagination={false}
          scroll={{ x: 1000 }}
          rowSelection={{
            selectedRowKeys,
            onChange: (selectedRowKeys: React.Key[]) =>
              setSelectedRowKeys(selectedRowKeys as string[]),
          }}
        />

        <div className={styles.paginationWrapper}>
          <Pagination
            current={pagination.current}
            pageSize={pagination.pageSize}
            total={pagination.total}
            onChange={handleTableChange}
            showSizeChanger
            showQuickJumper
            showTotal={(total, range) =>
              `第 ${range[0]}-${range[1]} 条/共 ${total} 条`
            }
          />
        </div>
      </Card>

      {/* 编辑配置模态框 */}
      <Modal
        title="修改用户配置"
        open={editModalVisible}
        onOk={handleEditSubmit}
        onCancel={() => setEditModalVisible(false)}
        confirmLoading={loading}
        destroyOnClose
        width={500}
      >
        <Form form={editForm} layout="vertical">
          <Form.Item name="username" label="用户名">
            <Input disabled />
          </Form.Item>
          <Form.Item
            name="chatModel"
            label="聊天模型"
            rules={[{ required: true, message: '请选择聊天模型' }]}
          >
            <Select
              placeholder="请选择聊天模型"
              showSearch
              filterOption={(input, option) =>
                (option?.children as unknown as string)
                  ?.toLowerCase()
                  .includes(input.toLowerCase())
              }
            >
              {chatModelOptions.map((model) => (
                <Option key={model} value={model}>
                  <Space>
                    <RobotOutlined />
                    {getModelDisplayName(model)}
                  </Space>
                </Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item
            name="embeddingModel"
            label="嵌入模型"
            rules={[{ required: true, message: '请选择嵌入模型' }]}
          >
            <Select
              placeholder="请选择嵌入模型"
              showSearch
              filterOption={(input, option) =>
                (option?.children as unknown as string)
                  ?.toLowerCase()
                  .includes(input.toLowerCase())
              }
            >
              {embeddingModelOptions.map((model) => (
                <Option key={model} value={model}>
                  <Space>
                    <ApiOutlined />
                    {getModelDisplayName(model)}
                  </Space>
                </Option>
              ))}
            </Select>
          </Form.Item>
        </Form>

        <div className={styles.formTip}>
          <p>• 聊天模型用于处理对话和文本生成任务</p>
          <p>• 嵌入模型用于文档向量化和语义搜索</p>
          <p>• 修改后将立即生效，影响该用户的所有操作</p>
        </div>
      </Modal>
    </div>
  );
};

export default UserConfigPage;
