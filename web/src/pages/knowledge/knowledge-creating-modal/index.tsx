import { IModalManagerChildrenProps } from '@/components/modal-manager';
import { Form, Input, Modal, Select } from 'antd';
import { useTranslation } from 'react-i18next';

const { Option } = Select;

type FieldType = {
  name?: string;
  parser_method?: string;
};

interface IProps extends Omit<IModalManagerChildrenProps, 'showModal'> {
  loading: boolean;
  onOk: (name: string, parserMethod?: string) => void;
}

const KnowledgeCreatingModal = ({
  visible,
  hideModal,
  loading,
  onOk,
}: IProps) => {
  const [form] = Form.useForm();

  const { t } = useTranslation('translation', { keyPrefix: 'knowledgeList' });

  const handleOk = async () => {
    const ret = await form.validateFields();

    onOk(ret.name, ret.parser_method);
  };

  return (
    <Modal
      title={t('createKnowledgeBase')}
      open={visible}
      onOk={handleOk}
      onCancel={hideModal}
      okButtonProps={{ loading }}
    >
      <Form
        name="Create"
        labelCol={{ span: 4 }}
        wrapperCol={{ span: 20 }}
        style={{ maxWidth: 600 }}
        autoComplete="off"
        form={form}
      >
        <Form.Item<FieldType>
          label={t('name')}
          name="name"
          rules={[{ required: true, message: t('namePlaceholder') }]}
        >
          <Input placeholder={t('namePlaceholder')} />
        </Form.Item>
        <Form.Item<FieldType>
          label="解析方法"
          name="parser_method"
          initialValue="mineru"
          rules={[{ required: true, message: '请选择解析方法' }]}
        >
          <Select placeholder="请选择解析方法">
            <Option value="mineru">MinerU</Option>
            <Option value="dots">DOTS</Option>
          </Select>
        </Form.Item>
      </Form>
    </Modal>
  );
};

export default KnowledgeCreatingModal;
