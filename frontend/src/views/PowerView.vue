<script setup>
import { ref } from 'vue'
import AppIcon from '@/components/common/AppIcon.vue'
import AppModal from '@/components/common/AppModal.vue'
import AppButton from '@/components/common/AppButton.vue'
import { useToastStore } from '@/stores/toast'
import {
  shutdown,
  shutdownAfter,
  cancelShutdown,
  reboot,
  lockScreen,
  logout,
  hibernate,
  sleep,
  turnOffMonitor,
  turnOnMonitor
} from '@/api/system'

const toast = useToastStore()

// 待确认的电源操作
const pending = ref(null)
const scheduleOpen = ref(false)
const scheduleMinutes = ref(60)
const busy = ref(false)

const ACTIONS = [
  {
    key: 'shutdown',
    label: '立即关机',
    hint: 'shutdown /s /t 0',
    icon: 'power',
    variant: 'danger',
    danger: true,
    confirmTitle: '确认关机',
    confirmText: '系统将立即关闭，所有未保存的数据都会丢失。',
    run: () => shutdown()
  },
  {
    key: 'reboot',
    label: '重启系统',
    hint: 'shutdown /r /t 0',
    icon: 'rotate',
    variant: 'warn',
    danger: true,
    confirmTitle: '确认重启',
    confirmText: '系统将立即重启，所有运行中的程序会被中断。',
    run: () => reboot()
  },
  {
    key: 'lock',
    label: '锁定屏幕',
    hint: 'LockWorkStation',
    icon: 'lock',
    variant: 'info',
    confirmTitle: '确认锁屏',
    confirmText: '屏幕将被锁定，需要重新输入密码才能解锁。',
    run: () => lockScreen()
  },
  {
    key: 'monitor-off',
    label: '关闭显示器',
    hint: 'SC_MONITORPOWER 2',
    icon: 'monitorOff',
    variant: 'info',
    confirmTitle: '确认关闭显示器',
    confirmText: '仅熄灭屏幕，系统与后台服务继续运行。移动鼠标/键盘，或点击「点亮显示器」即可恢复；熄屏期间屏幕共享画面会变黑。',
    run: () => turnOffMonitor()
  },
  {
    // 亮屏是恢复操作，熄屏后应能一键恢复，不再弹二次确认
    key: 'monitor-on',
    label: '点亮显示器',
    hint: 'SC_MONITORPOWER -1',
    icon: 'monitorOn',
    variant: '',
    instant: true,
    run: () => turnOnMonitor()
  },
  {
    key: 'logout',
    label: '注销用户',
    hint: 'shutdown /l',
    icon: 'logout',
    variant: 'info',
    danger: true,
    confirmTitle: '确认注销',
    confirmText: '当前用户将被注销，未保存的数据会丢失。',
    run: () => logout()
  },
  {
    key: 'cancel',
    label: '取消关机',
    hint: 'shutdown /a',
    icon: 'x',
    variant: '',
    confirmTitle: '确认取消',
    confirmText: '将中止任何已计划的关机或重启任务。',
    run: () => cancelShutdown()
  },
  {
    key: 'sleep',
    label: '睡眠',
    hint: 'SetSuspendState 1',
    icon: 'moon',
    variant: '',
    confirmTitle: '确认睡眠',
    confirmText: '系统将进入睡眠模式，屏幕关闭但程序保持运行。',
    run: () => sleep()
  },
  {
    key: 'hibernate',
    label: '休眠',
    hint: 'SetSuspendState 0',
    icon: 'clock',
    variant: '',
    confirmTitle: '确认休眠',
    confirmText: '系统会将当前状态写入磁盘后进入休眠。',
    run: () => hibernate()
  }
]

async function requestAction(action) {
  // instant 动作（如点亮显示器）跳过确认弹窗，熄屏后能一键恢复
  if (action.instant) {
    await executeAction(action)
    return
  }
  pending.value = action
}

async function executeAction(action) {
  busy.value = true
  try {
    const res = await action.run()
    const ok = res?.success !== false
    toast.push(ok ? `${action.label}指令已发送` : res?.message || `${action.label}失败`, ok ? 'success' : 'error')
  } catch (err) {
    toast.error(`${action.label}失败: ${err.message}`)
  } finally {
    busy.value = false
  }
}

async function confirmAction() {
  const action = pending.value
  if (!action) return
  pending.value = null
  await executeAction(action)
}

