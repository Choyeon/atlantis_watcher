<script setup>
import { computed } from 'vue'
import AppIcon from '@/components/common/AppIcon.vue'

/**
 * 仪表读数卡
 * 与旧版「图标+大圆角卡片+渐变」不同：
 * 读数用等宽表格数字，数值跳动时不抖动；左侧一道状态色条表意。
 */
const props = defineProps({
  label: { type: String, required: true },
  icon: { type: String, default: 'activity' },
  value: { type: [Number, String], default: 0 },
  unit: { type: String, default: '%' },
  percent: { type: [Number, String], default: null },
  level: { type: String, default: 'accent' }, // accent | ok | warn | danger | info
  meta: { type: Array, default: () => [] }
})

const LEVEL_COLOR = {
  accent: 'var(--aw-accent)',
  ok: 'var(--aw-ok)',
  warn: 'var(--aw-warn)',
  danger: 'var(--aw-danger)',
  info: 'var(--aw-info)'
}

const LEVEL_GHOST = {
  accent: 'var(--aw-accent-ghost)',
  ok: 'var(--aw-ok-ghost)',
  warn: 'var(--aw-warn-ghost)',
  danger: 'var(--aw-danger-ghost)',
  info: 'var(--aw-info-ghost)'
}

const color = computed(() => LEVEL_COLOR[props.level] || LEVEL_COLOR.accent)
const ghost = computed(() => LEVEL_GHOST[props.level] || LEVEL_GHOST.accent)
const width = computed(() => {
  const p = Number(props.percent)
  return Number.isFinite(p) ? Math.max(0, Math.min(100, p)) : null
})
</script>

<template>
  <article class="gauge" :style="{ '--gauge-color': color, '--gauge-ghost': ghost }">
    <div class="gauge__head">
      <span class="gauge__icon">
        <AppIcon :name="icon" :size="15" />
      </span>
      <span class="aw-label">{{ label }}</span>
    </div>

    <div class="gauge__value">
      <span class="gauge__num">{{ value }}</span>
      <span v-if="unit" class="gauge__unit">{{ unit }}</span>
    </div>

    <div v-if="width !== null" class="meter meter--segmented">
      <div
        class="meter__fill"
        :class="`meter__fill--${level}`"
        :style="{ width: `${width}%` }"
      />
    </div>

    <div v-if="meta.length" class="gauge__meta">
      <span v-for="(item, i) in meta" :key="i">{{ item }}</span>
    </div>
  </article>
</template>

<style scoped>
/*
  iOS 26 适配：移动端改为分组列表样式 ——
  连续圆角（squircle 观感）+ 玻璃材质 + 紧凑的信息层级。
  桌面端保留仪表盘的密集读数布局。
*/
.gauge {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: var(--aw-space-3);
  padding: var(--aw-space-4);
  background: var(--aw-panel);
  border: 1px solid var(--aw-line);
  border-radius: var(--aw-radius-lg);
  overflow: hidden;
}

@media (max-width: 900px) {
  .gauge {
    gap: var(--aw-space-2);
    padding: var(--aw-space-3) var(--aw-space-4);
    /* iOS 连续圆角观感：更大的圆角半径 */
    border-radius: var(--aw-radius-xl);
    background: var(--aw-panel-hi);
  }

  .gauge__num {
    font-size: 1.625rem;
  }
}
</style>
