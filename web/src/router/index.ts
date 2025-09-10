import { routerConfig } from '@/router/config';
import { registerNavigationGuard } from '@/router/guard';
import type { RouteRecordRaw } from 'vue-router';
import { createRouter } from 'vue-router';
import { flatMultiLevelRoutes } from './helper';

const Layouts = () => import('@/layouts/index.vue');

/**
 * @name 常驻路由
 * @description 除了 redirect/403/404/login 等隐藏页面，其他页面建议设置唯一的 Name 属性
 */
export const constantRoutes: RouteRecordRaw[] = [
  {
    path: '/redirect',
    component: Layouts,
    meta: {
      hidden: true,
    },
    children: [
      {
        path: ':path(.*)',
        component: () => import('@/pages/redirect/index.vue'),
      },
    ],
  },
  {
    path: '/403',
    component: () => import('@/pages/error/403.vue'),
    meta: {
      hidden: true,
    },
  },
  {
    path: '/404',
    component: () => import('@/pages/error/404.vue'),
    meta: {
      hidden: true,
    },
    alias: '/:pathMatch(.*)*',
  },
  {
    path: '/login',
    component: () => import('@/pages/login/index.vue'),
    meta: {
      hidden: true,
    },
  },
  // {
  //   path: "/",
  //   component: Layouts,
  //   redirect: "/dashboard",
  //   children: [
  //     {
  //       path: "dashboard",
  //       component: () => import("@/pages/dashboard/index.vue"),
  //       name: "Dashboard",
  //       meta: {
  //         title: "首页",
  //         svgIcon: "dashboard",
  //         affix: true
  //       }
  //     }
  //   ]
  // },

  // {
  //   path: "/",
  //   component: Layouts,
  //   redirect: "/dashboard",
  //   children: [
  //     {
  //       path: "dashboard",
  //       component: () => import("@/pages/dashboard/index.vue"),
  //       name: "Dashboard",
  //       meta: {
  //         title: "首页",
  //         svgIcon: "dashboard",
  //         affix: true
  //       }
  //     }
  //   ]
  // },

  {
    path: '/',
    component: Layouts,
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        component: () => import('@/pages/dashboard/index.vue'),
        name: 'Dashboard',
        meta: {
          title: '首页',
          svgIcon: 'dashboard',
          affix: true,
        },
      },
    ],
  },
  // {
  //   path: "/",
  //   component: () => import("@/pages/demo/element-plus/index.vue"),
  //   name: "ElementPlus",
  //   meta: {
  //     title: "Element Plus",
  //     keepAlive: true
  //   }
  // }

  // {
  //   path: "/demo",
  //   component: Layouts,
  //   redirect: "/demo/unocss",
  //   name: "Demo",
  //   meta: {
  //     title: "示例集合",
  //     elIcon: "DataBoard"
  //   },
  //   children: [
  //     {
  //       path: "unocss",
  //       component: () => import("@/pages/demo/unocss/index.vue"),
  //       name: "UnoCSS",
  //       meta: {
  //         title: "UnoCSS"
  //       }
  //     },

  //     {
  //       path: "vxe-table",
  //       component: () => import("@/pages/demo/vxe-table/index.vue"),
  //       name: "VxeTable",
  //       meta: {
  //         title: "Vxe Table",
  //         keepAlive: true
  //       }
  //     },
  //     {
  //       path: "level2",
  //       component: () => import("@/pages/demo/level2/index.vue"),
  //       redirect: "/demo/level2/level3",
  //       name: "Level2",
  //       meta: {
  //         title: "二级路由",
  //         alwaysShow: true
  //       },
  //       children: [
  //         {
  //           path: "level3",
  //           component: () => import("@/pages/demo/level2/level3/index.vue"),
  //           name: "Level3",
  //           meta: {
  //             title: "三级路由",
  //             keepAlive: true
  //           }
  //         }
  //       ]
  //     },
  //     {
  //       path: "composable-demo",
  //       redirect: "/demo/composable-demo/use-fetch-select",
  //       name: "ComposableDemo",
  //       meta: {
  //         title: "组合式函数"
  //       },
  //       children: [
  //         {
  //           path: "use-fetch-select",
  //           component: () => import("@/pages/demo/composable-demo/use-fetch-select.vue"),
  //           name: "UseFetchSelect",
  //           meta: {
  //             title: "useFetchSelect"
  //           }
  //         },
  //         {
  //           path: "use-fullscreen-loading",
  //           component: () => import("@/pages/demo/composable-demo/use-fullscreen-loading.vue"),
  //           name: "UseFullscreenLoading",
  //           meta: {
  //             title: "useFullscreenLoading"
  //           }
  //         },
  //         {
  //           path: "use-watermark",
  //           component: () => import("@/pages/demo/composable-demo/use-watermark.vue"),
  //           name: "UseWatermark",
  //           meta: {
  //             title: "useWatermark"
  //           }
  //         }
  //       ]
  //     }
  //   ]
  // },
  // {
  //   path: "/link",
  //   meta: {
  //     title: "文档链接",
  //     elIcon: "Link"
  //   },
  //   children: [
  //     {
  //       path: "https://juejin.cn/post/7445151895121543209",
  //       component: () => {},
  //       name: "Link1",
  //       meta: {
  //         title: "中文文档"
  //       }
  //     },
  //     {
  //       path: "https://juejin.cn/column/7207659644487139387",
  //       component: () => {},
  //       name: "Link2",
  //       meta: {
  //         title: "新手教程"
  //       }
  //     }
  //   ]
  // }
];

