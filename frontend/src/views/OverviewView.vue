<script setup>
import { computed, onMounted, ref } from 'vue'
import GaugeCard from '@/components/monitor/GaugeCard.vue'
import AppPanel from '@/components/common/AppPanel.vue'
import AppIcon from '@/components/common/AppIcon.vue'
import AppEmpty from '@/components/common/AppEmpty.vue'
import AppButton from '@/components/common/AppButton.vue'
import { useSystemStore } from '@/stores/system'
import { formatBytes, formatSpeed, formatPercent, usageLevel } from '@/utils/format'

const systemStore = useSystemStore()
const loading = ref(false)

onMounted(async () => {
  if (!systemStore.info) {
    loading.value = true
    await systemStore.loadInfo()
    loading.value = false
  }
})

const cpuLevel = computed(() => {
  const p = systemStore.cpu.percent
  if (p >= 90) return 'danger'
  if (p >= 75) return 'warn'
  return 'ok'
})

const memLevel = computed(() => {
  const p = systemStore.memory.percent
  if (p >= 90) return 'danger'
  if (p >= 80) return 'warn'
  return 'ok'
})

const cpuFreq = computed(() => {
  const f = systemStore.cpu.frequency
  if (!f?.current) return null
  return `${(f.current / 1000).toFixed(2)} GHz`
})

const netInterfaces = computed(() => systemStore.network.interfaces.slice(0, 6))
</script>

<template>
  <div class="view">
    <!-- 首次加载骨架屏，避免空白闪烁 -->
    <template v-if="loading && !systemStore.info">
      <div class="grid-gauges">
        <div v-for="i in 4" :key="i" class="skeleton" style="height: 132px; border-radius: var(--aw-radius-lg)" />
      </div>
      <div class="grid-2">
        <div class="skeleton" style="height: 260px; border-radius: var(--aw-radius-lg)" />
        <div class="skeleton" style="height: 260px; border-radius: var(--aw-radius-lg)" />
      </div>
    </template>

    <template v-else>
      <!-- 指标区 -->
      <div class="grid-gauges">
        <GaugeCard
          label="CPU 使用率"
          icon="cpu"
          :value="formatPercent(systemStore.cpu.percent)"
          unit=""
          :percent="systemStore.cpu.percent"
          :level="cpuLevel"
          :meta="[
            `${systemStore.cpu.count || '—'} 核`,
            cpuFreq || '频率未知'
          ]"
        />

        <GaugeCard
          label="内存使用率"
          icon="memory"
          :value="formatPercent(systemStore.memory.percent)"
          unit=""
          :percent="systemStore.memory.percent"
          :level="memLevel"
          :meta="[
            `${formatBytes(systemStore.memory.used)} / ${formatBytes(systemStore.memory.total)}`,
            `可用 ${formatBytes(systemStore.memory.available)}`
          ]"
        />

        <GaugeCard
          label="网络上传"
          icon="wifi"
          :value="formatSpeed(systemStore.network.uploadSpeed).replace('/s', '')"
          unit="/s"
          :level="'info'"
          :meta="[`累计 ${formatBytes(systemStore.network.totalSent)}`]"
        />

        <GaugeCard
          label="网络下载"
          icon="download"
          :value="formatSpeed(systemStore.network.downloadSpeed).replace('/s', '')"
          unit="/s"
          :level="'accent'"
          :meta="[`累计 ${formatBytes(systemStore.network.totalRecv)}`]"
        />
      </div>

      <div class="grid-2">
        <!-- 磁盘 -->
        <AppPanel title="磁盘分区" icon="hardDrive">
          <template #icon><AppIcon name="hardDrive" :size="15" /></template>
          <template #actions>
            <AppButton variant="ghost" size="sm" icon="refresh" @click="systemStore.loadInfo()">刷新</AppButton>
          </template>

          <div v-if="systemStore.disk.length" class="disk-list">
            <div v-for="disk in systemStore.disk" :key="disk.device" class="disk-row">
              <div class="disk-row__head">
                <span class="disk-row__dev aw-mono">{{ disk.device }}</span>
                <span class="disk-row__pct aw-mono" :class="`aw-text-${usageLevel(disk.percent)}`">
                  {{ formatPercent(disk.percent) }}%
                </span>
              </div>
              <div class="meter meter--segmented">
                <div
                  class="meter__fill"
                  :class="`meter__fill--${usageLevel(disk.percent)}`"
                  :style="{ width: `${Math.min(disk.percent, 100)}%` }"
                />
              </div>
              <div class="disk-row__meta aw-mono">
                <span>{{ formatBytes(disk.used) }} 已用</span>
                <span>{{ formatBytes(disk.free) }} 可用</span>
              </div>
            </div>
          </div>

          <AppEmpty
            v-else
            icon="hardDrive"
            title="暂无磁盘信息"
            description="未能读取到分区列表，可能是权限不足"
          />
        </AppPanel>

        <!-- 系统状态 -->
        <AppPanel title="系统状态" icon="server">
          <template #icon><AppIcon name="server" :size="15" /></template>

          <dl class="kv">
            <div class="kv__row">
              <dt class="aw-label">运行时间</dt>
              <dd class="aw-mono">{{ systemStore.system.uptimeFormatted }}</dd>
            </div>
            <div class="kv__row">
              <dt class="aw-label">进程总数</dt>
              <dd class="aw-mono">{{ systemStore.system.processCount || '—' }}</dd>
            </div>
            <div class="kv__row">
              <dt class="aw-label">启动时间</dt>
              <dd class="aw-mono">
                {{ systemStore.system.bootTime ? new Date(systemStore.system.bootTime).toLocaleString('zh-CN', { hour12: false }) : '—' }}
              </dd>
            </div>
            <div class="kv__row">
              <dt class="aw-label">CPU 核心</dt>
              <dd class="aw-mono">{{ systemStore.cpu.count || '—' }} 线程</dd>
            </div>
            <div class="kv__row">
              <dt class="aw-label">Swap 使用</dt>
              <dd class="aw-mono">
                {{ formatBytes(systemStore.memory.swapTotal) }} ·
                {{ formatPercent(systemStore.memory.swapPercent) }}%
              </dd>
            </div>
          </dl>

          <div v-if="netInterfaces.length" class="net-list">
            <div class="aw-label" style="margin-bottom: var(--aw-space-2)">网络接口</div>
            <div v-for="nic in netInterfaces" :key="nic.interface + nic.ip" class="net-row">
              <span class="net-row__name">{{ nic.interface }}</span>
              <span class="net-row__ip aw-mono">{{ nic.ip }}</span>
            </div>
          </div>
        </AppPanel>
      </div>
    </template>
  </div>
