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
  Table,
  Tabs,
  Tag,
  message,
} from 'antd';
import React, { useEffect, useState } from 'react';

const { TabPane } = Tabs;
const { Option } = Select;

interface PermissionModalProps {
  visible: boolean;
  onCancel: () => void;
  knowledgeBaseId: string;
  knowledgeBaseName: string;
}

interface UserPermission {
  user_id: string;
  username: string;
  permission_level: string;
  granted_at?: string;
  permission_source: 'user';
}

interface TeamPermission {
  team_id: string;
  team_name: string;
  permission_level: string;
  granted_at?: string;
  permission_source: 'team';
}

interface User {
  id: string;
  username: string;
  email: string;
}

interface Team {
  id: string;
  name: string;
  memberCount?: number;
}

const PermissionModal: React.FC<PermissionModalProps> = ({
  visible,
  onCancel,
  knowledgeBaseId,
  knowledgeBaseName,
}) => {
  const [userPermissions, setUserPermissions] = useState<UserPermission[]>([]);
  const [teamPermissions, setTeamPermissions] = useState<TeamPermission[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [loading, setLoading] = useState(false);
  const [addUserForm] = Form.useForm();
  const [addTeamForm] = Form.useForm();

  // 角色级别配置（对应 RBAC 角色：read=viewer, write=editor, admin=admin）
  const permissionLevels = [
    { value: 'read', label: '查看者（viewer）', color: 'blue' },
    { value: 'write', label: '编辑者（editor）', color: 'orange' },
    { value: 'admin', label: '管理员（admin）', color: 'red' },
  ];

  // 获取角色列表
  const fetchPermissions = async () => {
    if (!knowledgeBaseId) return;

    setLoading(true);
    try {
      console.log('开始获取角色列表，知识库ID:', knowledgeBaseId);
      const result = await request.get(
        `/api/knowflow/v1/knowledgebases/${knowledgeBaseId}/permissions`,
      );

      console.log('角色API响应状态:', result.response?.status);
      console.log('角色API响应类型:', typeof result);
      console.log('角色API原始响应:', result);

      const data = result.data;
      console.log('角色API解析后数据:', data);

      if (data.code === 0) {
        console.log('角色数据解析成功');
        console.log('直接用户角色:', data.data?.user_permissions);
        console.log('团队角色:', data.data?.team_permissions);

        setUserPermissions(data.data?.user_permissions || []);
        setTeamPermissions(data.data?.team_permissions || []);
      } else {
        console.error('角色API返回错误:', data);
        message.error(`获取角色列表失败: ${data.message || '未知错误'}`);
      }
    } catch (error) {
      console.error('角色API调用异常:', error);
      message.error('获取角色列表失败');
    } finally {
      setLoading(false);
    }
  };

  // 获取可分配角色的用户列表（排除超级管理员）
  const fetchUsers = async () => {
    try {
      console.log('开始获取可分配角色的用户列表...');
      const result = await request.get('/api/knowflow/v1/users/assignable', {
        params: { currentPage: 1, size: 100 },
      });
      console.log('可分配用户API响应:', result);

      const data = result.data;
      console.log('可分配用户API数据:', data);

      if (data.code === 0) {
        console.log('可分配用户列表获取成功，数量:', data.data?.list?.length);
        setUsers(data.data?.list || []);
      } else {
        console.error('可分配用户API返回错误:', data);
      }
    } catch (error) {
      console.error('获取可分配用户列表异常:', error);
    }
  };

  // 获取团队列表
  const fetchTeams = async () => {
    try {
      console.log('开始获取团队列表...');
      const result = await request.get('/api/knowflow/v1/teams', {
        params: { currentPage: 1, size: 100 },
      });
      console.log('团队API响应:', result);

      const data = result.data;
      console.log('团队API数据:', data);

      if (data.code === 0) {
        console.log('团队列表获取成功，数量:', data.data?.list?.length);
        setTeams(data.data?.list || []);
      } else {
        console.error('团队API返回错误:', data);
      }
    } catch (error) {
      console.error('获取团队列表异常:', error);
    }
  };

  // 分配用户角色
  const handleAddUserPermission = async (values: {
    user_id: string;
    permission_level: string;
  }) => {
    try {
      console.log('分配用户角色，数据:', values);
      const result = await request.post(
        `/api/knowflow/v1/knowledgebases/${knowledgeBaseId}/permissions/users`,
        {
          data: values,
        },
      );
      console.log('用户角色分配响应:', result);

      const data = result.data;
      if (data.code === 0) {
        message.success('用户角色分配成功');
        addUserForm.resetFields();
        fetchPermissions();
      } else {
        message.error(data.message || '角色分配失败');
      }
    } catch (error) {
      console.error('分配用户角色失败:', error);
      message.error('角色分配失败');
    }
  };

  // 分配团队角色
  const handleAddTeamPermission = async (values: {
    team_id: string;
    permission_level: string;
  }) => {
    try {
      console.log('分配团队角色，数据:', values);
      const result = await request.post(
        `/api/knowflow/v1/knowledgebases/${knowledgeBaseId}/permissions/teams`,
        {
          data: values,
        },
      );
      console.log('团队角色分配响应:', result);

      const data = result.data;
      if (data.code === 0) {
        message.success('团队角色分配成功');
        addTeamForm.resetFields();
        fetchPermissions();
      } else {
        message.error(data.message || '分配团队角色失败');
      }
    } catch (error) {
      console.error('分配团队角色失败:', error);
      message.error('分配团队角色失败');
    }
  };

  // 撤销用户角色
  const handleRevokeUserPermission = async (userId: string) => {
    try {
      const result = await request.delete(
        `/api/knowflow/v1/knowledgebases/${knowledgeBaseId}/permissions/users/${userId}`,
      );
      const data = result.data;
      if (data.code === 0) {
        message.success('角色撤销成功');
        fetchPermissions();
      } else {
        message.error('角色撤销失败');
      }
    } catch (error) {
      message.error('角色撤销失败');
    }
  };

  // 撤销团队角色
  const handleRevokeTeamPermission = async (teamId: string) => {
    try {
      const result = await request.delete(
        `/api/knowflow/v1/knowledgebases/${knowledgeBaseId}/permissions/teams/${teamId}`,
      );
      const data = result.data;
      if (data.code === 0) {
        message.success('团队角色撤销成功');
        fetchPermissions();
      } else {
        message.error('团队角色撤销失败');
      }
    } catch (error) {
      message.error('团队角色撤销失败');
    }
  };

  useEffect(() => {
    if (visible) {
      fetchPermissions();
      fetchUsers();
      fetchTeams();
    }
  }, [visible, knowledgeBaseId]);

  // 用户角色表格列
  const userColumns = [
    {
      title: '用户',
      dataIndex: 'username',
      key: 'username',
      render: (text: string) => (
        <span>
          <UserOutlined /> {text}
        </span>
      ),
    },
    {
      title: '角色',
      dataIndex: 'permission_level',
      key: 'permission_level',
      render: (level: string) => {
        const config = permissionLevels.find((p) => p.value === level);
        return <Tag color={config?.color}>{config?.label}</Tag>;
      },
    },
    {
      title: '授权时间',
      dataIndex: 'granted_at',
      key: 'granted_at',
      render: (time: string) => (time ? new Date(time).toLocaleString() : '-'),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: UserPermission) => (
        <Popconfirm
          title="确定要撤销该用户的角色吗？"
          onConfirm={() => handleRevokeUserPermission(record.user_id)}
          okText="确定"
          cancelText="取消"
        >
          <Button type="link" danger size="small" icon={<DeleteOutlined />}>
            撤销
          </Button>
        </Popconfirm>
      ),
    },
  ];

  // 团队角色表格列
  const teamColumns = [
    {
      title: '团队',
      dataIndex: 'team_name',
      key: 'team_name',
      render: (text: string) => (
        <span>
          <TeamOutlined /> {text}
        </span>
      ),
    },
    {
      title: '角色',
      dataIndex: 'permission_level',
      key: 'permission_level',
      render: (level: string) => {
        const config = permissionLevels.find((p) => p.value === level);
        return <Tag color={config?.color}>{config?.label}</Tag>;
      },
    },
    {
      title: '授权时间',
      dataIndex: 'granted_at',
      key: 'granted_at',
      render: (time: string) => (time ? new Date(time).toLocaleString() : '-'),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: TeamPermission) => (
        <Popconfirm
          title="确定要撤销该团队的角色吗？"
          onConfirm={() => handleRevokeTeamPermission(record.team_id)}
          okText="确定"
          cancelText="取消"
        >
          <Button type="link" danger size="small" icon={<DeleteOutlined />}>
            撤销
          </Button>
        </Popconfirm>
      ),
    },
  ];

  return (
    <Modal
      title={`角色管理 - ${knowledgeBaseName}`}
      visible={visible}
      onCancel={onCancel}
      width={900}
      footer={null}
      destroyOnClose
    >
      <Tabs defaultActiveKey="users">
        <TabPane
          tab={
            <span>
              <UserOutlined />
              用户角色 ({userPermissions.length})
            </span>
          }
          key="users"
        >
          {/* 分配用户角色表单 */}
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
                <Select
                  placeholder="选择用户"
                  style={{ width: 200 }}
                  showSearch
                  filterOption={(input, option) => {
                    const label = option?.label || option?.children;
                    return String(label)
                      .toLowerCase()
                      .includes(input.toLowerCase());
                  }}
                >
                  {users.map((user) => (
                    <Option key={user.id} value={user.id}>
                      {user.username} ({user.email})
                    </Option>
                  ))}
                </Select>
              </Form.Item>
              <Form.Item
                name="permission_level"
                rules={[{ required: true, message: '请选择角色' }]}
              >
                <Select placeholder="选择角色" style={{ width: 120 }}>
                  {permissionLevels.map((level) => (
                    <Option key={level.value} value={level.value}>
                      {level.label}
                    </Option>
                  ))}
                </Select>
              </Form.Item>
              <Form.Item>
                <Button
                  type="primary"
                  htmlType="submit"
                  icon={<PlusOutlined />}
                >
                  分配角色
                </Button>
              </Form.Item>
            </Form>
          </div>

          {/* 用户角色列表 */}
          <Table
            columns={userColumns}
            dataSource={userPermissions}
            rowKey="user_id"
            loading={loading}
            pagination={false}
            size="small"
          />
        </TabPane>

        <TabPane
          tab={
            <span>
              <TeamOutlined />
              团队角色 ({teamPermissions.length})
            </span>
          }
          key="teams"
        >
          {/* 分配团队角色表单 */}
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
                <Select
                  placeholder="选择团队"
                  style={{ width: 200 }}
                  showSearch
                  filterOption={(input, option) => {
                    const label = option?.label || option?.children;
                    return String(label)
                      .toLowerCase()
                      .includes(input.toLowerCase());
                  }}
                >
                  {teams.map((team) => (
                    <Option key={team.id} value={team.id}>
                      {team.name}{' '}
                      {team.memberCount && `(${team.memberCount}人)`}
                    </Option>
                  ))}
                </Select>
              </Form.Item>
              <Form.Item
                name="permission_level"
                rules={[{ required: true, message: '请选择角色' }]}
              >
                <Select placeholder="选择角色" style={{ width: 120 }}>
                  {permissionLevels.map((level) => (
                    <Option key={level.value} value={level.value}>
                      {level.label}
                    </Option>
                  ))}
                </Select>
              </Form.Item>
              <Form.Item>
                <Button
                  type="primary"
                  htmlType="submit"
                  icon={<PlusOutlined />}
                >
                  分配团队角色
                </Button>
              </Form.Item>
            </Form>
          </div>

          {/* 团队角色列表 */}
          <Table
            columns={teamColumns}
            dataSource={teamPermissions}
            rowKey="team_id"
            loading={loading}
            pagination={false}
            size="small"
          />
        </TabPane>
      </Tabs>

      {/* 角色说明 */}
      <div
        style={{
          marginTop: 16,
          padding: 12,
          backgroundColor: '#f5f5f5',
          borderRadius: 4,
        }}
      >
        <h4>角色说明：</h4>
        <ul style={{ margin: 0, paddingLeft: 20 }}>
          <li>
            <Tag color="red">管理员</Tag>
            ：可以新增和删除知识库，管理知识库的所有内容和权限
          </li>
          <li>
            <Tag color="orange">编辑者</Tag>
            ：可以上传文件以及文件解析，编辑知识库内容
          </li>
          <li>
            <Tag color="blue">查看者</Tag>：可以查看知识库内的文档内容
          </li>
        </ul>
        <div style={{ marginTop: 8, fontSize: '12px', color: '#666' }}>
          <p style={{ margin: '0 0 4px 0' }}>
            <strong>角色配置说明：</strong>
          </p>
          <p style={{ margin: '0 0 4px 0' }}>
            • 角色映射：查看者→viewer，编辑者→editor，管理员→admin
          </p>
          <p style={{ margin: '0', color: '#1890ff' }}>
            • 超级管理员自动拥有所有知识库的完全权限，无需单独分配
          </p>
        </div>
      </div>
    </Modal>
  );
};

export default PermissionModal;
