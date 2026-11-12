<script setup>
import { computed, onMounted, ref } from 'vue'
import AppIcon from '@/components/common/AppIcon.vue'
import AppButton from '@/components/common/AppButton.vue'
import AppPanel from '@/components/common/AppPanel.vue'
import { useToastStore } from '@/stores/toast'
import { fetchSettings, saveSettings, restartService } from '@/api/settings'

const toast = useToastStore()

const loading = ref(true)
const saving = ref(false)
const restarting = ref(false)
const needsRestart = ref(false)
const form = ref({})
const baseline = ref({})
const runtime = ref({})
const autoStart = ref({})

const SWITCHES = [
  {
    key: 'auto_start',
    label: '开机自动启动',
    hint: '写入当前用户注册表 Run 项，关闭即刻移除；首次启动会继承旧版自启状态'
  },
  {
    key: 'show_tray',
    label: '显示系统托盘图标',
    hint: '托盘标题与菜单会显示 IP 加端口的完整访问地址'
  },
  {
    key: 'start_minimized',
    label: '启动后不弹出管理页面',
    hint: '关闭时，服务启动后自动用默认浏览器打开管理页面'
  },
  {
    key: 'notify_on_start',
    label: '启动完成通知',
    hint: '服务就绪后通过托盘气泡提示访问地址'
  },
  {
    key: 'remote_control_enabled',
    label: '允许远程操控',
    hint: '屏幕共享页可注入鼠标 / 键盘；关闭后只能观看。服务当前无鉴权，不可信网络下建议关闭'
  },
  {
    key: 'require_admin',
    label: '校验管理员权限',
    hint: '关机、重启等系统操作需要管理员权限；修改后下次启动生效',
    restart: true
  }
]

const LOG_LEVELS = [
  { value: 'DEBUG', label: 'DEBUG · 详细' },
  { value: 'INFO', label: 'INFO · 常规' },
  { value: 'WARNING', label: 'WARNING · 告警' },
  { value: 'ERROR', label: 'ERROR · 仅错误' }
]

const dirtyKeys = computed(() =>
  Object.keys(form.value).filter(key => form.value[key] !== baseline.value[key])
)

const uptime = computed(() => {
  const seconds = Number(runtime.value?.uptime_seconds)
  if (!Number.isFinite(seconds)) return '—'
  const total = Math.floor(seconds)
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  return hours ? `${hours} 小时 ${minutes} 分` : `${minutes} 分 ${total % 60} 秒`
})

const autoStartLabel = computed(() => {
  if (!autoStart.value?.supported) return '当前系统不支持'
  return autoStart.value?.enabled ? '已开启（注册表）' : '未开启'
})

async function load() {
  loading.value = true
  try {
    const res = await fetchSettings()
    const data = res?.data || {}
    form.value = { ...(data.settings || {}) }
    baseline.value = { ...(data.settings || {}) }
    runtime.value = data.runtime || {}
    autoStart.value = data.auto_start || {}
  } catch (err) {
    toast.error(`读取设置失败: ${err.message}`)
  } finally {
    loading.value = false
  }
}

async function save() {
  if (!dirtyKeys.value.length || saving.value) return
  saving.value = true
  const patch = {}
  for (const key of dirtyKeys.value) patch[key] = form.value[key]
  try {
    const res = await saveSettings(patch)
    if (res?.success === false) throw new Error(res?.message || '保存失败')
    const data = res?.data || {}
    baseline.value = { ...form.value }
    needsRestart.value = !!data.requires_restart
    if (data.runtime) runtime.value = data.runtime
    if (data.auto_start) autoStart.value = data.auto_start
    toast.push(res?.message || '设置已保存', 'success')
    if (data.warning) toast.warning(data.warning)
  } catch (err) {
    toast.error(`保存失败: ${err.message}`)
  } finally {
    saving.value = false
  }
}

async function doRestart() {
  if (restarting.value) return
  restarting.value = true
  try {
    const res = await restartService()
    if (res?.success === false) throw new Error(res?.message || '重启失败')
    needsRestart.value = false
    toast.push('服务已重启', 'success')
  } catch (err) {
    toast.error(`重启失败: ${err.message}`)
  } finally {
    restarting.value = false
    // 端口会短暂不可用，等连接恢复后再刷新
    setTimeout(() => load(), 900)
  }
}

async function copyText(text) {
  if (!text) return
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
    } else {
      const el = document.createElement('textarea')
      el.value = text
      el.style.position = 'fixed'
      el.style.opacity = '0'
      document.body.appendChild(el)
      el.select()
      document.execCommand('copy')
      el.remove()
    }
    toast.push('已复制访问地址', 'success')
  } catch (err) {
    toast.error(`复制失败: ${err.message}`)
  }
}

onMounted(load)
</script>

