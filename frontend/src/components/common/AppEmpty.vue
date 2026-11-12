<script setup>
import AppIcon from './AppIcon.vue'

defineProps({
  icon: { type: String, default: 'info' },
  title: { type: String, default: '' },
  description: { type: String, default: '' }
})
</script>

<template>
  <div class="empty">
    <div class="empty__icon">
      <AppIcon :name="icon" :size="30" :stroke-width="1.4" />
    </div>
    <div v-if="title" class="empty__title">{{ title }}</div>
    <p v-if="description" class="empty__desc">{{ description }}</p>
    <slot />
  </div>
</template>
