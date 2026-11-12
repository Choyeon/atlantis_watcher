import { http } from './client'

/**
 * 系统与进程 API
 * 后端端点位于 app/routers/system.py
 */

/** 获取系统信息 (SystemInfo) */
export function fetchSystemInfo() {
  return http.get('/api/system/info')
}

/** 获取进程列表 */
export function fetchProcesses() {
  return http.get('/api/system/processes')
}

/** 终止进程 */
export function killProcess(pid, force = false) {
  return http.post('/api/system/kill-process', { pid, force })
}

/**
 * 电源 / 命令 API
 * 后端端点位于 app/api_commands.py
 * 注意：后端返回 BaseResponse { success, message, data }
 * 执行命令的输出实际位于 data.output / data.error
 */

/** 执行 CMD 或 PowerShell 命令 */
export async function executeCommand(command, isPowershell = false) {
  const res = await http.post('/api/cmd', { command, is_powershell: isPowershell })
  return {
    success: res?.success ?? false,
    output: res?.data?.output ?? '',
    error: res?.data?.error ?? '',
    returncode: res?.data?.returncode ?? 0,
    message: res?.message ?? ''
  }
}

/** 立即关机 */
export function shutdown() {
  return http.post('/api/shutdown', {})
}

/** 延时关机（秒） */
export function shutdownAfter(seconds) {
  return http.post(`/api/shutdown/${seconds}`, {})
}

/** 取消关机 / 重启 */
export function cancelShutdown() {
  return http.post('/api/cancel', {})
}

/** 重启 */
export function reboot() {
  return http.post('/api/reboot', {})
}

/** 锁屏 */
export function lockScreen() {
  return http.post('/api/lock', {})
}

/**
 * 显示器电源控制
 * 后端通过 WM_SYSCOMMAND / SC_MONITORPOWER 广播实现，Windows 专属。
 * 熄屏只切断显示输出，系统与服务继续运行，可用 turnOnMonitor 远程恢复。
 */

/** 关闭显示器（熄屏） */
export function turnOffMonitor() {
  return http.post('/api/monitor/off', {})
}

/** 点亮显示器 */
export function turnOnMonitor() {
  return http.post('/api/monitor/on', {})
}

/** 注销 */
export function logout() {
  return http.post('/api/logout', {})
}

/**
 * 休眠 / 睡眠
 * 后端无专用端点，通过 CMD 命令实现：
 *   休眠: rundll32 powrprof.dll,SetSuspendState 0,1,0
 *   睡眠: rundll32 powrprof.dll,SetSuspendState 1,1,0
 */
export function hibernate() {
  return executeCommand('rundll32 powrprof.dll,SetSuspendState 0,1,0', false)
}

export function sleep() {
  return executeCommand('rundll32 powrprof.dll,SetSuspendState 1,1,0', false)
}
