# Atlantis Watcher — 生产级构建指南

本文档描述 Atlantis Watcher 的完整打包体系：构建策略、工具链、安装包、代码签名与发布流程。

---

## 一、构建体系总览

```
                     ┌─────────────────────────────┐
                     │  frontend/ (Vue 3 + Vite)   │
                     │  npm run build               │
                     └──────────────┬──────────────┘
                                    │ 产物
                                    ▼
                     ┌─────────────────────────────┐
                     │  static/dist/                │
                     └──────────────┬──────────────┘
                                    │
   ┌────────────────────────────────┴────────────────────────────────┐
   │                                                                 │
   ▼                                                                 ▼
┌─────────────────────┐                                    ┌──────────────────────┐
│  onedir (目录版)    │                                    │  onefile (单文件)     │
│  → Inno Setup 安装包 │                                    │  → 便携版 / U盘分发    │
│  → 正式分发首选       │                                    │  → 免安装             │
└─────────────────────┘                                    └──────────────────────┘
```

### 为什么区分 onedir 与 onefile

| 维度 | onedir（目录版） | onefile（单文件） |
|------|-----------------|------------------|
| 启动速度 | **快**（无需解压） | 慢（每次启动解压到 temp） |
| 杀软误报 | **低**（无自解压行为） | 高（自解压壳是典型误报特征） |
| 更新方式 | 覆盖目录即可 | 需替换整个 exe |
| 分发形态 | 需压缩成安装包 | 单文件即用 |
| 适用场景 | **正式分发、企业部署** | 便携携带、临时测试 |

**结论**：生产环境正式分发走 onedir + Inno Setup 安装包；onefile 仅作便携备用。

---

## 二、快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt
pip install pyinstaller
cd frontend && npm install && cd ..

# 2. 完整构建（含前端 + 自检）
python build.py

# 3. 生成安装包（需先安装 Inno Setup）
python build.py --installer

# 4. 验收：真实启动打包产物并逐项验证
python tools/verify_package.py

