import { useFetchUserInfo } from '@/hooks/user-setting-hooks';
import { Flex, Spin } from 'antd';
import AgentTemplateModal from './agent-template-modal';
import FlowCard from './flow-card';
import { useFetchDataOnMount, useSaveFlow } from './hooks';

import { useTranslate } from '@/hooks/common-hooks';
import styles from './index.less';

const FlowList = () => {
  const { data: userInfo } = useFetchUserInfo();
  const {
    showFlowSettingModal,
    hideFlowSettingModal,
    flowSettingVisible,
    flowSettingLoading,
    onFlowOk,
  } = useSaveFlow();
  const { t } = useTranslate('flow');

  const { list, loading } = useFetchDataOnMount();

  return (
    <Flex className={styles.flowListWrapper} vertical flex={1}>
      <div className={styles.topTitle}>Agent</div>
      <div className={styles.topWrapper}>
        <span className={styles.title}>欢迎回来, {userInfo.nickname}</span>
        <p className={styles.description}>今天我们要使用哪个Agent？</p>
      </div>
      {/* <Flex justify={'end'}>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={showFlowSettingModal}
        >
          {t('createGraph')}
        </Button>
      </Flex> */}
      <Spin spinning={loading}>
        <Flex gap={'large'} wrap="wrap" className={styles.flowCardContainer}>
          <div className={styles.addCard} onClick={showFlowSettingModal}>
            <div className={styles.addIcon}></div>
            <div className={styles.addDesc}>创建Agent</div>
          </div>
          {list.map((item) => {
            return <FlowCard item={item} key={item.id}></FlowCard>;
          })}
        </Flex>
      </Spin>
      {flowSettingVisible && (
        <AgentTemplateModal
          visible={flowSettingVisible}
          onOk={onFlowOk}
          loading={flowSettingLoading}
          hideModal={hideFlowSettingModal}
        ></AgentTemplateModal>
      )}
    </Flex>
  );
};

export default FlowList;
