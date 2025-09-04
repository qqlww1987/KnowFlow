import { request } from '@/http/axios';
import type * as Auth from './type';

/** 获取登录验证码 */
// export function getCaptchaApi() {
//   return request<Auth.CaptchaResponseData>({
//     url: "v1/auth/captcha",
//     method: "get"
//   })
// }

/** 登录并返回 Token */
export function loginApi(data: Auth.LoginRequestData) {
  return request<Auth.LoginResponseData>({
    url: '/api/knowflow/v1/auth/login',
    method: 'post',
    data,
  });
}
