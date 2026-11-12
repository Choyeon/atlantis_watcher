<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import AppIcon from '@/components/common/AppIcon.vue'
import AppButton from '@/components/common/AppButton.vue'
import { useWebSocket } from '@/composables/useWebSocket'
import { useRemoteControl } from '@/composables/useRemoteControl'
import { useToastStore } from '@/stores/toast'

const toast = useToastStore()

const stageEl = ref(null)
const canvasEl = ref(null)
const streaming = ref(false)
const frames = ref(0)

// 影院模式：横屏全屏。rotated 表示设备未真正横过来、由 CSS 旋转画面兜底
const cinema = ref(false)
const rotated = ref(false)
const orientationLocked = ref(false)

const controlActive = ref(true)
const keyboardOpen = ref(false)
const textInput = ref('')
const modifiers = ref({ ctrl: false, alt: false, shift: false, win: false })

const MODS = [
  { key: 'ctrl', label: 'Ctrl' },
  { key: 'alt', label: 'Alt' },
  { key: 'shift', label: 'Shift' },
  { key: 'win', label: 'Win' }
]

const QUICK_KEYS = [
  { label: 'Esc', key: 'esc' },
  { label: 'Tab', key: 'tab' },
  { label: 'Enter', key: 'enter' },
  { label: 'Backspace', key: 'backspace' },
  { label: 'Delete', key: 'delete' },
  { label: 'Up', key: 'up' },
  { label: 'Down', key: 'down' },
  { label: 'Left', key: 'left' },
  { label: 'Right', key: 'right' },
  { label: 'Ctrl+C', key: 'ctrl+c' },
  { label: 'Ctrl+V', key: 'ctrl+v' },
  { label: 'Alt+Tab', key: 'alt+tab' },
  { label: 'Win', key: 'win' },
  { label: 'F5', key: 'f5' }
]

/**
 * 画面通道：/ws/screen 用 send_bytes 推 JPEG 二进制帧，
 * 必须 binaryType='arraybuffer' 接收后直接绘制到 canvas，按 JSON 解析会白屏。
 */
const { status: screenStatus, connect, disconnect } = useWebSocket('/ws/screen', {
  autoConnect: false,
  onBinary: buffer => {
    drawFrame(buffer)
    frames.value += 1
  },
  onOpen: () => {
    streaming.value = true
    toast.success('屏幕共享已连接')
  },
  onClose: () => {
    streaming.value = false
  }
})

const rc = useRemoteControl({
  onError: message => toast.warning(message)
})

const canControl = computed(() => streaming.value && controlActive.value && rc.enabled.value)
const controlLabel = computed(() => {
  if (!rc.enabled.value) return '操控已被设置禁用'
  return controlActive.value ? '操控已开启' : '操控已暂停'
})

function drawFrame(buffer) {
  const canvas = canvasEl.value
  if (!canvas) return
  const blob = new Blob([buffer], { type: 'image/jpeg' })
  const url = URL.createObjectURL(blob)
  const img = new Image()
  img.onload = () => {
    if (canvas.width !== img.width || canvas.height !== img.height) {
      canvas.width = img.width
      canvas.height = img.height
    }
    const ctx = canvas.getContext('2d')
    ctx.drawImage(img, 0, 0)
    URL.revokeObjectURL(url)
  }
  img.onerror = () => URL.revokeObjectURL(url)
  img.src = url
}

function clearCanvas() {
  const canvas = canvasEl.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  ctx.fillStyle = '#05090f'
  ctx.fillRect(0, 0, canvas.width || 1280, canvas.height || 720)
}

function toggleStream() {
  if (streaming.value || screenStatus.value === 'connecting') {
    disconnect()
    rc.disconnect()
    streaming.value = false
    clearCanvas()
  } else {
    connect()
    if (controlActive.value) {
      rc.refreshStatus()
      rc.connect()
    }
  }
}

function toggleControl() {
  controlActive.value = !controlActive.value
  if (controlActive.value && streaming.value) {
    rc.refreshStatus()
    rc.connect()
  } else if (!controlActive.value) {
    rc.disconnect()
  }
}

