<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppIcon from '@/components/common/AppIcon.vue'
import BrandMark from '@/components/common/BrandMark.vue'
import { useThemeStore } from '@/stores/theme'
import { useSystemStore } from '@/stores/system'

/**
 * 顶栏 — iOS 27 规范
 *
 * 移动端：大标题（Large Title）+ 轻量悬浮工具条 + 「更多」菜单
 *   底部导航精简为四个高频项后，屏幕 / 快捷 / 设置由此进入
 * 桌面端：紧凑单行工具条（侧栏保留全部入口，无需重复「更多」按钮）
 */

/** 低频功能：从底部导航移入顶栏更多菜单 */
const MORE_ITEMS = [
  { to: '/screen', icon: 'monitor', label: '屏幕共享', hint: '远程查看与操控' },
  { to: '/power', icon: 'zap', label: '快捷操作', hint: '关机 / 重启 / 锁屏' },
  { to: '/settings', icon: 'settings', label: '设置', hint: '服务与远程控制配置' }
]
const route = useRoute()
const themeStore = useThemeStore()
const systemStore = useSystemStore()

const now = ref(new Date())
const moreOpen = ref(false)
const moreRef = ref(null)
const moreButtonRef = ref(null)
const moreMenuRef = ref(null)
const menuStyle = ref({})
let timer = null

function closeMore() {
  moreOpen.value = false
}

/** 菜单投递到 body，按按钮位置固定，避免被顶栏层级或 Toast 遮挡 */
function toggleMore() {
  if (moreOpen.value) {
    closeMore()
    return
  }
  const rect = moreButtonRef.value?.getBoundingClientRect()
  if (rect) {
    menuStyle.value = {
      top: `${Math.round(rect.bottom + 10)}px`,
      right: `${Math.round(window.innerWidth - rect.right)}px`
    }
  }
  moreOpen.value = true
}

/** 点击面板外部 / Esc / 滚动 / 路由变化时收起菜单 */
function onDocumentPointerDown(event) {
  if (!moreOpen.value) return
  if (moreRef.value?.contains(event.target) || moreMenuRef.value?.contains(event.target)) return
  closeMore()
}

function onDocumentKeyDown(event) {
  if (event.key === 'Escape' && moreOpen.value) closeMore()
}

function onViewportChange() {
  if (moreOpen.value) closeMore()
}

watch(() => route.path, closeMore)

onMounted(() => {
  timer = setInterval(() => {
    now.value = new Date()
  }, 1000)
  document.addEventListener('pointerdown', onDocumentPointerDown)
  document.addEventListener('keydown', onDocumentKeyDown)
  window.addEventListener('scroll', onViewportChange, true)
  window.addEventListener('resize', onViewportChange)
})

onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
  document.removeEventListener('pointerdown', onDocumentPointerDown)
  document.removeEventListener('keydown', onDocumentKeyDown)
  window.removeEventListener('scroll', onViewportChange, true)
  window.removeEventListener('resize', onViewportChange)
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

        <!-- 低频功能入口：仅移动端显示，桌面端由侧栏提供 -->
        <div ref="moreRef" class="topbar__more">
          <button
            ref="moreButtonRef"
            class="topbar__theme"
            aria-label="更多功能"
            aria-haspopup="menu"
            :aria-expanded="moreOpen"
            title="更多功能"
            @click="toggleMore"
          >
            <AppIcon name="moreVertical" :size="17" />
          </button>
        </div>

        <!-- 投递到 body：不受顶栏层级与 Toast 浮层遮挡 -->
        <Teleport to="body">
          <Transition name="more-pop">
            <div
              v-if="moreOpen"
              ref="moreMenuRef"
              class="topbar__more-menu"
              :style="menuStyle"
              role="menu"
              aria-label="更多功能"
            >
              <p class="topbar__more-title aw-label">更多功能</p>
              <RouterLink
                v-for="item in MORE_ITEMS"
                :key="item.to"
                :to="item.to"
                class="topbar__more-item"
                :class="{ 'is-active': route.path === item.to }"
                role="menuitem"
                @click="closeMore"
              >
                <span class="topbar__more-icon"><AppIcon :name="item.icon" :size="17" /></span>
                <span class="topbar__more-text">
                  <span class="topbar__more-label">{{ item.label }}</span>
                  <span class="topbar__more-hint">{{ item.hint }}</span>
                </span>
              </RouterLink>
            </div>
          </Transition>
        </Teleport>
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
   「更多」菜单：桌面端由侧栏提供全部入口，仅移动端出现
   -------------------------------------------------------------------------- */
.topbar__more {
  display: none;
  position: relative;
}

.topbar__more-menu {
  position: fixed;
  width: 216px;
  padding: 6px;
  border-radius: 14px;
  background: color-mix(in srgb, var(--aw-hull) 96%, transparent);
  border: 1px solid var(--aw-line-hi);
  box-shadow: var(--aw-shadow-lg);
  -webkit-backdrop-filter: blur(18px) saturate(1.5);
  backdrop-filter: blur(18px) saturate(1.5);
  z-index: 400;
}

.topbar__more-title {
  padding: 6px 10px 8px;
  color: var(--aw-text-faint);
}

.topbar__more-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 10px;
  border-radius: 10px;
  color: var(--aw-text);
  transition: background-color var(--aw-dur-fast) var(--aw-ease);
}

.topbar__more-item:hover,
.topbar__more-item.is-active {
  background: var(--aw-accent-ghost);
  color: var(--aw-accent);
}

.topbar__more-icon {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  flex-shrink: 0;
  border-radius: 9px;
  background: var(--aw-panel-hi);
  color: var(--aw-text-dim);
}

.topbar__more-item.is-active .topbar__more-icon {
  color: var(--aw-accent);
}

.topbar__more-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
  line-height: 1.25;
}

.topbar__more-label {
  font-size: var(--aw-text-sm);
  font-weight: 600;
}

.topbar__more-hint {
  font-size: var(--aw-text-2xs);
  color: var(--aw-text-mute);
}

.more-pop-enter-active,
.more-pop-leave-active {
  transition: opacity 160ms var(--aw-ease), transform 160ms var(--aw-ease);
}

.more-pop-enter-from,
.more-pop-leave-to {
  opacity: 0;
  transform: translateY(-6px) scale(0.96);
}

/* --------------------------------------------------------------------------
   iOS 27 移动端：大标题 + 轻量悬浮工具条
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

  .topbar__more {
    display: block;
  }

  /* iOS 大标题 */
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
