<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { GlassTabBar, GlassTab } from 'glassy-liquid/vue'
import AppIcon from '@/components/common/AppIcon.vue'

/**
 * 移动端底部导航 — iOS 27 Liquid Glass
 *
 * 材质与拖动交互由 glassy-liquid 的 GlassTabBar 提供：
 *   1. 选中态平时是静态药丸；按下时抬升为「液态放大镜」，折射背景
 *   2. 拖动时药丸跟随手指，越过两端有橡皮筋阻尼，并按速度横向拉伸
 *   3. 松手吸附到最近项并弹性回位；方向键 / Home / End 同样可用
 *   4. Chromium 走 SVG feDisplacementMap 真折射，Safari/Firefox 自动降级
 *
 * 本组件只负责路由绑定、Tab 配置与主题变量；不再手写指示器与形变动画。
 */
const route = useRoute()
const router = useRouter()

/**
 * 底部只保留四个高频入口。
 * 屏幕共享 / 快捷操作 / 设置属于低频功能，收进顶栏「更多」菜单，
 * 避免在 390px 宽的屏幕上把图标与文字挤成一条。
 */
const TABS = [
  { to: '/overview', icon: 'gauge', label: '概览' },
  { to: '/processes', icon: 'layers', label: '进程' },
  { to: '/files', icon: 'folder', label: '文件' },
  { to: '/terminal', icon: 'terminal', label: '终端' }
]

/** 路由 ⇄ 选中项双向绑定：点击、拖动、键盘输入都由 GlassTabBar 统一派发 */
const active = computed({
  get: () => route.path,
  set: value => {
    if (typeof value === 'string' && value && value !== route.path) router.push(value)
  }
})
</script>

<template>
  <nav class="tabbar" aria-label="底部导航">
    <div class="tabbar__inner">
      <!-- 玻璃材质与拖动放大镜由 GlassTabBar 的 Shadow DOM 注入 -->
      <GlassTabBar
        v-model:value="active"
        class="tabbar__pill"
        aria-label="主导航"
        material="regular"
        appearance="auto"
        radius="capsule"
        :refraction="26"
        :bezel="16"
        :dispersion="0.34"
        :specular="1.1"
        light-angle="-135"
        profile="squircle"
        shadow="0 8px 26px rgba(4, 12, 22, 0.36)"
      >
        <GlassTab v-for="tab in TABS" :key="tab.to" :value="tab.to">
          <AppIcon :name="tab.icon" :size="21" />
          <span class="tabbar__label">{{ tab.label }}</span>
        </GlassTab>
      </GlassTabBar>
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
  GlassTabBar 是玻璃宿主：本身不设置 background / backdrop-filter，
  否则会成为 backdrop root 阻断折射。光学参数通过上方属性注入，
  颜色与尺寸通过下列 CSS 变量桥接到库内部样式。
*/
.tabbar__pill {
  flex: 1;
  min-width: 0;
  width: 100%;

  --glass-accent: var(--aw-accent);
  --glass-tab-selected: var(--aw-accent);
  --glass-foreground: var(--aw-text-mute);
  --glass-tab-bar-height: 58px;
  --glass-selector-padding: 5px;
  --glass-item-gap: 2px;
  --gl-item-icon: 21px;
  /* iOS 27 深色模式：选中态底色比玻璃更暗，而非更亮 */
  --glass-tab-selection: color-mix(in srgb, var(--aw-accent) 14%, rgba(3, 10, 18, 0.66));
}

[data-theme='light'] .tabbar__pill {
  --glass-tab-selection: color-mix(in srgb, var(--aw-accent) 12%, rgba(255, 255, 255, 0.82));
}

@media (max-width: 900px) {
  .tabbar {
    display: block;
  }
}

/* 四个 Tab 后空间充足，极窄屏仍保留文字标签，仅略微压低高度 */
@media (max-width: 380px) {
  .tabbar__pill {
    --glass-tab-bar-height: 54px;
  }
}
</style>
