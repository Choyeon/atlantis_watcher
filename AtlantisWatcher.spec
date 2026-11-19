# -*- mode: python ; coding: utf-8 -*-
"""
Atlantis Watcher — PyInstaller 规格文件（生产级）

相比命令行参数方式，spec 的优势：
  - 构建逻辑可版本管理、可 code review、可复现
  - 可精细控制 COLLECT（二进制/数据分离）、hiddenimports、excludes
  - 支持运行时 hook，处理动态导入与资源定位

构建：
    pyinstaller AtlantisWatcher.spec --noconfirm
    pyinstaller AtlantisWatcher.spec --noconfirm --onefile   # 便携单文件
"""

import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# 路径与版本
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(SPECPATH).resolve()
BUILD_DIR = PROJECT_ROOT / 'build'
DIST_DIR = PROJECT_ROOT / 'dist'
FRONTEND_DIST = PROJECT_ROOT / 'static' / 'dist'

APP_NAME = 'AtlantisWatcher'
APP_VERSION = '1.1.1'
APP_DESCRIPTION = 'Atlantis Watcher - Windows 远程控制与系统监控'

# ---------------------------------------------------------------------------
# 前置校验：前端产物缺失会导致 exe 内页面白屏，必须在构建前拦住
# ---------------------------------------------------------------------------
if not (FRONTEND_DIST / 'index.html').exists():
    raise SystemExit(
        '[构建中止] 未找到前端构建产物：{0}\n'
        '请先执行： cd frontend && npm install && npm run build'.format(FRONTEND_DIST)
    )

if not (PROJECT_ROOT / 'icon.ico').exists():
    raise SystemExit('[构建中止] 未找到 icon.ico，请执行: python tools/make_icon.py')

# ---------------------------------------------------------------------------
# 数据文件：静态资源与模板
# 说明：static 目录整体收集，确保 Vite 产物（assets 哈希文件名）全部就位
# ---------------------------------------------------------------------------
datas = [
    (str(FRONTEND_DIST), 'static/dist'),
    (str(PROJECT_ROOT / 'icon.ico'), '.'),
]

# 旧版 template/ 与 webgui/ 已清理：主页只服务 static/dist。
# 前端产物缺失时由 app/routers/meta.py 返回内置提示页，不再保留整套旧模板。

# ---------------------------------------------------------------------------
# 隐藏导入：动态导入与 PyInstaller 静态分析无法覆盖的模块
# ---------------------------------------------------------------------------
hiddenimports = [
    # FastAPI / Starlette
    'uvicorn.logging',
    'uvicorn.loops.auto',
    'uvicorn.loops.asyncio',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.http.h11_impl',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.protocols.websockets.websockets_impl',
    'uvicorn.lifespan.on',
    'uvicorn.lifespan.off',

    # 编码器（JSON 响应依赖）
    'encodings.idna',
    'charset_normalizer.md__mypyc',

    # 第三方
    'psutil',
    'cv2',
    'numpy',
    'pyautogui',
    'pyautogui._pyautogui_win',
    'pyautogui._mouseinfo',
    'PIL.Image',
    'PIL.ImageGrab',
    'PIL._tkinter_finder',
    'pystray',
    'pystray._win32',
    'win32com.client',
    'win32com.shell.shell',
    'pywintypes',
    'pythoncom',
    'multipart',
    'multipart.multipart',
    'email.mime.multipart',

    # 本项目模块（确保被显式收集）
    'app',
    'app.bootstrap',
    'app.factory',
    'app.runtime',
    'app.paths',
    'app.settings_store',
    'app.platform',
    'app.platform.windows',
    'app.api_commands',
    'app.routers.meta',
    'app.routers.settings',
    'app.config',
    'app.decorators',
    'app.exceptions',
    'app.logging_utils',
    'app.models',
    'app.server',
    'app.tray_icon',
    'app.utils',
    'app.routers.system',
    'app.routers.files',
    'app.routers.websocket',
    'app.routers.control',
    'app.services.command_service',
    'app.services.file_service',
    'app.services.system_service',
    'app.services.input_service',
]

# ---------------------------------------------------------------------------
# 排除模块：显著减小体积，避免带入无关依赖
# ---------------------------------------------------------------------------
excludes = [
    # 测试与交互式工具
    'pytest', '_pytest', 'nose', 'unittest',
    'IPython', 'jupyter', 'jupyter_client', 'notebook', 'nbformat',
    'spyder', 'pylint', 'mypy', 'flake8',

    # 科学计算（本项目不使用）
    'scipy', 'pandas', 'matplotlib', 'sympy', 'networkx',
    'tkinter', 'test', 'distutils',

    # 其他
    'setuptools', 'pip', 'wheel', 'pkg_resources',
    'docutils', 'sphinx',
    'torch', 'tensorflow',
    'email.mime.text',
]