# 5. 签名（生产环境必须）
python tools/sign.py --pfx cert.pfx --password "密码"
```

---

## 三、构建脚本参数

### `build.py` / `build_release.py`

| 参数 | 说明 |
|------|------|
| （无参数） | 构建 onedir，自动构建前端 + 产物自检 |
| `--onefile` | 构建单文件便携版 |
| `--installer` | 构建后调用 Inno Setup 生成安装包 |
| `--sign "证书"` | 使用证书签名（需 signtool 在 PATH） |
| `--skip-frontend` | 跳过前端构建（前端已构建且未改动时用，节省时间） |
| `--clean` | 清理 build/ 与 dist/ 后完整重建 |
| `--no-verify` | 跳过产物自检（不建议） |

> `build.py` 是薄入口，实际实现位于 `build_release.py`，两者参数完全一致。

### 构建流程（内部）

1. **前置校验** — 前端产物存在、图标合法、运行时依赖齐备，任一不过则中止
2. **版本同步** — 以 `pyproject.toml` 为唯一版本源，同步到 spec / main.py
3. **清理**（可选）
4. **PyInstaller 构建** — 基于 `AtlantisWatcher.spec`
5. **产物自检** — 校验 exe、静态资源、页面引用完整性、关键运行库
6. **安装包**（可选） — 调用 Inno Setup

---

## 四、关键文件说明

| 文件 | 作用 |
|------|------|
| `AtlantisWatcher.spec` | **PyInstaller 规格文件**：数据文件、隐藏导入、排除模块、版本资源、Windows 清单、运行时 hook 的唯一来源 |
| `build_release.py` | 构建流水线实现（校验 → 同步 → 构建 → 自检 → 安装包） |
| `build.py` | 兼容入口，转发到 build_release |
| `installer.iss` | Inno Setup 安装包脚本（安装向导/快捷方式/卸载/升级覆盖） |
| `tools/brand_assets.py` | **品牌图标单一真源**：一次生成全端资产（见 5.4） |
| `tools/make_icon.py` | Windows 图标兼容入口（16–256 七尺寸 ICO） |
| `tools/runtime_hook.py` | PyInstaller 运行时 hook：把工作目录切到可写位置 |
| `tools/verify_package.py` | 打包产物验收测试（真实启动 + 17 项校验） |
| `tools/sign.py` | 代码签名与签名状态检查 |

---

## 五、生产级要点

### 5.1 运行时目录（关键）

打包后的程序**不能**把工作目录指向 `_MEIPASS`（临时解压目录）：

- 该目录只读，且进程退出即被清理
- 日志写进去等于没写，故障无法追溯
- 程序目录可能是 `Program Files`，无写权限

本项目的处理：

- `tools/runtime_hook.py` 在启动最早期把工作目录切到 `%LOCALAPPDATA%\AtlantisWatcher`
- `main.py` 的 `resource_root()` / `resolve_resource()` 用 `sys._MEIPASS` 定位资源，
  **不依赖 cwd**（否则改了 cwd 就找不到静态资源，页面直接白屏）

### 5.2 Windows 应用清单（Manifest）

`AtlantisWatcher.spec` 中内嵌的 manifest 声明了：

| 项 | 值 | 原因 |
|----|-----|------|
| `requestedExecutionLevel` | `requireAdministrator` | 关机/重启/锁屏需管理员权限 |
| `dpiAwareness` | `PerMonitorV2` | 高分屏下界面与托盘图标不糊 |
| `longPathAware` | `true` | 支持 >260 字符路径 |
| `activeCodePage` | `UTF-8` | 中文路径与输出不乱码 |
| `supportedOS` | Win7–Win11 | 避免兼容性 shim 干扰 |

> 提权由 Windows 依据清单完成，代码内 `check_admin_privileges()` 仅作兜底校验，
> 不会重复弹 UAC。

### 5.3 版本号单一来源

`pyproject.toml` 的 `version` 是唯一来源。构建时自动同步到：

- `AtlantisWatcher.spec` 的 `APP_VERSION` 与版本资源
- `main.py` 中 FastAPI 的 `version=`
- `installer.iss` 的 `AppVersion`

避免了"文件属性显示 1.0.0、安装包是 0.1.0"这类问题。

### 5.4 图标（单一真源）

原 `icon.ico` 曾是 **PNG 文件改了扩展名**（64×64 单尺寸），资源管理器与托盘显示退化；
早期 `make_icon.py` / `make_android_icon.py` 又各画一遍，桌面与 APK 图形容易漂移。

现在全部资产由 `tools/brand_assets.py` 从 `assets/brand/atlantis-watcher-source.png` 这张主图生成：

| 产物 | 说明 |
|---|---|
| `icon.ico` | 16/24/32/48/64/128/256 七帧，统一使用主图并按尺寸高质量缩放 |
| `frontend/public/favicon.*` | SVG + ICO + 16/32/180/192/512 PNG；由 `app/routers/meta.py` 从站点根提供 |
| `frontend/src/assets/brandMark.svg` | 前端 BrandMark 使用的同源品牌资源 |
| `mipmap-*/ic_launcher*.png` | 五档密度方形/圆形/自适应前景/单色主题图标（108dp 安全区 66%） |
| `drawable*/splash.png` | 深底品牌启动图，替换 Capacitor 白色默认图 |
| `assets/brand/atlantis-watcher-source.png` / `preview.png` | 原始主图与人工目检总览图 |

配色来自主图：深午夜蓝底、电子青蓝网关、琥珀控制信号；Android 自适应图标会额外生成透明前景与单色主题资源。

```bash
python tools/brand_assets.py        # 全量重生成
python tools/make_icon.py           # 等价的 Windows 兼容入口（含 ICO 帧校验）
```

### 5.5 不使用 UPX

部分杀软对 UPX 压缩壳的误报率显著更高。生产分发保持 `upx=False`，
体积换安全。

---

## 六、代码签名

### 为什么必须签

未签名的 PyInstaller 程序在以下场景会被拦截：

- Windows Defender SmartScreen（"Windows 已保护你的电脑"）
- 企业终端管理 / EDR 策略（EDR 对自启动 + 屏幕截取行为高度敏感）
- 部分安全软件直接隔离

### 获取证书

| 方式 | 说明 | 成本 |
|------|------|------|
| OV 代码签名证书 | 需企业主体认证，SmartScreen 信誉需累积 | 年费千元级 |
| **EV 代码签名证书** | 即时获得 SmartScreen 信誉 | 年费数千元级 |
| Azure Trusted Signing | 微软云签名服务，按次计费 | 按需 |
| 自签名证书 | 仅内部测试用，用户需手动信任根证书 | 免费 |

### 使用

```bash
# 用 PFX 证书签名（推荐：密码走环境变量或交互输入）
python tools/sign.py --pfx cert.pfx --password "$CERT_PASSWORD"

# 从 Windows 证书存储按指纹签名
python tools/sign.py --thumbprint ABC123DEF456...

