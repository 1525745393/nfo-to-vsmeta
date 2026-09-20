# Changelog

本项目所有值得记录的变更都汇总在此文件。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)（X.Y.Z，见 version.py）。

变更分类：
- **新增**：新功能
- **修复**：缺陷修复
- **改进**：既有功能增强/重构（不改变外部行为或为修复铺路）
- **废弃**：即将移除的旧行为
- **移除**：已删除的功能
- **安全**：安全相关修复

## [Unreleased]

> 新变更先写在这里，发布时移动到对应版本条目并更新 version.py。

### 新增

### 修复

### 改进

### 废弃

### 移除

### 安全

## [1.2.0] - 2026-09-21

### 新增

- 版本管理与发布验证体系：`version.py`（版本号唯一权威源）、`CHANGELOG.md`、`scripts/check_release.py` 发布前自动校验、`RELEASING.md` 发布检查清单；
- 主脚本新增 `--version` 参数，输出当前版本号（读取 version.py，需与主脚本同目录部署）；
- CI 新增发布校验步骤：自动核对 version.py 与 CHANGELOG 最新条目、格式合规、单元测试。

### 改进

- README 中的变更记录迁移至独立 `CHANGELOG.md`，README 保留入口链接，避免双份维护；
- 版本号统一为三位语义化版本（v1.0 → 1.0.0、v1.0.1 → 1.0.1、v1.1 → 1.1.0）。

## [1.1.0] - 2025-05-07

### 新增

- TV 剧集支持：从文件名解析 `SxxEyy` / `xx x yy`，写入 vsmeta 的 season/episode 字段；
- `--dry-run` 干跑模式：只打印将转换的文件，不写盘；
- `--verify` 自检模式：转换后回读解析 vsmeta，校验年份/评分/季集等关键字段并写入日志；
- 日志轮转（`log_max_bytes` / `log_backup_count` 配置）；
- nfo 解析健壮性：支持 CDATA / 混合内容文本提取，支持 GBK / 无 XML 声明编码自动回退；
- 提取 studio（制片厂）字段，`studio_as_tagline: true` 时合并进 tagline（vsmeta 格式无独立 studio 字段）；
- 未识别文件提示（`ignore_extensions` 可配置忽略列表）。

### 修复

- 结尾数字解析（`Show.02`）改为配置开关 `parse_episode_from_trailing_digits`（默认关闭），并收紧为两位数字——修复 JAV 番号（如 `ABP-998`）与少数电影名被误判为剧集的问题；
- `--verify` 对非数字年份不再抛异常，改为记录"年份格式异常"问题。

### 改进

- 合并原 transfer.py，统一为一个脚本，消除重复代码；
- 新增单元测试套件（varint 边界、季集解析、编码回退、字段完整性、dry-run、自检、JAV 番号回归）与 GitHub Actions CI。

## [1.0.1] - 2025-05-06

### 修复

- 修复增强版只写入标题/海报/背景图，丢失简介、年份、日期、分级、评分、类型、演员、导演、编剧等字段的问题；
- 修复背景图（fanart）二进制结构写错导致群晖无法识别的问题；
- 海报/背景图改为 76 字符换行 Base64 编码，与群晖 Video Station 期望格式一致；
- 修复字段长度恰好为 128 字节时 varint 编码写出非法字节，导致整个文件后续字段错位的问题；
- 修复图片压缩函数资源泄漏问题；
- 修复可变默认参数等代码隐患。

### 新增

- 支持多目录扫描（`directory` 可为字符串或列表）；
- 支持 `max_workers`（并发线程数）、`compress_image` / `compress_kb`（图片压缩开关与目标大小）、`log_file`（日志文件路径）等配置；
- 配置文件自动合并默认值，缺失字段不再报错；
- 未安装 Pillow 时自动降级为不压缩，功能不受影响。

## [1.0.0] - 2025-05-01

### 新增

- 将 .nfo 转换为 .vsmeta；
- 支持递归扫描目录；
- 自动识别影片名称与封面；
- 基础 CLI 参数支持；
- 支持群晖 Video Station 索引识别格式。

[Unreleased]: https://github.com/1525745393/nfo-to-vsmeta/compare/v1.2.0...HEAD
[1.2.0]: https://github.com/1525745393/nfo-to-vsmeta/releases/tag/v1.2.0
[1.1.0]: https://github.com/1525745393/nfo-to-vsmeta/releases/tag/v1.1.0
[1.0.1]: https://github.com/1525745393/nfo-to-vsmeta/releases/tag/v1.0.1
[1.0.0]: https://github.com/1525745393/nfo-to-vsmeta/releases/tag/v1.0.0