/* --------------------------------------------------------------------------
   坐标换算 —— 网页 / APK 横屏全屏 / letterbox 黑边全部对齐的关键

   canvas 用 object-fit:contain 显示，画面周围可能有黑边；
   因此不能直接用元素矩形比例，必须按「实际画面显示区」反算。
   竖屏 CSS 旋转态下 getBoundingClientRect() 返回的是旋转后的包围盒，
   改用 clientWidth/Height（布局盒，不受 transform 影响）+ 屏幕坐标逆变换。
   -------------------------------------------------------------------------- */
function toNormalized(clientX, clientY) {
  const canvas = canvasEl.value
  if (!canvas) return { x: 0, y: 0 }

  const imgW = canvas.width || 1280
  const imgH = canvas.height || 720
  let localX
  let localY
  let boxW
  let boxH

  if (rotated.value) {
    // transform: rotate(90deg) translateY(-100%) 且 transform-origin: 0 0
    // 下，布局点 (u,v) 映射到屏幕点 (W-v, u)，故 u=clientY, v=W-clientX。
    const screenW = window.innerWidth
    localX = clientY
    localY = screenW - clientX
    boxW = canvas.clientWidth || imgW
    boxH = canvas.clientHeight || imgH
  } else {
    const rect = canvas.getBoundingClientRect()
    localX = clientX - rect.left
    localY = clientY - rect.top
    boxW = rect.width || imgW
    boxH = rect.height || imgH
  }

  const scale = Math.min(boxW / imgW, boxH / imgH)
  const displayW = imgW * scale
  const displayH = imgH * scale
  const offsetX = (boxW - displayW) / 2
  const offsetY = (boxH - displayH) / 2
  const clamp = value => Math.min(1, Math.max(0, value))

  return {
    x: clamp((localX - offsetX) / displayW),
    y: clamp((localY - offsetY) / displayH)
  }
}

function buttonOf(event) {
  if (event.button === 2) return 'right'
  if (event.button === 1) return 'middle'
  return 'left'
}

let pointerState = null
let longPressTimer = null

function onPointerDown(event) {
  if (!canControl.value) return
  event.preventDefault()
  stageEl.value?.focus?.({ preventScroll: true })
  const pos = toNormalized(event.clientX, event.clientY)
  const isTouch = event.pointerType !== 'mouse'

  pointerState = {
    id: event.pointerId,
    type: event.pointerType,
    button: isTouch ? 'left' : buttonOf(event),
    startX: event.clientX,
    startY: event.clientY,
    x: pos.x,
    y: pos.y,
    dragged: false,
    longPressed: false
  }

  try {
    event.currentTarget.setPointerCapture?.(event.pointerId)
  } catch {
    /* 某些 WebView 不支持指针捕获，忽略即可 */
  }

  if (!isTouch) {
    rc.emit({ type: 'down', x: pos.x, y: pos.y, button: pointerState.button })
  } else {
    // 触屏长按 = 右键；移动超过阈值则视为拖动
    longPressTimer = setTimeout(() => {
      if (!pointerState || pointerState.dragged) return
      pointerState.longPressed = true
      rc.emit({ type: 'click', x: pointerState.x, y: pointerState.y, button: 'right' })
    }, 550)
  }
}

function onPointerMove(event) {
  if (!canControl.value) return
  if (!pointerState) {
    if (event.pointerType === 'mouse') {
      const pos = toNormalized(event.clientX, event.clientY)
      rc.emitMove(pos.x, pos.y)
    }
    return
  }

  const moved = Math.hypot(
    event.clientX - pointerState.startX,
    event.clientY - pointerState.startY
  ) > 8

  if (moved && !pointerState.dragged) {
    pointerState.dragged = true
    clearTimeout(longPressTimer)
    longPressTimer = null
    if (pointerState.type !== 'mouse') {
      rc.emit({ type: 'down', x: pointerState.x, y: pointerState.y, button: 'left' })
    }
  }

  if (pointerState.dragged || pointerState.type === 'mouse') {
    const pos = toNormalized(event.clientX, event.clientY)
    pointerState.x = pos.x
    pointerState.y = pos.y
    rc.emitMove(pos.x, pos.y, pointerState.dragged)
  }
}

