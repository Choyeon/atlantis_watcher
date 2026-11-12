<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import AppPanel from '@/components/common/AppPanel.vue'
import AppIcon from '@/components/common/AppIcon.vue'
import AppButton from '@/components/common/AppButton.vue'
import AppModal from '@/components/common/AppModal.vue'
import AppEmpty from '@/components/common/AppEmpty.vue'
import { useSystemStore } from '@/stores/system'
import { useToastStore } from '@/stores/toast'
import { killProcess } from '@/api/system'
import { formatPercent, processStatusLevel } from '@/utils/format'

const systemStore = useSystemStore()
const toast = useToastStore()

const keyword = ref('')
const killTarget = ref(null)
const killing = ref(false)
const loading = ref(false)
const autoRefresh = ref(false)
const forceKill = ref(false)
const sortKey = ref('cpu_percent')

const SORT_OPTIONS = [
  { value: 'cpu_percent', label: 'CPU 占用' },
  { value: 'memory_percent', label: '内存占用' },
  { value: 'name', label: '进程名称' },
  { value: 'pid', label: 'PID' }
]

let refreshTimer = null

watch(autoRefresh, enabled => {
  clearInterval(refreshTimer)
  refreshTimer = enabled
    ? setInterval(() => systemStore.loadProcesses(), 5000)
    : null
})

onMounted(async () => {
  if (!systemStore.processes.length) {
    loading.value = true
    await systemStore.loadProcesses()
    loading.value = false
  }
})

onBeforeUnmount(() => clearInterval(refreshTimer))

const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  let list = systemStore.processes
  if (kw) list = list.filter(p => p.name.toLowerCase().includes(kw) || String(p.pid) === kw)

  const key = sortKey.value
  return [...list].sort((a, b) => {
    if (key === 'name') return String(a.name).localeCompare(String(b.name))
    if (key === 'pid') return a.pid - b.pid
    return (b[key] ?? 0) - (a[key] ?? 0)
  })
})

function requestKill(proc) {
  forceKill.value = false
  killTarget.value = proc
}

async function confirmKill() {
  const proc = killTarget.value
  if (!proc) return
  killing.value = true
  try {
    const res = await killProcess(proc.pid, forceKill.value)
    toast.success(res?.message || `进程 ${proc.name} 已终止`)
    killTarget.value = null
    forceKill.value = false
    await systemStore.loadProcesses()
  } catch (err) {
    toast.error(`终止失败: ${err.message}`)
  } finally {
    killing.value = false
  }
}
</script>

<template>
  <div class="view">
    <AppPanel title="进程管理" icon="layers">
      <template #icon><AppIcon name="layers" :size="15" /></template>
      <template #actions>
        <span v-if="!loading" class="chip chip--accent">{{ filtered.length }} / {{ systemStore.processes.length }}</span>
        <span v-else class="chip">加载中</span>
        <select v-model="sortKey" class="input sort-select" aria-label="进程排序">
          <option v-for="opt in SORT_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
        </select>
        <button
          type="button"
          class="chip chip--action"
          :class="{ 'chip--accent': autoRefresh }"
          @click="autoRefresh = !autoRefresh"
        >
          自动刷新 {{ autoRefresh ? 'ON' : 'OFF' }}
        </button>
        <AppButton variant="ghost" size="sm" icon="refresh" @click="systemStore.loadProcesses()">刷新</AppButton>
      </template>

      <div class="toolbar" style="margin-bottom: var(--aw-space-3)">
        <div class="search">
          <AppIcon name="search" :size="14" class="search__icon" />
          <input
            v-model="keyword"
            class="input search__input"
            type="search"
            placeholder="搜索进程名称或 PID…"
            aria-label="搜索进程"
          />
        </div>
      </div>

      <div v-if="loading" class="table-wrap" style="max-height: 60vh">
        <table class="table">
          <tbody>
            <tr v-for="i in 10" :key="i">
              <td><div class="skeleton" style="height: 11px; width: 60%" /></td>
              <td><div class="skeleton" style="height: 11px; width: 40px" /></td>
              <td><div class="skeleton" style="height: 11px; width: 100%" /></td>
              <td><div class="skeleton" style="height: 11px; width: 100%" /></td>
              <td><div class="skeleton" style="height: 11px; width: 50px" /></td>
              <td><div class="skeleton" style="height: 20px; width: 52px" /></td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-else-if="filtered.length" class="table-wrap" style="max-height: 60vh">
        <table class="table">
          <thead>
            <tr>
              <th>进程名称</th>
              <th style="width: 90px">PID</th>
              <th style="width: 130px">CPU</th>
              <th style="width: 130px">内存</th>
              <th style="width: 96px">状态</th>
              <th class="col-actions" style="width: 84px">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="proc in filtered" :key="proc.pid">
              <td class="proc-name" :title="proc.name">{{ proc.name }}</td>
              <td class="num">{{ proc.pid }}</td>
              <td>
                <div class="cell-meter">
                  <div class="meter">
                    <div
                      class="meter__fill"
                      :class="proc.cpu_percent >= 50 ? 'meter__fill--warn' : 'meter__fill--accent'"
                      :style="{ width: `${Math.min(proc.cpu_percent, 100)}%` }"
                    />
                  </div>
                  <span class="cell-meter__val aw-mono">{{ formatPercent(proc.cpu_percent) }}%</span>
                </div>
              </td>
              <td>
                <div class="cell-meter">
                  <div class="meter">
                    <div
                      class="meter__fill meter__fill--info"
                      :style="{ width: `${Math.min(proc.memory_percent, 100)}%` }"
                    />
                  </div>
                  <span class="cell-meter__val aw-mono">{{ formatPercent(proc.memory_percent) }}%</span>
                </div>
              </td>
              <td>
                <span class="chip" :class="`chip--${processStatusLevel(proc.status)}`">
                  {{ proc.status }}
                </span>
              </td>
              <td class="col-actions">
                <AppButton variant="danger" size="sm" @click="requestKill(proc)">结束</AppButton>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <AppEmpty
        v-else
        icon="search"
        :title="keyword ? '没有匹配的进程' : '暂无进程数据'"
        :description="keyword ? `未找到名称或 PID 包含「${keyword}」的进程` : '点击右上角刷新重新加载'"
      >
        <AppButton v-if="keyword" variant="ghost" size="sm" @click="keyword = ''">清除搜索</AppButton>
      </AppEmpty>
    </AppPanel>

    <AppModal
      v-if="killTarget"
      title="确认结束进程"
      subtitle="强制终止可能导致数据丢失"
      @close="killTarget = null"
    >
      <p class="confirm-text">
        即将结束进程
        <strong class="aw-mono">{{ killTarget.name }}</strong>
        （PID {{ killTarget.pid }}）。该操作无法撤销。
      </p>
      <p v-if="killTarget.create_time" class="confirm-meta aw-mono">
        启动时间 {{ killTarget.create_time }}
      </p>
      <label class="confirm-force">
        <input v-model="forceKill" type="checkbox" />
        <span>强制结束（直接 kill，可能导致未保存数据丢失）</span>
      </label>
      <template #footer>
        <AppButton variant="ghost" :disabled="killing" @click="killTarget = null">取消</AppButton>
        <AppButton variant="danger" :loading="killing" @click="confirmKill">确认结束</AppButton>
      </template>
    </AppModal>
  </div>
