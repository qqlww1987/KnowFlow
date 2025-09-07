import ChunkingConfig from '@/components/chunking-config';
import { DatasetConfigurationContainer } from '@/components/dataset-configuration-container';
import { useTranslate } from '@/hooks/common-hooks';
import { Form, Input } from 'antd';

export function DOTSConfiguration() {
  const { t } = useTranslate('knowledgeConfiguration');

  return (
    <section className="space-y-4 mb-4">
      <Form.Item
        label={t('parserName', 'Parser')}
        name={['parser_config', 'parser_engine']}
        initialValue="dots"
        hidden
      >
        <Input />
      </Form.Item>

      {/* DOTS 分块策略配置 */}
      <DatasetConfigurationContainer>
        <ChunkingConfig />
      </DatasetConfigurationContainer>
    </section>
  );
}
