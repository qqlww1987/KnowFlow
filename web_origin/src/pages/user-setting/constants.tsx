import {
  ApiIcon,
  LogOutIcon,
  ManagementIcon,
  ModelProviderIcon,
  PasswordIcon,
  ProfileIcon,
  TeamIcon,
} from '@/assets/icon/Icon';
import { LLMFactory } from '@/constants/llm';
import { UserSettingRouteKey } from '@/constants/setting';
import {
  DatabaseOutlined,
  FileOutlined,
  SettingOutlined,
} from '@ant-design/icons';

export const UserSettingIconMap = {
  [UserSettingRouteKey.Profile]: <ProfileIcon />,
  [UserSettingRouteKey.Password]: <PasswordIcon />,
  [UserSettingRouteKey.Model]: <ModelProviderIcon />,
  [UserSettingRouteKey.System]: <ModelProviderIcon />,
  [UserSettingRouteKey.Api]: <ApiIcon />,
  [UserSettingRouteKey.Team]: <TeamIcon />,
  [UserSettingRouteKey.Management]: <ManagementIcon />,
  [UserSettingRouteKey.FileManagement]: <FileOutlined />,
  [UserSettingRouteKey.KnowledgeManagement]: <DatabaseOutlined />,
  [UserSettingRouteKey.UserConfig]: <SettingOutlined />,
  [UserSettingRouteKey.Logout]: <LogOutIcon />,
};

export * from '@/constants/setting';

export const LocalLlmFactories = [
  LLMFactory.Ollama,
  LLMFactory.Xinference,
  LLMFactory.LocalAI,
  LLMFactory.LMStudio,
  LLMFactory.OpenAiAPICompatible,
  LLMFactory.TogetherAI,
  LLMFactory.Replicate,
  LLMFactory.OpenRouter,
  LLMFactory.HuggingFace,
  LLMFactory.GPUStack,
  LLMFactory.ModelScope,
  LLMFactory.VLLM,
];

export enum TenantRole {
  Owner = 'owner',
  Invite = 'invite',
  Normal = 'normal',
}
