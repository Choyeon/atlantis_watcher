import { createRouter, createWebHashHistory } from 'vue-router'

/**
 * 路由表
 * 使用 hash 模式：打包成 exe 后由本地静态服务器提供，
 * hash 路由不依赖服务端 rewrite 配置，最稳妥。
 */
const routes = [
  {
    path: '/',
    redirect: '/overview'
  },
  {
    path: '/overview',
    name: 'overview',
    component: () => import('@/views/OverviewView.vue'),
    meta: { title: '系统概览', icon: 'gauge', label: '概览' }
  },
  {
    path: '/power',
    name: 'power',
    component: () => import('@/views/PowerView.vue'),
    meta: { title: '快捷操作', icon: 'zap', label: '快捷' }
  },
  {
    path: '/monitor',
    name: 'monitor',
    component: () => import('@/views/MonitorView.vue'),
    meta: { title: '系统监控', icon: 'activity', label: '监控' }
  },
  {
    path: '/processes',
    name: 'processes',
    // 复用进程管理视图：/monitor 为兼容旧链接与回归脚本保留
    component: () => import('@/views/MonitorView.vue'),
    meta: { title: '进程管理', icon: 'layers', label: '进程' }
  },
  {
    path: '/files',
    name: 'files',
    component: () => import('@/views/FilesView.vue'),
    meta: { title: '文件管理', icon: 'folder', label: '文件' }
  },
  {
    path: '/terminal',
    name: 'terminal',
    component: () => import('@/views/TerminalView.vue'),
    meta: { title: '终端', icon: 'terminal', label: '终端' }
  },
  {
    path: '/screen',
    name: 'screen',
    component: () => import('@/views/ScreenView.vue'),
    meta: { title: '屏幕共享', icon: 'monitor', label: '屏幕' }
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('@/views/SettingsView.vue'),
    meta: { title: '设置', icon: 'settings', label: '设置' }
  },
  { path: '/:pathMatch(.*)*', redirect: '/overview' }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 })
})

router.afterEach(to => {
  const title = to.meta?.title
  document.title = title ? `${title} · Atlantis Watcher` : 'Atlantis Watcher'
})

export default router
