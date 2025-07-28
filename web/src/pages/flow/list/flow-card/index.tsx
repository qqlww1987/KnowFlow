import { formatDate } from '@/utils/date';
import { Card } from 'antd';
import { useNavigate } from 'umi';

import OperateDropdown from '@/components/operate-dropdown';
import { useDeleteFlow } from '@/hooks/flow-hooks';
import { IFlow } from '@/interfaces/database/flow';
import { useCallback } from 'react';
import GraphAvatar from '../graph-avatar';
import styles from './index.less';

interface IProps {
  item: IFlow;
}

const FlowCard = ({ item }: IProps) => {
  const navigate = useNavigate();
  const { deleteFlow } = useDeleteFlow();

  const removeFlow = useCallback(() => {
    return deleteFlow([item.id]);
  }, [deleteFlow, item]);

  const handleCardClick = () => {
    navigate(`/flow/${item.id}`);
  };

  return (
    <Card className={styles.card} onClick={handleCardClick}>
      <div className={styles.container}>
        <div className={styles.content}>
          <div className={styles.headContent}>
            <GraphAvatar avatar={item.avatar}></GraphAvatar>
            <span className={styles.name}>{item.title}</span>
          </div>
          <OperateDropdown deleteItem={removeFlow}></OperateDropdown>
        </div>
        <div className={styles.titleWrapper}>
          {/* <Typography.Title
            className={styles.title}
            ellipsis={{ tooltip: item.title }}
          >
            {item.title}
          </Typography.Title> */}
          <p>{item.description}</p>
        </div>
        <div className={styles.footer}>
          <div className={styles.bottom}>
            <div className={styles.bottomLeft}>
              <span className={styles.leftIconDate}></span>
              {/* <CalendarOutlined className={styles.leftIcon} /> */}
              <span className={styles.rightText}>
                {formatDate(item.update_time)}
              </span>
            </div>
          </div>
        </div>
      </div>
    </Card>
  );
};

export default FlowCard;
