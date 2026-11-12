<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useToastStore } from '@/stores/toast'
import AppModal from '@/components/common/AppModal.vue'
import AppButton from '@/components/common/AppButton.vue'

/**
 * 主机连接设置
 *
 * 场景：
 *   - 浏览器访问：默认用当前站点来源，无需配置
 *   - APK 安装后：前端资源打包在 APK 内，需要指向运行 Atlantis Watcher 的主机
 *
 * 主机地址持久化在 localStorage，切换后自动重连并刷新数据。
 */
const emit = defineEmits(['reconnect'])

const toast = useToastStore()

const STORAGE_KEY = 'atlantis-host'
const open = ref(false)
const input = ref('')
const testing = ref(false)

/** 当前生效的主机地址（空 = 同源） */
const host = ref('')

onMounted(() => {  try {
    host.value = localStorage.getItem(STORAGE_KEY) || ''
  } catch {
    host.value = ''
  }
  input.value = host.value
  // 顶栏齿轮按钮触发
  window.addEventListener('aw:open-host-settings', openSettings)
})

onBeforeUnmount(() => {
  window.removeEventListener('aw:open-host-settings', openSettings)
})

function openSettings() {
  input.value = host.value
  open.value = true
}

async function testConnection() {
  const target = input.value.trim()
  if (!target) {
    toast.info('留空表示使用当前站点')
    return
  }
  const url = /^https?:\/\//i.test(target) ? target : `http://${target}`
  testing.value = true
  try {
    const ctrl = new AbortController()
    const timer = setTimeout(() => ctrl.abort(), 6000)
    const res = await fetch(`${url.replace(/\/$/, '')}/health`, { signal: ctrl.signal })
    clearTimeout(timer)
    if (res.ok) {
      const data = await res.json()
      toast.success(`连接成功 · ${data.service || 'Atlantis Watcher'}`)
    } else {
      toast.error(`连接失败（HTTP ${res.status}）`)
    }
  } catch (err) {
    toast.error(err.name === 'AbortError' ? '连接超时' : '无法连接到该地址')
  } finally {
    testing.value = false
  }
}

function save() {
  const raw = input.value.trim()
  const normalized = raw ? (raw.replace(/\/$/, '')) : ''
  host.value = normalized
  try {
    if (normalized) {
      localStorage.setItem(STORAGE_KEY, normalized)
    } else {
      localStorage.removeItem(STORAGE_KEY)
    }
  } catch {
    /* 忽略存储失败 */
  }
  open.value = false
  toast.success(normalized ? `已切换到 ${normalized}` : '已恢复同源连接')
  emit('reconnect')
}

defineExpose({ openSettings })
</script>

<template>
  <AppModal
    v-if="open"
    title="主机连接"
    subtitle="指定运行 Atlantis Watcher 的电脑地址"
    @close="open = false"
  >
    <div class="field">
      <label class="field__label" for="host-input">主机地址</label>
      <input
        id="host-input"
        v-model="input"
        class="input input--mono"
        type="text"
        placeholder="192.168.1.100:26541"
        @keydown.enter="save"
      />
      <p class="aw-text-xs aw-text-mute">
        留空则使用当前访问来源。APK 安装后需填写主机地址才能连接。
      </p>
    </div>

    <template #footer>
      <AppButton variant="ghost" :loading="testing" @click="testConnection">测试连接</AppButton>
      <AppButton variant="primary" @click="save">保存</AppButton>
    </template>
  </AppModal>
</template>