<template>
  <div class="view">
    <div v-if="loading" class="state-line">读取设置…</div>

    <template v-else>
      <AppPanel title="访问地址" icon="globe">
        <template #icon><AppIcon name="globe" :size="15" /></template>
        <template #actions>
          <AppButton variant="ghost" size="sm" icon="refresh" @click="load">刷新</AppButton>
        </template>

        <div class="endpoint">
          <span class="aw-label">管理页面</span>
          <code class="endpoint__url aw-mono">{{ runtime.url || '—' }}</code>
          <AppButton variant="ghost" size="sm" icon="copy" @click="copyText(runtime.url)">复制</AppButton>
        </div>

        <div class="kv-grid">
          <div class="kv">
            <span>监听地址</span>
            <strong class="aw-mono">{{ runtime.ip }}:{{ runtime.port }}</strong>
          </div>
          <div class="kv">
            <span>运行时长</span>
            <strong class="aw-mono">{{ uptime }}</strong>
          </div>
          <div class="kv">
            <span>运行形态</span>
            <strong>{{ runtime.mode === 'frozen' ? '安装版' : '源码版' }} · v{{ runtime.version }}</strong>
          </div>
          <div class="kv">
            <span>开机自启</span>
            <strong :class="{ 'is-ok': autoStart.enabled }">{{ autoStartLabel }}</strong>
          </div>
        </div>

        <div v-if="runtime.addresses && runtime.addresses.length > 1" class="alt-addresses">
          <span class="aw-label">全部网卡</span>
          <code v-for="addr in runtime.addresses" :key="addr.ip" class="aw-mono">
            {{ addr.interface }} · {{ addr.ip }}:{{ runtime.port }}
          </code>
        </div>

        <div class="file-paths aw-text-xs aw-text-mute">
          <span>设置 {{ runtime.settings_file }}</span>
          <span>日志 {{ runtime.log_file }}</span>
        </div>
      </AppPanel>

      <AppPanel title="启动与托盘" icon="power">
        <template #icon><AppIcon name="power" :size="15" /></template>
        <div class="ios-group">
          <div v-for="sw in SWITCHES" :key="sw.key" class="setting-row">
            <div class="setting-row__text">
              <span class="setting-row__label">
                {{ sw.label }}
                <em v-if="sw.restart" class="setting-row__tag">下次启动生效</em>
              </span>
              <span class="setting-row__hint">{{ sw.hint }}</span>
            </div>
            <button
              type="button"
              class="ios-switch"
              :class="{ 'is-on': form[sw.key] }"
              role="switch"
              :aria-checked="!!form[sw.key]"
              :aria-label="sw.label"
              @click="form[sw.key] = !form[sw.key]"
            />
          </div>
        </div>
      </AppPanel>

      <AppPanel title="服务与性能" icon="settings">
        <template #icon><AppIcon name="settings" :size="15" /></template>
        <div class="ios-group">
          <label class="setting-row setting-row--field">
            <span class="setting-row__text">
              <span class="setting-row__label">监听地址 <em class="setting-row__tag">需重启服务</em></span>
              <span class="setting-row__hint">0.0.0.0 允许局域网访问；127.0.0.1 仅本机</span>
            </span>
            <input v-model.trim="form.host" class="input input--mono field-input" type="text" />
          </label>

          <label class="setting-row setting-row--field">
            <span class="setting-row__text">
              <span class="setting-row__label">服务端口 <em class="setting-row__tag">需重启服务</em></span>
              <span class="setting-row__hint">1024–65535；改动后手机端需重新嗅探或手动填写</span>
            </span>
            <input v-model.number="form.port" class="input input--mono field-input field-input--sm" type="number" min="1024" max="65535" />
          </label>

          <label class="setting-row setting-row--field">
            <span class="setting-row__text">
              <span class="setting-row__label">日志级别</span>
              <span class="setting-row__hint">修改后立即生效，无需重启</span>
            </span>
            <select v-model="form.log_level" class="input field-input">
              <option v-for="level in LOG_LEVELS" :key="level.value" :value="level.value">{{ level.label }}</option>
            </select>
          </label>

          <label class="setting-row setting-row--field">
            <span class="setting-row__text">
              <span class="setting-row__label">屏幕共享帧率</span>
              <span class="setting-row__hint">1–60 FPS，已有连接也会即时采用新值</span>
            </span>
            <input v-model.number="form.screen_share_fps" class="input input--mono field-input field-input--sm" type="number" min="1" max="60" />
          </label>

          <label class="setting-row setting-row--field">
            <span class="setting-row__text">
              <span class="setting-row__label">屏幕共享画质</span>
              <span class="setting-row__hint">JPEG 质量 10–100，越高越清晰、占用带宽越大</span>
            </span>
            <input v-model.number="form.screen_share_quality" class="input input--mono field-input field-input--sm" type="number" min="10" max="100" />
          </label>
        </div>
      </AppPanel>

      <div class="save-bar">
        <div class="save-bar__hint">
          <span v-if="dirtyKeys.length" class="is-dirty">{{ dirtyKeys.length }} 项未保存</span>
          <span v-else-if="needsRestart" class="is-warn">端口 / 监听地址已变更，需重启服务</span>
          <span v-else class="aw-text-mute">设置保存在本机，重启后依然生效</span>
        </div>
        <AppButton v-if="needsRestart" variant="warn" :disabled="restarting" @click="doRestart">
          {{ restarting ? '重启中…' : '立即重启服务' }}
        </AppButton>
        <AppButton variant="primary" :disabled="!dirtyKeys.length || saving" @click="save">
          {{ saving ? '保存中…' : '保存设置' }}
        </AppButton>
      </div>
    </template>
  </div>
