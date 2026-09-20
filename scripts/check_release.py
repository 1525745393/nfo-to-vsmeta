#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/check_release.py — 发布前自动验证（Release Pre-check）

在打 tag / 发布之前运行，自动核对：

1. version.py 的版本号符合语义化版本 SemVer（X.Y.Z）；
2. CHANGELOG.md 存在且包含 [Unreleased] 段落；
3. CHANGELOG.md 最新已发布条目（第一个 "## [X.Y.Z]"）与 version.py 一致；
4. 最新版本条目的变更分类均在允许集合内（新增/修复/改进/废弃/移除/安全）；
5. （可选 --run-tests）运行单元测试；
6. （可选 --check-tag）校验 git tag v<版本号> 已存在。

用法：
    python3 scripts/check_release.py
    python3 scripts/check_release.py --run-tests
    python3 scripts/check_release.py --check-tag --run-tests
    python3 scripts/check_release.py --repo-root /path/to/repo

退出码：0 = 全部通过；1 = 存在未通过项。
"""

import os
import re
import sys
import argparse
import subprocess

# 允许的变更分类（与 CHANGELOG.md 模板保持一致）
ALLOWED_SECTIONS = {"新增", "修复", "改进", "废弃", "移除", "安全"}

SEMVER_RE = re.compile(r'^\d+\.\d+\.\d+$')
VERSION_ENTRY_RE = re.compile(r'^## \[(\d+\.\d+\.\d+)\]')
UNRELEASED_RE = re.compile(r'^## \[Unreleased\]', re.MULTILINE)
SECTION_RE = re.compile(r'^### (.+)$')


def fail(checks, msg):
    checks.append(("FAIL", msg))


def pass_ok(checks, msg):
    checks.append(("ok", msg))


def load_version(repo_root):
    """读取 version.py 的 __version__（避免 import 副作用）"""
    path = os.path.join(repo_root, "version.py")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    m = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
    if not m:
        raise ValueError("version.py 中未找到 __version__")
    return m.group(1)


def check_changelog(repo_root, version, checks):
    """校验 CHANGELOG.md 结构与版本一致性"""
    path = os.path.join(repo_root, "CHANGELOG.md")
    if not os.path.exists(path):
        fail(checks, "CHANGELOG.md 不存在")
        return

    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    if not UNRELEASED_RE.search("".join(lines)):
        fail(checks, "CHANGELOG.md 缺少 [Unreleased] 段落")

    # 第一个已发布版本条目必须与 version.py 一致
    latest_published = None
    for line in lines:
        m = VERSION_ENTRY_RE.match(line.strip())
        if m:
            latest_published = m.group(1)
            break
    if latest_published is None:
        fail(checks, "CHANGELOG.md 中没有任何已发布版本条目（## [X.Y.Z]）")
    elif latest_published != version:
        fail(checks, f"版本不一致：CHANGELOG 最新条目 {latest_published} != version.py {version}")
    else:
        pass_ok(checks, f"CHANGELOG 最新条目与 version.py 一致（{version}）")

    # 最新条目（Unreleased 之后第一个版本）的分类必须合规
    in_latest_entry = False
    sections_found = []
    for line in lines:
        line = line.strip()
        if line.startswith("## "):
            if in_latest_entry:
                break
            if line == "## [Unreleased]":
                continue
            if VERSION_ENTRY_RE.match(line):
                in_latest_entry = True
                continue
        if in_latest_entry:
            m = SECTION_RE.match(line)
            if m:
                sections_found.append(m.group(1))

    bad = [s for s in sections_found if s not in ALLOWED_SECTIONS]
    if bad:
        fail(checks, f"最新版本条目含未允许的分类：{', '.join(bad)}（允许：{'/'.join(sorted(ALLOWED_SECTIONS))}）")
    elif not sections_found:
        fail(checks, "最新版本条目下没有任何变更分类")
    else:
        pass_ok(checks, f"最新版本条目分类合规：{'/'.join(sections_found)}")


def check_semver(version, checks):
    if not SEMVER_RE.match(version):
        fail(checks, f"version.py 版本号 {version!r} 不符合 SemVer（需 X.Y.Z）")
    else:
        pass_ok(checks, f"version.py 版本号格式合规（{version}）")


def run_tests(repo_root, checks):
    try:
        result = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
            cwd=repo_root, capture_output=True, text=True, timeout=300,
        )
    except subprocess.TimeoutExpired:
        fail(checks, "单元测试超时（>300s）")
        return
    if result.returncode == 0:
        pass_ok(checks, "单元测试全部通过")
    else:
        tail = "\n".join(result.stdout.splitlines()[-5:] + result.stderr.splitlines()[-5:])
        fail(checks, f"单元测试未通过（exit={result.returncode}）\n{tail}")


def check_tag(version, checks):
    tag = f"v{version}"
    try:
        result = subprocess.run(
            ["git", "tag", "-l", tag], capture_output=True, text=True, timeout=30,
        )
    except Exception as e:
        fail(checks, f"无法查询 git tag：{e}")
        return
    if tag in result.stdout.split():
        pass_ok(checks, f"git tag {tag} 已存在")
    else:
        fail(checks, f"git tag {tag} 不存在（发布前请先打 tag）")


def main():
    parser = argparse.ArgumentParser(description="发布前自动验证：版本号与 CHANGELOG 一致性")
    parser.add_argument("--repo-root", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        help="仓库根目录（默认自动探测）")
    parser.add_argument("--run-tests", action="store_true", help="同时运行单元测试")
    parser.add_argument("--check-tag", action="store_true", help="同时校验 git tag vX.Y.Z 已存在")
    args = parser.parse_args()

    checks = []
    version = None
    try:
        version = load_version(args.repo_root)
        check_semver(version, checks)
        check_changelog(args.repo_root, version, checks)
        if args.run_tests:
            run_tests(args.repo_root, checks)
        if args.check_tag:
            check_tag(version, checks)
    except Exception as e:
        fail(checks, f"验证脚本运行异常：{e}")

    print(f"== 发布前验证（version={version or '?'}）==")
    for status, msg in checks:
        print(f"  [{status}] {msg}")

    failed = sum(1 for s, _ in checks if s == "FAIL")
    print(f"\n结果：{len(checks) - failed}/{len(checks)} 项通过")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
