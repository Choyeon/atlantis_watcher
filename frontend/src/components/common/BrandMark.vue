<script setup>
import brandMarkUrl from '@/assets/brandMark.svg'

/**
 * 品牌标记「深渊网关」——与 exe 图标、favicon 和 APK 启动图标共用同一张源图。
 * 资源由 tools/brand_assets.py 生成，避免各端漂移。
 *
 * variant:
 *   full  含深海底板（用于浅色或中性背景、连接引导页）
 *   mark  网关图标（用于已有深色/玻璃容器）
 * mono:   单色兼容标记，保留接口以兼容既有调用方
 */
const props = defineProps({
  size: { type: [Number, String], default: 24 },
  variant: { type: String, default: 'full' },
  mono: { type: Boolean, default: false },
  title: { type: String, default: '' }
})

</script>

<template>
  <img
    :class="['brand-mark', { 'brand-mark--mono': props.mono }]"
    :width="size"
    :height="size"
    :role="title ? 'img' : undefined"
    :aria-label="title || undefined"
    :aria-hidden="title ? undefined : 'true'"
    :src="brandMarkUrl"
    alt=""
    decoding="async"
  >
</template>

<style scoped>
.brand-mark {
  display: block;
  flex-shrink: 0;
  object-fit: contain;
  border-radius: 22%;
}

.brand-mark--mono {
  filter: grayscale(1) brightness(0) invert(1);
}
</style>
