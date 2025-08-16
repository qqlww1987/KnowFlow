import React, { useState, useEffect } from 'react';
import {
  Card,
  Table,
  Button,
  Space,
  Modal,
  Form,
  Input,
  Select,
  message,
  Popconfirm,
  Tag,
  Avatar,
  Tooltip,
  Row,
  Col,
  Divider
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  UserOutlined,
  KeyOutlined,
  TeamOutlined,
  SettingOutlined
} from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import api from '@/utils/api';

const { Option } = Select;
const { TextArea } = Input;

interface User {
  id: string;
  username: string;
  email: string;
  full_name?: string;
  status: string;
  created_at: string;
  updated_at: string;
  roles?: string[];
  teams?: string[];
}

interface Role {
  id: string;
  name: string;
  code: string;
  description?: string;
}

interface Team {
  id: string;
  name: string;
  description?: string;
}

const UserManagement: React.FC = () => {
  const { t } = useTranslation();
  const [users, setUsers] = useState<User[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [roleModalVisible, setRoleModalVisible] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [form] = Form.useForm();
  const [roleForm] = Form.useForm();
  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: 10,
    total: 0
  });

  // 获取用户列表
  const fetchUsers = async (page = 1, pageSize = 10) => {
    try {
      setLoading(true);
      const response = await api.get('/api/v1/users', {
        params: {
          page,
          page_size: pageSize
        }
      });
      if (response.data.success) {
        setUsers(response.data.data.users);
        setPagination({
          current: page,
          pageSize,
          total: response.data.data.total
        });
      } else {
        message.error(response.data.message || '获取用户列表失败');
      }
    } catch (error) {
      message.error('获取用户列表失败');
    } finally {
      setLoading(false);
    }
  };

  // 获取角色列表
  const fetchRoles = async () => {
    try {
      const response = await api.get('/api/v1/rbac/roles');
      if (response.data.success) {
        setRoles(response.data.data);
      }
    } catch (error) {
      console.error('获取角色列表失败:', error);
    }
  };

  // 获取团队列表
  const fetchTeams = async () => {
    try {
      const response = await api.get('/api/v1/teams');
      if (response.data.success) {
        setTeams(response.data.data.teams);
      }
    } catch (error) {
      console.error('获取团队列表失败:', error);
    }
  };

  // 创建或更新用户
  const handleSubmit = async (values: any) => {
    try {
      setLoading(true);
      let response;
      if (editingUser) {
        response = await api.put(`/api/v1/users/${editingUser.id}`, values);
      } else {
        response = await api.post('/api/v1/users', values);
      }
      
      if (response.data.success) {
        message.success(editingUser ? '用户更新成功' : '用户创建成功');
        setModalVisible(false);
        form.resetFields();
        setEditingUser(null);
        fetchUsers(pagination.current, pagination.pageSize);
      } else {
        message.error(response.data.message || '操作失败');
      }
    } catch (error) {
      message.error('操作失败');
    } finally {
      setLoading(false);
    }
  };

  // 删除用户
  const handleDelete = async (userId: string) => {
    try {
      const response = await api.delete(`/api/v1/users/${userId}`);
      if (response.data.success) {
        message.success('用户删除成功');
        fetchUsers(pagination.current, pagination.pageSize);
      } else {
        message.error(response.data.message || '删除失败');
      }
    } catch (error) {
      message.error('删除失败');
    }
  };

  // 分配角色
  const handleAssignRoles = async (values: any) => {
    if (!selectedUser) return;
    
    try {
      setLoading(true);
      const response = await api.post(`/api/v1/users/${selectedUser.id}/roles`, {
        role_codes: values.roles
      });
      
      if (response.data.success) {
        message.success('角色分配成功');
        setRoleModalVisible(false);
        roleForm.resetFields();
        setSelectedUser(null);
        fetchUsers(pagination.current, pagination.pageSize);
      } else {
        message.error(response.data.message || '角色分配失败');
      }
    } catch (error) {
      message.error('角色分配失败');
    } finally {
      setLoading(false);
    }
  };

  // 获取用户角色
  const getUserRoles = async (userId: string) => {
    try {
      const response = await api.get(`/api/v1/users/${userId}/roles`);
      if (response.data.success) {
        return response.data.data.map((role: any) => role.code);
      }
    } catch (error) {
      console.error('获取用户角色失败:', error);
    }
    return [];
  };

  // 打开角色分配模态框
  const openRoleModal = async (user: User) => {
    setSelectedUser(user);
    const userRoles = await getUserRoles(user.id);
    roleForm.setFieldsValue({ roles: userRoles });
    setRoleModalVisible(true);
  };

  // 打开编辑模态框
  const openEditModal = (user: User) => {
    setEditingUser(user);
    form.setFieldsValue({
      username: user.username,
      email: user.email,
      full_name: user.full_name,
      status: user.status
    });
    setModalVisible(true);
  };

  // 打开新建模态框
  const openCreateModal = () => {
    setEditingUser(null);
    form.resetFields();
    setModalVisible(true);
  };

  useEffect(() => {
    fetchUsers();
    fetchRoles();
    fetchTeams();
  }, []);

  const columns = [
    {
      title: '用户',
      dataIndex: 'username',
      key: 'username',
      render: (text: string, record: User) => (
        <Space>
          <Avatar icon={<UserOutlined />} />
          <div>
            <div style={{ fontWeight: 'bold' }}>{text}</div>
            <div style={{ fontSize: '12px', color: '#666' }}>
              {record.full_name || record.email}
            </div>
          </div>
        </Space>
      )
    },
    {
      title: '邮箱',
      dataIndex: 'email',
      key: 'email'
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => (
        <Tag color={status === 'active' ? 'green' : 'red'}>
          {status === 'active' ? '活跃' : '禁用'}
        </Tag>
      )
    },
    {
      title: '角色',
      dataIndex: 'roles',
      key: 'roles',
      render: (roles: string[]) => (
        <Space wrap>
          {roles?.map(role => (
            <Tag key={role} color="blue">{role}</Tag>
          )) || '-'}
        </Space>
      )
    },
    {
      title: '团队',
      dataIndex: 'teams',
      key: 'teams',
      render: (teams: string[]) => (
        <Space wrap>
          {teams?.map(team => (
            <Tag key={team} color="orange">{team}</Tag>
          )) || '-'}
        </Space>
      )
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date: string) => new Date(date).toLocaleString()
    },
    {
      title: '操作',
      key: 'action',
      render: (_, record: User) => (
        <Space>
          <Tooltip title="编辑用户">
            <Button 
              type="text" 
              icon={<EditOutlined />} 
              onClick={() => openEditModal(record)}
            />
          </Tooltip>
          <Tooltip title="分配角色">
            <Button 
              type="text" 
              icon={<KeyOutlined />} 
              onClick={() => openRoleModal(record)}
            />
          </Tooltip>
          <Popconfirm
            title="确定要删除这个用户吗？"
            onConfirm={() => handleDelete(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Tooltip title="删除用户">
              <Button 
                type="text" 
                danger 
                icon={<DeleteOutlined />}
              />
            </Tooltip>
          </Popconfirm>
        </Space>
      )
    }
  ];

  return (
    <div style={{ padding: '24px' }}>
      <Card 
        title="用户管理" 
        extra={
          <Button 
            type="primary" 
            icon={<PlusOutlined />} 
            onClick={openCreateModal}
          >
            新建用户
          </Button>
        }
      >
        <Table
          columns={columns}
          dataSource={users}
          rowKey="id"
          loading={loading}
          pagination={{
            ...pagination,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total, range) => 
              `第 ${range[0]}-${range[1]} 条，共 ${total} 条`,
            onChange: (page, pageSize) => {
              fetchUsers(page, pageSize);
            }
          }}
        />
      </Card>

      {/* 用户创建/编辑模态框 */}
      <Modal
        title={editingUser ? '编辑用户' : '新建用户'}
        open={modalVisible}
        onCancel={() => {
          setModalVisible(false);
          form.resetFields();
          setEditingUser(null);
        }}
        footer={null}
        width={600}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
        >
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="username"
                label="用户名"
                rules={[
                  { required: true, message: '请输入用户名' },
                  { min: 3, message: '用户名至少3个字符' }
                ]}
              >
                <Input placeholder="输入用户名" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="email"
                label="邮箱"
                rules={[
                  { required: true, message: '请输入邮箱' },
                  { type: 'email', message: '请输入有效的邮箱地址' }
                ]}
              >
                <Input placeholder="输入邮箱" />
              </Form.Item>
            </Col>
          </Row>
          
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="full_name"
                label="全名"
              >
                <Input placeholder="输入全名" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="status"
                label="状态"
                initialValue="active"
              >
                <Select>
                  <Option value="active">活跃</Option>
                  <Option value="inactive">禁用</Option>
                </Select>
              </Form.Item>
            </Col>
          </Row>

          {!editingUser && (
            <Form.Item
              name="password"
              label="密码"
              rules={[
                { required: true, message: '请输入密码' },
                { min: 6, message: '密码至少6个字符' }
              ]}
            >
              <Input.Password placeholder="输入密码" />
            </Form.Item>
          )}

          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={loading}>
                {editingUser ? '更新' : '创建'}
              </Button>
              <Button onClick={() => {
                setModalVisible(false);
                form.resetFields();
                setEditingUser(null);
              }}>
                取消
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 角色分配模态框 */}
      <Modal
        title={`为 ${selectedUser?.username} 分配角色`}
        open={roleModalVisible}
        onCancel={() => {
          setRoleModalVisible(false);
          roleForm.resetFields();
          setSelectedUser(null);
        }}
        footer={null}
        width={500}
      >
        <Form
          form={roleForm}
          layout="vertical"
          onFinish={handleAssignRoles}
        >
          <Form.Item
            name="roles"
            label="选择角色"
            rules={[{ required: true, message: '请选择至少一个角色' }]}
          >
            <Select
              mode="multiple"
              placeholder="选择角色"
              optionFilterProp="children"
            >
              {roles.map(role => (
                <Option key={role.code} value={role.code}>
                  <Space>
                    <Tag color="blue">{role.name}</Tag>
                    <span>{role.description}</span>
                  </Space>
                </Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={loading}>
                分配角色
              </Button>
              <Button onClick={() => {
                setRoleModalVisible(false);
                roleForm.resetFields();
                setSelectedUser(null);
              }}>
                取消
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default UserManagement;