function onPointerUp(event) {
  clearTimeout(longPressTimer)
  if (!pointerState) return
  if (!canControl.value) {
    pointerState = null
    return
  }
  longPressTimer = null

  const pos = toNormalized(event.clientX, event.clientY)
  const state = pointerState
  pointerState = null

  if (state.type === 'mouse') {
    rc.emit({ type: 'up', x: pos.x, y: pos.y, button: state.button })
  } else if (state.dragged) {
    rc.emit({ type: 'up', x: pos.x, y: pos.y, button: 'left' })
  } else if (!state.longPressed) {
    rc.emit({ type: 'click', x: pos.x, y: pos.y, button: 'left' })
  }

  try {
    event.currentTarget.releasePointerCapture?.(event.pointerId)
  } catch {
    /* 忽略 */
  }
}

function onWheel(event) {
  if (!canControl.value) return
  const pos = toNormalized(event.clientX, event.clientY)
  // 浏览器 deltaY 向下为正；pyautogui.scroll 正数向上，故取反
  let delta = Math.round(-event.deltaY / 100)
  if (!delta) delta = event.deltaY > 0 ? -1 : 1
  rc.emit({ type: 'wheel', x: pos.x, y: pos.y, delta: Math.max(-12, Math.min(12, delta)) })
}

const MODIFIER_KEYS = ['ctrl', 'alt', 'shift', 'win']
const PUNCT_KEYS = '`-=[]\\;\',./'

function normalizeKey(event) {
  const key = event.key
  if (key === ' ') return 'space'
  if (key === 'Control') return 'ctrl'
  if (key === 'Alt') return 'alt'
  if (key === 'Shift') return 'shift'
  if (key === 'Meta') return 'win'
  if (key === 'Escape') return 'esc'
  if (key.startsWith('Arrow')) return key.slice(5).toLowerCase()
  if (/^F([1-9]|1[0-2])$/.test(key)) return key.toLowerCase()
  if (['Enter', 'Tab', 'Backspace', 'Delete', 'Insert', 'Home', 'End', 'PageUp', 'PageDown', 'Pause'].includes(key)) {
    return key.toLowerCase()
  }
  if (key.length === 1 && (/[a-zA-Z0-9]/.test(key) || PUNCT_KEYS.includes(key))) {
    return key.toLowerCase()
  }
  return null
}

function onKeyDown(event) {
  if (!canControl.value) return
  const key = normalizeKey(event)
  if (!key) return
  event.preventDefault()

  if (MODIFIER_KEYS.includes(key)) {
    rc.emit({ type: 'keydown', key })
    return
  }

  const parts = []
  if (event.ctrlKey || modifiers.value.ctrl) parts.push('ctrl')
  if (event.altKey || modifiers.value.alt) parts.push('alt')
  if (event.shiftKey || modifiers.value.shift) parts.push('shift')
  if (event.metaKey || modifiers.value.win) parts.push('win')
  parts.push(key)
  rc.emit({ type: 'key', key: parts.join('+') })
}

function onKeyUp(event) {
  if (!canControl.value) return
  const key = normalizeKey(event)
  if (key && MODIFIER_KEYS.includes(key)) {
    event.preventDefault()
    rc.emit({ type: 'keyup', key })
  }
}

function sendQuickKey(key) {
  if (!canControl.value) {
    toast.warning('请先开始共享并开启操控')
    return
  }
  if (key.includes('+')) {
    rc.emit({ type: 'key', key })
    return
  }
  const parts = MODS.filter(item => modifiers.value[item.key]).map(item => item.key)
  parts.push(key)
  rc.emit({ type: 'key', key: parts.join('+') })
}

function sendText() {
  const value = textInput.value
  if (!value) return
  if (!canControl.value) {
    toast.warning('请先开始共享并开启操控')
    return
  }
  // 中文等非 ASCII 走后端剪贴板粘贴
  const needsPaste = [...value].some(ch => ch.charCodeAt(0) > 127)
  rc.emit({ type: needsPaste ? 'paste' : 'text', text: value })
  textInput.value = ''
}

/* --------------------------------------------------------------------------
   影院模式（APK 横屏全屏）
   优先用 screen.orientation.lock('landscape') 真正把设备转过来；
   老 WebView 不支持时，用 CSS 把画面旋转 90° 铺满，坐标换算同步逆变换。
   -------------------------------------------------------------------------- */
function syncRotation() {
  if (orientationLocked.value) {
    rotated.value = false
    return
  }
  const landscape = window.matchMedia
    ? window.matchMedia('(orientation: landscape)').matches
    : window.innerWidth >= window.innerHeight
  rotated.value = !landscape
}

