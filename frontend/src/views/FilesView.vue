<script setup>
import { onMounted, ref } from 'vue'
import AppIcon from '@/components/common/AppIcon.vue'
import AppButton from '@/components/common/AppButton.vue'
import AppModal from '@/components/common/AppModal.vue'
import AppEmpty from '@/components/common/AppEmpty.vue'
import { useToastStore } from '@/stores/toast'
import {
  fetchDrives,
  listFiles,
  fileOperation,
  executeFile,
  downloadUrl,
  uploadFile,
  createDirectory,
  createFile,
  fetchFileContent,
  saveFileContent
} from '@/api/files'
import { formatBytes, formatDateTime, joinPath, parentPath, baseName } from '@/utils/format'

const toast = useToastStore()

const currentPath = ref('')
const items = ref([])
const drives = ref([])
const loading = ref(false)
const selected = ref(null)
const pathInput = ref('')

/** 剪贴板：copy / cut */
const clipboard = ref({ files: [], operation: '' })

// 弹窗状态
const ctxMenu = ref(null)
const createOpen = ref(false)
const createType = ref('folder')
const createName = ref('')
const renameTarget = ref(null)
const renameValue = ref('')
const uploadOpen = ref(false)
const uploadFiles = ref([])
const uploadProgress = ref(0)
const uploadStatus = ref('')
const uploading = ref(false)
const editorOpen = ref(false)
const editorPath = ref('')
const editorContent = ref('')
const editorSaving = ref(false)
const preview = ref(null)

const FILE_ICONS = {
  directory: 'folder',
  image: 'image',
  video: 'video',
  audio: 'music',
  text: 'fileText',
  executable: 'settings',
  archive: 'package',
  document: 'file',
  file: 'file'
}

const FILE_COLORS = {
  directory: 'var(--aw-accent)',
  image: '#5aa9ff',
  video: '#c084fc',
  audio: '#f5b642',
  text: '#3fcf8e',
  executable: '#ff6b6b',
  archive: '#fb923c',
  document: '#38bdf8',
  file: 'var(--aw-text-mute)'
}

onMounted(async () => {
  await loadDrives()
})

async function loadDrives() {
  try {
    const data = await fetchDrives()
    drives.value = data?.drives || []
    if (drives.value.length) {
      await navigate(drives.value[0].path)
    } else {
      await navigate('C:\\')
    }
  } catch (err) {
    toast.error(`加载驱动器失败: ${err.message}`)
    await navigate('C:\\')
  }
}

async function navigate(path) {
  if (!path) return
  loading.value = true
  selected.value = null
  try {
    const data = await listFiles(path)
    // 后端返回的 path 为规范化后的真实路径
    currentPath.value = data?.path || path
    pathInput.value = currentPath.value
    items.value = data?.items || []
  } catch (err) {
    items.value = []
    toast.error(`加载目录失败: ${err.message}`)
  } finally {
    loading.value = false
  }
}

async function refresh() {
  await navigate(currentPath.value)
}

function goUp() {
  const parent = parentPath(currentPath.value)
  if (parent && parent !== currentPath.value) navigate(parent)
}

function goBack() {
  const parent = parentPath(currentPath.value)
  if (parent) navigate(parent)
}

function onPathEnter() {
  const value = pathInput.value.trim()
  if (value) navigate(value)
}

function pickDrive(event) {
  const path = event.target.value
  if (path) navigate(path)
}

/* ---------------------------------------------------------------- 选中与菜单 */
function selectItem(item) {
  selected.value = selected.value?.path === item.path ? null : item
}

function openItem(item) {
  if (item.is_directory) {
    navigate(item.path)
  } else {
    handleFileOpen(item)
  }
}

function showContextMenu(event, item) {
  event.preventDefault()
  selected.value = item
  ctxMenu.value = { x: event.clientX, y: event.clientY, item }
}

function closeContextMenu() {
  ctxMenu.value = null
}

/** 从右键菜单打开项目 */
function openFromMenu() {
  const item = ctxMenu.value?.item
  closeContextMenu()
  if (item) openItem(item)
}

/** 从右键菜单编辑文本文件 */
function editFromMenu() {
  const item = ctxMenu.value?.item
  closeContextMenu()
  if (item) openEditor(item)
}

async function copyItem() {
  const item = ctxMenu.value?.item
  closeContextMenu()
  if (!item) return
  clipboard.value = { files: [item.path], operation: 'copy' }
  toast.info(`已复制「${item.name}」`)
}

