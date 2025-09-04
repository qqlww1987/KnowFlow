import { request } from '@/http/axios';
import type * as Users from './type';

/** 获取当前登录用户详情 */
export function getCurrentUserApi() {
  return request<Users.CurrentUserResponseData>({
    url: 'api/knowflow/v1/users/me',
    method: 'get',
  });
}
