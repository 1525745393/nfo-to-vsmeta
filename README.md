# nfo to vsmeta

[![CI](https://github.com/1525745393/nfo-to-vsmeta/actions/workflows/test.yml/badge.svg)](https://github.com/1525745393/nfo-to-vsmeta/actions/workflows/test.yml)

通过 Emby/Jellyfin/TinyMediaManager 等刮削到的 nfo 元数据，转换成群晖 Video Station 专用 vsmeta 元数据，实现刮削数据共享复用。

> 感谢原版大佬建议，更改代码自用版。

## 仓库内容

| 文件 | 说明 |
| --- | --- |
| `nfo-to-vsmeta.1.0.py` | 统一版脚本（原 transfer.py 已合并至此）：支持配置、多线程、多目录、剧集季/集、完整元数据字段、图片压缩、干跑与自检 |
| `version.py` | 版本号唯一权威源（SemVer），**需与主脚本同目录部署**；`--version` 输出它 |
| `config.json` | 配置文件（示例见 `config.json 示例`） |
| `使用教程v1.0` | 详细使用教程 |
| `CHANGELOG.md` | 版本变更记录（Keep a Changelog 标准） |
| `RELEASING.md` | 版本更新检查清单 |
| `scripts/check_release.py` | 发布前自动验证（版本号/CHANGELOG 一致性 + 可选测试与 git tag） |
| `scripts/build_release.py` | 构建发布 zip（`dist/nfo-to-vsmeta-<版本>.zip`），供自动发布上传 |
| `scripts/release.py` | 一键发布：`--bump minor` 完成 版本号→CHANGELOG→验证→提交→tag |
| `scripts/benchmark.py` | 转换性能基准（合成数据测吞吐，供跨版本对比） |
| `tests/` | 单元测试（`python3 -m unittest discover -s tests`） |
| `.github/workflows/test.yml` | CI：Linter（ruff）+ 类型检查（mypy）+ 测试矩阵（Python 3.8–3.12）+ 发布校验 |
| `.github/workflows/release.yml` | 自动发布：推送 `v*` 标签即构建发布包并创建 GitHub Release（含 SHA256 校验与预发布支持） |

## 发布方式（维护者）

代码推送到 `main` 会自动触发 CI（Lint/类型检查/测试）。需要发版时：

```bash
python3 scripts/release.py --bump minor        # 一键：bump → CHANGELOG → 验证 → 提交 → 打 tag
  git push origin main --tags                    # 推送标签即触发自动发布
```

打标签推送后，GitHub Actions 会自动：验证 → 打包 `nfo-to-vsmeta-vX.Y.Z.zip` + `SHA256SUMS` → 解压自检 → 创建 Release（notes 取自 CHANGELOG）。预发布用 `vX.Y.Z-rcN` 标签（自动标记 Prerelease）。详细流程见 [RELEASING.md](RELEASING.md)。

## 使用方法

1. 将 `nfo-to-vsmeta.1.0.py`、`version.py` 和 `config.json` 保存到群晖任意目录（三个文件需在同一目录）；
2. 编辑 `config.json`，将 `directory` 改为视频文件实际目录（建议配合 NasTool 使用硬链目录），海报/背景图后缀与刮削结果一致；
3. 确认目录下每个视频有同名 `.nfo` 文件，以及同名海报/背景图（如 `xxx-poster.jpg`、`xxx-fanart.jpg`，可在配置中修改后缀）；
4. 在群晖控制面板 > 任务计划，新增 > 计划的任务 > 用户定义的脚本；
5. 计划名称、执行时间、执行频率按需设置；
6. 自定义脚本栏输入命令（注意修改路径为实际保存脚本的路径）：

   ```bash
   python3 /volume1/xxx/nfo-to-vsmeta.1.0.py --config /volume1/xxx/config.json --verify
   ```

7. 已转换过的不会重复转换；**若 nfo/海报/背景图被更新（如重新刮削），下次运行会自动重新转换**（`update_stale_vsmeta: false` 可关闭）。如需全量重置，可将 `config.json` 中 `delete_vsmeta` 改为 `true` 再运行一次（会自动删除所有 `.vsmeta` 并重新转换），之后建议改回 `false`；重置后需手动点 设置 > 视频库 > 再次搜索所有视频信息 刷新元数据缓存。

## 命令行参数

| 参数 | 说明 |
| --- | --- |
| `--config FILE` | 指定配置文件路径（默认 `config.json`） |
| `--directory DIR` | 指定扫描目录，覆盖配置（也支持 `--poster` / `--fanart` 覆盖后缀） |
| `--dry-run` | 干跑模式：只打印将转换的文件，不写盘 |
| `--verify` | 转换后回读 vsmeta 自检字段完整性（标题/年份/日期/分级/评分/演员/季集），结果写入日志 |
| `--log-file FILE` | 指定日志文件路径，覆盖配置 |
| `--version` | 输出版本号（读取 version.py） |
| `--check-update` | 检查 GitHub 是否有新版本并提示（联网失败静默，不影响转换） |
| `--quiet` | 终端只显示警告与错误（日志仍完整写入文件） |

## 功能特性

- **电影 + 剧集**：自动从文件名解析季/集号（`S01E02` / `S01E02E03` 合辑取首集 / `1x2`），剧集写入 season/episode 字段；结尾数字（如 `Show.02`）需配置 `parse_episode_from_trailing_digits: true` 才启用（默认关闭，避免 JAV 番号等误判为剧集）；
- **完整元数据**：标题、副标题、标语、简介、年份、日期、分级、评分、类型、演员、导演、编剧；
- **自动更新**：源文件（nfo/海报/背景）更新后自动重新转换（`update_stale_vsmeta`，默认开）；
- **可靠写入**：vsmeta 采用原子写入（临时文件 + 替换），中断不会留下损坏文件；配置错误在启动时即明确报错；
- **图片压缩**：已安装 Pillow 时自动把海报/背景图压缩至 `compress_kb`（默认 200KB）以内；
- **多目录**：`directory` 可填列表一次处理多个路径；
- **日志轮转**：`log_file` 超过 `log_max_bytes` 自动轮转，保留 `log_backup_count` 份；大批量运行时可用 `--quiet` 降噪；
- **健壮解析**：支持 CDATA/混合内容文本，支持 GBK 等编码自动回退；
- **自检**：`--verify` 转换后回读校验年份、日期、分级、评分、演员数量、季/集等关键字段；
- **脚本友好**：转换有失败时退出码为 1，可被任务计划/脚本感知。

## 环境要求

- Python 3.8 或更高版本
- 可选依赖（图片压缩）：`pip install Pillow`（未安装时自动跳过压缩，功能不受影响）

## 使用效果

![image](https://github.com/JuanWoo/nfo-to-vsmeta/assets/4869539/5c089d2c-8064-4c94-bf42-c6e3117e2492)

---

## 更新日志（CHANGELOG）

完整变更记录见 [CHANGELOG.md](CHANGELOG.md)（Keep a Changelog 标准，变更分类：新增/修复/改进/废弃/移除/安全）。

版本更新流程见 [RELEASING.md](RELEASING.md)。协作与贡献见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## License

[MIT](LICENSE)
