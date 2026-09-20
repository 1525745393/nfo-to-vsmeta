# -*- coding: utf-8 -*-
"""
version.py — nfo-to-vsmeta 版本号唯一权威源（Single Source of Truth）

版本号格式：语义化版本 SemVer（X.Y.Z）
- X 主版本：不兼容的重大变更
- Y 次版本：向后兼容的功能新增
- Z 修订版本：向后兼容的缺陷修复

规则：
1. 所有版本信息（CHANGELOG 最新条目、git tag vX.Y.Z、--version 输出）必须与此处一致；
2. 发布前运行 `python3 scripts/check_release.py` 自动校验一致性；
3. 本文件必须与 nfo-to-vsmeta.1.0.py 放在同一目录（主脚本运行时导入）。
"""

__version__ = "1.2.0"

# 版本号仅允许 SemVer 主.次.修订（可含预发布/构建元数据，本仓库暂不使用）
__version_info__ = tuple(int(part) for part in __version__.split(".")[:3])