# ---------------------------------------------------------------------------
# 版本资源
# 注意：EXE(version=) 需要文件路径而非脚本文本，故写入独立文件
# ---------------------------------------------------------------------------
version_file = PROJECT_ROOT / 'build' / 'version_info.txt'
version_file.parent.mkdir(parents=True, exist_ok=True)
version_file.write_text(f'''# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({APP_VERSION.replace('.', ',')}, 0),
    prodvers=({APP_VERSION.replace('.', ',')}, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          '040904B0',
          [
            StringStruct('CompanyName', 'Atlantis'),
            StringStruct('FileDescription', '{APP_DESCRIPTION}'),
            StringStruct('FileVersion', '{APP_VERSION}'),
            StringStruct('InternalName', '{APP_NAME}'),
            StringStruct('LegalCopyright', 'Copyright (C) 2026 Atlantis'),
            StringStruct('OriginalFilename', '{APP_NAME}.exe'),
            StringStruct('ProductName', '{APP_NAME}'),
            StringStruct('ProductVersion', '{APP_VERSION}'),
            StringStruct('Comments', 'Windows 远程控制与系统监控工具')
          ])
      ]),
    VarFileInfo([VarStruct('Translation', [2052, 1200])])
  ]
)''', encoding='utf-8')

# ---------------------------------------------------------------------------
# Windows 应用清单
# 关键点：
#   - requestedExecutionLevel: requireAdministrator（关机/重启/锁屏需管理员）
#   - dpiAware / dpiAwareness: PerMonitorV2（高 DPI 屏不糊）
#   - longPathAware: 支持 >260 字符路径
#   - supportedOS: 声明 Win10/11，避免兼容性 shim 干扰
# ---------------------------------------------------------------------------
manifest = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">
  <assemblyIdentity type="win32" name="Atlantis.Watcher" version="0.1.0.0"
                    processorArchitecture="amd64"/>
  <description>Atlantis Watcher - Windows 远程控制与系统监控</description>

  <trustInfo xmlns="urn:schemas-microsoft-com:asm.v3">
    <security>
      <requestedPrivileges>
        <requestedExecutionLevel level="requireAdministrator" uiAccess="false"/>
      </requestedPrivileges>
    </security>
  </trustInfo>

  <compatibility xmlns="urn:schemas-microsoft-com:compatibility.v1">
    <application>
      <supportedOS Id="{8e0f7a12-bfb3-4fe8-b9a5-48fd50a15a9a}"/> <!-- Win10/11 -->
      <supportedOS Id="{1f676c76-80e1-4239-95bb-83d0f6d0da78}"/> <!-- Win8.1 -->
      <supportedOS Id="{4a2f28e3-53b9-4441-ba9c-d69d4a4a6e38}"/> <!-- Win8 -->
      <supportedOS Id="{35138b9a-5d96-4fbd-8e2d-a2440225f93a}"/> <!-- Win7 -->
    </application>
  </compatibility>

  <application xmlns="urn:schemas-microsoft-com:asm.v3">
    <windowsSettings>
      <dpiAware xmlns="http://schemas.microsoft.com/SMI/2005/WindowsSettings">true/pm</dpiAware>
      <dpiAwareness xmlns="http://schemas.microsoft.com/SMI/2016/WindowsSettings">PerMonitorV2, PerMonitor</dpiAwareness>
      <longPathAware xmlns="http://schemas.microsoft.com/SMI/2016/WindowsSettings">true</longPathAware>
      <activeCodePage xmlns="http://schemas.microsoft.com/SMI/2019/WindowsSettings">UTF-8</activeCodePage>
    </windowsSettings>
  </application>
</assembly>
'''

# ---------------------------------------------------------------------------
# 运行时 Hook：把冻结态下的运行目录指向可写位置
# 生产环境必须保证：日志、自启快捷方式等不写入 _MEIPASS 临时目录
# 注意：runtime_hooks 参数需要文件路径，脚本内容写在 tools/runtime_hook.py
# ---------------------------------------------------------------------------
RUNTIME_HOOK = str(PROJECT_ROOT / 'tools' / 'runtime_hook.py')
if not Path(RUNTIME_HOOK).exists():
    raise SystemExit(f'[构建中止] 未找到运行时 hook: {RUNTIME_HOOK}')

block_cipher = None

# ---------------------------------------------------------------------------
# 构建入口
#
# 单文件 / 目录版双模式：
#   PyInstaller 6.x 不允许对 spec 文件传 --onefile/--onedir，
#   因此通过环境变量 AW_ONEFILE 切换 EXE 的 exclude_binaries 与 COLLECT。
# ---------------------------------------------------------------------------
import os

ONEFILE = os.environ.get('AW_ONEFILE', '').lower() in ('1', 'true', 'yes')

a = Analysis(
    ['main.py'],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[RUNTIME_HOOK],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

if ONEFILE:
    # 单文件：所有内容压入 exe，运行时解压到 _MEIPASS
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name=APP_NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,               # 不使用 UPX：部分杀软对 UPX 壳误报率高
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=str(PROJECT_ROOT / 'icon.ico'),
        version=str(version_file),
        manifest=manifest,
    )
else:
    # 目录版：exe 与 _internal/ 分离，启动快、误报率低
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name=APP_NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=str(PROJECT_ROOT / 'icon.ico'),
        version=str(version_file),
        manifest=manifest,
    )

    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=False,
        upx_exclude=[],
        name=APP_NAME,
    )