async function enterCinema() {
  cinema.value = true
  orientationLocked.value = false
  await nextTick()

  try {
    const orientation = window.screen?.orientation
    if (orientation?.lock) {
      await orientation.lock('landscape')
      orientationLocked.value = true
    }
  } catch {
    orientationLocked.value = false
  }

  // 影院态刻意不调用 Fullscreen API：浏览器会强制元素尺寸为屏幕大小，
  // 与竖屏 CSS 旋转的 transform 冲突。fixed 铺满在 APK / 浏览器里都足够，
  // 桌面要隐藏地址栏可用工具条的「全屏」按钮。
  syncRotation()
  window.addEventListener('resize', syncRotation)
  window.addEventListener('orientationchange', syncRotation)
  stageEl.value?.focus?.({ preventScroll: true })

  if (!orientationLocked.value && rotated.value) {
    toast.success('已进入横屏全屏（画面旋转模式）')
  } else {
    toast.success('已进入横屏全屏')
  }
}

async function exitCinema() {
  cinema.value = false
  rotated.value = false
  orientationLocked.value = false
  window.removeEventListener('resize', syncRotation)
  window.removeEventListener('orientationchange', syncRotation)
  try {
    window.screen?.orientation?.unlock?.()
  } catch {
    /* 忽略 */
  }
  if (document.fullscreenElement) {
    try {
      await document.exitFullscreen()
    } catch {
      /* 忽略 */
    }
  }
  keyboardOpen.value = false
}

async function toggleCinema() {
  if (cinema.value) await exitCinema()
  else await enterCinema()
}

async function toggleFullscreen() {
  const stage = stageEl.value
  if (!stage) return
  try {
    if (!document.fullscreenElement) await stage.requestFullscreen()
    else await document.exitFullscreen()
  } catch {
    toast.warning('当前浏览器不支持全屏模式，可使用「横屏全屏」')
  }
}

function capture() {
  const canvas = canvasEl.value
  if (!canvas || !frames.value) {
    toast.warning('尚未获取到画面，无法截图')
    return
  }
  try {
    const link = document.createElement('a')
    link.download = `atlantis-screen-${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.png`
    link.href = canvas.toDataURL('image/png')
    link.click()
    toast.success('截图已保存')
  } catch {
    toast.error('截图失败')
  }
}

watch(screenStatus, value => {
  if (value === 'closed' || value === 'error') streaming.value = false
})

onMounted(() => {
  rc.refreshStatus()
})

onBeforeUnmount(() => {
  disconnect()
  rc.disconnect()
  clearTimeout(longPressTimer)
  window.removeEventListener('resize', syncRotation)
  window.removeEventListener('orientationchange', syncRotation)
  try {
    window.screen?.orientation?.unlock?.()
  } catch {
    /* 忽略 */
  }
})
</script>

