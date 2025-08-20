import { useTranslate } from '@/hooks/common-hooks';
import {
  DatabaseOutlined,
  FileOutlined,
  SettingOutlined,
  TeamOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { Tabs, Typography } from 'antd';
import React from 'react';
import { Outlet, useLocation, useNavigate } from 'umi';
import styles from './index.less';

const { Title, Paragraph } = Typography;

const UserSettingManagement = () => {
  const { t } = useTranslate('setting');
  const navigate = useNavigate();
  const location = useLocation();

  const menuItems = [
    {
      key: 'user-management',
      icon: <UserOutlined />,
      label: '用户管理',
      path: '/user-setting/management/user-management',
    },
    {
      key: 'team-management',
      icon: <TeamOutlined />,
      label: '团队管理',
      path: '/user-setting/management/team-management',
    },
    {
      key: 'file-management',
      icon: <FileOutlined />,
      label: '文件管理',
      path: '/user-setting/management/file-management',
    },
    {
      key: 'knowledge-management',
      icon: <DatabaseOutlined />,
      label: '知识库管理',
      path: '/user-setting/management/knowledge-management',
    },
    {
      key: 'user-config',
      icon: <SettingOutlined />,
      label: '用户配置',
      path: '/user-setting/management/user-config',
    },
  ];

  const handleMenuClick = (path: string) => {
    navigate(path);
  };

  // 获取当前活跃的菜单项
  const getActiveKey = () => {
    const currentPath = location.pathname;
    const activeItem = menuItems.find((item) => currentPath.includes(item.key));
    return activeItem?.key || 'user-management';
  };

  // 如果是根路径，默认跳转到用户管理
  React.useEffect(() => {
    if (
      location.pathname === '/user-setting/management' ||
      location.pathname === '/user-setting/management/'
    ) {
      navigate('/user-setting/management/user-management');
    }
  }, [location.pathname, navigate]);

  const tabItems = menuItems.map((item) => ({
    key: item.key,
    label: (
      <div className={styles.tabLabel}>
        <span className={styles.tabIcon}>{item.icon}</span>
        <span>{item.label}</span>
      </div>
    ),
  }));

  const handleTabChange = (activeKey: string) => {
    const selectedItem = menuItems.find((item) => item.key === activeKey);
    if (selectedItem) {
      handleMenuClick(selectedItem.path);
    }
  };

  return (
    <div className={styles.managementWrapper}>
      <div className={styles.tabsContainer}>
        <Tabs
          activeKey={getActiveKey()}
          onChange={handleTabChange}
          items={tabItems}
          className={styles.managementTabs}
          size="large"
          tabBarStyle={{
            marginBottom: 0,
            borderBottom: '1px solid #f0f0f0',
            backgroundColor: '#fff',
          }}
        />
      </div>
      <div className={styles.managementContent}>
        <Outlet />
      </div>
    </div>
  );
};

export default UserSettingManagement;
