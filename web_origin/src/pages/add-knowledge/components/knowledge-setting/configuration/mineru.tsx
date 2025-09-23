import {
  AutoKeywordsItem,
  AutoQuestionsItem,
} from '@/components/auto-keywords-item';
import { DatasetConfigurationContainer } from '@/components/dataset-configuration-container';
import Delimiter from '@/components/delimiter';
import ExcelToHtml from '@/components/excel-to-html';
import LayoutRecognize from '@/components/layout-recognize';
import MaxTokenNumber from '@/components/max-token-number';
import PageRank from '@/components/page-rank';
import ParseConfiguration from '@/components/parse-configuration';
import GraphRagItems from '@/components/parse-configuration/graph-rag-items';
import { useTranslate } from '@/hooks/common-hooks';
import { Divider, Form, Input } from 'antd';
import { TagItems } from '../tag-item';
import { ChunkMethodItem, EmbeddingModelItem } from './common-item';

export function MinerUConfiguration() {
  const { t } = useTranslate('knowledgeConfiguration');

  return (
    <section className="space-y-4 mb-4">
      <DatasetConfigurationContainer>
        <LayoutRecognize></LayoutRecognize>
        <EmbeddingModelItem></EmbeddingModelItem>
        <ChunkMethodItem></ChunkMethodItem>
        <MaxTokenNumber></MaxTokenNumber>
        <Delimiter></Delimiter>
      </DatasetConfigurationContainer>

      <Divider></Divider>

      {/* MinerU 解析配置 */}
      <DatasetConfigurationContainer>
        <Form.Item
          name={['parser_config', 'parse_method']}
          label="解析方法"
          tooltip="MinerU 解析方法，支持 auto、ocr、txt 等"
          initialValue="auto"
        >
          <Input placeholder="auto" />
        </Form.Item>

        <Form.Item
          name={['parser_config', 'language']}
          label="文档语言"
          tooltip="文档主要语言，支持 ch（中文）、en（英文）等"
          initialValue="ch"
        >
          <Input placeholder="ch" />
        </Form.Item>
      </DatasetConfigurationContainer>

      <Divider></Divider>

      <DatasetConfigurationContainer>
        <PageRank></PageRank>
        <AutoKeywordsItem></AutoKeywordsItem>
        <AutoQuestionsItem></AutoQuestionsItem>
        <ExcelToHtml></ExcelToHtml>
        <TagItems></TagItems>
      </DatasetConfigurationContainer>

      <Divider></Divider>

      <DatasetConfigurationContainer>
        <ParseConfiguration></ParseConfiguration>
      </DatasetConfigurationContainer>

      <Divider></Divider>

      <GraphRagItems></GraphRagItems>
    </section>
  );
}