<template>
  <div class="view">
    <div class="toolbar">
      <AppButton
        :variant="streaming ? 'danger' : 'primary'"
        size="sm"
        :icon="streaming ? 'stop' : 'play'"
        @click="toggleStream"
      >
        {{ streaming ? '停止共享' : '开始共享' }}
      </AppButton>
      <AppButton variant="ghost" size="sm" icon="maximize" @click="toggleFullscreen">全屏</AppButton>
      <AppButton variant="ghost" size="sm" icon="landscape" @click="toggleCinema">横屏全屏</AppButton>
      <AppButton variant="ghost" size="sm" icon="camera" @click="capture">截图</AppButton>
      <AppButton
        :variant="controlActive ? 'warn' : 'ghost'"
        size="sm"
        icon="mouse"
        @click="toggleControl"
      >
        {{ controlActive ? '操控中' : '操控关' }}
      </AppButton>
      <AppButton variant="ghost" size="sm" icon="keyboard" @click="keyboardOpen = !keyboardOpen">键盘</AppButton>

      <div class="toolbar__spacer" />

      <span class="chip" :class="streaming ? 'chip--ok' : ''">
        <span class="dot" :class="streaming ? 'dot--ok dot--pulse' : ''" />
        {{ streaming ? 'LIVE' : 'OFFLINE' }}
      </span>
      <span v-if="frames" class="aw-label aw-mono">{{ frames }} 帧</span>
    </div>

    <div
      ref="stageEl"
      class="screen-stage"
      :class="{ 'is-cinema': cinema, 'is-rotated': rotated, 'is-control': canControl }"
      tabindex="0"
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
      @pointercancel="onPointerUp"
      @contextmenu.prevent
      @wheel.prevent="onWheel"
      @keydown="onKeyDown"
      @keyup="onKeyUp"
    >
      <canvas ref="canvasEl" width="1280" height="720" />

      <div v-if="!frames" class="screen-stage__overlay">
        <AppIcon name="monitor" :size="34" :stroke-width="1.3" />
        <div>
          <div class="aw-text-md" style="color: var(--aw-text-dim)">
            {{ streaming ? '正在等待画面…' : '屏幕共享未开启' }}
          </div>
          <p class="aw-text-xs aw-text-mute" style="margin-top: 4px">
            点击「开始共享」以接收主机画面，开启「操控」后可直接点击、拖拽与输入
          </p>
        </div>
      </div>

      <div v-if="frames && !cinema" class="screen-stage__bar">
        <button class="screen-stage__btn" :title="streaming ? '停止' : '开始'" @click="toggleStream">
          <AppIcon :name="streaming ? 'stop' : 'play'" :size="16" />
        </button>
        <button class="screen-stage__btn" title="横屏全屏" @click="toggleCinema">
          <AppIcon name="landscape" :size="16" />
        </button>
        <button class="screen-stage__btn" title="截图" @click="capture">
          <AppIcon name="camera" :size="16" />
        </button>
      </div>

      <!-- 影院态常驻工具条：APK 横屏全屏下仍可退出与呼出键盘 -->
      <div v-if="cinema" class="cinema-bar" @pointerdown.stop @wheel.stop>
        <button class="cinema-bar__btn" @click="exitCinema">
          <AppIcon name="minimize" :size="15" /> 退出横屏
        </button>
        <span class="cinema-bar__state">{{ controlLabel }}</span>
        <button class="cinema-bar__btn" @click="keyboardOpen = !keyboardOpen">
          <AppIcon name="keyboard" :size="15" /> 键盘
        </button>
      </div>

      <!-- 虚拟键盘 / 快捷按键：阻止冒泡，避免点按钮时把点击注入主机 -->
      <div
        v-if="keyboardOpen"
        class="control-panel"
        @pointerdown.stop
        @pointerup.stop
        @wheel.stop
        @keydown.stop
      >
        <div class="control-panel__row">
          <button
            v-for="item in MODS"
            :key="item.key"
            class="key-btn"
            :class="{ 'is-on': modifiers[item.key] }"
            @click="modifiers[item.key] = !modifiers[item.key]"
          >
            {{ item.label }}
          </button>
          <span class="control-panel__hint">修饰键点亮后，与下方按键组合发送</span>
        </div>

        <div class="control-panel__row control-panel__row--wrap">
          <button v-for="item in QUICK_KEYS" :key="item.key" class="key-btn" @click="sendQuickKey(item.key)">
            {{ item.label }}
          </button>
        </div>

        <div class="control-panel__row">
          <input
            v-model="textInput"
            class="input control-panel__input"
            type="text"
            placeholder="输入文字后发送（支持中文）"
            aria-label="远程输入文本"
            @keydown.enter="sendText"
          />
          <AppButton size="sm" variant="primary" @click="sendText">发送</AppButton>
        </div>
      </div>
    </div>

    <div v-if="!cinema" class="control-tips aw-text-xs aw-text-mute">
      <span><strong>鼠标</strong>：单击 / 右键 / 拖拽 / 滚轮</span>
      <span><strong>触屏</strong>：轻点左键、长按右键、滑动拖拽</span>
      <span><strong>键盘</strong>：点击画面后直接输入，或用「键盘」面板发送组合键与中文</span>
      <span>{{ controlLabel }} · 可在设置页全局关闭远程操控</span>
    </div>
  </div>
</template>

<style scoped>
.view {
  display: flex;
  flex-direction: column;
  gap: var(--aw-space-3);
}

.screen-stage.is-control {
  cursor: crosshair;
  outline: none;
}

.screen-stage.is-control:focus-visible {
  box-shadow: inset 0 0 0 2px var(--aw-accent);
}