</template>

<style scoped>
.view {
  display: flex;
  flex-direction: column;
  gap: var(--aw-space-4);
  max-width: 1440px;
}

.grid-gauges {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
  gap: var(--aw-space-3);
}

.grid-2 {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
  gap: var(--aw-space-4);
  align-items: start;
}

.disk-list {
  display: flex;
  flex-direction: column;
  gap: var(--aw-space-4);
}

.disk-row__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--aw-space-2);
  margin-bottom: var(--aw-space-2);
}

.disk-row__dev {
  font-size: var(--aw-text-sm);
  font-weight: 500;
  color: var(--aw-text);
}

.disk-row__pct {
  font-size: var(--aw-text-sm);
  font-weight: 600;
}

.disk-row__meta {
  display: flex;
  justify-content: space-between;
  gap: var(--aw-space-2);
  margin-top: var(--aw-space-2);
  font-size: var(--aw-text-2xs);
  color: var(--aw-text-faint);
}

.kv {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.kv__row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--aw-space-4);
  padding: var(--aw-space-2) 0;
  border-bottom: 1px solid var(--aw-line-soft);
}

.kv__row:last-child {
  border-bottom: none;
}

.kv__row dd {
  font-size: var(--aw-text-sm);
  color: var(--aw-text);
  text-align: right;
}

.net-list {
  margin-top: var(--aw-space-4);
  padding-top: var(--aw-space-3);
  border-top: 1px solid var(--aw-line);
}

.net-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--aw-space-3);
  padding: 3px 0;
  font-size: var(--aw-text-xs);
}

.net-row__name {
  color: var(--aw-text-dim);
}

.net-row__ip {
  color: var(--aw-text-mute);
  font-size: var(--aw-text-2xs);
}

/* --------------------------------------------------------------------------
   iOS 26 移动端：分组列表观感
   -------------------------------------------------------------------------- */
@media (max-width: 900px) {
  .view {
    gap: var(--aw-space-3);
  }

  .grid-gauges {
    /* 指标卡两列排布，接近 iOS 小组件网格 */
    grid-template-columns: repeat(2, 1fr);
    gap: var(--aw-space-2);
  }

  .grid-2 {
    grid-template-columns: 1fr;
    gap: var(--aw-space-3);
  }

  /* 磁盘分区：转为 iOS 风格行 */
  .disk-list {
    gap: var(--aw-space-3);
  }

  .disk-row {
    padding: var(--aw-space-2) 0;
    border-bottom: 1px solid var(--aw-line-soft);
  }

  .disk-row:last-child {
    border-bottom: none;
  }

  .disk-row__meta {
    font-size: var(--aw-text-2xs);
  }

  /* 系统状态：键值行更接近 iOS 设置列表 */
  .kv__row {
    padding: var(--aw-space-3) 0;
  }

  .kv__row dd {
    font-size: var(--aw-text-base);
  }
}
</style>
