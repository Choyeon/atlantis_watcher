# -*- coding: utf-8 -*-
"""
打包产物验收测试

验证打包后的 exe 是否真的可用，而不是只看文件是否存在：
  1. 启动 dist/AtlantisWatcher/AtlantisWatcher.exe
  2. 等待端口就绪
  3. 校验首页返回的是前端构建产物（含 assets 引用）
  4. 校验静态资源可访问
  5. 校验 API 端点可用
  6. 校验 WebSocket 通道可用
  7. 校验日志写入到了可写目录（而非临时解压目录）
  8. 优雅关闭进程

用法:
    python tools/verify_package.py
    python tools/verify_package.py --port 8999
"""

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = PROJECT_ROOT / 'dist'
APP_NAME = 'AtlantisWatcher'

PASS = '\033[32m✓\033[0m'
FAIL = '\033[31m✗\033[0m'
WARN = '\033[33m!\033[0m'
INFO = '\033[36m·\033[0m'

results = []


def check(name, condition, detail=''):
    ok = bool(condition)
    results.append((name, ok))
    mark = PASS if ok else FAIL
    print(f'  {mark} {name}' + (f'  {detail}' if detail else ''))
    return ok


def port_in_use(port, host='127.0.0.1'):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def http_get(url, timeout=10):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.status, r.read().decode('utf-8', errors='replace')


