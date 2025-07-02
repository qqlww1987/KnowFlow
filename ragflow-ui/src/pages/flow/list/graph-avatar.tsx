import { ReactComponent as NothingIcon } from '@/assets/svg/nothing.svg';
import { Avatar } from 'antd';

const GraphAvatar = ({ avatar }: { avatar?: string | null }) => {
  return (
    <div>
      {avatar ? (
        <Avatar size={30} icon={<NothingIcon />} src={avatar} />
      ) : (
        <NothingIcon width={30} height={30} />
      )}
    </div>
  );
};

export default GraphAvatar;
