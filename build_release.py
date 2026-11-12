# -*- coding: utf-8 -*-
"""
Atlantis Watcher — 生产级构建脚本

相比原始 build.py 的改进：
  1. 统一版本号来源（pyproject.toml），消除三处版本不一致
  2. 前置校验：前端产物、图标、依赖齐备才允许构建
  3. 基于 spec 文件构建，构建逻辑可版本管理
  4. 构建后自检：产物存在、静态资源可达、关键模块已打包
  5. 支持 onedir（安装包用）/ onefile（便携版）
  6. 可选代码签名

用法:
    python build.py                 # 默认 onedir（配合 Inno Setup 制作安装包）
    python build.py --onefile       # 单文件便携版
    python build.py --installer     # 构建后调用 Inno Setup 生成安装包
    python build.py --sign "CN=..." # 使用证书签名
    python build.py --skip-frontend # 跳过前端构建（已构建过时）
    python build.py --clean         # 清理后完整重建
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
BUILD_DIR = PROJECT_ROOT / 'build'
DIST_DIR = PROJECT_ROOT / 'dist'
FRONTEND_DIR = PROJECT_ROOT / 'frontend'
FRONTEND_DIST = PROJECT_ROOT / 'static' / 'dist'
SPEC_FILE = PROJECT_ROOT / 'AtlantisWatcher.spec'

APP_NAME = 'AtlantisWatcher'


class C:
    """控制台颜色"""
    RESET = '\033[0m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    CYAN = '\033[36m'
    BOLD = '\033[1m'


def log(msg, level='INFO'):
    color = {
        'INFO': C.CYAN, 'OK': C.GREEN, 'WARN': C.YELLOW,
        'ERR': C.RED, 'STEP': C.BLUE + C.BOLD
    }.get(level, '')
    print(f'{color}[{level}]{C.RESET} {msg}', flush=True)


def step(msg):
    log(f'▶ {msg}', 'STEP')


def ok(msg):
    log(f'✓ {msg}', 'OK')


def warn(msg):
    log(f'! {msg}', 'WARN')


def err(msg):
    log(f'✗ {msg}', 'ERR')


def read_version():
    """从 pyproject.toml 读取版本号（唯一版本源）"""
    pyproject = PROJECT_ROOT / 'pyproject.toml'
    if not pyproject.exists():
        return '1.1.0'
    in_project = False
    for line in pyproject.read_text(encoding='utf-8').splitlines():
        stripped = line.strip()
        if stripped.startswith('['):
            in_project = stripped == '[project]'
            continue
        if in_project and stripped.startswith('version'):
            return stripped.split('=', 1)[1].strip().strip('"').strip("'")
    return '1.1.0'


def sync_version(version):
    """把版本号同步到 spec 与 FastAPI 应用，消除不一致"""
    spec_path = PROJECT_ROOT / 'AtlantisWatcher.spec'
    if spec_path.exists():
        content = spec_path.read_text(encoding='utf-8')
        content = re.sub(r"APP_VERSION = '[^']+'", f"APP_VERSION = '{version}'", content)
        content = re.sub(r'version="1\.\d+\.\d+\.0"', f'version="{version}.0"', content)
        spec_path.write_text(content, encoding='utf-8')
        ok(f'version 已同步至 spec: {version}')

    pyproject = PROJECT_ROOT / 'pyproject.toml'
    if pyproject.exists():
        content = pyproject.read_text(encoding='utf-8')
        new = re.sub(r'(?m)^version\s*=\s*["\'][^"\']+["\']', f'version = "{version}"', content)
        if new != content:
            pyproject.write_text(new, encoding='utf-8')
            ok(f'version 已同步至 pyproject.toml: {version}')

    main_py = PROJECT_ROOT / 'main.py'
    if main_py.exists():
        content = main_py.read_text(encoding='utf-8')
        new = re.sub(r'version="[^"]*"', f'version="{version}"', content, count=1)
        if new != content:
            main_py.write_text(new, encoding='utf-8')
            ok(f'version 已同步至 main.py: {version}')


def check_frontend():
    """前置校验：前端产物"""
    if not (FRONTEND_DIST / 'index.html').exists():
        err('未找到前端构建产物 static/dist/index.html')
        return False
    assets = list((FRONTEND_DIST / 'assets').glob('*.js'))
    if not assets:
        err('前端产物缺少 JS 资源')
        return False
    ok(f'前端产物就绪（{len(assets)} 个 JS chunk）')
    return True


def check_icon():
    """前置校验：图标是否为合法多尺寸 ICO"""
    icon = PROJECT_ROOT / 'icon.ico'
    if not icon.exists():
        err('未找到 icon.ico，请执行: python tools/make_icon.py')
        return False
    try:
        import struct
        data = icon.read_bytes()
        reserved, typ, count = struct.unpack('<HHH', data[:6])
        if typ != 1:
            err(f'icon.ico 不是合法的 ICO 文件（type={typ}）')
            return False
        if count < 3:
            warn(f'icon.ico 仅含 {count} 个尺寸，建议 >= 4（16/32/48/256）')
        else:
            ok(f'图标就绪（{count} 个尺寸）')
        return True
    except Exception as e:
        err(f'图标校验失败: {e}')
        return False


def check_deps():
    """前置校验：关键依赖"""
    try:
        import PyInstaller  # noqa: F401
        ok('PyInstaller 已安装')
    except ImportError:
        err('未安装 PyInstaller，请执行: pip install pyinstaller')
        return False

    missing = []
    for mod in ['fastapi', 'uvicorn', 'psutil', 'cv2', 'pyautogui', 'pystray', 'PIL', 'multipart']:
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        err(f'缺少运行时依赖: {", ".join(missing)}')
        return False
    ok('运行时依赖齐备')
    return True


def build_frontend():
    """构建前端产物"""
    if not FRONTEND_DIR.exists():
        err('未找到 frontend 目录')
        return False

    npm = shutil.which('npm')
    if not npm:
        err('未找到 npm，无法构建前端')
        return False

    if not (FRONTEND_DIR / 'node_modules').exists():
        log('首次构建，正在安装前端依赖…')
        r = subprocess.run([npm, 'install', '--no-fund', '--no-audit'], cwd=FRONTEND_DIR)
        if r.returncode != 0:
            err('npm install 失败')
            return False

    log('正在构建前端…')
    r = subprocess.run([npm, 'run', 'build'], cwd=FRONTEND_DIR)
    if r.returncode != 0:
        err('前端构建失败')
        return False
    ok('前端构建完成')
    return True


def clean():
    """清理构建产物"""
    for d in (BUILD_DIR, DIST_DIR):
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
            log(f'已清理 {d.name}/')


def run_pyinstaller(onefile=False, sign_identity=None):
    """执行 PyInstaller 构建

    PyInstaller 6.x 不允许对 spec 文件传 --onefile/--onedir，
    因此通过环境变量 AW_ONEFILE 让 spec 自行切换模式。
    """
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        str(SPEC_FILE),
        '--noconfirm',
        '--distpath', str(DIST_DIR),
        '--workpath', str(BUILD_DIR),
    ]

    env = os.environ.copy()
    if onefile:
        env['AW_ONEFILE'] = '1'
        log('构建模式：单文件便携版（onefile）')
    else:
        env['AW_ONEFILE'] = '0'
        log('构建模式：目录版（onedir，供安装包使用）')

    if sign_identity:
        cmd += ['--sign', sign_identity]
        ok(f'将使用证书签名: {sign_identity}')

    step('执行 PyInstaller（首次构建耗时较长，约 2-5 分钟）…')
    start = time.time()
    r = subprocess.run(cmd, cwd=PROJECT_ROOT, env=env)
    elapsed = time.time() - start

    if r.returncode != 0:
        err(f'PyInstaller 构建失败（退出码 {r.returncode}）')
        return False
    ok(f'PyInstaller 构建完成，用时 {elapsed:.1f}s')
    return True


def verify_artifact(onefile=False):
    """构建后自检：确保 exe 与静态资源齐全"""
    if onefile:
        exe = DIST_DIR / f'{APP_NAME}.exe'
        if not exe.exists():
            err(f'未找到产物 {exe}')
            return False
        size_mb = exe.stat().st_size / 1024 / 1024
        ok(f'产物: {exe.name}  {size_mb:.1f} MB')
        if size_mb < 20:
            warn(f'单文件体积偏小（{size_mb:.1f} MB），可能缺少依赖')
        return True

    app_dir = DIST_DIR / APP_NAME
    exe = app_dir / f'{APP_NAME}.exe'
    if not exe.exists():
        err(f'未找到产物 {exe}')
        return False

    size_mb = exe.stat().st_size / 1024 / 1024
    ok(f'产物: {exe.name}  {size_mb:.1f} MB')

    # PyInstaller 6.x onedir 布局：数据文件位于 _internal/ 下
    internal = app_dir / '_internal'
    if not internal.exists():
        warn('未找到 _internal 目录（PyInstaller 版本较旧？）')

    # 关键检查：静态资源必须随包分发，否则页面打开即白屏
    index = internal / 'static' / 'dist' / 'index.html'
    if not index.exists():
        err('缺少 _internal/static/dist/index.html —— 打包后页面会白屏')
        return False

    assets_dir = internal / 'static' / 'dist' / 'assets'
    if not assets_dir.exists():
        err('缺少 _internal/static/dist/assets 目录')
        return False

    js_files = list(assets_dir.glob('*.js'))
    css_files = list(assets_dir.glob('*.css'))
    if not js_files or not css_files:
        err('前端资源不完整（缺 JS 或 CSS）')
        return False
    ok(f'静态资源就绪（{len(js_files)} JS / {len(css_files)} CSS）')

    # 校验 index.html 引用的资源确实存在
    html = index.read_text(encoding='utf-8')
    import re
    refs = re.findall(r'/static/dist/assets/([a-zA-Z0-9._-]+)', html)
    missing = [r for r in refs if not (assets_dir / r).exists()]
    if missing:
        err(f'index.html 引用了不存在的资源: {missing}')
        return False
    ok(f'页面资源引用校验通过（{len(refs)} 项）')

    # 检查关键运行时库
    # 注意：纯 Python 模块（fastapi/uvicorn/pystray）会被打进 base_library.zip，
    # 不以目录形式存在，需通过 PYZ 归档校验；带扩展名的则表现为目录。
    for probe, label in [
        ('cv2', 'opencv'),
        ('numpy', 'numpy'),
        ('psutil', 'psutil'),
        ('PIL', 'pillow'),
        ('win32com', 'pywin32'),
    ]:
        if not (internal / probe).exists():
            warn(f'未检测到 {label} 运行库目录')

    # 校验纯 Python 模块已归档
    pyz = BUILD_DIR / APP_NAME / 'PYZ-00.pyz'
    if pyz.exists():
        ok(f'PYZ 归档: {pyz.stat().st_size / 1024:.0f} KB')
    else:
        warn('未找到 PYZ 归档（纯 Python 模块可能缺失）')

    total_mb = sum(f.stat().st_size for f in app_dir.rglob('*') if f.is_file()) / 1024 / 1024
    ok(f'目录总体积: {total_mb:.1f} MB')
    return True


def build_installer():
    """调用 Inno Setup 生成安装包"""
    iscc_candidates = [
        r'C:\Program Files (x86)\Inno Setup 6\ISCC.exe',
        r'C:\Program Files\Inno Setup 6\ISCC.exe',
    ]
    iscc = next((p for p in iscc_candidates if Path(p).exists()), None)
    if not iscc:
        found = shutil.which('iscc')
        iscc = found if found else None

    if not iscc:
        warn('未检测到 Inno Setup（ISCC.exe），跳过安装包构建')
        warn('下载地址: https://jrsoftware.org/isdl.php')
        return False

    iss = PROJECT_ROOT / 'installer.iss'
    if not iss.exists():
        err(f'未找到安装包脚本 {iss}')
        return False

    step('使用 Inno Setup 生成安装包…')
    r = subprocess.run([iscc, str(iss)], cwd=PROJECT_ROOT)
    if r.returncode != 0:
        err(f'Inno Setup 构建失败（退出码 {r.returncode}）')
        return False

    setup = DIST_DIR / f'{APP_NAME}-Setup-{read_version()}.exe'
    if setup.exists():
        size_mb = setup.stat().st_size / 1024 / 1024
        ok(f'安装包: {setup.name}  {size_mb:.1f} MB')
    return True


def main():
    parser = argparse.ArgumentParser(
        description='Atlantis Watcher 生产级构建脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--onefile', action='store_true', help='构建单文件便携版')
    parser.add_argument('--installer', action='store_true', help='构建后生成 Inno Setup 安装包')
    parser.add_argument('--sign', default=None, help='代码签名证书（需要 signtool 在 PATH）')
    parser.add_argument('--skip-frontend', action='store_true', help='跳过前端构建')
    parser.add_argument('--clean', action='store_true', help='清理后完整重建')
    parser.add_argument('--no-verify', action='store_true', help='跳过产物自检')
    args = parser.parse_args()

    version = read_version()
    print()
    log(f'Atlantis Watcher 构建系统  v{version}', 'STEP')
    print('─' * 62)

    # 1. 前置校验
    step('前置校验')
    checks_ok = True
    if not args.skip_frontend:
        if not build_frontend():
            checks_ok = False
    if checks_ok and not check_frontend():
        checks_ok = False
    if not check_icon():
        checks_ok = False
    if not check_deps():
        checks_ok = False
    if not checks_ok:
        print()
        err('前置校验未通过，构建中止')
        return 1

    # 2. 版本同步
    step('同步版本号')
    sync_version(version)

    # 3. 清理
    if args.clean:
        step('清理旧产物')
        clean()

    # 4. 构建
    step('PyInstaller 构建')
    if not run_pyinstaller(onefile=args.onefile, sign_identity=args.sign):
        return 1

    # 5. 自检
    if not args.no_verify:
        step('产物自检')
        if not verify_artifact(onefile=args.onefile):
            return 1

    # 6. 安装包
    if args.installer and not args.onefile:
        step('安装包构建')
        build_installer()

    print()
    log(f'构建完成 → {DIST_DIR}', 'OK')
    print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
