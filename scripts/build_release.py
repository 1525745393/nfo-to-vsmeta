#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/build_release.py — 构建发布包（Release Build）

把发布所需的文件打包为 dist/nfo-to-vsmeta-<version>.zip（含顶层目录），
供 GitHub Actions release 工作流上传到 Release 附件。

用法：
    python3 scripts/build_release.py            # 生成发布 zip
    python3 scripts/build_release.py --notes    # 输出 CHANGELOG 当前版本条目（release notes）

退出码：0 = 成功；1 = 失败。
"""

import os
import re
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 随发布包分发的文件（相对于仓库根目录）；不存在的文件自动跳过
RELEASE_FILES = [
    "nfo-to-vsmeta.1.0.py",
    "version.py",
    "config.json 示例",
    "使用教程v1.0",
    "README.md",
    "CHANGELOG.md",
    "RELEASING.md",
]


def load_version():
    """读取 version.py 的 __version__"""
    with open(os.path.join(ROOT, "version.py"), "r", encoding="utf-8") as f:
        content = f.read()
    m = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
    if not m:
        raise ValueError("version.py 中未找到 __version__")
    return m.group(1)


def release_notes(version):
    """从 CHANGELOG.md 提取对应版本条目作为 Release notes"""
    path = os.path.join(ROOT, "CHANGELOG.md")
    if not os.path.exists(path):
        raise FileNotFoundError("CHANGELOG.md 不存在")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    pattern = re.compile(
        rf"^## \[{re.escape(version)}\] - \d{{4}}-\d{{2}}-\d{{2}}\n(.*?)(?=^## \[|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = pattern.search(content)
    if not m:
        raise ValueError(f"CHANGELOG.md 中没有 [{version}] 条目")
    return f"## v{version}\n\n{m.group(1).strip()}\n"


def build_zip(version):
    dist_dir = os.path.join(ROOT, "dist")
    os.makedirs(dist_dir, exist_ok=True)
    zip_path = os.path.join(dist_dir, f"nfo-to-vsmeta-{version}.zip")
    top_dir = f"nfo-to-vsmeta-{version}"

    packed = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in RELEASE_FILES:
            src = os.path.join(ROOT, rel)
            if not os.path.exists(src):
                print(f"[skip] 不存在，跳过: {rel}", file=sys.stderr)
                continue
            zf.write(src, os.path.join(top_dir, rel))
            packed += 1
            print(f"[add ] {rel}")

    print(f"\n已打包 {packed} 个文件 -> {zip_path}")
    return zip_path


def main():
    version = load_version()
    if "--notes" in sys.argv:
        print(release_notes(version))
        return 0
    build_zip(version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