async function cutItem() {
  const item = ctxMenu.value?.item
  closeContextMenu()
  if (!item) return
  clipboard.value = { files: [item.path], operation: 'cut' }
  toast.info(`已剪切「${item.name}」`)
}

/**
 * 计算粘贴目标路径
 * 与 Windows 资源管理器一致：目标已存在时自动追加 "(1)"、"(2)"…
 */
function resolveTargetPath(dir, fileName) {
  const base = fileName
  const ext = base.includes('.') ? base.slice(base.lastIndexOf('.')) : ''
  const stem = ext ? base.slice(0, base.length - ext.length) : base

  let candidate = joinPath(dir, base)
  let counter = 1
  while (items.value.some(i => i.name.toLowerCase() === candidate.split('\\').pop().toLowerCase())) {
    candidate = joinPath(dir, `${stem} (${counter})${ext}`)
    counter += 1
    if (counter > 999) break
  }
  return candidate
}

async function pasteItem() {
  closeContextMenu()
  if (!clipboard.value.files.length) return
  const targetDir = currentPath.value
  try {
    for (const src of clipboard.value.files) {
      const dest = resolveTargetPath(targetDir, baseName(src))
      await fileOperation({
        path: src,
        operation: clipboard.value.operation === 'cut' ? 'move' : 'copy',
        targetPath: dest
      })
    }
    toast.success(`已粘贴 ${clipboard.value.files.length} 个项目`)
    clipboard.value = { files: [], operation: '' }
    await refresh()
  } catch (err) {
    toast.error(`粘贴失败: ${err.message}`)
  }
}

function openRename() {
  const item = ctxMenu.value?.item
  closeContextMenu()
  if (!item) return
  renameTarget.value = item
  renameValue.value = item.name
}

async function confirmRename() {
  const item = renameTarget.value
  const newName = renameValue.value.trim()
  if (!item || !newName || newName === item.name) {
    renameTarget.value = null
    return
  }
  try {
    await fileOperation({ path: item.path, operation: 'rename', newName })
    toast.success('重命名成功')
    renameTarget.value = null
    await refresh()
  } catch (err) {
    toast.error(`重命名失败: ${err.message}`)
  }
}

async function deleteItem() {
  const item = ctxMenu.value?.item
  closeContextMenu()
  if (!item) return
  try {
    await fileOperation({ path: item.path, operation: 'delete' })
    toast.success(`已删除「${item.name}」`)
    await refresh()
  } catch (err) {
    toast.error(`删除失败: ${err.message}`)
  }
}

async function runItem() {
  const item = ctxMenu.value?.item
  closeContextMenu()
  if (!item) return
  try {
    const res = await executeFile(item.path)
    toast.success(res?.message || '已启动')
  } catch (err) {
    toast.error(`执行失败: ${err.message}`)
  }
}

function downloadItem() {
  const item = ctxMenu.value?.item
  closeContextMenu()
  if (!item) return
  window.open(downloadUrl(item.path), '_blank')
}

function openPreviewDownload() {
  if (preview.value) window.open(preview.value.url, '_blank')
}

/* ------------------------------------------------------------ 文件打开方式 */
async function handleFileOpen(item) {
  if (item.type === 'image' || item.type === 'video' || item.type === 'audio') {
    preview.value = { kind: item.type, path: item.path, name: item.name, url: downloadUrl(item.path) }
    return
  }
  if (item.type === 'text') {
    await openEditor(item)
    return
  }
  // 其他类型：可执行则运行，否则下载
  if (item.type === 'executable') {
    try {
      const res = await executeFile(item.path)
      toast.success(res?.message || '已启动')
    } catch (err) {
      toast.error(`执行失败: ${err.message}`)
    }
    return
  }
  downloadItem()
}

async function openEditor(item) {
  try {
    const data = await fetchFileContent(item.path)
    editorPath.value = item.path
    editorContent.value = data?.content ?? ''
    editorOpen.value = true
  } catch (err) {
    toast.error(`打开文件失败: ${err.message}`)
  }
}

async function saveEditor() {
  editorSaving.value = true
  try {
    await saveFileContent(editorPath.value, editorContent.value)
    toast.success('文件已保存')
    editorOpen.value = false
    await refresh()
  } catch (err) {
    toast.error(`保存失败: ${err.message}`)
  } finally {
    editorSaving.value = false
  }
}

