<script setup>
import { nextTick, onMounted, ref, watch } from 'vue'

import AppButton from '@/components/common/AppButton.vue'
import { useTerminalStore } from '@/stores/terminal'

const terminal = useTerminalStore()

const input = ref('')
const isPowershell = ref(false)
const outputEl = ref(null)
const inputEl = ref(null)

const QUICK_COMMANDS = [
  { label: '系统信息', cmd: 'systeminfo' },
  { label: '网络配置', cmd: 'ipconfig /all' },
  { label: '进程列表', cmd: 'tasklist' },
  { label: '端口监控', cmd: 'netstat -ano' },
  { label: '磁盘空间', cmd: 'wmic logicaldisk get size,freespace,caption' },
  { label: '清屏', cmd: 'cls' }
]

const PS_QUICK = [
  { label: 'CPU 排序', cmd: 'Get-Process | Sort-Object CPU -Descending | Select-Object -First 10' },
  { label: '服务列表', cmd: 'Get-Service | Where-Object {$_.Status -eq "Running"}' },
  { label: '磁盘状态', cmd: 'Get-Disk | Select-Object Number,Size,HealthStatus' },
  { label: '系统日志', cmd: 'Get-EventLog -LogName System -Newest 15' }
]

async function scrollToBottom() {
  await nextTick()
  if (outputEl.value) {
    outputEl.value.scrollTop = outputEl.value.scrollHeight
  }
}

async function submit() {
  const cmd = input.value
  if (!cmd.trim()) return
  input.value = ''
  await terminal.run(cmd, isPowershell.value)
  scrollToBottom()
}

function useQuick(cmd) {
  input.value = cmd
  inputEl.value?.focus()
}

function onKeydown(event) {
  if (event.key === 'Enter') {
    event.preventDefault()
    submit()
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    const value = terminal.navigateHistory('up')
    if (value) input.value = value
  } else if (event.key === 'ArrowDown') {
    event.preventDefault()
    const value = terminal.navigateHistory('down')
    input.value = value
  } else if (event.key === 'Tab') {
    event.preventDefault()
    const partial = input.value.trim().toLowerCase()
    const pool = ['dir', 'cd', 'mkdir', 'del', 'ipconfig', 'ping', 'netstat', 'tasklist', 'systeminfo', 'cls']
    const hits = pool.filter(c => c.startsWith(partial))
    if (hits.length === 1) {
      input.value = hits[0]
    } else if (hits.length > 1) {
      terminal.addLine(hits.join('    '), 'info')
      scrollToBottom()
    }
  }
}

watch(
  () => terminal.lines.length,
  () => scrollToBottom()
)

onMounted(() => {
  terminal.addLine('Atlantis Watcher 终端 · 支持 CMD 与 PowerShell', 'ok')
  terminal.addLine('快捷键: ↑/↓ 浏览历史 · Tab 补全', 'muted')
  terminal.addLine('─'.repeat(52), 'muted')
  scrollToBottom()
})
</script>

<template>
  <div class="view">
    <div class="terminal">
      <div ref="outputEl" class="terminal__out aw-scroll">
        <div
          v-for="line in terminal.lines"
          :key="line.id"
          class="terminal__line"
          :class="`terminal__line--${line.type}`"
        >
          {{ line.text }}
        </div>
      </div>

      <form class="terminal__form" @submit.prevent="submit">
        <span class="terminal__prompt">{{ isPowershell ? 'PS' : '>' }}</span>
        <input
          ref="inputEl"
          v-model="input"
          class="terminal__input"
          type="text"
          placeholder="输入命令后回车执行…"
          autocomplete="off"
          spellcheck="false"
          aria-label="命令输入"
          @keydown="onKeydown"
        />
        <label class="check terminal__ps">
          <input v-model="isPowershell" type="checkbox" />
          <span>PowerShell</span>
        </label>
        <AppButton variant="ghost" size="sm" icon-only icon="trash" title="清屏" @click="terminal.clear()" />
      </form>
    </div>

    <div class="quick">
      <div class="quick__group">
        <span class="aw-label">CMD 常用</span>
        <div class="quick__list">
          <button v-for="q in QUICK_COMMANDS" :key="q.cmd" class="quick__chip" @click="useQuick(q.cmd)">
            {{ q.label }}
          </button>
        </div>
      </div>

      <div class="quick__group">
        <span class="aw-label">PowerShell 常用</span>
        <div class="quick__list">
          <button v-for="q in PS_QUICK" :key="q.cmd" class="quick__chip quick__chip--ps" @click="useQuick(q.cmd)">
            {{ q.label }}
          </button>
        </div>
      </div>

      <div class="toolbar__spacer" />

      <AppButton variant="ghost" size="sm" icon="download" @click="terminal.exportHistory()">
        导出记录
      </AppButton>
    </div>
  </div>
</template>

<style scoped>
.view {
  display: flex;
  flex-direction: column;
  gap: var(--aw-space-3);
  height: 100%;
  min-height: 0;
}

.terminal {
  flex: 1;
  min-height: 320px;
}

.terminal__ps {
  font-size: var(--aw-text-xs);
  flex-shrink: 0;
}

.quick {
  display: flex;
  flex-direction: column;
  gap: var(--aw-space-3);
  padding: var(--aw-space-3);
  background: var(--aw-panel);
  border: 1px solid var(--aw-line);
  border-radius: var(--aw-radius-lg);
}

.quick__group {
  display: flex;
  align-items: baseline;
  gap: var(--aw-space-3);
  flex-wrap: wrap;
}

.quick__list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--aw-space-2);
}

.quick__chip {
  padding: 3px var(--aw-space-3);
  font-family: var(--aw-font-mono);
  font-size: var(--aw-text-2xs);
  color: var(--aw-text-dim);
  background: var(--aw-panel-hi);
  border: 1px solid var(--aw-line);
  border-radius: var(--aw-radius-xs);
  transition: all var(--aw-dur-fast) var(--aw-ease);
}

.quick__chip:hover {
  border-color: var(--aw-accent-line);
  color: var(--aw-accent);
}

.quick__chip--ps {
  color: var(--aw-info);
}

.quick__chip--ps:hover {
  border-color: var(--aw-info);
  color: var(--aw-info);
}

/* --------------------------------------------------------------------------
   iOS 26 移动端：快捷命令改为可横向滚动的胶囊组（类似 iOS 工具栏）
   -------------------------------------------------------------------------- */
@media (max-width: 900px) {
  .view {
    gap: var(--aw-space-2);
  }

  .terminal {
    min-height: 0;
    border-radius: var(--aw-radius-xl);
  }

  .quick {
    border-radius: var(--aw-radius-xl);
    background: var(--aw-panel-hi);
    padding: var(--aw-space-3) 0;
    gap: var(--aw-space-2);
  }

  .quick__group {
    flex-direction: column;
    align-items: stretch;
    gap: var(--aw-space-2);
    padding: 0 var(--aw-space-4);
  }

  .quick__list {
    flex-wrap: nowrap;
    overflow-x: auto;
    scroll-snap-type: x proximity;
    /* 隐藏滚动条 */
    scrollbar-width: none;
    margin: 0 calc(-1 * var(--aw-space-4));
    padding: 0 var(--aw-space-4);
  }

  .quick__list::-webkit-scrollbar {
    display: none;
  }

  .quick__chip {
    flex-shrink: 0;
    scroll-snap-align: start;
    /* iOS 风格：胶囊形 */
    border-radius: var(--aw-radius-pill);
    padding: 6px var(--aw-space-3);
    font-size: var(--aw-text-xs);
  }
}
</style>
