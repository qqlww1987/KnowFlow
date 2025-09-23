import { useFetchUserInfo } from '@/hooks/user-setting-hooks';
import request from '@/utils/request';
import { useCallback, useEffect, useMemo, useState } from 'react';

export type KbPermissionType = 'read' | 'write' | 'admin';

/**
 * 直接检查某个知识库的权限（一次性调用）
 */
export async function checkKbPermission(params: {
  userId: string;
  kbId: string;
  permission: KbPermissionType;
}): Promise<boolean> {
  const { userId, kbId, permission } = params;
  if (!userId || !kbId) return false;
  try {
    const res = await request.post(
      `/api/v1/knowledgebases/${kbId}/permissions/check`,
      {
        data: {
          user_id: userId,
          permission_type: permission,
        },
      },
    );
    const data = res?.data;
    if (data?.code === 0) return Boolean(data?.data?.has_permission);
    // 兼容期：后端未开启/不可用 RBAC 或返回结构不一致，默认放行，避免误伤前端体验
    return true;
  } catch (e) {
    // 兼容期：检查失败默认放行，由后端装饰器进行最终强制
    return true;
  }
}

/**
 * 检查是否拥有全局 kb_admin 能力（用于创建知识库等不指定资源的操作）
 */
export async function checkGlobalKbAdmin(params: {
  userId: string;
}): Promise<boolean> {
  const { userId } = params;
  if (!userId) return false;
  try {
    const res = await request.post('/api/v1/rbac/permissions/simple-check', {
      data: {
        permission_code: 'kb_admin',
        user_id: userId,
      },
    });
    const data = res?.data;
    if (typeof data?.has_permission !== 'undefined')
      return Boolean(data?.has_permission);
    if (typeof data?.data?.has_permission !== 'undefined')
      return Boolean(data?.data?.has_permission);
    // 兼容期默认放行
    return true;
  } catch (e) {
    return true;
  }
}

/**
 * 为当前选定的知识库提供权限状态与便捷方法
 */
export function useKbPermission(kbId?: string) {
  const { data: userInfo } = useFetchUserInfo();
  const userId = userInfo?.id;

  const [canRead, setCanRead] = useState<boolean>(false);
  const [canWrite, setCanWrite] = useState<boolean>(false);
  const [canAdmin, setCanAdmin] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(false);

  const isReady = Boolean(kbId && userId);

  const refresh = useCallback(async () => {
    if (!isReady) return;
    setLoading(true);
    try {
      const [r, w, a] = await Promise.all([
        checkKbPermission({
          userId: userId as string,
          kbId: kbId as string,
          permission: 'read',
        }),
        checkKbPermission({
          userId: userId as string,
          kbId: kbId as string,
          permission: 'write',
        }),
        checkKbPermission({
          userId: userId as string,
          kbId: kbId as string,
          permission: 'admin',
        }),
      ]);
      setCanRead(r);
      setCanWrite(w);
      setCanAdmin(a);
    } finally {
      setLoading(false);
    }
  }, [isReady, kbId, userId]);

  useEffect(() => {
    // 初次进入某个知识库详情时进行一次预检
    if (isReady) refresh();
    else {
      setCanRead(false);
      setCanWrite(false);
      setCanAdmin(false);
    }
  }, [isReady, kbId, userId, refresh]);

  const can = useCallback(
    async (permission: KbPermissionType): Promise<boolean> => {
      if (!isReady) return false;
      return checkKbPermission({
        userId: userId as string,
        kbId: kbId as string,
        permission,
      });
    },
    [isReady, kbId, userId],
  );

  return useMemo(
    () => ({ canRead, canWrite, canAdmin, loading, can, refresh, userId }),
    [canRead, canWrite, canAdmin, loading, can, refresh, userId],
  );
}

/**
 * 是否具备全局管理知识库的能力（用于渲染“新建知识库”等入口）
 */
export function useGlobalKbAdmin() {
  const { data: userInfo } = useFetchUserInfo();
  const userId = userInfo?.id;
  const [allowed, setAllowed] = useState<boolean>(false);

  const refresh = useCallback(async () => {
    if (!userId) return setAllowed(false);
    const ok = await checkGlobalKbAdmin({ userId });
    setAllowed(ok);
  }, [userId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { allowed, refresh, userId };
}