/* ------------------------------------------------------------------ 新建 */
function openCreate(type) {
  createType.value = type
  createName.value = ''
  createOpen.value = true
}

async function confirmCreate() {
  const name = createName.value.trim()
  if (!name) {
    toast.warning('请输入名称')
    return
  }
  const target = joinPath(currentPath.value, name)
  try {
    if (createType.value === 'folder') {
      await createDirectory(target)
    } else {
      await createFile(target)
    }
    toast.success(createType.value === 'folder' ? '文件夹已创建' : '文件已创建')
    createOpen.value = false
    await refresh()
  } catch (err) {
    toast.error(`创建失败: ${err.message}`)
  }
}

/* ------------------------------------------------------------------ 上传 */
function openUpload() {
  uploadFiles.value = []
  uploadProgress.value = 0
  uploadStatus.value = ''
  uploadOpen.value = true
}

function onFilePicked(event) {
  uploadFiles.value = Array.from(event.target.files || [])
}

async function confirmUpload() {
  if (!uploadFiles.value.length) {
    toast.warning('请先选择文件')
    return
  }
  uploading.value = true
  uploadProgress.value = 0
  let ok = 0
  let fail = 0
  for (let i = 0; i < uploadFiles.value.length; i++) {
    const file = uploadFiles.value[i]
    uploadStatus.value = `正在上传 ${file.name}（${i + 1}/${uploadFiles.value.length}）`
    try {
      await uploadFile(file, currentPath.value)
      ok += 1
    } catch (err) {
      fail += 1
      console.warn('上传失败:', file.name, err)
    }
    uploadProgress.value = Math.round(((i + 1) / uploadFiles.value.length) * 100)
  }
  uploading.value = false
  if (fail === 0) {
    toast.success(`成功上传 ${ok} 个文件`)
    uploadOpen.value = false
  } else {
    toast.warning(`上传完成：成功 ${ok} 个，失败 ${fail} 个`)
  }
  await refresh()
}

const iconOf = item => FILE_ICONS[item.type] || 'file'
const colorOf = item => (item.is_directory ? 'var(--aw-accent)' : FILE_COLORS[item.type] || 'var(--aw-text-mute)')
</script>

