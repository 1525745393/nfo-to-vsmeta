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

- 一键发布脚本 `scripts/release.py`：`--bump patch|minor|major` 一条命令完成 版本号递增 → CHANGELOG 搬运 → 发布前验证 → 提交 → 打 tag；
- 性能基准工具 `scripts/benchmark.py`：合成数据测量 nfo→vsmeta 转换吞吐，供跨版本对比；
- 主脚本新增 `--check-update`：查询 GitHub Releases 提示新版本（联网失败静默，不影响转换）；
- 发布包安全增强：Release 附件增加 SHA256SUMS 校验和，工作流自动验证发布包解压后 `--version` 一致；
- 预发布支持：`vX.Y.Z-rcN` 标签自动标记为 Prerelease，可先发布到测试环境验证；
- 源文件更新自动重转：nfo/海报/背景图比 vsmeta 新时自动重新转换（配置 `update_stale_vsmeta`，默认开）；
- vsmeta 原子写入：先写临时文件再替换，中断不会留下损坏文件；
- 主脚本新增 `--quiet`：终端只显示警告与错误（日志仍完整写入文件）；
- 多集命名支持：`S01E02E03` 合辑自动取第一集号；
- 配置校验：`config.json` 类型错误在启动时即明确报错，不再运行期崩溃；
- 退出码：转换有失败时返回 1，可被群晖任务计划/脚本化调用感知；
- 仓库新增 `LICENSE`（MIT）、`CONTRIBUTING.md`、issue/PR 模板与 CodeQL 安全扫描。

### 修复

### 改进

- CI 提速：pip / ruff / mypy 缓存、同分支新提交自动取消旧运行、发布校验从测试矩阵中抽出独立执行一次；
- CI 新增 smoke 测试（`--version` 与 CLI 冒烟），测试矩阵保持 Python 3.8–3.12；
- `check_release.py --check-tag` 兼容预发布 tag（`v1.3.0-rc1` 也视为已打 tag）；
- `--verify` 自检增强：新增日期、分级、演员数量校验（parse_vsmeta_fields 现保留字符串字段内容）。

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
