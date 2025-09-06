import ChunkingConfig from '@/components/chunking-config';
import { DatasetConfigurationContainer } from '@/components/dataset-configuration-container';
import { useTranslate } from '@/hooks/common-hooks';
import { Divider, Form, Input, InputNumber, Slider } from 'antd';

export function DOTSConfiguration() {
  const { t } = useTranslate('knowledgeConfiguration');

  return (
    <section className="space-y-4 mb-4">
      <DatasetConfigurationContainer>
        <Form.Item
          label={t('parserName', 'Parser')}
          name={['parser_config', 'parser_engine']}
          initialValue="dots"
          hidden
        >
          <Input />
        </Form.Item>

        <Form.Item
          label={t('dotsServiceUrl', 'DOTS Service URL')}
          name={['parser_config', 'dots_service_url']}
          tooltip={t('dotsServiceUrlTip', 'The URL of your DOTS OCR service')}
        >
          <Input placeholder="http://8.134.177.47:30001" />
        </Form.Item>

        <Form.Item
          label={t('dotsModelName', 'DOTS Model Name')}
          name={['parser_config', 'dots_model_name']}
          tooltip={t(
            'dotsModelNameTip',
            'The model name to use for OCR processing',
          )}
        >
          <Input placeholder="dotsocr-model" />
        </Form.Item>

        <Form.Item
          label={t('dotsTimeout', 'Request Timeout (seconds)')}
          name={['parser_config', 'dots_timeout']}
          tooltip={t(
            'dotsTimeoutTip',
            'Maximum time to wait for OCR processing',
          )}
        >
          <InputNumber min={30} max={600} step={30} />
        </Form.Item>

        <Form.Item
          label={t('dotsTemperature', 'Temperature')}
          name={['parser_config', 'dots_temperature']}
          tooltip={t(
            'dotsTemperatureTip',
            'Controls randomness in OCR output (0.0-1.0)',
          )}
        >
          <Slider min={0} max={1} step={0.1} />
        </Form.Item>

        <Form.Item
          label={t('dotsTopP', 'Top P')}
          name={['parser_config', 'dots_top_p']}
          tooltip={t('dotsTopPTip', 'Nucleus sampling parameter (0.0-1.0)')}
        >
          <Slider min={0} max={1} step={0.1} />
        </Form.Item>

        <Form.Item
          label={t('dotsMaxTokens', 'Max Completion Tokens')}
          name={['parser_config', 'dots_max_completion_tokens']}
          tooltip={t(
            'dotsMaxTokensTip',
            'Maximum number of tokens in the response',
          )}
        >
          <InputNumber min={1024} max={32768} step={1024} />
        </Form.Item>
      </DatasetConfigurationContainer>

      <Divider></Divider>

      {/* DOTS 分块策略配置 */}
      <DatasetConfigurationContainer>
        <ChunkingConfig />
      </DatasetConfigurationContainer>
    </section>
  );
}