<template>
  <div class="view" @click="closeContextMenu">
    <!-- 路径工具条 -->
    <div class="toolbar-panel">
      <div class="path-bar" style="flex: 1">
        <AppButton variant="ghost" size="sm" icon="arrowLeft" title="上级目录" @click="goBack" />
        <AppButton variant="ghost" size="sm" icon="arrowUp" title="返回上一级" @click="goUp" />
        <input
          v-model="pathInput"
          class="path-bar__input"
          aria-label="当前路径"
          @keydown.enter="onPathEnter"
        />
        <AppButton variant="ghost" size="sm" icon="refresh" title="刷新" @click="refresh" />
      </div>

      <select v-if="drives.length" class="input drive-select" aria-label="驱动器" @change="pickDrive">
        <option value="">驱动器…</option>
        <option v-for="d in drives" :key="d.path" :value="d.path">
          {{ d.name }} · {{ d.path }}
        </option>
      </select>
    </div>

    <!-- 操作条 -->
    <div class="toolbar">
      <AppButton size="sm" icon="folderPlus" @click="openCreate('folder')">新建文件夹</AppButton>
      <AppButton size="sm" icon="filePlus" @click="openCreate('file')">新建文件</AppButton>
      <AppButton size="sm" icon="upload" @click="openUpload">上传</AppButton>
      <AppButton
        size="sm"
        icon="clipboard"
        :disabled="!clipboard.files.length"
        @click="pasteItem"
      >
        粘贴<span v-if="clipboard.files.length"> ({{ clipboard.files.length }})</span>
      </AppButton>

      <div class="toolbar__spacer" />

      <span class="aw-label">{{ items.length }} 项</span>
      <span class="chip chip--accent aw-mono" title="当前路径">{{ currentPath || '—' }}</span>
    </div>

    <!-- 文件列表 -->
    <div class="panel file-panel">
      <div v-if="loading" class="file-list">
        <div v-for="i in 6" :key="i" class="file-row">
          <div class="skeleton" style="width: 26px; height: 26px" />
          <div style="flex: 1">
            <div class="skeleton" style="height: 10px; width: 45%" />
          </div>
          <div class="skeleton" style="height: 10px; width: 70px" />
        </div>
      </div>

      <div v-else-if="items.length" class="file-list aw-scroll">
        <div
          v-for="item in items"
          :key="item.path"
          class="file-row"
          :class="{ 'is-selected': selected?.path === item.path }"
          tabindex="0"
          @click="selectItem(item)"
          @dblclick="openItem(item)"
          @contextmenu="showContextMenu($event, item)"
          @keydown.enter="openItem(item)"
        >
          <span class="file-row__icon" :class="{ 'file-row__icon--dir': item.is_directory }" :style="{ color: colorOf(item) }">
            <AppIcon :name="iconOf(item)" :size="15" />
          </span>

          <div class="file-row__main">
            <div class="file-row__name" :title="item.name">{{ item.name }}</div>
            <div class="file-row__meta">
              {{ item.is_directory ? '目录' : formatBytes(item.size) }}
              · {{ formatDateTime(item.modified) }}
            </div>
          </div>

          <div class="file-row__actions">
            <AppButton
              variant="ghost"
              size="sm"
              icon-only
              icon="moreVertical"
              title="更多操作"
              @click.stop="showContextMenu($event, item)"
            />
          </div>
        </div>
      </div>

      <AppEmpty
        v-else
        icon="folder"
        title="此目录为空"
        description="可以新建文件、上传本地文件，或返回上一级目录"
      >
        <AppButton size="sm" icon="arrowUp" @click="goUp">返回上级</AppButton>
      </AppEmpty>
    </div>

    <!-- 右键菜单 -->
    <div
      v-if="ctxMenu"
      class="ctx-menu"
      :style="{ left: `${ctxMenu.x}px`, top: `${ctxMenu.y}px` }"
      @click.stop
    >
      <button class="ctx-menu__item" @click="openFromMenu">
        <AppIcon name="file" :size="13" />打开
      </button>
      <button v-if="ctxMenu.item.type === 'text'" class="ctx-menu__item" @click="editFromMenu">
        <AppIcon name="edit" :size="13" />编辑
      </button>
      <button class="ctx-menu__item" @click="openRename">
        <AppIcon name="edit" :size="13" />重命名
      </button>
      <button class="ctx-menu__item" @click="copyItem">
        <AppIcon name="copy" :size="13" />复制
      </button>
      <button class="ctx-menu__item" @click="cutItem">
        <AppIcon name="scissors" :size="13" />剪切
      </button>
      <button v-if="!ctxMenu.item.is_directory" class="ctx-menu__item" @click="downloadItem">
        <AppIcon name="download" :size="13" />下载
      </button>
      <button v-if="ctxMenu.item.type === 'executable'" class="ctx-menu__item" @click="runItem">
        <AppIcon name="play" :size="13" />运行
      </button>
      <div class="ctx-menu__sep" />
      <button class="ctx-menu__item ctx-menu__item--danger" @click="deleteItem">
        <AppIcon name="trash" :size="13" />删除
      </button>
    </div>

    <!-- 新建 -->
    <AppModal v-if="createOpen" title="新建项目" @close="createOpen = false">
      <div class="field">
        <label class="field__label">类型</label>
        <div class="seg">
          <button :class="{ 'is-active': createType === 'folder' }" @click="createType = 'folder'">文件夹</button>
          <button :class="{ 'is-active': createType === 'file' }" @click="createType = 'file'">文件</button>
        </div>
      </div>
      <div class="field" style="margin-top: var(--aw-space-4)">
        <label class="field__label" for="create-name">名称</label>
        <input id="create-name" v-model="createName" class="input" @keydown.enter="confirmCreate" />
      </div>
      <template #footer>
        <AppButton variant="ghost" @click="createOpen = false">取消</AppButton>
        <AppButton variant="primary" @click="confirmCreate">创建</AppButton>
      </template>
    </AppModal>

    <!-- 重命名 -->
    <AppModal v-if="renameTarget" title="重命名" @close="renameTarget = null">
      <div class="field">
        <label class="field__label" for="rename-input">新名称</label>
        <input
          id="rename-input"
          v-model="renameValue"
          class="input"
          @keydown.enter="confirmRename"
        />
      </div>
      <template #footer>
        <AppButton variant="ghost" @click="renameTarget = null">取消</AppButton>
        <AppButton variant="primary" @click="confirmRename">保存</AppButton>
      </template>
    </AppModal>

    <!-- 上传 -->
    <AppModal v-if="uploadOpen" title="上传文件" subtitle="支持多文件上传" @close="uploadOpen = false">
      <div class="field">
        <label class="field__label" for="upload-input">选择文件</label>
        <input id="upload-input" class="input" type="file" multiple @change="onFilePicked" />
        <p v-if="uploadFiles.length" class="aw-text-xs aw-text-mute">
          已选 {{ uploadFiles.length }} 个文件
        </p>
      </div>

      <div v-if="uploading || uploadStatus" class="upload-progress">
        <div class="meter">
          <div class="meter__fill meter__fill--accent" :style="{ width: `${uploadProgress}%` }" />
        </div>
        <span class="aw-text-xs aw-text-mute">{{ uploadStatus }}</span>
      </div>

      <template #footer>
        <AppButton variant="ghost" :disabled="uploading" @click="uploadOpen = false">取消</AppButton>
        <AppButton variant="primary" :loading="uploading" @click="confirmUpload">开始上传</AppButton>
      </template>
    </AppModal>

    <!-- 文本编辑器 -->
    <AppModal
      v-if="editorOpen"
      :title="baseName(editorPath)"
      :subtitle="editorPath"
      size="wide"
      @close="editorOpen = false"
    >
      <textarea v-model="editorContent" class="input input--mono editor-area" spellcheck="false" />
      <template #footer>
        <AppButton variant="ghost" @click="editorOpen = false">取消</AppButton>
        <AppButton variant="primary" :loading="editorSaving" @click="saveEditor">保存</AppButton>
      </template>
    </AppModal>

    <!-- 媒体预览 -->
    <AppModal
      v-if="preview"
      :title="preview.name"
      :subtitle="preview.path"
      size="full"
      @close="preview = null"
    >
      <div class="media-preview">
        <img v-if="preview.kind === 'image'" :src="preview.url" :alt="preview.name" />
        <video v-else-if="preview.kind === 'video'" :src="preview.url" controls autoplay />
        <audio v-else :src="preview.url" controls autoplay />
      </div>
      <template #footer>
        <AppButton variant="ghost" @click="preview = null">关闭</AppButton>
        <AppButton variant="primary" icon="download" @click="openPreviewDownload">
          下载
        </AppButton>
      </template>
    </AppModal>
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

