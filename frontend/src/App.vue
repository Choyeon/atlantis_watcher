<script setup>
import { onMounted, ref } from 'vue'
import AppSidebar from '@/components/layout/AppSidebar.vue'
import AppTopbar from '@/components/layout/AppTopbar.vue'
import AppTabbar from '@/components/layout/AppTabbar.vue'
import ToastHost from '@/components/common/ToastHost.vue'
import HostSettings from '@/components/common/HostSettings.vue'
import ConnectGuide from '@/components/common/ConnectGuide.vue'
import { useSystemStore } from '@/stores/system'
import { useWebSocket } from '@/composables/useWebSocket'

const systemStore = useSystemStore()
const hostSettings = ref(null)

/**
 * 独立客户端（APK / 桌面壳）需先完成主机嗅探，
 * 在此之前不建立 WebSocket、不拉数据 —— 否则会请求到 https://localhost。
 */
const ready = ref(false)

// 实时监控流：/ws/monitor 每 2 秒推送一次系统指标
// 延迟连接：主机地址确定后才建立连接
const monitor = useWebSocket('/ws/monitor', {
  autoConnect: false,
  onJson: data => {
    if (data?.error) {
      systemStore.setConnected(false)
      return
    }
    systemStore.applyLive(data)
    systemStore.setConnected(true)
  },
  onClose: () => systemStore.setConnected(false)
})

onMounted(() => {
  // 数据加载延后到主机确定之后（handleConnected 内触发）
})

/** 主机确定后重连并加载数据 */
async function handleConnected() {
  ready.value = true
  monitor.connect()
  await systemStore.loadInfo()
  await systemStore.loadProcesses()
}

/** 切换主机后重新拉取数据 */
async function handleReconnect() {
  monitor.disconnect()
  monitor.connect()
  await systemStore.loadInfo()
  await systemStore.loadProcesses()
}
</script>

<template>
  <div class="shell">
    <ConnectGuide v-if="!ready" @connected="handleConnected" />

    <template v-else>
      <div class="shell__body">
        <AppSidebar />

        <div class="shell__main">
          <AppTopbar />

          <main class="shell__content aw-scroll">
            <RouterView v-slot="{ Component }">
              <Transition name="aw-fade" mode="out-in">
                <component :is="Component" />
              </Transition>
            </RouterView>
          </main>
        </div>
      </div>

      <AppTabbar />
      <ToastHost />
    </template>

    <HostSettings ref="hostSettings" @reconnect="handleReconnect" />
  </div>
</template>

<style scoped>
.shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  height: 100dvh;
  overflow: hidden;
}

.shell__body {
  flex: 1;
  min-height: 0;
  display: flex;
  overflow: hidden;
}

.shell__main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.shell__content {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  position: relative;
  padding: var(--aw-space-5);
}

@media (max-width: 900px) {
  .shell__content {
    padding: var(--aw-space-3);
    /* 为悬浮玻璃导航条预留空间 + iOS 底部安全区 */
    padding-bottom: calc(96px + env(safe-area-inset-bottom));
    /* iOS 风格滚动回弹 */
    -webkit-overflow-scrolling: touch;
    overscroll-behavior-y: contain;
  }
}
</style>
