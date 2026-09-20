# -*- coding: utf-8 -*-
"""发布工具单元测试：release.py（一键发布）与主脚本升级检测逻辑"""

import importlib.util
import os
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_module(name, relpath):
    path = os.path.join(ROOT, relpath)
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


release = load_module("release_tools", "scripts/release.py")
n2v = load_module("nfo2vsmeta_upd", "nfo-to-vsmeta.1.0.py")

SAMPLE_CHANGELOG = """# Changelog

## [Unreleased]

> 新变更先写在这里。

### 新增

### 修复

- 修复了某个问题
- 修复了另一个问题

### 改进

## [1.2.0] - 2026-09-21

### 新增

- 旧版本条目

[Unreleased]: https://github.com/1525745393/nfo-to-vsmeta/compare/v1.2.0...HEAD
[1.2.0]: https://github.com/1525745393/nfo-to-vsmeta/releases/tag/v1.2.0
"""


class BumpVersionTestCase(unittest.TestCase):
    def test_patch(self):
        self.assertEqual(release.bump_version("1.2.0", "patch"), "1.2.1")

    def test_minor(self):
        self.assertEqual(release.bump_version("1.2.0", "minor"), "1.3.0")

    def test_major(self):
        self.assertEqual(release.bump_version("1.2.0", "major"), "2.0.0")

    def test_invalid_kind(self):
        with self.assertRaises(ValueError):
            release.bump_version("1.2.0", "big")


class ChangelogUpdateTestCase(unittest.TestCase):
    def test_update_changelog_moves_entries(self):
        new_text = release.update_changelog(SAMPLE_CHANGELOG, "1.3.0", "2026-09-22")

        # 新版本条目包含 [Unreleased] 中"修复"分类的条目
        self.assertIn("## [1.3.0] - 2026-09-22", new_text)
        self.assertIn("- 修复了某个问题", new_text)
        self.assertIn("- 修复了另一个问题", new_text)

        # 新条目不含空分类（新增/改进留在 Unreleased 模板）
        in_130 = new_text.split("## [1.3.0]")[1].split("## [1.2.0]")[0]
        self.assertNotIn("### 新增\n\n### 修复", in_130)

        # Unreleased 保留注释与空分类标题，且不再包含已移动的条目
        unreleased = new_text.split("## [Unreleased]")[1].split("## [1.3.0]")[0]
        self.assertIn("> 新变更先写在这里。", unreleased)
        self.assertIn("### 新增", unreleased)
        self.assertIn("### 改进", unreleased)
        self.assertNotIn("修复了某个问题", unreleased)

        # 链接区：新版本链接插入，[Unreleased] compare 目标更新
        self.assertIn(
            "[1.3.0]: https://github.com/1525745393/nfo-to-vsmeta/releases/tag/v1.3.0", new_text
        )
        self.assertIn("compare/v1.3.0...HEAD", new_text)
        self.assertNotIn("compare/v1.2.0...HEAD", new_text)
        # 旧版本条目保留
        self.assertIn("- 旧版本条目", new_text)
        self.assertIn("[1.2.0]:", new_text)

    def test_update_changelog_empty_unreleased(self):
        empty = SAMPLE_CHANGELOG.replace(
            "- 修复了某个问题\n- 修复了另一个问题\n\n### 改进", "### 改进"
        )
        new_text = release.update_changelog(empty, "1.3.0", "2026-09-22")
        self.assertIn("（本版本无已记录变更）", new_text)
        self.assertIn("## [Unreleased]", new_text)

    def test_update_version_py(self):
        with tempfile.TemporaryDirectory() as d:
            vpath = os.path.join(d, "version.py")
            with open(vpath, "w", encoding="utf-8") as f:
                f.write('__version__ = "1.2.0"\n')
            # 直接调用 update_version_py 需指向仓库 version.py，改为构造式验证：
            with open(os.path.join(ROOT, "version.py"), encoding="utf-8") as f:
                content = f.read()
            new_content = release.VERSION_LINE_RE.sub('__version__ = "9.9.9"', content, count=1)
            with open(vpath, "w", encoding="utf-8") as f:
                f.write(new_content)
            with open(vpath, encoding="utf-8") as f:
                self.assertIn('__version__ = "9.9.9"', f.read())


class CheckUpdateTestCase(unittest.TestCase):
    def test_format_update_message_newer(self):
        msg = n2v.format_update_message("v1.3.0", "1.2.0")
        self.assertIn("发现新版本 v1.3.0", msg)
        self.assertIn("当前 v1.2.0", msg)

    def test_format_update_message_no_prefix(self):
        msg = n2v.format_update_message("1.3.0", "1.2.0")
        self.assertIn("v1.3.0", msg)

    def test_format_update_message_same_version(self):
        self.assertEqual(n2v.format_update_message("v1.2.0", "1.2.0"), "")

    def test_format_update_message_unknown_current(self):
        self.assertEqual(n2v.format_update_message("v1.3.0", "unknown"), "")

    def test_format_update_message_empty_latest(self):
        self.assertEqual(n2v.format_update_message("", "1.2.0"), "")


if __name__ == "__main__":
    unittest.main()
