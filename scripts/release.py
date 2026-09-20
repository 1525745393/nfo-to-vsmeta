#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/release.py — 一键发布（Release Helper）

把发布流程压缩为一条命令：
    更新 version.py → 移动 CHANGELOG [Unreleased] → 发布前验证 → git commit → git tag

用法：
    python3 scripts/release.py --bump minor          # 交互确认后执行
    python3 scripts/release.py --bump patch --yes    # 跳过确认
    python3 scripts/release.py --bump major --dry-run # 只预览，不写文件

参数：
    --bump {patch|minor|major}  版本增量类型（SemVer）
    --yes                       跳过交互确认
    --dry-run                   只打印将要执行的变更，不写任何文件
    --skip-tag                  提交后不打 tag（演练用）

执行后仍需推送（需要远程认证）：
    git push origin main --tags
"""

import argparse
import datetime
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION_PY = os.path.join(ROOT, "version.py")
CHANGELOG_MD = os.path.join(ROOT, "CHANGELOG.md")
REPO_URL = "https://github.com/1525745393/nfo-to-vsmeta"

UNRELEASED_RE = re.compile(r"^## \[Unreleased\]\n(.*?)(?=^## \[\d)", re.MULTILINE | re.DOTALL)
SECTION_RE = re.compile(r"^### (.+?)\n(.*?)(?=^### |\Z)", re.MULTILINE | re.DOTALL)
VERSION_LINE_RE = re.compile(r'^__version__\s*=\s*["\'][^"\']+["\']', re.MULTILINE)
UNRELEASED_LINK_RE = re.compile(r"compare/v[\d.]+\.\.\.HEAD")


def current_version() -> str:
    with open(VERSION_PY, encoding="utf-8") as f:
        content = f.read()
    m = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
    if not m:
        raise RuntimeError("version.py 中未找到 __version__")
    return m.group(1)


def bump_version(version: str, kind: str) -> str:
    """SemVer 递增：patch/minor/major"""
    major, minor, patch = (int(p) for p in version.split("."))
    if kind == "major":
        return f"{major + 1}.0.0"
    if kind == "minor":
        return f"{major}.{minor + 1}.0"
    if kind == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ValueError(f"未知的版本增量类型: {kind}")


def split_changelog(text: str):
    """把 CHANGELOG 拆为 (head, links)：head 含 [Unreleased] 与各版本条目，links 为文末链接区"""
    m = re.search(r"^\[Unreleased\]:", text, re.MULTILINE)
    if not m:
        raise RuntimeError("CHANGELOG 文末缺少 [Unreleased] 链接")
    return text[: m.start()], text[m.start() :]


def extract_unreleased_blocks(body: str):
    """解析 [Unreleased] 段：(有内容的分类块列表, 空分类标题列表, 注释行列表)"""
    filled, empty = [], []
    for bm in SECTION_RE.finditer(body):
        title, items = bm.group(1), bm.group(2)
        if items.strip():
            filled.append(f"### {title}\n{items.rstrip()}")
        else:
            empty.append(f"### {title}")
    comments = [ln for ln in body.splitlines() if ln.strip().startswith(">")]
    return filled, empty, comments


def update_changelog(text: str, new_version: str, date: str) -> str:
    """把 [Unreleased] 内容移动到新版本条目，保留空分类模板，并更新链接区"""
    head, links = split_changelog(text)
    m = UNRELEASED_RE.search(head)
    if not m:
        raise RuntimeError("CHANGELOG 缺少 [Unreleased] 段落")

    filled, empty, comments = extract_unreleased_blocks(m.group(1))

    new_unreleased = "## [Unreleased]\n\n"
    if comments:
        new_unreleased += "\n".join(comments) + "\n\n"
    new_unreleased += "\n\n".join(empty)
    if empty:
        new_unreleased += "\n"

    if filled:
        new_entry = f"## [{new_version}] - {date}\n\n" + "\n\n".join(filled) + "\n"
    else:
        new_entry = f"## [{new_version}] - {date}\n\n（本版本无已记录变更）\n"

    new_head = head[: m.start()] + new_unreleased + "\n" + new_entry + head[m.end() :]

    # 链接区：更新 [Unreleased] compare 目标，并插入新版本链接
    new_links = UNRELEASED_LINK_RE.sub(f"compare/v{new_version}...HEAD", links)
    lines = new_links.splitlines()
    insert_at = next(
        (i for i, ln in enumerate(lines) if ln.startswith("[Unreleased]:")), len(lines)
    )
    lines.insert(insert_at, f"[{new_version}]: {REPO_URL}/releases/tag/v{new_version}")
    return new_head + "\n".join(lines) + ("\n" if new_links.endswith("\n") else "")


def update_version_py(new_version: str) -> None:
    with open(VERSION_PY, encoding="utf-8") as f:
        content = f.read()
    content = VERSION_LINE_RE.sub(f'__version__ = "{new_version}"', content, count=1)
    with open(VERSION_PY, "w", encoding="utf-8") as f:
        f.write(content)


def run(cmd, **kwargs):
    return subprocess.run(cmd, cwd=ROOT, check=True, capture_output=True, text=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(
        description="一键发布：bump 版本 + CHANGELOG + 验证 + 提交 + tag"
    )
    parser.add_argument(
        "--bump", required=True, choices=["patch", "minor", "major"], help="版本增量类型"
    )
    parser.add_argument("--yes", action="store_true", help="跳过交互确认")
    parser.add_argument("--dry-run", action="store_true", help="只预览，不写文件")
    parser.add_argument("--skip-tag", action="store_true", help="提交后不打 tag")
    args = parser.parse_args()

    current = current_version()
    new_version = bump_version(current, args.bump)
    date = datetime.date.today().isoformat()

    with open(CHANGELOG_MD, encoding="utf-8") as f:
        changelog = f.read()
    filled, empty, comments = extract_unreleased_blocks(UNRELEASED_RE.search(changelog).group(1))
    moving = sum(len(s.splitlines()) - 1 for s in filled)

    print(f"当前版本 : v{current}")
    print(f"新版本   : v{new_version}（{args.bump} 增量）")
    print(f"变更条目 : 将把 [Unreleased] 下 {moving} 条变更移动到 v{new_version}")
    if not filled:
        print("提示: [Unreleased] 下没有任何变更条目，仍将创建空版本条目。")

    if not args.yes and not args.dry_run:
        answer = input("确认执行发布？[y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            print("已取消。")
            return 1

    if args.dry_run:
        print("\n[dry-run] 将更新:")
        print(f'  - version.py: __version__ = "{new_version}"')
        print(f"  - CHANGELOG.md: 新增 [{new_version}] 条目并清空 [Unreleased]")
        print("  - 运行 check_release.py --run-tests")
        print('  - git commit -m "release: v' + new_version + '"')
        print("  - git tag v" + new_version)
        return 0

    update_version_py(new_version)
    with open(CHANGELOG_MD, "w", encoding="utf-8") as f:
        f.write(update_changelog(changelog, new_version, date))
    print(f"已更新 version.py 与 CHANGELOG.md（v{new_version}）")

    print("运行发布前验证...")
    run([sys.executable, "scripts/check_release.py", "--run-tests"])

    print("提交并打 tag...")
    run(["git", "add", "-A"])
    run(["git", "commit", "-m", f"release: v{new_version}"])
    if not args.skip_tag:
        run(["git", "tag", f"v{new_version}"])
        print(f"已打 tag v{new_version}")
    else:
        print("--skip-tag：未打 tag")

    print("\n完成。推送发布（推送 v* 标签会自动触发 GitHub Actions 自动发布）:")
    print("  git push origin main --tags")
    return 0


if __name__ == "__main__":
    sys.exit(main())