/* --------------------------------------------------------------------------
   影院模式：fixed 铺满，z-index 高于 Tabbar(90)
   -------------------------------------------------------------------------- */
.screen-stage.is-cinema {
  position: fixed;
  inset: 0;
  z-index: 9999;
  width: 100vw;
  height: 100dvh;
  aspect-ratio: auto;
  border: none;
  border-radius: 0;
  background: #000;
}

.screen-stage.is-cinema.is-rotated {
  /* 竖屏设备强制横屏：布局盒 = (屏幕高, 屏幕宽)，绕左上角旋转 90° 后铺满。
     screenX = W - v, screenY = u，坐标逆变换见 toNormalized()。 */
  width: 100dvh;
  height: 100dvw;
  inset: 0 auto auto 0;
  transform: rotate(90deg) translateY(-100%);
  transform-origin: 0 0;
}

.screen-stage:fullscreen:not(.is-cinema) {
  border-radius: 0;
  border: none;
  aspect-ratio: auto;
  height: 100vh;
  width: 100vw;
}

.screen-stage.is-cinema canvas {
  object-fit: contain;
}

.screen-stage.is-cinema .screen-stage__bar {
  display: none;
}

.cinema-bar {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--aw-space-2);
  padding: var(--aw-space-2) var(--aw-space-3);
  background: rgba(6, 12, 22, 0.9);
  border-bottom: 1px solid var(--aw-line-hi);
  z-index: 5;
}

.cinema-bar__btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-radius: var(--aw-radius-sm);
  color: var(--aw-text-dim);
  font-size: var(--aw-text-xs);
  white-space: nowrap;
}

.cinema-bar__btn:hover {
  background: var(--aw-panel-hi);
  color: var(--aw-accent);
}

.cinema-bar__state {
  font-size: var(--aw-text-2xs);
  color: var(--aw-text-mute);
  white-space: nowrap;
}

/* --------------------------------------------------------------------------
   虚拟键盘 / 快捷按键
   -------------------------------------------------------------------------- */
.control-panel {
  position: absolute;
  left: 50%;
  bottom: var(--aw-space-3);
  transform: translateX(-50%);
  width: min(760px, calc(100% - var(--aw-space-4)));
  display: flex;
  flex-direction: column;
  gap: var(--aw-space-2);
  padding: var(--aw-space-3);
  background: rgba(6, 12, 22, 0.94);
  border: 1px solid var(--aw-line-hi);
  border-radius: var(--aw-radius);
  z-index: 6;
}

.control-panel__row {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.control-panel__row--wrap {
  flex-wrap: wrap;
}

.control-panel__hint {
  margin-left: auto;
  font-size: var(--aw-text-2xs);
  color: var(--aw-text-faint);
  white-space: nowrap;
}

.control-panel__input {
  flex: 1;
  min-width: 0;
  height: 32px;
}

.key-btn {
  flex-shrink: 0;
  min-width: 44px;
  padding: 5px 9px;
  border: 1px solid var(--aw-line);
  border-radius: var(--aw-radius-sm);
  background: var(--aw-panel);
  color: var(--aw-text-dim);
  font-size: var(--aw-text-2xs);
  white-space: nowrap;
}

.key-btn:hover {
  color: var(--aw-accent);
  border-color: var(--aw-accent-ghost);
}

.key-btn.is-on {
  background: var(--aw-accent-ghost);
  border-color: var(--aw-accent);
  color: var(--aw-accent);
}

.control-tips {
  display: flex;
  flex-wrap: wrap;
  gap: 4px var(--aw-space-4);
  line-height: 1.7;
}

.control-tips strong {
  color: var(--aw-text-dim);
  font-weight: 600;
}

/* --------------------------------------------------------------------------
   iOS 26 移动端
   -------------------------------------------------------------------------- */
@media (max-width: 900px) {
  .view {
    gap: var(--aw-space-2);
  }

  .screen-stage {
    border-radius: var(--aw-radius-xl);
    border: none;
    box-shadow: var(--aw-shadow-md);
  }

  .screen-stage__bar {
    opacity: 1;
    transform: translateX(-50%);
  }

  .screen-stage__btn {
    width: 38px;
    height: 38px;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.06);
  }

  .control-panel__hint {
    display: none;
  }

  .control-panel {
    max-height: 52%;
    overflow-y: auto;
  }
}
</style>
