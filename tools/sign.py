# -*- coding: utf-8 -*-
"""
代码签名工具

Windows Defender / 企业杀软对未签名的 PyInstaller 程序误报率极高。
本脚本封装 signtool 的常用流程：

  1. 检查签名工具与证书是否存在
  2. 使用证书对 exe / 安装包签名（时间戳服务器保证签名长期有效）
  3. 验证签名状态

签名证书获取方式（生产环境）：
  - 购买 OV/EV 代码签名证书（推荐 EV，可获得 SmartScreen 信誉）
  - 或使用 Azure Trusted Signing / SignPath 等云签名服务
  - 测试环境可用自签名证书（New-SelfSignedCertificate）

用法:
    python tools/sign.py --check                          # 检查签名状态
    python tools/sign.py --pfx cert.pfx --password xxx     # 用 PFX 签名
    python tools/sign.py --thumbprint ABC123...            # 用证书指纹签名
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = PROJECT_ROOT / 'dist'

PASS = '\033[32m✓\033[0m'
FAIL = '\033[31m✗\033[0m'
WARN = '\033[33m!\033[0m'
INFO = '\033[36m·\033[0m'

# 公共时间戳服务器（RFC 3161）
TIMESTAMP_URL = 'http://timestamp.digicert.com'

SIGNTOOL_CANDIDATES = [
    r'C:\Program Files (x86)\Windows Kits\10\bin\x64\signtool.exe',
    r'C:\Program Files\Windows Kits\10\bin\x64\signtool.exe',
]


def find_signtool():
    """定位 signtool.exe"""
    for p in SIGNTOOL_CANDIDATES:
        if Path(p).exists():
            return p
    # 从 Windows Kits 目录中查找最新版本
    kits = Path(r'C:\Program Files (x86)\Windows Kits\10\bin')
    if kits.exists():
        versions = sorted(
            [d for d in kits.iterdir() if d.is_dir()],
            key=lambda d: d.name, reverse=True
        )
        for v in versions:
            candidate = v / 'x64' / 'signtool.exe'
            if candidate.exists():
                return str(candidate)
    found = shutil.which('signtool')
    return found


def find_signable_files():
    """找出待签名的文件"""
    targets = []
    for pattern in ['*.exe', '*/*.exe']:
        targets.extend(DIST_DIR.glob(pattern))
    return [t for t in targets if t.is_file() and 'unins' not in t.name.lower()]


def check_signature(targets):
    """检查签名状态"""
    signtool = find_signtool()
    if not signtool:
        print(f'{FAIL} 未找到 signtool.exe')
        print('  安装 Windows SDK: https://developer.microsoft.com/windows/downloads/windows-sdk/')
        return False

    all_ok = True
    for f in targets:
        print(f'\n{INFO} {f.name}')
        r = subprocess.run(
            [signtool, 'verify', '/pa', '/v', str(f)],
            capture_output=True, text=True, errors='replace'
        )
        out = r.stdout + r.stderr
        if r.returncode == 0:
            # 提取签名者与有效期
            signer = ''
            for line in out.splitlines():
                if 'Subject:' in line and 'CN=' in line:
                    signer = line.split('CN=')[1].split(',')[0].strip()
                    break
            print(f'  {PASS} 已签名' + (f' — {signer}' if signer else ''))
        else:
            print(f'  {FAIL} 未签名')
            print('  ' + '\n  '.join(out.splitlines()[:4]))
            all_ok = False
    return all_ok


def sign_file(target, pfx=None, password=None, thumbprint=None, timestamp=TIMESTAMP_URL):
    """签名单个文件"""
    signtool = find_signtool()
    if not signtool:
        print(f'{FAIL} 未找到 signtool.exe')
        return False

    cmd = [signtool, 'sign']
    if pfx:
        cmd += ['/f', str(pfx)]
        if password:
            cmd += ['/p', password]
    elif thumbprint:
        cmd += ['/sha1', thumbprint]
    else:
        print(f'{FAIL} 需要提供 --pfx 或 --thumbprint')
        return False

    # 时间戳：保证签名在证书过期后依然有效
    if timestamp:
        cmd += ['/td', 'sha256', '/tr', timestamp, '/a']
    cmd += ['/fd', 'sha256', '/v', str(target)]

    print(f'{INFO} 签名: {target.name}')
    r = subprocess.run(cmd, capture_output=True, text=True, errors='replace')
    if r.returncode != 0:
        print(f'{FAIL} 签名失败')
        print('  ' + (r.stdout + r.stderr)[-1500:])
        return False
    print(f'{PASS} 签名完成')
    return True


def main():
    parser = argparse.ArgumentParser(
        description='Atlantis Watcher 代码签名工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--check', action='store_true', help='仅检查签名状态')
    parser.add_argument('--pfx', default=None, help='PFX 证书文件路径')
    parser.add_argument('--password', default=None, help='PFX 密码')
    parser.add_argument('--thumbprint', default=None, help='证书指纹（从证书存储选择）')
    parser.add_argument('--timestamp', default=TIMESTAMP_URL, help='时间戳服务器 URL')
    parser.add_argument('--all', action='store_true', help='签名所有产物')
    args = parser.parse_args()

    targets = find_signable_files()
    if not targets:
        print(f'{WARN} 未找到待签名文件（先执行 python build.py）')
        return 1

    print(f'\n\033[1mAtlantis Watcher — 代码签名\033[0m')
    print(f'{"─" * 62}')

    if args.check or not (args.pfx or args.thumbprint):
        if not (args.pfx or args.thumbprint):
            print(f'{WARN} 未提供证书，仅执行检查\n')
        ok = check_signature(targets)
        if ok:
            print(f'\n{PASS} 所有产物签名有效')
            return 0
        print(f'\n{FAIL} 部分产物未签名')
        print('\n未签名的 exe 在 Windows Defender / 企业环境中可能被误报拦截。')
        print('建议：购买 OV/EV 代码签名证书，或使用 Azure Trusted Signing。')
        return 1

    all_ok = True
    for f in targets:
        if not sign_file(f, args.pfx, args.password, args.thumbprint, args.timestamp):
            all_ok = False

    if all_ok:
        print(f'\n{PASS} 全部 {len(targets)} 个产物签名完成')
        return 0
    return 1


if __name__ == '__main__':
    sys.exit(main())
