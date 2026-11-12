<script setup>
defineProps({
  title: { type: String, default: '' },
  icon: { type: String, default: '' },
  flush: { type: Boolean, default: false }
})
</script>

<template>
  <section class="panel">
    <header v-if="title || $slots.actions" class="panel__head">
      <h2 class="panel__title">
        <slot name="icon" />
        {{ title }}
      </h2>
      <div class="toolbar">
        <slot name="actions" />
      </div>
    </header>
    <div class="panel__body" :class="{ 'panel__body--flush': flush }">
      <slot />
    </div>
  </section>
</template>