/**
 * @name 动态路由
 * @description 用来放置有权限 (Roles 属性) 的路由
 * @description 必须带有唯一的 Name 属性
 */
export const dynamicRoutes: RouteRecordRaw[] = [
  {
    path: '/management',
    component: Layouts,
    redirect: '/management/users',
    name: 'Management',
    meta: {
      title: '系统管理',
      svgIcon: 'management',
      // 管理员和超级管理员都可以访问
      roles: ['admin', 'super_admin'],
      alwaysShow: true,
    },
    children: [
      {
        path: 'users',
        component: () => import('@/pages/user-management/index.vue'),
        name: 'UserManagement',
        meta: {
          title: '用户管理',
          svgIcon: 'user-management',
          roles: ['admin', 'super_admin'],
        },
      },
      {
        path: 'teams',
        component: () => import('@/pages/team-management/index.vue'),
        name: 'TeamManagement',
        meta: {
          title: '团队管理',
          svgIcon: 'team-management',
          roles: ['admin', 'super_admin'],
        },
      },
      {
        path: 'files',
        component: () => import('@/pages/file/index.vue'),
        name: 'FileManagement',
        meta: {
          title: '文件管理',
          svgIcon: 'file',
          roles: ['admin', 'super_admin'],
        },
      },
      {
        path: 'knowledgebases',
        component: () => import('@/pages/knowledgebase/index.vue'),
        name: 'KnowledgeBaseManagement',
        meta: {
          title: '知识库管理',
          svgIcon: 'kb',
          roles: ['admin', 'super_admin'],
        },
      },
      {
        path: 'configs',
        component: () => import('@/pages/user-config/index.vue'),
        name: 'UserConfigManagement',
        meta: {
          title: '用户配置',
          svgIcon: 'user-config',
          roles: ['admin', 'super_admin'],
        },
      },
    ],
  },
];

/** 路由实例 */
export const router = createRouter({
  history: routerConfig.history,
  routes: routerConfig.thirdLevelRouteCache
    ? flatMultiLevelRoutes(constantRoutes)
    : constantRoutes,
});

/** 重置路由 */
export function resetRouter() {
  try {
    // 注意：所有动态路由路由必须带有 Name 属性，否则可能会不能完全重置干净
    router.getRoutes().forEach((route) => {
      const { name, meta } = route;
      if (name && meta.roles?.length) {
        router.hasRoute(name) && router.removeRoute(name);
      }
    });
  } catch {
    // 强制刷新浏览器也行，只是交互体验不是很好
    location.reload();
  }
}

// 注册路由导航守卫
registerNavigationGuard(router);
