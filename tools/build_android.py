# -*- coding: utf-8 -*-
"""
Android APK 构建脚本

流程：
  1. 校验环境（JDK / Android SDK / Gradle）
  2. 构建前端产物（static/dist）
  3. 同步版本号到 build.gradle
  4. 生成 local.properties（指向本机 SDK）
  5. 生成 Android 图标
  6. npx cap sync android（拷贝 web 资源 + 更新原生插件）
  7. Gradle 打包 APK
  8. 产物校验（大小、清单、签名）

用法:
    python tools/build_android.py                  # debug APK
    python tools/build_android.py --release        # release APK（需签名配置）
    python tools/build_android.py --clean          # 清理后重建
    python tools/build_android.py --install        # 打包后安装到已连接设备
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = PROJECT_ROOT / 'frontend'
ANDROID_DIR = FRONTEND_DIR / 'android'
GRADLE_WRAPPER = ANDROID_DIR / ('gradlew.bat' if os.name == 'nt' else 'gradlew')

PASS = '\033[32m✓\033[0m'
FAIL = '\033[31m✗\033[0m'
WARN = '\033[33m!\033[0m'
INFO = '\033[36m·\033[0m'
STEP = '\033[1m\033[34m▶\033[0m'


def log(msg, mark=INFO):
    print(f'{mark} {msg}', flush=True)


def step(msg):
    log(f'{STEP} {msg}', '')


def ok(msg):
    log(f'{PASS} {msg}', '')


def warn(msg):
    log(f'{WARN} {msg}', '')


def err(msg):
    log(f'{FAIL} {msg}', '')


def find_sdk():
    """定位 Android SDK"""
    candidates = [
        os.environ.get('ANDROID_HOME'),
        os.environ.get('ANDROID_SDK_ROOT'),
        os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Android', 'Sdk'),
        r'D:\AndroidToolchain\android-sdk',
        r'C:\Android\Sdk',
    ]
    for c in candidates:
        if c and os.path.isdir(c):
            return c
    return None


def find_jdk21():
    """查找 JDK 21（Capacitor 7/8 的 AGP 要求 Java 21）

    顺序：
      1. JAVA_HOME 指向的 JDK（需 ≥21）
      2. 常见安装位置（AndroidToolchain / Program Files / Adoptium / Zulu）
      3. PATH 中的 java
    """
    candidates = []

    java_home = os.environ.get('JAVA_HOME')
    if java_home:
        candidates.append(java_home)

    # 本项目常用的工具链目录
    candidates += [
        r'D:\AndroidToolchain\jdk21',
        r'D:\AndroidToolchain\jdk-21',
        r'C:\Program Files\Java\jdk-21',
        r'C:\Program Files\Eclipse Adoptium\jdk-21',
        r'C:\Program Files\Microsoft\jdk-21',
        r'C:\Program Files\Zulu\zulu-21',
    ]

    # 扫描 AndroidToolchain 下的 jdk-21* 目录
    toolchain = Path(r'D:\AndroidToolchain')
    if toolchain.exists():
        for d in sorted(toolchain.glob('jdk-21*'), reverse=True):
            candidates.append(str(d))

    # Android Studio 自带 JBR（通常为 21）
    candidates.append(r'C:\Program Files\Android\Android Studio\jbr')

    for c in candidates:
        if not c:
            continue
        java_exe = Path(c) / 'bin' / 'java.exe'
        if not java_exe.exists():
            java_exe = Path(c) / 'bin' / 'java'
        if not java_exe.exists():
            continue
        try:
            r = subprocess.run(
                [str(java_exe), '-version'], capture_output=True, text=True, errors='replace'
            )
            ver = (r.stderr or r.stdout)
            major = re.search(r'version "(\d+)', ver)
            if major and int(major.group(1)) >= 21:
                return str(java_exe)
        except Exception:
            continue

    # 退回 PATH
    java = shutil.which('java')
    if java:
        try:
            r = subprocess.run([java, '-version'], capture_output=True, text=True, errors='replace')
            major = re.search(r'version "(\d+)', r.stderr or r.stdout)
            if major and int(major.group(1)) >= 21:
                return java
        except Exception:
            pass

    return None


def check_env():
    """环境校验"""
    ok_all = True

    # JDK 21：Capacitor 7/8 的 AGP 8.13 要求 Java 21
    java21 = find_jdk21()
    if java21:
        try:
            r = subprocess.run([java21, '-version'], capture_output=True, text=True, errors='replace')
            ver = (r.stderr or r.stdout).splitlines()[0].strip()
            ok(f'JDK 21: {ver}')
            ok(f'  路径: {java21}')
        except Exception:
            ok('JDK 21: 已检测到')
    else:
        err('未找到 JDK 21（Capacitor 7/8 的 Android Gradle Plugin 8.13 要求 Java 21）')
        err('  安装：https://adoptium.net/temurin/releases/?version=21')
        err('  或设置 JAVA_HOME 指向 JDK 21 后重试')
        ok_all = False

    # Android SDK
    sdk = find_sdk()
    if not sdk:
        err('未找到 Android SDK')
        err('  设置环境变量 ANDROID_HOME，或安装 Android Studio')
        ok_all = False
    else:
        ok(f'Android SDK: {sdk}')
        platforms = os.path.join(sdk, 'platforms')
        build_tools = os.path.join(sdk, 'build-tools')
        if not os.path.isdir(platforms):
            err('SDK 缺少 platforms 组件')
            ok_all = False
        if not os.path.isdir(build_tools):
            err('SDK 缺少 build-tools 组件')
            ok_all = False

    if not ANDROID_DIR.exists():
        err('未找到 android 工程目录，请先执行: cd frontend && npx cap add android')
        ok_all = False

    return ok_all, sdk, java21


def read_version():
    """从 pyproject.toml 读取版本号"""
    pyproject = PROJECT_ROOT / 'pyproject.toml'
    if not pyproject.exists():
        return '1.1.0'
    in_project = False
    for line in pyproject.read_text(encoding='utf-8').splitlines():
        s = line.strip()
        if s.startswith('['):
            in_project = s == '[project]'
            continue
        if in_project and s.startswith('version'):
            return s.split('=', 1)[1].strip().strip('"').strip("'")
    return '1.1.0'


def version_to_code(version):
    """语义化版本 → versionCode 整数

    1.2.3 → 10203，规则：大版本*10000 + 次版本*100 + 修订号
    """
    parts = re.findall(r'\d+', version)
    while len(parts) < 3:
        parts.append('0')
    major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
    return major * 10000 + minor * 100 + patch


def sync_version(version):
    """同步版本号到 build.gradle"""
    gradle = ANDROID_DIR / 'app' / 'build.gradle'
    if not gradle.exists():
        return
    content = gradle.read_text(encoding='utf-8')
    code = version_to_code(version)
    content = re.sub(r'def awVersionName = "[^"]+"', f'def awVersionName = "{version}"', content)
    content = re.sub(r'def awVersionCode = \d+', f'def awVersionCode = {code}', content)
    gradle.write_text(content, encoding='utf-8')
    ok(f'版本已同步: {version} (versionCode={code})')

    # strings.xml 中的应用名保持与桌面端一致
    strings = ANDROID_DIR / 'app' / 'src' / 'main' / 'res' / 'values' / 'strings.xml'
    if strings.exists():
        c = strings.read_text(encoding='utf-8')
        c = re.sub(r'<string name="app_name">[^<]*</string>',
                   f'<string name="app_name">Atlantis Watcher</string>', c)
        strings.write_text(c, encoding='utf-8')


def write_local_properties(sdk):
    """生成 local.properties"""
    if not sdk:
        return
    path = ANDROID_DIR / 'local.properties'
    # Windows 路径中的反斜杠与冒号需要转义
    escaped = sdk.replace('\\', '\\\\').replace(':', '\\:')
    path.write_text(
        f'## 由 tools/build_android.py 自动生成，请勿提交到版本库\n'
        f'sdk.dir={escaped}\n',
        encoding='utf-8'
    )
    ok(f'local.properties 已写入 SDK 路径')


def build_frontend():
    """构建前端"""
    npm = shutil.which('npm')
    if not npm:
        err('未找到 npm')
        return False

    if not (FRONTEND_DIR / 'node_modules').exists():
        log('安装前端依赖…')
        r = subprocess.run([npm, 'install', '--no-fund', '--no-audit'], cwd=FRONTEND_DIR)
        if r.returncode != 0:
            err('npm install 失败')
            return False

    log('构建前端…')
    r = subprocess.run([npm, 'run', 'build'], cwd=FRONTEND_DIR)
    if r.returncode != 0:
        err('前端构建失败')
        return False
    ok('前端构建完成')
    return True


def cap_sync():
    """同步 web 资源到 Android 工程

    优先使用 `cap copy`（仅拷贝资源）；
    若失败则回退到 `cap sync`（会清理 Cordova 插件目录）。
    """
    npx = shutil.which('npx')
    if not npx:
        err('未找到 npx')
        return False

    log('同步 Web 资源到 Android 工程…')
    r = subprocess.run([npx, 'cap', 'copy', 'android'], cwd=FRONTEND_DIR)
    if r.returncode == 0:
        ok('Web 资源已同步')
        return True

    warn('cap copy 失败，回退到 cap sync…')
    r = subprocess.run([npx, 'cap', 'sync', 'android'], cwd=FRONTEND_DIR)
    if r.returncode != 0:
        err('Capacitor 同步失败')
        return False
    ok('Web 资源已同步')
    return True


def configure_android():
    """应用 Android 工程配置（幂等）"""
    script = PROJECT_ROOT / 'tools' / 'configure_android.py'
    if not script.exists():
        return True
    r = subprocess.run([sys.executable, str(script)], cwd=PROJECT_ROOT)
    return r.returncode == 0


def make_icons():
    """生成 Android 图标"""
    script = PROJECT_ROOT / 'tools' / 'make_android_icon.py'
    if not script.exists():
        return
    r = subprocess.run([sys.executable, str(script)], cwd=PROJECT_ROOT)
    if r.returncode == 0:
        ok('Android 图标已生成')


def run_gradle(mode='debug', clean=False, java21=None):
    """执行 Gradle 构建"""
    if not GRADLE_WRAPPER.exists():
        err(f'未找到 Gradle wrapper: {GRADLE_WRAPPER}')
        return None

    task = 'assembleDebug' if mode == 'debug' else 'assembleRelease'
    cmd = [str(GRADLE_WRAPPER), task, '--no-daemon']
    if clean:
        cmd.append('clean')

    # 指定 JDK 21：Gradle 会优先使用 JAVA_HOME
    env = os.environ.copy()
    if java21:
        env['JAVA_HOME'] = str(Path(java21).parent.parent)

    step(f'Gradle 构建 ({task}) —— 首次需下载依赖，耗时较长')
    start = time.time()
    r = subprocess.run(cmd, cwd=ANDROID_DIR, env=env)
    elapsed = time.time() - start

    if r.returncode != 0:
        err(f'Gradle 构建失败（退出码 {r.returncode}）')
        return None
    ok(f'Gradle 构建完成，用时 {elapsed:.1f}s')
    return elapsed


def find_apk(mode='debug'):
    """定位构建出的 APK"""
    outputs = ANDROID_DIR / 'app' / 'build' / 'outputs' / 'apk'
    if not outputs.exists():
        return None
    pattern = f'**/app-{"debug" if mode == "debug" else "release"}*.apk'
    apks = sorted(outputs.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return apks[0] if apks else None


def verify_apk(apk):
    """校验 APK"""
    if not apk:
        err('未找到 APK 产物')
        return False

    size_mb = apk.stat().st_size / 1024 / 1024
    ok(f'APK: {apk.name}  {size_mb:.1f} MB')

    try:
        with zipfile.ZipFile(apk) as z:
            names = z.namelist()

            # 前端资源必须打进去
            has_index = any(n.endswith('assets/public/index.html') for n in names)
            has_js = any(n.startswith('assets/public/assets/') and n.endswith('.js') for n in names)
            has_css = any(n.startswith('assets/public/assets/') and n.endswith('.css') for n in names)

            if not has_index:
                err('APK 内缺少前端入口 index.html')
                return False
            if not has_js:
                err('APK 内缺少 JS 资源')
                return False
            if not has_css:
                err('APK 内缺少 CSS 资源')
                return False
            ok('前端资源已打包（index.html + JS + CSS）')

            # 图标
            has_icon = any('ic_launcher' in n for n in names)
            if not has_icon:
                warn('未找到应用图标资源')
            else:
                ok('应用图标已打包')

            # 签名
            has_sig = any(n.startswith('META-INF/') and n.endswith(('.RSA', '.DSA', '.EC')) for n in names)
            if has_sig:
                ok('APK 已签名')
            else:
                warn('APK 未签名（debug 包为正常现象，正式分发请配置签名）')

    except zipfile.BadZipFile:
        err('APK 文件损坏')
        return False

    return True


def install_apk(apk):
    """安装到已连接设备"""
    adb = shutil.which('adb')
    if not adb:
        sdk = find_sdk()
        if sdk:
            candidate = Path(sdk) / 'platform-tools' / 'adb.exe'
            if candidate.exists():
                adb = str(candidate)

    if not adb:
        warn('未找到 adb，跳过安装')
        return False

    r = subprocess.run([adb, 'devices'], capture_output=True, text=True, errors='replace')
    devices = [l for l in r.stdout.splitlines()[1:] if l.strip() and 'device' in l]
    if not devices:
        warn('未检测到已连接的 Android 设备')
        return False

    log(f'安装到设备: {devices[0].split()[0]}')
    r = subprocess.run([adb, 'install', '-r', str(apk)], capture_output=True, text=True, errors='replace')
    if r.returncode == 0:
        ok('安装成功')
        return True
    err(f'安装失败: {r.stdout} {r.stderr}')
    return False


def main():
    parser = argparse.ArgumentParser(
        description='Atlantis Watcher Android APK 构建脚本'
    )
    parser.add_argument('--release', action='store_true', help='构建 release 包（需签名配置）')
    parser.add_argument('--clean', action='store_true', help='构建前清理')
    parser.add_argument('--install', action='store_true', help='打包后安装到已连接设备')
    parser.add_argument('--skip-frontend', action='store_true', help='跳过前端构建')
    args = parser.parse_args()

    mode = 'release' if args.release else 'debug'
    version = read_version()

    print()
    log(f'\033[1mAtlantis Watcher — Android 构建\033[0m  v{version}  ({mode})', '')
    print('─' * 62)

    # 1. 环境校验
    step('环境校验')
    env_ok, sdk, java21 = check_env()
    if not env_ok:
        print()
        err('环境校验未通过，构建中止')
        return 1

    # 2. 前端构建
    if not args.skip_frontend:
        step('前端构建')
        if not build_frontend():
            return 1
    elif not (PROJECT_ROOT / 'static' / 'dist' / 'index.html').exists():
        err('跳过前端构建但未找到产物，请先执行 npm run build')
        return 1

    # 3. 版本同步 + SDK 配置
    step('配置同步')
    sync_version(version)
    write_local_properties(sdk)
    configure_android()
    make_icons()

    # 4. 同步 Web 资源
    step('Capacitor 同步')
    if not cap_sync():
        return 1

    # 5. Gradle 构建
    step('Gradle 打包')
    if run_gradle(mode=mode, clean=args.clean, java21=java21) is None:
        return 1

    # 6. 校验
    step('产物校验')
    apk = find_apk(mode)
    if not verify_apk(apk):
        return 1

    # 7. 安装
    if args.install and apk:
        step('安装到设备')
        install_apk(apk)

    print()
    log(f'\033[32m构建完成\033[0m  → {apk}', '')
    print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