</template>

<style scoped>
.view {
  display: flex;
  flex-direction: column;
  gap: var(--aw-space-4);
}

.search {
  position: relative;
  flex: 1;
  max-width: 380px;
}

.search__icon {
  position: absolute;
  left: var(--aw-space-3);
  top: 50%;
  transform: translateY(-50%);
  color: var(--aw-text-faint);
  pointer-events: none;
}

.search__input {
  padding-left: 32px;
}

.proc-name {
  font-weight: 500;
  color: var(--aw-text);
  max-width: 320px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cell-meter {
  display: flex;
  align-items: center;
  gap: var(--aw-space-2);
}

.cell-meter .meter {
  flex: 1;
  min-width: 40px;
}

.cell-meter__val {
  font-size: var(--aw-text-2xs);
  color: var(--aw-text-mute);
  width: 42px;
  text-align: right;
  flex-shrink: 0;
}

.confirm-text {
  font-size: var(--aw-text-base);
  color: var(--aw-text-dim);
  line-height: 1.7;
}

.confirm-meta {
  margin-top: calc(var(--aw-space-2) * -1);
  font-size: var(--aw-text-2xs);
  color: var(--aw-text-faint);
}

.confirm-force {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: var(--aw-space-3);
  font-size: var(--aw-text-xs);
  color: var(--aw-text-dim);
  cursor: pointer;
}

.sort-select {
  width: auto;
  min-width: 112px;
  height: 30px;
  font-size: var(--aw-text-xs);
}

.chip--action {
  cursor: pointer;
  border: 1px solid var(--aw-line);
  background: transparent;
  color: var(--aw-text-mute);
  font: inherit;
  white-space: nowrap;
}

.chip--action:hover {
  color: var(--aw-accent);
  border-color: var(--aw-accent-ghost);
}

@media (max-width: 720px) {
  .proc-name {
    max-width: 130px;
  }
}

/* --------------------------------------------------------------------------
   iOS 26 移动端：表格转为分组列表
   -------------------------------------------------------------------------- */
@media (max-width: 900px) {
  .view {
    gap: var(--aw-space-3);
  }

  .search__input {
    height: 38px;
    border-radius: var(--aw-radius-xl);
  }

  /* 表格转为卡片式行，规避横向滚动 */
  .table thead {
    display: none;
  }

  .table,
  .table tbody,
  .table tr,
  .table td {
    display: block;
    width: 100%;
  }

  .table tbody tr {
    position: relative;
    padding: var(--aw-space-3) var(--aw-space-4);
    border-bottom: 1px solid var(--aw-line-soft);
  }

  .table tbody tr:last-child {
    border-bottom: none;
  }

  .table tbody td {
    padding: 0;
    border: none;
  }

  /* 进程名独占一行 */
  .table tbody td:first-child {
    margin-bottom: var(--aw-space-2);
  }

  .proc-name {
    max-width: none;
    font-size: var(--aw-text-base);
    white-space: normal;
  }

  /* CPU / 内存 并排显示 */
  .table tbody td:nth-child(3),
  .table tbody td:nth-child(4) {
    display: inline-block;
    width: 48%;
    vertical-align: middle;
    padding-right: var(--aw-space-2);
  }

  .table tbody td:nth-child(5) {
    display: inline-block;
    vertical-align: middle;
    padding-left: var(--aw-space-2);
  }

  /* 操作按钮移到右上角 */
  .table .col-actions {
    position: absolute;
    top: var(--aw-space-3);
    right: var(--aw-space-4);
    width: auto;
  }

  .cell-meter .meter {
    min-width: 30px;
  }

  .cell-meter__val {
    width: 38px;
    font-size: var(--aw-text-2xs);
  }
}
</style>
