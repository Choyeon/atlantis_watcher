<script setup>
import { onMounted, ref } from 'vue'
import BrandMark from '@/components/common/BrandMark.vue'
import AppButton from '@/components/common/AppButton.vue'
import { scanLanHosts, getLocalIPs } from '@/utils/lanScan'

/**
 * 首次连接引导
 *
 * 仅在「独立客户端」场景出现（APK / 桌面壳）——
 * 此时前端资源打包在应用内，页面来源是 https://localhost，
 * 无法直接访问运行 Atlantis Watcher 的主机。
 *
 * 浏览器直接访问 http://主机:26541 时同源可用，跳过本流程。
 *
 * 流程：
 *   1. 嗅探局域网，找开着 26541 且响应 Atlantis Watcher 健康检查的主机
 *   2. 找到 → 自动配置并进入应用
 *   3. 超时未找到 → 停在引导页，可手动输入地址或重试
 */
const emit = defineEmits(['connected'])

const HOST_STORAGE_KEY = 'atlantis-host'

const phase = ref('hidden') // hidden | idle | scanning | found | failed
const progress = ref({ scanned: 0, total: 0 })
const foundHost = ref('')
const manualHost = ref('')
const localIPs = ref([])

/** 是否处于独立客户端环境（页面来源不是真实主机） */
function isStandalone() {
  // Capacitor Android 用 https://localhost 提供本地资源
  const origin = window.location.origin
  return (
    origin === 'https://localhost' ||
    origin === 'capacitor://localhost' ||
    origin === 'http://localhost' ||
    origin.startsWith('capacitor://')
  )
}

/** 读取已保存的主机地址 */
function readSavedHost() {
  try {
    return (localStorage.getItem(HOST_STORAGE_KEY) || '').replace(/\/$/, '')
  } catch {
    return ''
  }
}

async function runScan() {
  phase.value = 'scanning'
  progress.value = { scanned: 0, total: 0 }

  const saved = readSavedHost()
  const result = await scanLanHosts({
    // 已保存的地址优先探测，命中最快
    extraCandidates: saved ? [saved.replace(/^https?:\/\//i, '')] : [],
    onProgress: (_hit, scanned, total) => {
      progress.value = { scanned, total }
    }
  })

  if (result.host) {
    foundHost.value = result.host
    phase.value = 'found'
    applyHost(result.host)
  } else {
    phase.value = 'failed'
  }
}

/** 写入主机地址并通知上层重连 */
function applyHost(host) {
  const normalized = host.replace(/\/$/, '')
  try {
    localStorage.setItem(HOST_STORAGE_KEY, normalized)
  } catch {
    /* 忽略存储失败 */
  }
  emit('connected', normalized)
}

function useManual() {
  const raw = manualHost.value.trim()
  if (!raw) return
  const url = /^https?:\/\//i.test(raw) ? raw : `http://${raw}`
  applyHost(url)
}

onMounted(async () => {
  if (!isStandalone()) {
    // 同源部署：无需配置，直接放行（隐藏引导页，避免闪现）
    phase.value = 'hidden'
    emit('connected', readSavedHost())
    return
  }

  localIPs.value = await getLocalIPs()

  // 已有保存的主机 → 直接用
  const saved = readSavedHost()
  if (saved) {
    applyHost(saved)
    phase.value = 'found'
    return
  }

  await runScan()
})
</script>

<template>
  <div v-if="phase === 'scanning' || phase === 'failed'" class="guide">
    <div class="guide__card">
      <div class="guide__mark">
        <BrandMark :size="60" title="Atlantis Watcher" />
      </div>

      <h1 class="guide__title">ATLANTIS WATCHER</h1>

      <!-- 扫描中 -->
      <template v-if="phase === 'scanning'">
        <p class="guide__status">正在搜索局域网中的主机…</p>
        <div class="guide__bar">
          <span
            class="guide__bar-fill"
            :style="{
              width: progress.total
                ? `${Math.round((progress.scanned / progress.total) * 100)}%`
                : '8%'
            }"
          />
        </div>
        <p class="guide__hint">
          已探测 {{ progress.scanned }} / {{ progress.total }} 个地址
        </p>
      </template>

      <!-- 失败 -->
      <template v-else-if="phase === 'failed'">
        <p class="guide__status guide__status--warn">未找到运行中的主机</p>
        <p class="guide__hint">
          请确认目标电脑已启动 Atlantis Watcher，且与本机在同一局域网。
        </p>

        <div class="guide__field">
          <input
            v-model="manualHost"
            class="input input--mono"
            type="text"
            placeholder="192.168.1.100:26541"
            @keydown.enter="useManual"
          />
        </div>

        <div class="guide__actions">
          <AppButton variant="ghost" @click="runScan">重新扫描</AppButton>
          <AppButton variant="primary" @click="useManual">连接</AppButton>
        </div>

        <p v-if="localIPs.length" class="guide__hint guide__hint--dim">
          本机地址：{{ localIPs.join('、') }}
        </p>
      </template>
    </div>
  </div>
</template>

<style scoped>
.guide {
  position: fixed;
  inset: 0;
  z-index: 400;
  display: grid;
  place-items: center;
  padding: var(--aw-space-5);
  background: var(--aw-deep);
}

.guide__card {
  width: min(380px, 100%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--aw-space-3);
  text-align: center;
}

.guide__mark {
  display: grid;
  place-items: center;
  width: 60px;
  height: 60px;
  margin: 0 auto var(--aw-space-4);
}

.guide__title {
  margin: 0;
  font-family: var(--aw-font-mono);
  font-size: 13px;
  font-weight: 500;
  letter-spacing: 0.22em;
  color: var(--aw-accent);
}

.guide__status {
  margin: 0;
  font-size: var(--aw-text-sm);
  color: var(--aw-text-dim);
}

.guide__status--warn {
  color: var(--aw-warn, #f5b642);
}

.guide__bar {
  width: 100%;
  height: 3px;
  border-radius: 2px;
  background: var(--aw-line);
  overflow: hidden;
}

.guide__bar-fill {
  display: block;
  height: 100%;
  background: var(--aw-accent);
  transition: width 320ms var(--aw-ease);
}

.guide__hint {
  margin: 0;
  font-size: var(--aw-text-2xs);
  line-height: 1.7;
  color: var(--aw-text-mute);
}

.guide__hint--dim {
  opacity: 0.7;
}

.guide__field {
  width: 100%;
  margin-top: var(--aw-space-2);
}

.guide__actions {
  display: flex;
  gap: var(--aw-space-2);
}
</style>
