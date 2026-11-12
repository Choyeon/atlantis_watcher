<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useGlass } from 'glassy-liquid/vue'
import AppIcon from '@/components/common/AppIcon.vue'

/**
 * 移动端底部导航 — iOS 26 Liquid Glass
 *
 * 材质由 glassy-liquid 提供（useGlass 原地升级 DOM）：
 *   - Chromium 走 SVG feDisplacementMap 折射路径（真畸变）
 *   - Safari/Firefox 自动降级为 WebGL scene 或 CSS 磨砂
 *
 * 本组件负责导航逻辑与液态选中指示器：
 *   1. 药丸形玻璃容器悬浮于内容之上，滚动时内容从其下方穿过并被折射
 *   2. 选中态为「液态气泡」——切换时发生形变并伴随拉伸回弹
 */
const route = useRoute()

const TABS = [
  { to: '/overview', icon: 'gauge', label: '概览' },
  { to: '/power', icon: 'zap', label: '快捷' },
  { to: '/processes', icon: 'layers', label: '进程' },
  { to: '/files', icon: 'folder', label: '文件' },
  { to: '/terminal', icon: 'terminal', label: '终端' },
  { to: '/screen', icon: 'monitor', label: '屏幕' },
  { to: '/settings', icon: 'settings', label: '设置' }
]

const navRef = ref(null)
const itemRefs = ref([])
const indicator = ref({ left: 0, width: 0 })
const morphing = ref(false)

const activeIndex = computed(() => TABS.findIndex(t => t.to === route.path))

/**
 * 玻璃材质参数（iOS 26 光学模型）
 *
 *   refraction   边缘最大位移（px）——玻璃把背景向外挤压的程度
 *   bezel        折射边缘宽度（px）——玻璃壁的厚度
 *   dispersion   边缘色散强度 0-1——光在玻璃棱角内的分离
 *   specular     边缘高光强度 0-2
 *   lightAngle   光源方向（度），-135 为左上方
 *   profile      边缘截面：squircle（苹果风）/ convex / lip / flat
 *
 * 注意：宿主元素不能有 background，否则会成为 backdrop root 导致折射失效。
 */
const glassOptions = {
  material: 'regular',
  appearance: 'auto',
  radius: 'capsule',
  refraction: 38,
  bezel: 22,
  dispersion: 0.28,
  specular: 1.15,
  lightAngle: -135,
  profile: 'squircle',
  shadow: true
}

useGlass(navRef, glassOptions)

/** 重新定位液态指示器 */
async function syncIndicator(animate = true) {
  await nextTick()
  const idx = activeIndex.value
  if (idx < 0) return

  // Vue 的 :ref 回调在 v-for 中可能传入组件实例而非 DOM 元素，
  // 需要取其 $el 才能调用 getBoundingClientRect
  const raw = itemRefs.value[idx]
  const el = raw && raw.$el ? raw.$el : raw
  const nav = navRef.value
  if (!el || !nav || typeof el.getBoundingClientRect !== 'function') return

  const navRect = nav.getBoundingClientRect()
  const rect = el.getBoundingClientRect()

  if (animate) {
    // 触发形变动画：重置后重新置位，确保动画重新播放
    morphing.value = false
    await nextTick()
    morphing.value = true
    setTimeout(() => {
      morphing.value = false
    }, 560)
  }

  indicator.value = {
    left: rect.left - navRect.left,
    width: rect.width
  }
}

function setItemRef(el, index) {
  if (el) itemRefs.value[index] = el
}

watch(() => route.path, () => syncIndicator(true))

onMounted(() => {
  syncIndicator(false)
  window.addEventListener('resize', () => syncIndicator(false))
})
</script>

<template>
  <nav class="tabbar" aria-label="底部导航">
    <div class="tabbar__inner">
      <!-- 液态玻璃药丸：材质由 glassy-liquid 注入 gl-fx 图层 -->
      <div
        ref="navRef"
        class="tabbar__pill"
      >
        <!-- 液态选中指示器 -->
        <span
          class="lg-liquid-indicator"
          :class="{ 'is-morphing': morphing }"
          :style="{
            transform: `translateX(${indicator.left}px)`,
            width: `${indicator.width}px`
          }"
          aria-hidden="true"
        />

        <RouterLink
          v-for="(tab, index) in TABS"
          :key="tab.to"
          :ref="el => setItemRef(el, index)"
          :to="tab.to"
          class="tabbar__item"
          :class="{ 'is-active': activeIndex === index }"
        >
          <span class="tabbar__icon">
            <AppIcon :name="tab.icon" :size="21" />
          </span>
          <span class="tabbar__label">{{ tab.label }}</span>
        </RouterLink>
      </div>
    </div>
  </nav>
</template>

<style scoped>
.tabbar {
  display: none;
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 90;
  padding: 0 var(--aw-space-3);
  padding-bottom: calc(var(--aw-space-3) + env(safe-area-inset-bottom));
  /* 底部渐隐遮罩：让内容在玻璃上方柔和淡出 */
  background: linear-gradient(
    to top,
    var(--aw-deep) 0%,
    color-mix(in srgb, var(--aw-deep) 78%, transparent) 55%,
    transparent 100%
  );
  pointer-events: none;
}

.tabbar__inner {
  display: flex;
  align-items: center;
  gap: var(--aw-space-2);
  pointer-events: auto;
}

/*
  药丸容器
  重要：此处刻意不设置 background / backdrop-filter。
  glassy-liquid 会把 gl-fx 图层插到元素内部并用 backdrop-filter 做折射，
  若宿主自带背景会成为 backdrop root，导致折射失效。
*/
.tabbar__pill {
  position: relative;
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: stretch;
  justify-content: space-between;
  padding: 5px;
  min-height: 58px;
  border-radius: var(--aw-radius-pill);
  /* 主题色板：注入 glassy-liquid 的 CSS 变量 */
  --glass-accent: var(--aw-accent);
}

/* 导航项：需在玻璃的折射/高光层之上 */
.tabbar__item {
  position: relative;
  z-index: 3;
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  padding: 4px 2px;
  border-radius: var(--aw-radius-pill);
  color: var(--aw-text-mute);
  transition: color 260ms var(--aw-ease);
}

.tabbar__item.is-active {
  color: var(--aw-accent);
}

.tabbar__icon {
  display: grid;
  place-items: center;
  transition: transform 420ms var(--aw-ease-liquid, cubic-bezier(0.34, 1.56, 0.64, 1));
}

.tabbar__item.is-active .tabbar__icon {
  transform: translateY(-1px) scale(1.06);
}

.tabbar__label {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.01em;
  white-space: nowrap;
}

@media (max-width: 900px) {
  .tabbar {
    display: block;
  }
}

/* 极窄屏：隐藏文字标签，仅留图标 */
@media (max-width: 380px) {
  .tabbar__label {
    display: none;
  }

  .tabbar__pill {
    min-height: 52px;
  }
}
</style>
