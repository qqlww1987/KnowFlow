import React, { useState, useEffect } from 'react';
import {
  Card,
  Button,
  Table,
  Space,
  message,
  Modal,
  Form,
  Select,
  Input,
  Statistic,
  Row,
  Col,
  Tag,
  Descriptions,
  Popconfirm,
  Tooltip
} from 'antd';
import {
  ReloadOutlined,
  DeleteOutlined,
  EyeOutlined,
  CompareArrowsOutlined,
  InfoCircleOutlined
} from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import api from '@/utils/api';

const { Option } = Select;

interface CacheStats {
  total_entries: number;
  hit_count: number;
  miss_count: number;
  hit_rate: number;
  expired_entries: number;
  memory_usage: string;
}

interface PermissionResult {
  has_permission: boolean;
  permission_level?: string;
  source: string;
  direct_roles: string[];
  team_roles: string[];
  effective_roles: string[];
  reason: string;
  cached?: boolean;
}

interface UserPermission {
  [key: string]: PermissionResult;
}

const PermissionManagement: React.FC = () => {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);
  const [cacheStats, setCacheStats] = useState<CacheStats | null>(null);
  const [permissionCheckForm] = Form.useForm();
  const [userPermissionForm] = Form.useForm();
  const [compareForm] = Form.useForm();
  const [permissionResult, setPermissionResult] = useState<PermissionResult | null>(null);
  const [userPermissions, setUserPermissions] = useState<UserPermission | null>(null);
  const [compareResult, setCompareResult] = useState<any>(null);
  const [checkModalVisible, setCheckModalVisible] = useState(false);
  const [userPermissionModalVisible, setUserPermissionModalVisible] = useState(false);
  const [compareModalVisible, setCompareModalVisible] = useState(false);

  // 获取缓存统计信息
  const fetchCacheStats = async () => {
    try {
      setLoading(true);
      const response = await api.get('/api/permissions/cache/stats');
      if (response.data.success) {
        setCacheStats(response.data.data);
      } else {
        message.error(response.data.message || '获取缓存统计失败');
      }
    } catch (error) {
      message.error('获取缓存统计失败');
    } finally {
      setLoading(false);
    }
  };

  // 清理过期缓存
  const cleanupCache = async () => {
    try {
      setLoading(true);
      const response = await api.post('/api/permissions/cache/cleanup');
      if (response.data.success) {
        message.success(response.data.message);
        fetchCacheStats();
      } else {
        message.error(response.data.message || '清理缓存失败');
      }
    } catch (error) {
      message.error('清理缓存失败');
    } finally {
      setLoading(false);
    }
  };

  // 使用户缓存失效
  const invalidateUserCache = async (userId: string) => {
    try {
      const response = await api.delete(`/api/permissions/cache/invalidate/user/${userId}`);
      if (response.data.success) {
        message.success(response.data.message);
        fetchCacheStats();
      } else {
        message.error(response.data.message || '使缓存失效失败');
      }
    } catch (error) {
      message.error('使缓存失效失败');
    }
  };

  // 使资源缓存失效
  const invalidateResourceCache = async (resourceType: string, resourceId: string) => {
    try {
      const response = await api.delete('/api/permissions/cache/invalidate/resource', {
        data: {
          resource_type: resourceType,
          resource_id: resourceId
        }
      });
      if (response.data.success) {
        message.success(response.data.message);
        fetchCacheStats();
      } else {
        message.error(response.data.message || '使缓存失效失败');
      }
    } catch (error) {
      message.error('使缓存失效失败');
    }
  };

  // 使团队缓存失效
  const invalidateTeamCache = async (teamId: string) => {
    try {
      const response = await api.delete(`/api/permissions/cache/invalidate/team/${teamId}`);
      if (response.data.success) {
        message.success(response.data.message);
        fetchCacheStats();
      } else {
        message.error(response.data.message || '使缓存失效失败');
      }
    } catch (error) {
      message.error('使缓存失效失败');
    }
  };

  // 检查权限
  const checkPermission = async (values: any) => {
    try {
      setLoading(true);
      const response = await api.post('/api/permissions/check', values);
      if (response.data.success) {
        setPermissionResult(response.data.data);
      } else {
        message.error(response.data.message || '权限检查失败');
      }
    } catch (error) {
      message.error('权限检查失败');
    } finally {
      setLoading(false);
    }
  };

  // 获取用户有效权限
  const getUserEffectivePermissions = async (values: any) => {
    try {
      setLoading(true);
      const { user_id, ...params } = values;
      const response = await api.get(`/api/permissions/user/${user_id}/effective`, {
        params
      });
      if (response.data.success) {
        setUserPermissions(response.data.data);
      } else {
        message.error(response.data.message || '获取用户权限失败');
      }
    } catch (error) {
      message.error('获取用户权限失败');
    } finally {
      setLoading(false);
    }
  };

  // 比较用户权限
  const compareUserPermissions = async (values: any) => {
    try {
      setLoading(true);
      const response = await api.post('/api/permissions/compare', values);
      if (response.data.success) {
        setCompareResult(response.data.data);
      } else {
        message.error(response.data.message || '权限比较失败');
      }
    } catch (error) {
      message.error('权限比较失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCacheStats();
  }, []);

  const renderPermissionResult = (result: PermissionResult) => {
    return (
      <Descriptions column={1} bordered size="small">
        <Descriptions.Item label="权限状态">
          <Tag color={result.has_permission ? 'green' : 'red'}>
            {result.has_permission ? '有权限' : '无权限'}
          </Tag>
          {result.cached && <Tag color="blue">缓存</Tag>}
        </Descriptions.Item>
        {result.permission_level && (
          <Descriptions.Item label="权限级别">
            <Tag color="purple">{result.permission_level}</Tag>
          </Descriptions.Item>
        )}
        <Descriptions.Item label="权限来源">
          {result.source}
        </Descriptions.Item>
        <Descriptions.Item label="直接角色">
          {result.direct_roles.map(role => (
            <Tag key={role} color="blue">{role}</Tag>
          ))}
        </Descriptions.Item>
        <Descriptions.Item label="团队角色">
          {result.team_roles.map(role => (
            <Tag key={role} color="orange">{role}</Tag>
          ))}
        </Descriptions.Item>
        <Descriptions.Item label="有效角色">
          {result.effective_roles.map(role => (
            <Tag key={role} color="green">{role}</Tag>
          ))}
        </Descriptions.Item>
        <Descriptions.Item label="原因">
          {result.reason}
        </Descriptions.Item>
      </Descriptions>
    );
  };

  return (
    <div style={{ padding: '24px' }}>
      <Card title="权限管理" style={{ marginBottom: '24px' }}>
        {/* 缓存统计 */}
        <Card title="缓存统计" style={{ marginBottom: '24px' }}>
          {cacheStats && (
            <Row gutter={16}>
              <Col span={4}>
                <Statistic title="总条目" value={cacheStats.total_entries} />
              </Col>
              <Col span={4}>
                <Statistic title="命中次数" value={cacheStats.hit_count} />
              </Col>
              <Col span={4}>
                <Statistic title="未命中次数" value={cacheStats.miss_count} />
              </Col>
              <Col span={4}>
                <Statistic 
                  title="命中率" 
                  value={cacheStats.hit_rate} 
                  precision={2}
                  suffix="%"
                />
              </Col>
              <Col span={4}>
                <Statistic title="过期条目" value={cacheStats.expired_entries} />
              </Col>
              <Col span={4}>
                <Statistic title="内存使用" value={cacheStats.memory_usage} />
              </Col>
            </Row>
          )}
          <div style={{ marginTop: '16px' }}>
            <Space>
              <Button 
                icon={<ReloadOutlined />} 
                onClick={fetchCacheStats}
                loading={loading}
              >
                刷新统计
              </Button>
              <Popconfirm
                title="确定要清理过期缓存吗？"
                onConfirm={cleanupCache}
                okText="确定"
                cancelText="取消"
              >
                <Button 
                  icon={<DeleteOutlined />}
                  loading={loading}
                >
                  清理过期缓存
                </Button>
              </Popconfirm>
            </Space>
          </div>
        </Card>

        {/* 权限操作 */}
        <Card title="权限操作">
          <Space wrap>
            <Button 
              type="primary"
              icon={<EyeOutlined />}
              onClick={() => setCheckModalVisible(true)}
            >
              检查权限
            </Button>
            <Button 
              icon={<InfoCircleOutlined />}
              onClick={() => setUserPermissionModalVisible(true)}
            >
              查看用户权限
            </Button>
            <Button 
              icon={<CompareArrowsOutlined />}
              onClick={() => setCompareModalVisible(true)}
            >
              比较用户权限
            </Button>
          </Space>
        </Card>
      </Card>

      {/* 权限检查模态框 */}
      <Modal
        title="权限检查"
        open={checkModalVisible}
        onCancel={() => {
          setCheckModalVisible(false);
          setPermissionResult(null);
          permissionCheckForm.resetFields();
        }}
        footer={null}
        width={800}
      >
        <Form
          form={permissionCheckForm}
          layout="vertical"
          onFinish={checkPermission}
        >
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="resource_type"
                label="资源类型"
                rules={[{ required: true, message: '请选择资源类型' }]}
              >
                <Select placeholder="选择资源类型">
                  <Option value="KNOWLEDGEBASE">知识库</Option>
                  <Option value="DOCUMENT">文档</Option>
                  <Option value="TEAM">团队</Option>
                  <Option value="SYSTEM">系统</Option>
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="resource_id"
                label="资源ID"
                rules={[{ required: true, message: '请输入资源ID' }]}
              >
                <Input placeholder="输入资源ID" />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="permission_type"
                label="权限类型"
                rules={[{ required: true, message: '请选择权限类型' }]}
              >
                <Select placeholder="选择权限类型">
                  <Option value="read">读取权限</Option>
                  <Option value="write">写入权限</Option>
                  <Option value="delete">删除权限</Option>
                  <Option value="admin">管理权限</Option>
                  <Option value="share">分享权限</Option>
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="tenant_id"
                label="租户ID"
              >
                <Input placeholder="输入租户ID（可选）" />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={loading}>
                检查权限
              </Button>
              <Button onClick={() => permissionCheckForm.resetFields()}>
                重置
              </Button>
            </Space>
          </Form.Item>
        </Form>

        {permissionResult && (
          <div style={{ marginTop: '24px' }}>
            <h4>权限检查结果：</h4>
            {renderPermissionResult(permissionResult)}
          </div>
        )}
      </Modal>

      {/* 用户权限查看模态框 */}
      <Modal
        title="用户权限查看"
        open={userPermissionModalVisible}
        onCancel={() => {
          setUserPermissionModalVisible(false);
          setUserPermissions(null);
          userPermissionForm.resetFields();
        }}
        footer={null}
        width={1000}
      >
        <Form
          form={userPermissionForm}
          layout="vertical"
          onFinish={getUserEffectivePermissions}
        >
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item
                name="user_id"
                label="用户ID"
                rules={[{ required: true, message: '请输入用户ID' }]}
              >
                <Input placeholder="输入用户ID" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item
                name="resource_type"
                label="资源类型"
                rules={[{ required: true, message: '请选择资源类型' }]}
              >
                <Select placeholder="选择资源类型">
                  <Option value="KNOWLEDGEBASE">知识库</Option>
                  <Option value="DOCUMENT">文档</Option>
                  <Option value="TEAM">团队</Option>
                  <Option value="SYSTEM">系统</Option>
                </Select>
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item
                name="resource_id"
                label="资源ID"
                rules={[{ required: true, message: '请输入资源ID' }]}
              >
                <Input placeholder="输入资源ID" />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={loading}>
                查看权限
              </Button>
              <Button onClick={() => userPermissionForm.resetFields()}>
                重置
              </Button>
            </Space>
          </Form.Item>
        </Form>

        {userPermissions && (
          <div style={{ marginTop: '24px' }}>
            <h4>用户有效权限：</h4>
            {Object.entries(userPermissions).map(([permName, result]) => (
              <Card key={permName} size="small" style={{ marginBottom: '8px' }}>
                <h5>{permName}</h5>
                {renderPermissionResult(result)}
              </Card>
            ))}
          </div>
        )}
      </Modal>

      {/* 权限比较模态框 */}
      <Modal
        title="用户权限比较"
        open={compareModalVisible}
        onCancel={() => {
          setCompareModalVisible(false);
          setCompareResult(null);
          compareForm.resetFields();
        }}
        footer={null}
        width={1000}
      >
        <Form
          form={compareForm}
          layout="vertical"
          onFinish={compareUserPermissions}
        >
          <Row gutter={16}>
            <Col span={6}>
              <Form.Item
                name="user1_id"
                label="用户1 ID"
                rules={[{ required: true, message: '请输入用户1 ID' }]}
              >
                <Input placeholder="输入用户1 ID" />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item
                name="user2_id"
                label="用户2 ID"
                rules={[{ required: true, message: '请输入用户2 ID' }]}
              >
                <Input placeholder="输入用户2 ID" />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item
                name="resource_type"
                label="资源类型"
                rules={[{ required: true, message: '请选择资源类型' }]}
              >
                <Select placeholder="选择资源类型">
                  <Option value="KNOWLEDGEBASE">知识库</Option>
                  <Option value="DOCUMENT">文档</Option>
                  <Option value="TEAM">团队</Option>
                  <Option value="SYSTEM">系统</Option>
                </Select>
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item
                name="resource_id"
                label="资源ID"
                rules={[{ required: true, message: '请输入资源ID' }]}
              >
                <Input placeholder="输入资源ID" />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={loading}>
                比较权限
              </Button>
              <Button onClick={() => compareForm.resetFields()}>
                重置
              </Button>
            </Space>
          </Form.Item>
        </Form>

        {compareResult && (
          <div style={{ marginTop: '24px' }}>
            <h4>权限比较结果：</h4>
            <pre style={{ background: '#f5f5f5', padding: '16px', borderRadius: '4px' }}>
              {JSON.stringify(compareResult, null, 2)}
            </pre>
          </div>
        )}
      </Modal>
    </div>
  );
};

export default PermissionManagement;