async function confirmSchedule() {
  const minutes = Number(scheduleMinutes.value)
  if (!Number.isInteger(minutes) || minutes < 1 || minutes > 1440) {
    toast.warning('请输入 1–1440 之间的分钟数')
    return
  }
  scheduleOpen.value = false
  busy.value = true
  try {
    const res = await shutdownAfter(minutes * 60)
    const ok = res?.success !== false
    toast.push(ok ? `已设置 ${minutes} 分钟后关机` : res?.message || '设置失败', ok ? 'success' : 'error')
  } catch (err) {
    toast.error(`设置失败: ${err.message}`)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="view">
    <AppPanel title="电源管理" icon="power">
      <template #icon><AppIcon name="power" :size="15" /></template>
      <template #actions>
        <AppButton variant="ghost" size="sm" icon="clock" @click="scheduleOpen = true">
          定时关机
        </AppButton>
      </template>

      <div class="action-grid">
        <button
          v-for="action in ACTIONS"
          :key="action.key"
          class="action-tile"
          :class="{ 'action-tile--danger': action.variant === 'danger', 'action-tile--warn': action.variant === 'warn', 'action-tile--info': action.variant === 'info' }"
          :disabled="busy"
          @click="requestAction(action)"
        >
          <span class="action-tile__icon">
            <AppIcon :name="action.icon" :size="16" />
          </span>
          <span class="action-tile__label">{{ action.label }}</span>
          <span class="action-tile__hint">{{ action.hint }}</span>
        </button>
      </div>
    </AppPanel>

    <AppPanel title="命令执行结果" icon="terminal">
      <template #icon><AppIcon name="terminal" :size="15" /></template>
      <div id="resultBox" class="result-box">
        <p class="aw-text-mute">等待执行命令…</p>
      </div>
    </AppPanel>

    <!-- 危险操作确认 -->
    <AppModal
      v-if="pending"
      :title="pending.confirmTitle"
      :subtitle="pending.danger ? '此操作影响整台机器' : ''"
      @close="pending = null"
    >
      <p class="confirm-text">{{ pending.confirmText }}</p>
      <template #footer>
        <AppButton variant="ghost" @click="pending = null">取消</AppButton>
        <AppButton :variant="pending.danger ? 'danger' : 'primary'" @click="confirmAction">
          确认{{ pending.label }}
        </AppButton>
      </template>
    </AppModal>

    <!-- 定时关机 -->
    <AppModal
      v-if="scheduleOpen"
      title="定时关机"
      subtitle="设定关机倒计时，最长 24 小时"
      @close="scheduleOpen = false"
    >
      <div class="field">
        <label class="field__label" for="shutdown-minutes">延迟时间（分钟）</label>
        <input
          id="shutdown-minutes"
          v-model.number="scheduleMinutes"
          class="input input--mono"
          type="number"
          min="1"
          max="1440"
          @keydown.enter="confirmSchedule"
        />
        <div class="presets">
          <button v-for="m in [15, 30, 60, 120, 480]" :key="m" class="preset" @click="scheduleMinutes = m">
            {{ m }} 分
          </button>
        </div>
        <p class="aw-text-xs aw-text-mute">
          将于 {{ scheduleMinutes }} 分钟后执行关机指令（shutdown /s /t {{ (scheduleMinutes || 0) * 60 }}）
        </p>
      </div>
      <template #footer>
        <AppButton variant="ghost" @click="scheduleOpen = false">取消</AppButton>
        <AppButton variant="primary" @click="confirmSchedule">确认</AppButton>
      </template>
    </AppModal>
  </div>
</template>

<style scoped>
.view {
  display: flex;
  flex-direction: column;
  gap: var(--aw-space-4);
  max-width: 1000px;
}

.confirm-text {
  font-size: var(--aw-text-base);
  color: var(--aw-text-dim);
  line-height: 1.7;
}

.result-box {
  padding: var(--aw-space-3);
  min-height: 72px;
  background: var(--aw-abyss);
  border: 1px solid var(--aw-line);
  border-radius: var(--aw-radius);
  font-family: var(--aw-font-mono);
  font-size: var(--aw-text-sm);
  white-space: pre-wrap;
  word-break: break-word;
}

.presets {
  display: flex;
  flex-wrap: wrap;
  gap: var(--aw-space-2);
}

.preset {
  padding: 3px var(--aw-space-3);
  font-family: var(--aw-font-mono);
  font-size: var(--aw-text-xs);
  color: var(--aw-text-dim);
  background: var(--aw-panel-hi);
  border: 1px solid var(--aw-line);
  border-radius: var(--aw-radius-xs);
  transition: all var(--aw-dur-fast) var(--aw-ease);
}

.preset:hover {
  border-color: var(--aw-accent-line);
  color: var(--aw-accent);
}

@media (max-width: 900px) {
  .view {
    gap: var(--aw-space-3);
  }

  .action-grid {
    /* iOS 26：两列网格，间距更大，元素呼吸感更足 */
    grid-template-columns: repeat(2, 1fr);
    gap: var(--aw-space-3);
  }

  .action-tile {
    /* 连续圆角 + 更大内边距，接近 iOS 图标按钮观感 */
    border-radius: var(--aw-radius-xl);
    padding: var(--aw-space-4);
    gap: var(--aw-space-3);
    background: var(--aw-panel-hi);
  }

  .action-tile__icon {
    width: 36px;
    height: 36px;
    border-radius: 6px;
  }

  .action-tile__label {
    font-size: var(--aw-text-base);
    font-weight: 600;
  }

  .action-tile__hint {
    font-size: var(--aw-text-2xs);
  }

  .result-box {
    border-radius: var(--aw-radius-xl);
    min-height: 96px;
  }

  /* 预设时长改为 iOS 风格胶囊 */
  .preset {
    border-radius: var(--aw-radius-pill);
    padding: 6px var(--aw-space-4);
  }
}
</style>