def http_post(url, payload=None, timeout=10):
    data = json.dumps(payload or {}).encode()
    req = urllib.request.Request(
        url, data=data, headers={'Content-Type': 'application/json'}, method='POST'
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode('utf-8', errors='replace')


def wait_port(port, timeout=45):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if port_in_use(port):
            return True
        time.sleep(0.5)
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=26541)
    parser.add_argument('--exe', default=None, help='指定 exe 路径')
    args = parser.parse_args()

    exe_path = Path(args.exe) if args.exe else DIST_DIR / APP_NAME / f'{APP_NAME}.exe'
    if not exe_path.exists():
        print(f'{FAIL} 未找到打包产物: {exe_path}')
        print(f'  请先执行: python build.py')
        return 1

    print(f'\n\033[1mAtlantis Watcher — 打包产物验收\033[0m')
    print(f'  产物: {exe_path}')
    print(f'  体积: {exe_path.stat().st_size / 1024 / 1024:.1f} MB')
    print(f'{"─" * 62}')

    if port_in_use(args.port):
        print(f'{FAIL} 端口 {args.port} 已被占用，请先停止占用进程')
        return 1

    # 记录打包前 %LOCALAPPDATA%\AtlantisWatcher 的日志状态
    log_dir = Path(os.environ.get('LOCALAPPDATA', '')) / 'AtlantisWatcher'
    log_file = log_dir / 'log.txt'
    log_existed = log_file.exists()
    log_mtime_before = log_file.stat().st_mtime if log_existed else 0

    print(f'\n\033[1m[1/6] 启动进程\033[0m')
    proc = subprocess.Popen(
        [str(exe_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=str(PROJECT_ROOT),
    )
    print(f'  {INFO} PID={proc.pid}')

    try:
        # 2. 端口就绪
        print(f'\n\033[1m[2/6] 等待服务就绪\033[0m')
        ready = wait_port(args.port, timeout=60)
        if not check(f'服务在 60s 内监听 {args.port}', ready):
            proc.terminate()
            out = proc.stdout.read().decode('utf-8', errors='replace')[-2000:]
            print(f'{WARN} 进程输出:\n{out}')
            return 1
        print(f'  {INFO} 端口已就绪')

        base = f'http://127.0.0.1:{args.port}'

        # 3. 首页
        print(f'\n\033[1m[3/6] 首页与静态资源\033[0m')
        status, html = http_get(base + '/')
        check(f'首页返回 200', status == 200, f'(status={status})')
        # Vite 以 base:'./' 构建，资源引用形如 ./assets/xxx.js
        is_vite = 'assets/' in html and ('id="app"' in html)
        check('首页为 Vite 构建产物', is_vite)
        check('首页含应用挂载点', '<div id="app">' in html)

        import re
        # 同时兼容相对路径（./assets/...）与旧的绝对路径
        refs = re.findall(r'(?:\./|/)(?:static/dist/)?assets/([a-zA-Z0-9._-]+\.(?:js|css))', html)
        check('首页引用了资源', len(refs) > 0, f'({len(refs)} 项)')
        for r in sorted(set(refs)):
            s, body = http_get(f'{base}/assets/{r}')
            check(f'资源可访问 {r[:32]}', s == 200 and len(body) > 0, f'({len(body)}B)')

        # 4. API
        print(f'\n\033[1m[4/6] API 端点\033[0m')
        s, body = http_get(base + '/health')
        check('/health 可用', s == 200 and 'healthy' in body)

        s, body = http_get(base + '/api/system/info')
        try:
            info = json.loads(body)
            check('/api/system/info 返回完整数据',
                  'cpu' in info and 'memory' in info and 'disk' in info,
                  f"(cores={info.get('cpu', {}).get('count')})")
        except Exception:
            check('/api/system/info 返回完整数据', False)

        s, body = http_get(base + '/api/files/drives')
        try:
            drives = json.loads(body)
            check('/api/files/drives 返回驱动器', drives.get('count', 0) > 0,
                  f"({drives.get('count')} 个)")
        except Exception:
            check('/api/files/drives 返回驱动器', False)

        s, body = http_get(base + '/api/files/list?path=C%3A%5C')
        try:
            flist = json.loads(body)
            check('/api/files/list 支持 path 参数', flist.get('success') is True,
                  f"({flist.get('count')} 项)")
        except Exception:
            check('/api/files/list 支持 path 参数', False)

        # 显示器控制：只实调无副作用的「点亮」，不要把验收机屏幕弄黑
        try:
            s, body = http_post(base + '/api/monitor/on')
            mon = json.loads(body)
            check('/api/monitor/on 显示器控制可用',
                  s == 200 and mon.get('success') is True,
                  f"({mon.get('message')})")
        except Exception as e:
            check('/api/monitor/on 显示器控制可用', False, f'({type(e).__name__})')

        try:
            s, body = http_get(base + '/openapi.json')
            paths = json.loads(body).get('paths', {})
            check('显示器控制两条路由已注册',
                  s == 200 and '/api/monitor/off' in paths and '/api/monitor/on' in paths)
        except Exception as e:
            check('显示器控制两条路由已注册', False, f'({type(e).__name__})')

        # 5. WebSocket
        print(f'\n\033[1m[5/6] WebSocket 通道\033[0m')
        ws_ok = False
        monitor_data = {}
        try:
            import asyncio
            import websockets

            async def probe():
                uri = f'ws://127.0.0.1:{args.port}/ws/monitor'
                async with websockets.connect(uri, open_timeout=15) as ws:
                    raw = await asyncio.wait_for(ws.recv(), timeout=15)
                    return json.loads(raw)

            monitor_data = asyncio.run(probe())
            ws_ok = 'cpu_percent' in monitor_data
            check('/ws/monitor 推送监控数据', ws_ok,
                  f"(cpu={monitor_data.get('cpu_percent')}%)")
        except ImportError:
            print(f'  {WARN} 未安装 websockets，跳过 WS 校验')
        except Exception as e:
            check('/ws/monitor 推送监控数据', False, f'({type(e).__name__})')

        # 6. 日志落盘位置
        print(f'\n\033[1m[6/6] 运行时目录与日志\033[0m')
        time.sleep(2)
        check('日志目录为 %LOCALAPPDATA%\\AtlantisWatcher',
              log_dir.exists(), f'({log_dir})')
        if log_file.exists():
            mtime_after = log_file.stat().st_mtime
            check('日志文件已写入', mtime_after > log_mtime_before,
                  f'({log_file.stat().st_size} 字节)')
            content = log_file.read_text(encoding='utf-8', errors='replace')
            check('日志包含启动记录', 'Atlantis Watcher' in content or '工作目录' in content)
            # 确认没有写进临时解压目录
            check('日志未写入临时解压目录',
                  not any(p.suffix == '.log' for p in Path(
                      getattr(sys, '_MEIPASS', PROJECT_ROOT)).glob('*.log')))
        else:
            check('日志文件已写入', False, f'(未找到 {log_file})')

    finally:
        print(f'\n\033[1m清理\033[0m')
        proc.terminate()
        try:
            proc.wait(timeout=10)
            print(f'  {PASS} 进程已优雅退出')
        except subprocess.TimeoutExpired:
            proc.kill()
            print(f'  {WARN} 进程强制终止')

    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f'\n{"─" * 62}')
    if passed == total:
        print(f'\033[32m\033[1m全部通过: {passed}/{total}\033[0m')
        print(f'打包产物可正常使用\n')
        return 0
    print(f'\033[31m\033[1m失败: {total - passed}/{total} 项未通过\033[0m')
    for name, ok in results:
        if not ok:
            print(f'  {FAIL} {name}')
    print()
    return 1


if __name__ == '__main__':
    sys.exit(main())
