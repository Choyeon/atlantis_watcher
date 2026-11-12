import { http, withQuery } from './client'

/**
 * 文件管理 API
 * 后端端点位于 app/routers/files.py
 *
 * 重要：listFiles 必须显式传 path，
 * 否则后端默认 path="/" 在 Windows 上会指向当前盘根目录且无法列出。
 */

/** 获取驱动器列表 */
export function fetchDrives() {
  return http.get('/api/files/drives')
}

/** 列出目录内容 */
export function listFiles(path) {
  return http.get(withQuery('/api/files/list', { path }))
}

/** 读取文本文件内容 */
export function fetchFileContent(path) {
  return http.get(withQuery('/api/files/content', { path }))
}

/** 保存文本文件 */
export function saveFileContent(path, content) {
  return http.post('/api/files/content', { path, content })
}

/**
 * 文件操作：rename / delete / copy / move
 * 后端枚举 FileOperationType: rename|delete|copy|move
 */
export function fileOperation({ path, operation, newName, targetPath }) {
  const body = { path, operation }
  if (newName) body.new_name = newName
  if (targetPath) body.target_path = targetPath
  return http.post('/api/files/operation', body)
}

/** 运行可执行文件 / 快捷方式 */
export function executeFile(path) {
  return http.post('/api/files/execute', { path })
}

/** 下载文件地址 */
export function downloadUrl(path) {
  return withQuery('/api/files/download', { path })
}

/** 上传文件（FormData 需同时带 file 与 path） */
export function uploadFile(file, targetDir) {
  const form = new FormData()
  form.append('file', file)
  form.append('path', targetDir)
  return http.post('/api/files/upload', form)
}

/** 新建文件夹 */
export function createDirectory(path) {
  return http.post('/api/files/mkdir', { path })
}

/** 新建空文件 */
export function createFile(path, content = '') {
  return http.post('/api/files/create', { path, content })
}