# 只检查签名状态
python tools/sign.py --check
```

签名会附加 RFC 3161 时间戳（默认 DigiCert），保证证书过期后签名依然有效。

> 密码不要写进脚本或提交到仓库。

---

## 七、安装包

### 生成

```bash
# 需先安装 Inno Setup 6: https://jrsoftware.org/isdl.php
python build.py --installer
```

产物：`dist/AtlantisWatcher-Setup-1.1.0.exe`

### 安装包特性

- 安装向导：安装位置、开始菜单、桌面快捷方式、卸载入口
- **升级覆盖**：同版本覆盖安装，自动关闭运行中的程序
- **卸载可选清理**：卸载时询问是否删除日志与本地数据（默认保留以便排查问题）
- UAC 提权：安装到 `Program Files` 时自动请求管理员权限
- LZMA2 压缩，安装包体积最小

---

## 八、验收测试

```bash
python tools/verify_package.py
```

真实启动打包后的 exe 并逐项验证（17 项）：

| 分组 | 检查项 |
|------|--------|
| 启动 | 进程可启动、60s 内端口就绪 |
| 静态资源 | 首页 200、为 Vite 产物、含挂载点、引用的资源逐个可访问 |
| API | `/health`、`/api/system/info`、`/api/files/drives`、`/api/files/list?path=` |
| WebSocket | `/ws/monitor` 推送监控数据 |
| 运行时 | 日志目录为 `%LOCALAPPDATA%\AtlantisWatcher`、日志已写入且含启动记录、未写入临时解压目录 |

全部通过才算构建合格。

---

## 九、发布清单

```bash
# 1. 确认版本
vim pyproject.toml            # version = "1.1.0"

# 2. 完整构建 + 安装包
python build.py --installer --clean

# 3. 验收
python tools/verify_package.py

# 4. 签名
python tools/sign.py --pfx cert.pfx --password "$CERT_PASSWORD"

# 5. 复核签名
python tools/sign.py --check

# 6. 前端回归（确认 UI 无退化）
cd frontend && node verify.mjs && node verify-interaction.mjs && cd ..

# 7. 产出清单
#    dist/AtlantisWatcher-Setup-1.1.0.exe   ← 分发给用户
#    dist/AtlantisWatcher/                    ← onedir 产物
```

---

## 十、故障排除

### 构建期

| 现象 | 原因与解决 |
|------|-----------|
| `[构建中止] 未找到前端构建产物` | 先执行 `cd frontend && npm run build` |
| `OSError: Invalid argument` 指向 spec | `version=` / `runtime_hooks=` 需要**文件路径**而非脚本文本 |
| `ModuleNotFoundError` 运行时 | 在 `AtlantisWatcher.spec` 的 `hiddenimports` 中补充 |
| 产物体积异常大 | 检查 `excludes` 是否遗漏；`numpy`/`cv2` 本身占比较大 |

### 运行期

| 现象 | 原因与解决 |
|------|-----------|
| **页面白屏** | 静态资源未随包分发。执行 `python tools/verify_package.py` 定位；确认 `static/dist` 已构建 |
| 静态资源 404 | `main.py` 的资源定位用了 cwd。必须用 `resolve_resource()`（基于 `_MEIPASS`） |
| 找不到主页模板 | 同上，检查 `static/dist/index.html` 是否存在于 `_internal/` 下 |
| 日志丢失 | 工作目录指向了 `_MEIPASS`。确认 `tools/runtime_hook.py` 已生效 |
| 中文路径乱码 | 确认 manifest 中 `activeCodePage=UTF-8` |
| 界面在高分屏发虚 | manifest 中 `dpiAwareness=PerMonitorV2` |
| 被杀软拦截 | 未签名。用 `tools/sign.py` 签名 |

### PyInstaller 6.x 目录布局说明

```
dist/AtlantisWatcher/
├── AtlantisWatcher.exe          ← 主程序（8.4 MB）
└── _internal/                   ← 依赖与数据
    ├── static/dist/             ← 前端构建产物（唯一 UI 资源）
    ├── cv2/ numpy/ PIL/ ...     ← 原生依赖
    └── base_library.zip         ← 纯 Python 模块
```

注意：**数据文件在 `_internal/` 下**，不是 exe 同级目录。资源路径统一由
`app/paths.py` 解析（`sys._MEIPASS`），日志与设置则落在
`%LOCALAPPDATA%\AtlantisWatcher\`，与工作目录无关。旧版 `template/`、`webgui/`
降级资源已删除，前端产物缺失时主页返回内置提示页。

---

## 十一、构建性能参考

| 阶段 | 耗时 |
|------|------|
| 前端构建（Vite） | ~1s |
| PyInstaller 冷构建 | ~15s |
| PyInstaller 增量构建 | ~12s |
| 产物验收 | ~15s |
| 目录总体积 | ~213 MB（numpy + opencv 为主） |

---

## 十二、注意事项

- 打包前**必须**先构建前端，否则 `static/dist` 是旧产物或不存在
- 生产分发必须签名，否则企业环境会被拦截
- 不要提交 `dist/`、`build/`、`*.pfx` 到仓库
- 修改 `AtlantisWatcher.spec` 中的 `datas` 时，注意 PyInstaller 6.x 的 `_internal` 布局
