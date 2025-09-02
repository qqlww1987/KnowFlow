import {
  AutoKeywordsItem,
  AutoQuestionsItem,
} from '@/components/auto-keywords-item';
import ChunkingConfig from '@/components/chunking-config';
import { DatasetConfigurationContainer } from '@/components/dataset-configuration-container';
import Delimiter from '@/components/delimiter';
import ExcelToHtml from '@/components/excel-to-html';
import LayoutRecognize from '@/components/layout-recognize';
import MaxTokenNumber from '@/components/max-token-number';
import PageRank from '@/components/page-rank';
import ParseConfiguration from '@/components/parse-configuration';
import GraphRagItems from '@/components/parse-configuration/graph-rag-items';
import { useTranslate } from '@/hooks/common-hooks';
import { Divider } from 'antd';
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

      {/* MinerU 分块策略配置 */}
      <DatasetConfigurationContainer>
        <ChunkingConfig />
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
