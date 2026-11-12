# -*- coding: utf-8 -*-
"""
运行时 Hook（PyInstaller）

在打包后的应用启动时、任何业务模块导入之前执行。

职责：把工作目录从只读的临时解压目录（_MEIPASS）切换到可写位置。
原因：_MEIPASS 在进程退出后即被清理，日志、自启快捷方式等写入其中等于没写，
      生产环境需要日志可追溯。
"""

import os
import sys

if getattr(sys, 'frozen', False):
    # 优先使用 %LOCALAPPDATA%（用户可写、无需管理员权限）
    appdata = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')
    runtime_dir = os.path.join(appdata, 'AtlantisWatcher')

    try:
        os.makedirs(runtime_dir, exist_ok=True)
    except OSError:
        # 兜底：程序所在目录（onedir 模式下通常可写，Program Files 下则不可写）
        runtime_dir = os.path.dirname(sys.executable)

    try:
        os.chdir(runtime_dir)
    except OSError:
        pass
