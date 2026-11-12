<script setup>
import AppIcon from './AppIcon.vue'
import { useToastStore } from '@/stores/toast'

const toast = useToastStore()

const ICONS = {
  success: 'check',
  error: 'alert',
  warning: 'alert',
  info: 'info'
}
</script>

<template>
  <div class="toasts" role="status" aria-live="polite">
    <TransitionGroup name="toast">
      <div
        v-for="item in toast.items"
        :key="item.id"
        class="toast"
        :class="`toast--${item.type}`"
      >
        <span class="toast__icon">
          <AppIcon :name="ICONS[item.type] || 'info'" :size="15" />
        </span>
        <div class="toast__body">
          <div v-if="item.title" class="toast__title">{{ item.title }}</div>
          <div class="toast__desc">{{ item.message }}</div>
        </div>
        <button class="toast__close" aria-label="关闭通知" @click="toast.dismiss(item.id)">
          <AppIcon name="x" :size="13" />
        </button>
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.toast-leave-active {
  transition: opacity 160ms ease, transform 160ms ease;
}
.toast-leave-to {
  opacity: 0;
  transform: translateX(20px);
}
</style>
