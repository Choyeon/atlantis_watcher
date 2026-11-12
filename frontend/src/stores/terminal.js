import { defineStore } from 'pinia'
import { ref } from 'vue'
import { executeCommand } from '@/api/system'

const MAX_HISTORY = 100
let lineSeq = 0

/**
 * 终端 Store
 * 修复旧版 bug：旧 terminal.js 读取 result.output，
 * 而后端 BaseResponse 把输出包在 data.output 中，导致终端永远无输出。
 */
export const useTerminalStore = defineStore('terminal', () => {
  const lines = ref([])
  const history = ref([])
  const historyIndex = ref(-1)
  const busy = ref(false)

  function addLine(text, type = 'output') {
    lines.value.push({ id: ++lineSeq, text, type })
    // 限制行数，避免长时间运行内存膨胀
    if (lines.value.length > 500) {
      lines.value.splice(0, lines.value.length - 500)
    }
  }

  function clear() {
    lines.value = []
  }

  function pushHistory(command) {
    if (!command) return
    if (history.value[history.value.length - 1] !== command) {
      history.value.push(command)
      if (history.value.length > MAX_HISTORY) history.value.shift()
    }
    historyIndex.value = history.value.length
  }

  function navigateHistory(direction) {
    if (!history.value.length) return ''
    if (direction === 'up') {
      if (historyIndex.value > 0) {
        historyIndex.value -= 1
        return history.value[historyIndex.value]
      }
    } else if (direction === 'down') {
      if (historyIndex.value < history.value.length - 1) {
        historyIndex.value += 1
        return history.value[historyIndex.value]
      }
      historyIndex.value = history.value.length
      return ''
    }
    return ''
  }

  /** 执行命令 */
  async function run(command, isPowershell = false) {
    const cmd = String(command || '').trim()
    if (!cmd || busy.value) return

    busy.value = true
    pushHistory(cmd)
    addLine(cmd, 'cmd')

    try {
      const result = await executeCommand(cmd, isPowershell)
      if (result.output) {
        addLine(result.output, result.success ? 'output' : 'err')
      }
      if (result.error) {
        addLine(result.error, 'err')
      }
      if (!result.output && !result.error) {
        addLine(result.success ? '命令执行成功（无输出）' : '命令执行失败', result.success ? 'ok' : 'err')
      }
    } catch (err) {
      addLine(`错误: ${err.message || '请求失败'}`, 'err')
    } finally {
      busy.value = false
    }
  }

  function exportHistory() {
    const text = lines.value.map(l => l.text).join('\n')
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `atlantis-terminal-${new Date().toISOString().slice(0, 10)}.txt`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }

  return {
    lines,
    history,
    historyIndex,
    busy,
    addLine,
    clear,
    pushHistory,
    navigateHistory,
    run,
    exportHistory
  }
})
