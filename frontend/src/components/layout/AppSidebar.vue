<script setup>
import { computed } from 'vue'

import AppIcon from '@/components/common/AppIcon.vue'
import BrandMark from '@/components/common/BrandMark.vue'
import { useThemeStore } from '@/stores/theme'
import { useSystemStore } from '@/stores/system'


const themeStore = useThemeStore()
const systemStore = useSystemStore()

const NAV = [
  { to: '/overview', icon: 'gauge', label: '概览' },
  { to: '/power', icon: 'zap', label: '快捷操作' },
  { to: '/processes', icon: 'layers', label: '进程管理' },
  { to: '/files', icon: 'folder', label: '文件管理' },
  { to: '/terminal', icon: 'terminal', label: '终端' },
  { to: '/screen', icon: 'monitor', label: '屏幕共享' },
  { to: '/settings', icon: 'settings', label: '设置' }
]

const connectionLabel = computed(() => {
  switch (systemStore.connected) {
    case true:
      return '实时连接'
    case false:
      return '连接中'
    default:
      return '离线'
  }
})

const connectionLevel = computed(() => (systemStore.connected ? 'ok' : 'warn'))
</script>

<template>
  <aside class="rail">
    <div class="rail__brand">
      <span class="rail__mark">
        <BrandMark :size="22" variant="mark" title="Atlantis Watcher" />
      </span>
      <span class="rail__names">
        <span class="rail__title">ATLANTIS</span>
        <span class="rail__sub">WATCHER</span>
      </span>
    </div>

    <nav class="rail__nav" aria-label="主导航">
      <RouterLink
        v-for="item in NAV"
        :key="item.to"
        :to="item.to"
        class="rail__item"
        active-class="is-active"
      >
        <AppIcon :name="item.icon" :size="17" />
        <span>{{ item.label }}</span>
      </RouterLink>
    </nav>

    <div class="rail__foot">
      <div class="rail__status">
        <span
          class="dot"
          :class="[connectionLevel, { 'dot--pulse': systemStore.connected }]"
        />
        <span class="aw-label">{{ connectionLabel }}</span>
      </div>

      <button
        class="rail__theme"
        :aria-label="themeStore.theme === 'dark' ? '切换到浅色主题' : '切换到深色主题'"
        :title="themeStore.theme === 'dark' ? '浅色主题' : '深色主题'"
        @click="themeStore.toggle()"
      >
        <AppIcon :name="themeStore.theme === 'dark' ? 'sun' : 'moon'" :size="16" />
      </button>
    </div>
  </aside>
</template>

<style scoped>
.rail {
  width: var(--aw-rail-w);
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--aw-hull);
  border-right: 1px solid var(--aw-line);
  overflow: hidden;
}

.rail__brand {
  display: flex;
  align-items: center;
  gap: var(--aw-space-3);
  height: var(--aw-topbar-h);
  padding: 0 var(--aw-space-4);
  border-bottom: 1px solid var(--aw-line);
  flex-shrink: 0;
}

.rail__mark {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border-radius: var(--aw-radius-sm);
  /* 深海仪表盘：边框分区，不用渐变/阴影浮起 */
  border: 1px solid var(--aw-line);
  background: var(--aw-accent-ghost);
  flex-shrink: 0;
}

.rail__names {
  display: flex;
  flex-direction: column;
  line-height: 1.15;
  min-width: 0;
}

.rail__title {
  font-family: var(--aw-font-mono);
  font-size: var(--aw-text-sm);
  font-weight: 600;
  letter-spacing: 0.16em;
  color: var(--aw-text);
}

.rail__sub {
  font-family: var(--aw-font-mono);
  font-size: var(--aw-text-2xs);
  letter-spacing: 0.24em;
  color: var(--aw-text-faint);
}

.rail__nav {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: var(--aw-space-3) var(--aw-space-2);
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.rail__item {
  display: flex;
  align-items: center;
  gap: var(--aw-space-3);
  padding: var(--aw-space-2) var(--aw-space-3);
  border-radius: var(--aw-radius);
  font-size: var(--aw-text-sm);
  color: var(--aw-text-mute);
  border-left: 2px solid transparent;
  transition: all var(--aw-dur-fast) var(--aw-ease);
}

.rail__item:hover {
  background: var(--aw-panel-hi);
  color: var(--aw-text);
}

.rail__item.is-active {
  background: var(--aw-accent-ghost);
  border-left-color: var(--aw-accent);
  color: var(--aw-accent);
  font-weight: 500;
}

.rail__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--aw-space-2);
  padding: var(--aw-space-3) var(--aw-space-4);
  border-top: 1px solid var(--aw-line);
  flex-shrink: 0;
}

.rail__status {
  display: flex;
  align-items: center;
  gap: var(--aw-space-2);
}

.rail__theme {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border-radius: var(--aw-radius-sm);
  color: var(--aw-text-mute);
  transition: all var(--aw-dur-fast) var(--aw-ease);
}

.rail__theme:hover {
  background: var(--aw-panel-hi);
  color: var(--aw-accent);
}

/* 移动端：侧栏转为顶部紧凑条 */
@media (max-width: 900px) {
  .rail {
    display: none;
  }
}
</style>