</template>

<style scoped>
.view {
  display: flex;
  flex-direction: column;
  gap: var(--aw-space-4);
  max-width: 1000px;
}

.state-line {
  padding: var(--aw-space-6);
  color: var(--aw-text-mute);
  font-family: var(--aw-font-mono);
}

.endpoint {
  display: flex;
  align-items: center;
  gap: var(--aw-space-3);
  padding-bottom: var(--aw-space-4);
  border-bottom: 1px solid var(--aw-line);
}

.endpoint__url {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--aw-text-lg);
  color: var(--aw-accent);
}

.kv-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--aw-space-3);
  padding: var(--aw-space-4) 0;
}

.kv {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: var(--aw-space-3);
  background: var(--aw-abyss);
  border: 1px solid var(--aw-line);
  border-radius: var(--aw-radius);
}

.kv span {
  font-size: var(--aw-text-xs);
  color: var(--aw-text-mute);
}

.kv strong {
  font-size: var(--aw-text-sm);
  font-weight: 600;
  color: var(--aw-text);
  overflow-wrap: anywhere;
}

.kv strong.is-ok {
  color: var(--aw-ok);
}

.alt-addresses,
.file-paths {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--aw-space-2) var(--aw-space-3);
  padding-bottom: var(--aw-space-2);
}

.alt-addresses code {
  padding: 2px var(--aw-space-2);
  font-size: var(--aw-text-xs);
  color: var(--aw-text-dim);
  background: var(--aw-panel-hi);
  border: 1px solid var(--aw-line);
  border-radius: var(--aw-radius-xs);
}

.file-paths {
  flex-direction: column;
  align-items: flex-start;
  overflow-wrap: anywhere;
}

.setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--aw-space-4);
  padding: var(--aw-space-3) var(--aw-space-4);
  border-bottom: 1px solid var(--aw-line);
}

.setting-row:last-child {
  border-bottom: none;
}

.setting-row__text {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.setting-row__label {
  font-size: var(--aw-text-sm);
  font-weight: 600;
  color: var(--aw-text);
}

.setting-row__tag {
  margin-left: var(--aw-space-2);
  padding: 1px 6px;
  font-size: var(--aw-text-2xs);
  font-style: normal;
  font-weight: 500;
  color: var(--aw-warn);
  border: 1px solid var(--aw-warn-line, var(--aw-line));
  border-radius: var(--aw-radius-xs);
}

.setting-row__hint {
  font-size: var(--aw-text-xs);
  line-height: 1.6;
  color: var(--aw-text-mute);
}

.field-input {
  width: 190px;
  flex-shrink: 0;
}

.field-input--sm {
  width: 110px;
}

.save-bar {
  display: flex;
  align-items: center;
  gap: var(--aw-space-3);
  padding: var(--aw-space-3) var(--aw-space-4);
  background: var(--aw-panel);
  border: 1px solid var(--aw-line);
  border-radius: var(--aw-radius);
}

.save-bar__hint {
  flex: 1;
  min-width: 0;
  font-size: var(--aw-text-xs);
}

.is-dirty {
  color: var(--aw-warn);
}

.is-warn {
  color: var(--aw-danger);
}

@media (max-width: 900px) {
  .view {
    gap: var(--aw-space-3);
  }

  .kv-grid {
    grid-template-columns: 1fr;
  }

  .endpoint {
    flex-wrap: wrap;
  }

  .endpoint__url {
    flex-basis: 100%;
    order: 2;
    font-size: var(--aw-text-base);
  }

  .setting-row--field {
    flex-direction: column;
    align-items: stretch;
    gap: var(--aw-space-2);
  }

  .field-input,
  .field-input--sm {
    width: 100%;
  }

  .save-bar {
    flex-wrap: wrap;
    border-radius: var(--aw-radius-xl);
  }

  .save-bar__hint {
    flex-basis: 100%;
  }
}
</style>
