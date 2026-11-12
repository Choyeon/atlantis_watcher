<script setup>
import AppIcon from './AppIcon.vue'

defineProps({
  variant: { type: String, default: 'default' }, // default | primary | ghost | danger | warn
  size: { type: String, default: 'md' }, // sm | md | lg
  icon: { type: String, default: '' },
  iconOnly: { type: Boolean, default: false },
  block: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  type: { type: String, default: 'button' }
})
</script>

<template>
  <button
    :type="type"
    class="btn"
    :class="[
      variant !== 'default' ? `btn--${variant}` : '',
      size !== 'md' ? `btn--${size}` : '',
      { 'btn--icon': iconOnly, 'btn--block': block, 'btn--loading': loading }
    ]"
    :disabled="disabled || loading"
    :aria-busy="loading ? 'true' : undefined"
  >
    <AppIcon v-if="icon" :name="icon" :size="size === 'sm' ? 13 : size === 'lg' ? 17 : 15" />
    <slot />
  </button>
</template>
