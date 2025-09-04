import { useTranslate } from '@/hooks/common-hooks';
import request from '@/utils/request';
import {
  DeleteOutlined,
  PlusOutlined,
  ReloadOutlined,
  SearchOutlined,
  TeamOutlined,
  UserOutlined,
} from '@ant-design/icons';
import {
  Button,
  Card,
  Descriptions,
  Empty,
  Form,
  Input,
  Modal,
  Pagination,
  Popconfirm,
  Radio,
  Select,
  Space,
  Table,
  Tag,
  message,
} from 'antd';
import React, { useEffect, useState } from 'react';
import styles from './index.less';

const { Option } = Select;

interface TeamData {
  id: string;
  name: string;
  ownerName: string;
  memberCount: number;
  createTime: string;
  updateTime: string;
}

interface TeamMember {
  userId: number | string;
  username: string;
  role: string;
  joinTime: string;
}

interface UserData {
  id: string;
  username: string;
  email: string;
}

const TeamManagementPage = () => {
  const { t } = useTranslate('setting');
  const [loading, setLoading] = useState(false);
  const [memberLoading, setMemberLoading] = useState(false);
  const [userLoading, setUserLoading] = useState(false);

  const [teamData, setTeamData] = useState<TeamData[]>([]);
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>([]);
  const [userList, setUserList] = useState<UserData[]>([]);
  const [availableUsers, setAvailableUsers] = useState<UserData[]>([]);

  const [memberModalVisible, setMemberModalVisible] = useState(false);
  const [addMemberModalVisible, setAddMemberModalVisible] = useState(false);
  const [currentTeam, setCurrentTeam] = useState<TeamData | null>(null);
  const [selectedRowKeys, setSelectedRowKeys] = useState<string[]>([]);
  const [selectedUser, setSelectedUser] = useState<string>('');
  const [selectedRole, setSelectedRole] = useState<string>('normal');

  const [searchForm] = Form.useForm();
  const [addMemberForm] = Form.useForm();

  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: 10,
    total: 0,
  });

  useEffect(() => {
    loadTeamData();
    loadUserList();
  }, [pagination.current, pagination.pageSize]);

  const loadTeamData = async () => {
    setLoading(true);
    try {
      const values = searchForm.getFieldsValue();
      const res = await request.get('/api/knowflow/v1/teams', {
        params: {
          currentPage: pagination.current,
          size: pagination.pageSize,
          name: values.name,
          ownerName: values.ownerName,
        },
      });
      const data = res?.data?.data || {};
      setTeamData(data.list || []);
      setPagination((prev) => ({ ...prev, total: data.total || 0 }));
    } catch (error) {
      message.error('加载团队数据失败');
    } finally {
      setLoading(false);
    }
  };

  const loadUserList = async () => {
    setUserLoading(true);
    try {
      const res = await request.get('/api/knowflow/v1/users', {
        params: {
          currentPage: 1,
          size: 1000, // Get all users for selection
        },
      });
      const data = res?.data?.data || {};
      const users = (data.list || []).map((user: any) => ({
        id: user.id,
        username: user.username,
        email: user.email, // 添加邮箱字段
      }));
      setUserList(users);
    } catch (error) {
      message.error('加载用户列表失败');
    } finally {
      setUserLoading(false);
    }
  };

  const loadTeamMembers = async (teamId: string) => {
    setMemberLoading(true);
    try {
      const res = await request.get(`/api/knowflow/v1/teams/${teamId}/members`);
      const data = res?.data?.data || [];
      setTeamMembers(data);

      // 更新可添加的用户列表
      const memberUserIds = new Set(
        data.map((member: TeamMember) => member.userId),
      );
      const available = userList.filter((user) => !memberUserIds.has(user.id));
      setAvailableUsers(available);
    } catch (error) {
      message.error('加载团队成员失败');
      setTeamMembers([]);
    } finally {
      setMemberLoading(false);
    }
  };

  const handleSearch = async () => {
    const values = searchForm.getFieldsValue();
    console.log('搜索条件:', values);
    loadTeamData();
  };

  const handleReset = () => {
    searchForm.resetFields();
    loadTeamData();
  };

  const handleManageMembers = (team: TeamData) => {
    setCurrentTeam(team);
    setMemberModalVisible(true);
    loadTeamMembers(team.id);
  };

  const handleAddMember = () => {
    setSelectedUser('');
    setSelectedRole('normal');
    addMemberForm.resetFields();
    setAddMemberModalVisible(true);
  };

  const handleAddMemberSubmit = async () => {
    try {
      const values = await addMemberForm.validateFields();
      console.log('表单验证结果:', values); // 调试日志
      console.log('当前用户列表:', userList); // 调试日志
      setMemberLoading(true);
      if (currentTeam) {
        // 根据 knowflow 实现，使用邮箱查找用户
        const selectedUser = userList.find((user) => user.id === values.userId);
        console.log('选中的用户:', selectedUser); // 调试日志

        if (!selectedUser) {
          message.error('用户不存在');
          return;
        }

        if (!selectedUser.email && !selectedUser.username) {
          message.error('用户邮箱信息缺失');
          return;
        }

        // 参考 knowflow 的请求格式：通过邮箱添加用户到租户
        const requestData = {
          email: selectedUser.email || selectedUser.username, // 优先使用邮箱，后备使用用户名
        };

        console.log('实际发送的请求数据:', requestData);

        if (!requestData.email) {
          message.error('无法获取用户邮箱信息');
          return;
        }

        // 使用 knowflow 的 API 端点格式，直接传递数据
        const response = await request.post(
          `/v1/tenant/${currentTeam.id}/user`,
          {
            data: requestData,
          },
        );

        message.success('添加成员成功');
        setAddMemberModalVisible(false);
        await loadTeamMembers(currentTeam.id);
        await loadTeamData(); // Refresh team list to update member counts
      }
    } catch (error) {
      console.error('添加成员错误:', error); // 调试日志
      message.error(
        `添加团队成员失败: ${error.message || JSON.stringify(error)}`,
      );
    } finally {
      setMemberLoading(false);
    }
  };

  const handleRemoveMember = async (member: TeamMember) => {
    if (!currentTeam) return;

    setMemberLoading(true);
    try {
      await request.delete(
        `/api/knowflow/v1/teams/${currentTeam.id}/members/${member.userId}`,
      );
      message.success('移除成员成功');
      await loadTeamMembers(currentTeam.id);
      await loadTeamData(); // Refresh team list to update member counts
    } catch (error) {
      message.error('移除成员失败');
    } finally {
      setMemberLoading(false);
    }
  };

  const handleDeleteTeam = async (teamId: string) => {
    setLoading(true);
    try {
      await request.delete(`/api/knowflow/v1/teams/${teamId}`);
      message.success('删除团队成功');
      await loadTeamData();
    } catch (error) {
      message.error('删除团队失败');
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    {
      title: '团队名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string) => (
        <Space>
          <TeamOutlined />
          {text}
        </Space>
      ),
    },
    {
      title: '负责人',
      dataIndex: 'ownerName',
      key: 'ownerName',
      render: (text: string) => <Tag color="blue">{text}</Tag>,
    },
    {
      title: '成员数量',
      dataIndex: 'memberCount',
      key: 'memberCount',
      render: (count: number) => <Tag color="green">{count}人</Tag>,
    },
    {
      title: '创建时间',
      dataIndex: 'createTime',
      key: 'createTime',
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
      width: 200,
      render: (_: any, record: TeamData) => (
        <Space size="small">
          <Button
            type="link"
            size="small"
            icon={<UserOutlined />}
            onClick={() => handleManageMembers(record)}
          >
            成员管理
          </Button>
          <Popconfirm
            title="确定删除这个团队吗？"
            onConfirm={() => handleDeleteTeam(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const memberColumns = [
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
      title: '角色',
      dataIndex: 'role',
      key: 'role',
      render: (role: string) => (
        <Tag color={role === 'owner' ? 'red' : 'blue'}>
          {role === 'owner' ? '拥有者' : '普通成员'}
        </Tag>
      ),
    },
    {
      title: '加入时间',
      dataIndex: 'joinTime',
      key: 'joinTime',
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_: any, record: TeamMember) => (
        <Popconfirm
          title={`确认将 ${record.username} 从团队中移除吗？`}
          onConfirm={() => handleRemoveMember(record)}
          disabled={record.role === 'owner'}
        >
          <Button
            type="link"
            size="small"
            danger
            icon={<DeleteOutlined />}
            disabled={record.role === 'owner'}
          >
            移除
          </Button>
        </Popconfirm>
      ),
    },
  ];

  const handleTableChange = (page: number, pageSize: number) => {
    setPagination((prev) => ({ ...prev, current: page, pageSize }));
  };

  return (
    <div className={styles.teamManagementWrapper}>
      {/* 搜索区域 */}
      <Card className={styles.searchCard} size="small">
        <Form form={searchForm} layout="inline">
          <Form.Item name="name" label="团队名称">
            <Input placeholder="请输入团队名称" allowClear />
          </Form.Item>
          <Form.Item>
            <Space>
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
          </Form.Item>
        </Form>
      </Card>

      {/* 团队列表 */}
      <Card className={styles.tableCard}>
        <div className={styles.tableHeader}>
          <Space>
            <Button icon={<ReloadOutlined />} onClick={loadTeamData}>
              刷新
            </Button>
          </Space>
        </div>

        <Table
          columns={columns}
          dataSource={teamData}
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

      {/* 团队成员管理模态框 */}
      <Modal
        title={`${currentTeam?.name || ''} - 成员管理`}
        open={memberModalVisible}
        onCancel={() => setMemberModalVisible(false)}
        width={800}
        footer={[
          <Button key="close" onClick={() => setMemberModalVisible(false)}>
            关闭
          </Button>,
        ]}
      >
        {currentTeam && (
          <div>
            <Descriptions
              className={styles.teamInfo}
              column={2}
              bordered
              size="small"
            >
              <Descriptions.Item label="团队名称">
                {currentTeam.name}
              </Descriptions.Item>
              <Descriptions.Item label="负责人">
                {currentTeam.ownerName}
              </Descriptions.Item>
            </Descriptions>

            <div className={styles.memberToolbar}>
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={handleAddMember}
                disabled={availableUsers.length === 0}
              >
                添加成员
              </Button>
            </div>

            <Table
              columns={memberColumns}
              dataSource={teamMembers}
              rowKey="userId"
              loading={memberLoading}
              pagination={false}
              size="small"
              locale={{
                emptyText: <Empty description="暂无成员数据" />,
              }}
            />
          </div>
        )}
      </Modal>

      {/* 添加成员模态框 */}
      <Modal
        title="添加团队成员"
        open={addMemberModalVisible}
        onOk={handleAddMemberSubmit}
        onCancel={() => setAddMemberModalVisible(false)}
        confirmLoading={loading}
        destroyOnClose
      >
        <Form form={addMemberForm} layout="vertical">
          <Form.Item
            name="userId"
            label="选择用户"
            rules={[{ required: true, message: '请选择用户' }]}
          >
            <Select
              placeholder={
                availableUsers.length > 0
                  ? '请选择用户'
                  : '(当前无可添加的用户)'
              }
              disabled={availableUsers.length === 0}
              loading={userLoading}
            >
              {availableUsers.map((user) => (
                <Option key={user.id} value={user.id}>
                  {user.username} ({user.email || '无邮箱'})
                </Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item
            name="role"
            label="角色"
            initialValue="normal"
            rules={[{ required: true, message: '请选择角色' }]}
          >
            <Radio.Group>
              <Radio value="normal">普通成员</Radio>
            </Radio.Group>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default TeamManagementPage;
