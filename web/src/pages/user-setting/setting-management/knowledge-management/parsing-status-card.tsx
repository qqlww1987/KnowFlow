import { Popover, Tag } from 'antd';
import reactStringReplace from 'react-string-replace';

interface DocumentData {
  id: string;
  name: string;
  chunk_num: number;
  progress: number;
  status: string;
  create_date: string;
  logs?: LogItem[];
}

interface LogItem {
  time: string;
  message: string;
}

interface IProps {
  record: DocumentData;
  isBatchParsing?: boolean;
  currentBatchDocument?: string | null;
}

enum RunningStatus {
  UNSTART = '0',
  RUNNING = '1',
  CANCEL = '2',
  DONE = '3',
  FAIL = '4',
}

const RunningStatusMap = {
  [RunningStatus.UNSTART]: { color: '#d1d5db', label: '未开始' },
  [RunningStatus.RUNNING]: { color: '#3b82f6', label: '运行中' },
  [RunningStatus.CANCEL]: { color: '#f59e0b', label: '已取消' },
  [RunningStatus.DONE]: { color: '#10b981', label: '已完成' },
  [RunningStatus.FAIL]: { color: '#ef4444', label: '失败' },
};

function Dot({ progress }: { progress: number }) {
  let status: RunningStatus;
  if (progress === 0) status = RunningStatus.UNSTART;
  else if (progress === 1) status = RunningStatus.DONE;
  else status = RunningStatus.RUNNING;

  const runningStatus = RunningStatusMap[status];
  return (
    <span
      style={{
        display: 'inline-block',
        width: '8px',
        height: '8px',
        borderRadius: '50%',
        backgroundColor: runningStatus.color,
        marginRight: '6px',
      }}
    />
  );
}

export const PopoverContent = ({
  record,
  isBatchParsing,
  currentBatchDocument,
}: IProps) => {
  const replaceText = (text: string) => {
    // Remove duplicate \n
    const nextText = text.replace(/(\n)\1+/g, '$1');

    const replacedText = reactStringReplace(
      nextText,
      /(\[ERROR\].+\s)/g,
      (match, i) => {
        return (
          <span key={i} style={{ color: '#ef4444' }}>
            {match}
          </span>
        );
      },
    );

    return replacedText;
  };

  // 将 logs 格式转换为展示格式
  const progressMsg =
    record.logs && record.logs.length > 0
      ? record.logs.map((log) => `${log.time} ${log.message}`).join('\n')
      : '';

  const items = [
    {
      key: 'create_date',
      label: '创建时间',
      children: record.create_date,
    },
    {
      key: 'chunk_num',
      label: '分块数量',
      children: `${record.chunk_num}`,
    },
    {
      key: 'progress_msg',
      label: '处理日志',
      children: replaceText(progressMsg || '暂无日志'),
    },
  ];

  const formatParseStatus = (progress: number): string => {
    if (progress === 0) return '未解析';
    if (progress === 1) return '已完成';
    return `解析中 ${Math.floor(progress * 100)}%`;
  };

  // 判断当前文档是否是批量解析中的活跃文档
  const isCurrentBatchDocument =
    isBatchParsing &&
    currentBatchDocument &&
    record.name === currentBatchDocument;

  const displayStatus = isCurrentBatchDocument
    ? `批量解析中 ${Math.floor(record.progress * 100)}%`
    : formatParseStatus(record.progress);

  return (
    <div style={{ minWidth: '300px', maxWidth: '500px' }}>
      <div
        style={{ display: 'flex', alignItems: 'center', marginBottom: '12px' }}
      >
        <Dot progress={record.progress} />
        <span style={{ fontWeight: 'bold' }}>{displayStatus}</span>
      </div>

      {/* 批量解析状态提示 */}
      {isBatchParsing && (
        <div
          style={{
            background: '#f0f9ff',
            border: '1px solid #0ea5e9',
            borderRadius: '4px',
            padding: '8px',
            marginBottom: '12px',
            fontSize: '12px',
            color: '#0369a1',
          }}
        >
          {isCurrentBatchDocument
            ? '🔄 当前正在批量解析此文档'
            : '⏳ 等待批量解析队列处理'}
        </div>
      )}
      <div style={{ maxHeight: '50vh', overflowY: 'auto' }}>
        {items.map((x, idx) => {
          return (
            <div key={x.key} style={{ marginBottom: '8px' }}>
              <div
                style={{
                  fontWeight: 'bold',
                  color: '#666',
                  marginBottom: '4px',
                }}
              >
                {x.label}:
              </div>
              <div
                style={{
                  whiteSpace: 'pre-line',
                  wordWrap: 'break-word',
                  fontSize: '14px',
                  lineHeight: '1.4',
                }}
              >
                {x.children}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export function ParsingStatusCard({
  record,
  isBatchParsing,
  currentBatchDocument,
}: IProps) {
  const formatParseStatus = (progress: number): string => {
    if (progress === 0) return '未解析';
    if (progress === 1) return '已完成';
    return `解析中 ${Math.floor(progress * 100)}%`;
  };

  const getParseStatusType = (progress: number): string => {
    if (progress === 0) return 'default';
    if (progress === 1) return 'success';
    return 'processing';
  };

  // 判断当前文档是否是批量解析中的活跃文档
  const isCurrentBatchDocument =
    isBatchParsing &&
    currentBatchDocument &&
    record.name === currentBatchDocument;

  // 如果是批量解析且当前文档是活跃文档，显示特殊状态
  const displayStatus = isCurrentBatchDocument
    ? `批量解析中 ${Math.floor(record.progress * 100)}%`
    : formatParseStatus(record.progress);

  const displayType = isCurrentBatchDocument
    ? 'processing'
    : getParseStatusType(record.progress);

  return (
    <Popover
      content={
        <PopoverContent
          record={record}
          isBatchParsing={isBatchParsing}
          currentBatchDocument={currentBatchDocument}
        />
      }
      title={null}
      trigger="hover"
      placement="top"
      overlayStyle={{
        maxWidth: '500px',
      }}
    >
      <Tag
        color={displayType}
        style={{
          animation: isCurrentBatchDocument
            ? 'batchDocumentPulse 2s infinite'
            : undefined,
        }}
        className={isCurrentBatchDocument ? 'batch-document-tag' : ''}
      >
        {displayStatus}
      </Tag>
      {/* 添加全局样式 */}
      {isCurrentBatchDocument && (
        <style>
          {`
            @keyframes batchDocumentPulse {
              0% { opacity: 1; }
              50% { opacity: 0.5; }
              100% { opacity: 1; }
            }
            .batch-document-tag {
              animation: batchDocumentPulse 2s infinite;
            }
          `}
        </style>
      )}
    </Popover>
  );
}
