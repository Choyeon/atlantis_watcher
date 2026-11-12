<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import AppIcon from '@/components/common/AppIcon.vue'
import BrandMark from '@/components/common/BrandMark.vue'
import { useThemeStore } from '@/stores/theme'
import { useSystemStore } from '@/stores/system'

/**
 * 顶栏 — iOS 26 规范
 *
 * 移动端：大标题（Large Title）+ 轻量悬浮工具条
 * 桌面端：紧凑单行工具条（保留仪表盘风格，避免破坏桌面信息密度）
 */
const route = useRoute()
const themeStore = useThemeStore()
const systemStore = useSystemStore()

const now = ref(new Date())
let timer = null

onMounted(() => {
  timer = setInterval(() => {
    now.value = new Date()
  }, 1000)
})

onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
})

const clock = computed(() =>
  now.value.toLocaleTimeString('zh-CN', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
)

const title = computed(() => route.meta?.title || 'Atlantis Watcher')
const subtitle = computed(() => route.meta?.subtitle || '')

/** 打开主机连接设置 */
function openHostSettings() {
  window.dispatchEvent(new CustomEvent('aw:open-host-settings'))
}
</script>

<template>
  <header class="topbar">
    <div class="topbar__row">
      <div class="topbar__left">
        <span class="topbar__mark">
          <BrandMark :size="20" variant="mark" title="Atlantis Watcher" />
        </span>
        <div class="topbar__titles">
          <h1 class="topbar__title">{{ title }}</h1>
          <p v-if="subtitle" class="topbar__subtitle">{{ subtitle }}</p>
        </div>
      </div>

      <div class="topbar__right">
        <div class="topbar__clock aw-mono">{{ clock }}</div>

        <div class="topbar__conn">
          <span class="dot" :class="systemStore.connected ? 'dot--ok dot--pulse' : 'dot--warn'" />
          <span class="aw-label">{{ systemStore.connected ? 'LIVE' : 'OFFLINE' }}</span>
        </div>

        <button
          class="topbar__theme"
          aria-label="主机连接设置"
          title="主机连接设置"
          @click="openHostSettings"
        >
          <AppIcon name="server" :size="16" />
        </button>

        <button
          class="topbar__theme"
          :aria-label="themeStore.theme === 'dark' ? '切换到浅色主题' : '切换到深色主题'"
          @click="themeStore.toggle()"
        >
          <AppIcon :name="themeStore.theme === 'dark' ? 'sun' : 'moon'" :size="16" />
        </button>
      </div>
    </div>
  </header>
</template>

<style scoped>
.topbar {
  flex-shrink: 0;
  background: var(--aw-hull);
  border-bottom: 1px solid var(--aw-line);
}

.topbar__row {
  height: var(--aw-topbar-h);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--aw-space-4);
  padding: 0 var(--aw-space-4);
}

.topbar__left {
  display: flex;
  align-items: center;
  gap: var(--aw-space-3);
  min-width: 0;
}

.topbar__mark {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: var(--aw-radius-sm);
  background: var(--aw-accent-ghost);
  color: var(--aw-accent);
  flex-shrink: 0;
}

.topbar__titles {
  min-width: 0;
}

.topbar__title {
  font-size: var(--aw-text-md);
  font-weight: 600;
  letter-spacing: -0.01em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.topbar__subtitle {
  font-size: var(--aw-text-xs);
  color: var(--aw-text-mute);
}

.topbar__right {
  display: flex;
  align-items: center;
  gap: var(--aw-space-4);
}

.topbar__clock {
  font-size: var(--aw-text-xs);
  color: var(--aw-text-mute);
  letter-spacing: 0.04em;
}

.topbar__conn {
  display: flex;
  align-items: center;
  gap: var(--aw-space-2);
  padding: 3px var(--aw-space-2);
  border: 1px solid var(--aw-line);
  border-radius: var(--aw-radius-xs);
}

.topbar__theme {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border-radius: var(--aw-radius-sm);
  color: var(--aw-text-mute);
  transition: all var(--aw-dur-fast) var(--aw-ease);
}

.topbar__theme:hover {
  background: var(--aw-panel-hi);
  color: var(--aw-accent);
}

/* --------------------------------------------------------------------------
   iOS 26 移动端：大标题 + 轻量悬浮工具条
   -------------------------------------------------------------------------- */
@media (max-width: 900px) {
  .topbar {
    background: transparent;
    border-bottom: none;
    position: sticky;
    top: 0;
    z-index: 80;
    padding-top: env(safe-area-inset-top);
    /* 顶部内容在标题下方柔和淡出 */
    background: linear-gradient(
      to bottom,
      var(--aw-deep) 68%,
      color-mix(in srgb, var(--aw-deep) 0%, transparent) 100%
    );
  }

  .topbar__row {
    height: auto;
    min-height: 56px;
    padding: var(--aw-space-2) var(--aw-space-4) var(--aw-space-3);
    flex-direction: column;
    align-items: stretch;
    gap: var(--aw-space-1);
  }

  .topbar__left {
    order: 2;
  }

  .topbar__right {
    order: 1;
    justify-content: flex-end;
    position: absolute;
    top: calc(var(--aw-space-2) + env(safe-area-inset-top));
    right: var(--aw-space-4);
  }

  /* iOS 26 大标题 */
  .topbar__title {
    font-size: 1.75rem;
    font-weight: 700;
    letter-spacing: -0.025em;
    line-height: 1.15;
  }

  .topbar__mark {
    display: none;
  }

  .topbar__clock {
    display: none;
  }

  /* 连接状态改为轻量点 */
  .topbar__conn {
    border: none;
    padding: 0;
  }

  .topbar__conn .aw-label {
    display: none;
  }
}
</style>