.toolbar-panel {
  display: flex;
  gap: var(--aw-space-2);
  align-items: stretch;
}

.drive-select {
  width: auto;
  min-width: 150px;
  flex-shrink: 0;
}

.file-panel {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.file-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.seg {
  display: flex;
  gap: var(--aw-space-1);
  padding: 3px;
  background: var(--aw-abyss);
  border: 1px solid var(--aw-line);
  border-radius: var(--aw-radius);
}

.seg button {
  flex: 1;
  padding: var(--aw-space-2);
  font-size: var(--aw-text-sm);
  color: var(--aw-text-mute);
  border-radius: var(--aw-radius-xs);
  transition: all var(--aw-dur-fast) var(--aw-ease);
}

.seg button.is-active {
  background: var(--aw-accent-ghost);
  color: var(--aw-accent);
  font-weight: 500;
}

.upload-progress {
  display: flex;
  flex-direction: column;
  gap: var(--aw-space-2);
  margin-top: var(--aw-space-4);
}

.editor-area {
  min-height: 52vh;
  font-size: var(--aw-text-sm);
  line-height: 1.7;
}

@media (max-width: 720px) {
  .toolbar-panel {
    flex-direction: column;
  }
  .drive-select {
    width: 100%;
  }
}

/* --------------------------------------------------------------------------
   iOS 26 移动端
   -------------------------------------------------------------------------- */
@media (max-width: 900px) {
  .view {
    gap: var(--aw-space-2);
  }

  .path-bar {
    border-radius: var(--aw-radius-xl);
    background: var(--aw-panel-hi);
  }

  .path-bar__input {
    height: 32px;
    font-size: var(--aw-text-xs);
  }

  .file-panel {
    border-radius: var(--aw-radius-xl);
  }

  /* iOS 分组列表：行高更宽松、图标更大 */
  .file-row {
    padding: var(--aw-space-3) var(--aw-space-4);
    gap: var(--aw-space-3);
  }

  .file-row__icon {
    width: 32px;
    height: 32px;
    border-radius: var(--aw-radius-md, 6px);
  }

  .file-row__name {
    font-size: var(--aw-text-base);
  }

  .file-row__meta {
    font-size: var(--aw-text-2xs);
  }

  /* 工具按钮改为 iOS 风格圆形 */
  .file-row__actions :deep(.btn) {
    border-radius: 50%;
  }
}
</style>
