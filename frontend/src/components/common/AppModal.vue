<script setup>
import { onBeforeUnmount, onMounted } from 'vue'
import AppIcon from './AppIcon.vue'

/**
 * 弹窗 — iOS 26 规范
 *
 * 移动端：从底部升起的 Sheet（抽屉），顶部有拖拽指示条，
 *         背景内容随之缩小并变暗（iOS 26 的 modal presentation）
 * 桌面端：居中对话框（保持高信息密度）
 */
const props = defineProps({
  title: { type: String, default: '' },
  subtitle: { type: String, default: '' },
  icon: { type: String, default: '' },
  size: { type: String, default: 'md' }, // md | wide | full
  closable: { type: Boolean, default: true }
})

const emit = defineEmits(['close'])

function onKeydown(event) {
  if (event.key === 'Escape' && props.closable) {
    emit('close')
  }
}

onMounted(() => {
  document.addEventListener('keydown', onKeydown)
  document.body.style.overflow = 'hidden'
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeydown)
  document.body.style.overflow = ''
})
</script>

<template>
  <div class="modal-backdrop" @click.self="closable && emit('close')">
    <div
      class="modal"
      :class="{ 'modal--wide': size === 'wide', 'modal--full': size === 'full' }"
      role="dialog"
      aria-modal="true"
    >
      <!-- iOS Sheet 拖拽指示条 -->
      <div class="modal__grip" aria-hidden="true" />

      <header v-if="title" class="modal__head">
        <div class="modal__heading">
          <h2 class="modal__title">{{ title }}</h2>
          <p v-if="subtitle" class="modal__subtitle">{{ subtitle }}</p>
        </div>
        <button
          v-if="closable"
          class="modal__close"
          aria-label="关闭"
          @click="emit('close')"
        >
          <AppIcon name="x" :size="15" />
        </button>
      </header>

      <div class="modal__body" :class="{ 'modal__body--flush': size === 'full' }">
        <slot />
      </div>

      <footer v-if="$slots.footer" class="modal__foot">
        <slot name="footer" />
      </footer>
    </div>
  </div>
</template>

<style scoped>
.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 200;
  display: grid;
  place-items: center;
  padding: var(--aw-space-4);
  background: var(--aw-scrim);
  backdrop-filter: blur(3px);
  -webkit-backdrop-filter: blur(3px);
  animation: modal-fade-in var(--aw-dur) var(--aw-ease);
}

@keyframes modal-fade-in {
  from {
    opacity: 0;
  }
}

.modal {
  width: 100%;
  max-width: 460px;
  max-height: calc(100dvh - 2 * var(--aw-space-4));
  display: flex;
  flex-direction: column;
  background: var(--aw-panel);
  border: 1px solid var(--aw-line-hi);
  border-radius: var(--aw-radius-lg);
  box-shadow: var(--aw-shadow-lg);
  overflow: hidden;
  animation: modal-rise var(--aw-dur) var(--aw-ease-out);
}

@keyframes modal-rise {
  from {
    opacity: 0;
    transform: translateY(10px) scale(0.985);
  }
}

.modal--wide {
  max-width: 860px;
}

.modal--full {
  max-width: min(1240px, 96vw);
  height: calc(100dvh - 2 * var(--aw-space-4));
}

/* 拖拽指示条：桌面端隐藏 */
.modal__grip {
  display: none;
}

.modal__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--aw-space-3);
  padding: var(--aw-space-4);
  border-bottom: 1px solid var(--aw-line);
  background: var(--aw-panel-hi);
}

.modal__heading {
  min-width: 0;
}

.modal__title {
  font-size: var(--aw-text-md);
  font-weight: 600;
  color: var(--aw-text);
}

.modal__subtitle {
  font-size: var(--aw-text-xs);
  color: var(--aw-text-mute);
  margin-top: 2px;
}

.modal__close {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  flex-shrink: 0;
  border-radius: 50%;
  background: var(--aw-raised);
  color: var(--aw-text-mute);
  transition: all var(--aw-dur-fast) var(--aw-ease);
}

.modal__close:hover {
  background: var(--aw-danger-ghost);
  color: var(--aw-danger);
}

.modal__body {
  padding: var(--aw-space-4);
  overflow: auto;
  flex: 1;
}

.modal__body--flush {
  padding: 0;
}

.modal__foot {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--aw-space-2);
  padding: var(--aw-space-3) var(--aw-space-4);
  border-top: 1px solid var(--aw-line);
  background: var(--aw-panel-hi);
}

/* --------------------------------------------------------------------------
   iOS 26 移动端：底部 Sheet
   -------------------------------------------------------------------------- */
@media (max-width: 900px) {
  .modal-backdrop {
    place-items: end stretch;
    padding: 0;
  }

  .modal {
    max-width: none;
    width: 100%;
    max-height: 92dvh;
    height: auto;
    border-radius: var(--aw-radius-xl) var(--aw-radius-xl) 0 0;
    border-bottom: none;
    animation: sheet-rise 340ms var(--aw-ease-out);
  }

  @keyframes sheet-rise {
    from {
      transform: translateY(100%);
    }
  }

  .modal--full {
    height: 92dvh;
  }

  /* 拖拽指示条 */
  .modal__grip {
    display: block;
    width: 36px;
    height: 5px;
    border-radius: 3px;
    background: var(--aw-line-hi);
    margin: var(--aw-space-2) auto 0;
    flex-shrink: 0;
  }

  .modal__head {
    padding: var(--aw-space-3) var(--aw-space-4);
  }

  .modal__body {
    padding: var(--aw-space-4);
    /* 适配底部安全区 */
    padding-bottom: calc(var(--aw-space-4) + env(safe-area-inset-bottom));
  }

  .modal__foot {
    padding: var(--aw-space-3) var(--aw-space-4);
    padding-bottom: calc(var(--aw-space-3) + env(safe-area-inset-bottom));
    /* Sheet 内按钮贴底更符合 iOS 习惯 */
    position: sticky;
    bottom: 0;
  }
}
</style>
