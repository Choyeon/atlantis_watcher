# -*- coding: utf-8 -*-
"""
应用 Android 工程配置

`npx cap add android` 会重建 android/ 目录，丢失手工配置。
本脚本把定制点重新应用回去，保证可重复构建。

用法:
    python tools/configure_android.py
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from brand_assets import ACCENT, DEEP, android_colors_xml  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ANDROID_DIR = PROJECT_ROOT / 'frontend' / 'android'
RES = ANDROID_DIR / 'app' / 'src' / 'main' / 'res'
MANIFEST = ANDROID_DIR / 'app' / 'src' / 'main' / 'AndroidManifest.xml'
BUILD_GRADLE = ANDROID_DIR / 'app' / 'build.gradle'
ROOT_GRADLE = ANDROID_DIR / 'build.gradle'
WRAPPER = ANDROID_DIR / 'gradle' / 'wrapper' / 'gradle-wrapper.properties'

APP_ID = 'com.atlantis.watcher'
BRAND = 'Atlantis Watcher'
BG = DEEP

# 需要写入的权限
PERMISSIONS = [
    ('android.permission.INTERNET', '访问局域网内的 Atlantis Watcher 主机'),
    ('android.permission.ACCESS_NETWORK_STATE', '检测网络状态'),
    ('android.permission.ACCESS_WIFI_STATE', '读取 Wi-Fi 状态'),
    ('android.permission.CHANGE_WIFI_MULTICAST_STATE', '局域网设备发现（mDNS）'),
    ('android.permission.WAKE_LOCK', '屏幕共享时保持屏幕常亮'),
    ('android.permission.VIBRATE', '操作反馈')
]


def apply_manifest():
    """写入权限与明文流量配置"""
    if not MANIFEST.exists():
        print('✗ 未找到 AndroidManifest.xml，请先执行 npx cap add android')
        return False

    content = MANIFEST.read_text(encoding='utf-8')

    # 允许明文 HTTP（局域网主机通常无 HTTPS）
    if 'usesCleartextTraffic' not in content:
        content = content.replace(
            'android:supportsRtl="true"',
            'android:supportsRtl="true"\n        android:usesCleartextTraffic="true"'
        )

    # 移除本脚本此前写入的权限块（避免重复累积）
    content = re.sub(
        r'\n\s*<!-- =+ 权限 =+ -->\n.*?(?=\n\s*</manifest>)',
        '',
        content,
        flags=re.S
    )

    # 收集已存在的权限（含 Capacitor 默认声明的）
    existing = set(re.findall(r'uses-permission android:name="([^"]+)"', content))

    perms_lines = [
        f'    <uses-permission android:name="{name}" />'
        for name, _ in PERMISSIONS
        if name not in existing
    ]
    perms = '\n'.join(perms_lines)
    features = (
        '    <uses-feature android:name="android.hardware.touchscreen" android:required="false" />\n'
        '    <uses-feature android:name="android.hardware.camera" android:required="false" />'
    )

    block = f'\n    <!-- ============ 权限 ============ -->\n{perms}\n\n{features}\n'
    content = content.replace('\n</manifest>', block + '\n</manifest>')

    MANIFEST.write_text(content, encoding='utf-8')
    print(f'✓ AndroidManifest 已配置（新增 {len(perms_lines)} 项权限）')
    return True


def apply_build_gradle():
    """写入版本号、签名配置、Java 版本"""
    if not BUILD_GRADLE.exists():
        print('✗ 未找到 app/build.gradle')
        return False

    content = BUILD_GRADLE.read_text(encoding='utf-8')

    # 版本号变量
    if 'def awVersionName' not in content:
        content = content.replace(
            'apply plugin: \'com.android.application\'',
            'apply plugin: \'com.android.application\'\n\n'
            '// 版本号：由 tools/build_android.py 在构建前同步\n'
            'def awVersionName = "1.1.0"\n'
            'def awVersionCode = 1'
        )
        content = content.replace(
            'versionCode 1',
            'versionCode awVersionCode'
        ).replace(
            'versionName "1.0"',
            'versionName awVersionName'
        )

    # 签名配置
    if 'signingConfigs' not in content:
        signing = '''
    signingConfigs {
        release {
            // 正式签名配置写入 android/keystore.properties（已 gitignore）
            def propsFile = rootProject.file('keystore.properties')
            if (propsFile.exists()) {
                def props = new Properties()
                props.load(new FileInputStream(propsFile))
                storeFile file(props['storeFile'])
                storePassword props['storePassword']
                keyAlias props['keyAlias']
                keyPassword props['keyPassword']
            }
        }
    }
'''
        content = content.replace('    buildTypes {', signing + '\n    buildTypes {')

    # release 构建类型：启用压缩 + 条件签名
    content = re.sub(
        r'release \{\s*\n(\s*)minifyEnabled false\s*\n(\s*)proguardFiles([^\n]+)\n',
        lambda m: (
            f'release {{\n{m.group(1)}minifyEnabled true\n'
            f'{m.group(1)}shrinkResources true\n'
            f'{m.group(1)}proguardFiles{m.group(3)}\n'
            f'{m.group(1)}signingConfig rootProject.file(\'keystore.properties\').exists()\n'
            f'{m.group(1)}    ? signingConfigs.release\n'
            f'{m.group(1)}    : signingConfigs.debug\n'
        ),
        content
    )

    # debug 包加后缀，便于与正式包共存
    if 'applicationIdSuffix' not in content:
        content = content.replace(
            '    buildTypes {',
            '    buildTypes {\n        debug {\n'
            '            applicationIdSuffix ".debug"\n'
            '            versionNameSuffix "-debug"\n'
            '        }'
        )

    BUILD_GRADLE.write_text(content, encoding='utf-8')
    print('✓ app/build.gradle 已配置（版本号 / 签名 / 压缩）')
    return True


def apply_root_gradle():
    """配置国内镜像加速"""
    if not ROOT_GRADLE.exists():
        return False

    content = ROOT_GRADLE.read_text(encoding='utf-8')

    if 'maven.aliyun.com' in content:
        print('✓ 根 build.gradle 镜像配置已存在')
        return True

    content = content.replace(
        '    repositories {\n        google()\n        mavenCentral()\n    }',
        '    repositories {\n'
        "        maven { url 'https://maven.aliyun.com/repository/google' }\n"
        "        maven { url 'https://maven.aliyun.com/repository/central' }\n"
        "        maven { url 'https://maven.aliyun.com/repository/gradle-plugin' }\n"
        '        google()\n        mavenCentral()\n        gradlePluginPortal()\n    }'
    )
    content = content.replace(
        'allprojects {\n    repositories {\n        google()\n        mavenCentral()\n    }\n}',
        'allprojects {\n    repositories {\n'
        "        maven { url 'https://maven.aliyun.com/repository/google' }\n"
        "        maven { url 'https://maven.aliyun.com/repository/central' }\n"
        '        google()\n        mavenCentral()\n    }\n}'
    )

    ROOT_GRADLE.write_text(content, encoding='utf-8')
    print('✓ 根 build.gradle 已配置阿里云镜像加速')
    return True


def apply_wrapper():
    """配置 Gradle 发行包镜像"""
    if not WRAPPER.exists():
        return False

    content = WRAPPER.read_text(encoding='utf-8')
    if 'mirrors.cloud.tencent.com' in content:
        print('✓ Gradle wrapper 镜像配置已存在')
        return True

    content = re.sub(
        r'distributionUrl=.*',
        r'distributionUrl=https\://mirrors.cloud.tencent.com/gradle/gradle-8.14.3-bin.zip',
        content
    )
    content = re.sub(r'networkTimeout=\d+', 'networkTimeout=600000', content)
    content = re.sub(r'validateDistributionUrl=\w+', 'validateDistributionUrl=false', content)

    WRAPPER.write_text(content, encoding='utf-8')
    print('✓ Gradle wrapper 已配置腾讯云镜像')
    return True


def apply_gradle_properties():
    """配置 Gradle 性能参数"""
    path = ANDROID_DIR / 'gradle.properties'
    if not path.exists():
        return False

    content = path.read_text(encoding='utf-8')
    additions = []
    if 'org.gradle.parallel' not in content:
        additions.append('org.gradle.parallel=true')
        additions.append('org.gradle.caching=true')
    if 'org.gradle.jvmargs=-Xmx1536m' in content:
        content = content.replace(
            'org.gradle.jvmargs=-Xmx1536m',
            'org.gradle.jvmargs=-Xmx2048m -Dfile.encoding=UTF-8'
        )

    if additions:
        content = content.rstrip() + '\n\n' + '\n'.join(additions) + '\n'
        path.write_text(content, encoding='utf-8')
        print('✓ gradle.properties 已优化')
    return True


def apply_styles():
    """配置深色主题样式"""
    values = RES / 'values'

    colors = values / 'colors.xml'
    # 与 tools/brand_assets.py 共用同一份色板，避免两次写入互相覆盖后缺色项
    colors.write_text(android_colors_xml(), encoding='utf-8')

    styles = values / 'styles.xml'
    styles.write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<resources>\n'
        '    <!-- 深色为默认：WebView 内页面自行实现明暗切换 -->\n'
        '    <style name="AppTheme" parent="Theme.AppCompat.DayNight.NoActionBar">\n'
        '        <item name="colorPrimary">@color/colorPrimary</item>\n'
        '        <item name="colorPrimaryDark">@color/colorPrimaryDark</item>\n'
        '        <item name="colorAccent">@color/colorAccent</item>\n'
        '        <item name="android:windowBackground">@color/aw_background</item>\n'
        '    </style>\n'
        '\n'
        '    <style name="AppTheme.NoActionBar" parent="Theme.AppCompat.DayNight.NoActionBar">\n'
        '        <item name="windowActionBar">false</item>\n'
        '        <item name="windowNoTitle">true</item>\n'
        '        <item name="android:background">@null</item>\n'
        '        <item name="android:windowBackground">@color/aw_background</item>\n'
        '    </style>\n'
        '\n'
        '    <!-- 启动主题：沉浸式状态栏 + 深色底，避免白闪 -->\n'
        '    <style name="AppTheme.NoActionBarLaunch" parent="Theme.SplashScreen">\n'
        '        <item name="android:background">@color/aw_background</item>\n'
        '        <item name="windowSplashScreenBackground">@color/aw_background</item>\n'
        '        <item name="postSplashScreenTheme">@style/AppTheme.NoActionBar</item>\n'
        '        <item name="android:statusBarColor">@android:color/transparent</item>\n'
        '        <item name="android:navigationBarColor">@android:color/transparent</item>\n'
        '        <item name="android:windowLightStatusBar">false</item>\n'
        '        <item name="android:windowLightNavigationBar">false</item>\n'
        '    </style>\n'
        '</resources>\n',
        encoding='utf-8'
    )
    print('✓ 主题样式已配置（深色 + 沉浸式）')


def apply_strings():
    """应用名称"""
    strings = RES / 'values' / 'strings.xml'
    if not strings.exists():
        return False
    content = strings.read_text(encoding='utf-8')
    content = re.sub(
        r'<string name="app_name">[^<]*</string>',
        f'<string name="app_name">{BRAND}</string>',
        content
    )
    content = re.sub(
        r'<string name="title_activity_main">[^<]*</string>',
        f'<string name="title_activity_main">{BRAND}</string>',
        content
    )
    strings.write_text(content, encoding='utf-8')
    print('✓ 应用名称已配置')
    return True


def main():
    print('应用 Android 工程配置…')
    print('─' * 50)
    results = [
        apply_manifest(),
        apply_build_gradle(),
        apply_root_gradle(),
        apply_wrapper(),
        apply_gradle_properties(),
        apply_styles(),
        apply_strings()
    ]
    print('─' * 50)
    ok_count = sum(1 for r in results if r)
    print(f'完成 {ok_count}/{len(results)} 项配置')
    return 0 if all(r for r in results if r is not None) else 1


if __name__ == '__main__':
    raise SystemExit(main())
