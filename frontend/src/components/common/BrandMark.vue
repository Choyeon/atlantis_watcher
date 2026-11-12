<script setup>
import { computed } from 'vue'

import { BRAND_PATHS } from '@/assets/brandPaths'

/**
 * 品牌标记「声呐眼」——与 exe 图标 / favicon / APK 启动图标共用同一组几何。
 * 路径由 tools/brand_assets.py 生成，禁止在此手写图形，避免各端漂移。
 *
 * variant:
 *   full  含深海底板（用于浅色或中性背景、连接引导页）
 *   mark  透明底，瞳孔镂空（用于已有深色/玻璃容器）
 * mono:   单色，颜色跟随 currentColor（用于强调主题适配的小图标）
 */
const props = defineProps({
  size: { type: [Number, String], default: 24 },
  variant: { type: String, default: 'full' },
  mono: { type: Boolean, default: false },
  title: { type: String, default: '' }
})

const paths = computed(() => {
  if (props.mono) return BRAND_PATHS.mark
  return BRAND_PATHS[props.variant] || BRAND_PATHS.full
})

function fillOf(path) {
  if (props.mono) return path.fill ? 'currentColor' : 'none'
  return path.fill || 'none'
}

function strokeOf(path) {
  if (props.mono) return path.stroke ? 'currentColor' : 'none'
  return path.stroke || 'none'
}
</script>

<template>
  <svg
    class="brand-mark"
    :width="size"
    :height="size"
    viewBox="0 0 100 100"
    :role="title ? 'img' : undefined"
    :aria-label="title || undefined"
    :aria-hidden="title ? undefined : 'true'"
    focusable="false"
  >
    <title v-if="title">{{ title }}</title>
    <path
      v-for="(path, index) in paths"
      :key="index"
      :d="path.d"
      :fill="fillOf(path)"
      :stroke="strokeOf(path)"
      :stroke-width="path.stroke ? path.sw : 0"
      stroke-linecap="butt"
    />
  </svg>
</template>

<style scoped>
.brand-mark {
  display: block;
  flex-shrink: 0;
}
</style>
