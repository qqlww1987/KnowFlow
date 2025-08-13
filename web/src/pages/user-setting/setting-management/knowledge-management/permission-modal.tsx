import request from '@/utils/request';
import {
  DeleteOutlined,
  PlusOutlined,
  TeamOutlined,
  UserOutlined,
} from '@ant-design/icons';
import {
  Button,
  Form,
  Modal,
  Popconfirm,
  Select,
  Space,
  Table,
  Tabs,
  Tag,
  message,
} from 'antd';
import React, { useEffect, useState } from 'react';

const { Option } = Select;
const { TabPane } = Tabs;

interface PermissionModalProps {
  visible: boolean;
  onCancel: () => void;
  knowledgeBaseId: string;
  knowledgeBaseName: string;
}

interface Permission {
  user_id: string;
  username: string;
  permission_level: 'admin' | 'write' | 'read';
  role_name: string;
  granted_at: string;
  granted_by: string;
}

interface User {
  id: string;
  username: string;
}

interface Team {
  id: string;
  name: string;
}

const PermissionModal: React.FC<PermissionModalProps> = ({
  visible,
  onCancel,
  knowledgeBaseId,
  knowledgeBaseName,
}) => {
  const [loading, setLoading] = useState(false);
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [addUserForm] = Form.useForm();
  const [addTeamForm] = Form.useForm();

  // 权限级别映射
  const permissionLevelMap = {
    admin: { text: '管理员', color: 'red' },
    write: { text: '编辑者', color: 'orange' },
    read: { text: '查看者', color: 'green' },
  };

  useEffect(() => {
    if (visible && knowledgeBaseId) {
      loadPermissions();
      loadUsers();
      loadTeams();
    }
  }, [visible, knowledgeBaseId]);

  const loadPermissions = async () => {
    setLoading(true);
    try {
      const res = await request.get(
        `/api/v1/knowledgebases/${knowledgeBaseId}/permissions`,
      );
      const data = res?.data?.data || {};
      setPermissions(data.permissions || []);
    } catch (error) {
      message.error('加载权限列表失败');
    } finally {
      setLoading(false);
    }
  };

  const loadUsers = async () => {
    try {
      const res = await request.get('/api/v1/users', {
        params: { currentPage: 1, size: 1000 },
      });
      const data = res?.data?.data || {};
      setUsers(data.list || []);
    } catch (error) {
      message.error('加载用户列表失败');
    }
  };

  const loadTeams = async () => {
    try {
      const res = await request.get('/api/v1/teams', {
        params: { currentPage: 1, size: 1000 },
      });
      const data = res?.data?.data || {};
      setTeams(data.list || []);
    } catch (error) {
      message.error('加载团队列表失败');
    }
  };

  const handleAddUserPermission = async () => {
    try {
      const values = await addUserForm.validateFields();
      await request.post(
        `/api/v1/knowledgebases/${knowledgeBaseId}/permissions/users`,
        {
          data: values,
        },
      );
      message.success('权限授予成功');
      addUserForm.resetFields();
      loadPermissions();
    } catch (error) {
      message.error('权限授予失败');
    }
  };

  const handleAddTeamPermission = async () => {
    try {
      const values = await addTeamForm.validateFields();
      await request.post(
        `/api/v1/knowledgebases/${knowledgeBaseId}/permissions/teams`,
        {
          data: values,
        },
      );
      message.success('团队权限授予成功');
      addTeamForm.resetFields();
      loadPermissions();
    } catch (error) {
      message.error('团队权限授予失败');
    }
  };

  const handleRevokeUserPermission = async (userId: string) => {
    try {
      await request.delete(
        `/api/v1/knowledgebases/${knowledgeBaseId}/permissions/users/${userId}`,
      );
      message.success('权限撤销成功');
      loadPermissions();
    } catch (error) {
      message.error('权限撤销失败');
    }
  };

  const userColumns = [
    {
      title: '用户',
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
      title: '权限级别',
      dataIndex: 'permission_level',
      key: 'permission_level',
      render: (level: 'admin' | 'write' | 'read') => {
        const config = permissionLevelMap[level];
        return <Tag color={config.color}>{config.text}</Tag>;
      },
    },
    {
      title: '授予时间',
      dataIndex: 'granted_at',
      key: 'granted_at',
    },
    {
      title: '授予人',
      dataIndex: 'granted_by',
      key: 'granted_by',
    },
    {
      title: '操作',
      key: 'action',
      render: (_, record: Permission) => (
        <Popconfirm
          title="确定要撤销该用户的权限吗？"
          onConfirm={() => handleRevokeUserPermission(record.user_id)}
          okText="确定"
          cancelText="取消"
        >
          <Button type="text" danger icon={<DeleteOutlined />} size="small">
            撤销
          </Button>
        </Popconfirm>
      ),
    },
  ];

  return (
    <Modal
      title={`权限管理 - ${knowledgeBaseName}`}
      visible={visible}
      onCancel={onCancel}
      width={800}
      footer={null}
    >
      <Tabs defaultActiveKey="users">
        <TabPane tab="用户权限" key="users">
          <div style={{ marginBottom: 16 }}>
            <Form
              form={addUserForm}
              layout="inline"
              onFinish={handleAddUserPermission}
            >
              <Form.Item
                name="user_id"
                rules={[{ required: true, message: '请选择用户' }]}
              >
                <Select placeholder="选择用户" style={{ width: 200 }}>
                  {users
                    .filter(
                      (user) => !permissions.some((p) => p.user_id === user.id),
                    )
                    .map((user) => (
                      <Option key={user.id} value={user.id}>
                        {user.username}
                      </Option>
                    ))}
                </Select>
              </Form.Item>
              <Form.Item
                name="permission_level"
                rules={[{ required: true, message: '请选择权限级别' }]}
              >
                <Select placeholder="选择权限级别" style={{ width: 150 }}>
                  <Option value="admin">管理员</Option>
                  <Option value="write">编辑者</Option>
                  <Option value="read">查看者</Option>
                </Select>
              </Form.Item>
              <Form.Item>
                <Button
                  type="primary"
                  htmlType="submit"
                  icon={<PlusOutlined />}
                >
                  添加权限
                </Button>
              </Form.Item>
            </Form>
          </div>

          <Table
            columns={userColumns}
            dataSource={permissions}
            rowKey="user_id"
            loading={loading}
            pagination={false}
            size="small"
          />
        </TabPane>

        <TabPane tab="团队权限" key="teams">
          <div style={{ marginBottom: 16 }}>
            <Form
              form={addTeamForm}
              layout="inline"
              onFinish={handleAddTeamPermission}
            >
              <Form.Item
                name="team_id"
                rules={[{ required: true, message: '请选择团队' }]}
              >
                <Select placeholder="选择团队" style={{ width: 200 }}>
                  {teams.map((team) => (
                    <Option key={team.id} value={team.id}>
                      {team.name}
                    </Option>
                  ))}
                </Select>
              </Form.Item>
              <Form.Item
                name="permission_level"
                rules={[{ required: true, message: '请选择权限级别' }]}
              >
                <Select placeholder="选择权限级别" style={{ width: 150 }}>
                  <Option value="admin">管理员</Option>
                  <Option value="write">编辑者</Option>
                  <Option value="read">查看者</Option>
                </Select>
              </Form.Item>
              <Form.Item>
                <Button
                  type="primary"
                  htmlType="submit"
                  icon={<PlusOutlined />}
                >
                  添加团队权限
                </Button>
              </Form.Item>
            </Form>
          </div>

          <div style={{ padding: 20, textAlign: 'center', color: '#999' }}>
            <TeamOutlined style={{ fontSize: 24, marginBottom: 8 }} />
            <div>团队权限管理功能开发中...</div>
            <div style={{ fontSize: 12, marginTop: 4 }}>
              将为团队中的所有成员授予相应权限
            </div>
          </div>
        </TabPane>
      </Tabs>

      <div
        style={{
          marginTop: 16,
          padding: 16,
          backgroundColor: '#f5f5f5',
          borderRadius: 4,
        }}
      >
        <h4 style={{ margin: '0 0 8px 0' }}>权限说明：</h4>
        <ul style={{ margin: 0, paddingLeft: 20 }}>
          <li>
            <Tag color="red">管理员</Tag>：可以新增和删除知识库，管理权限
          </li>
          <li>
            <Tag color="orange">编辑者</Tag>：可以上传文件以及文件解析，编辑内容
          </li>
          <li>
            <Tag color="green">查看者</Tag>：可以查看知识库内的文档内容
          </li>
        </ul>
      </div>
    </Modal>
  );
};

export default PermissionModal;
