# 版本更新检查清单（RELEASING）

发布新版本前的完整操作清单。按顺序执行，每步都有对应验证命令。

## 版本号规则（SemVer）

| 变更类型 | 版本增量 | 示例 |
| --- | --- | --- |
| 不兼容的重大变更 | 主版本 +1 | 1.2.0 → 2.0.0 |
| 向后兼容的新功能 | 次版本 +1 | 1.2.0 → 1.3.0 |
| 向后兼容的缺陷修复 | 修订版本 +1 | 1.2.0 → 1.2.1 |

版本号唯一权威源：`version.py` 的 `__version__`。

## 快速发布（推荐，一键）

把变更写进 `CHANGELOG.md` 的 `[Unreleased]` 段后，执行：

```bash
python3 scripts/release.py --bump minor   # patch | minor | major
```

一条命令完成：**版本号递增 → CHANGELOG 搬运 → 发布前验证（含单元测试）→ git 提交 → 打 tag**。
确认无误后推送（推送 `v*` 标签会自动触发 GitHub Actions 自动发布）：

```bash
git push origin main --tags
```

其他选项：
- `--bump patch|minor|major`：版本增量类型（必填）；
- `--yes`：跳过交互确认（脚本化/CI 使用）；
- `--dry-run`：只预览将要执行的变更，不写任何文件；
- `--skip-tag`：提交后不打 tag（演练用）。

## 发布前检查清单（release.py 未覆盖项）

- [ ] 功能/修复按预期工作，本机端到端验证通过（如 `--dry-run` → 正式转换 → `--verify`）
- [ ] 新增/修改的代码有对应单元测试，`python3 -m unittest discover -s tests -v` 全过
- [ ] 变更已按分类写入 `CHANGELOG.md` 的 `[Unreleased]`：新增 / 修复 / 改进 / 废弃 / 移除 / 安全
- [ ] README.md / 使用教程 若涉及命令行参数或配置变化，同步更新
- [ ] 部署注意事项核对（version.py 需与主脚本同目录）

## 发布后确认（自动发布）

推送 `v*` 标签后，GitHub Actions `release` 工作流自动执行：

1. 发布前验证（版本号/CHANGELOG/单元测试/git tag）；
2. `scripts/build_release.py` 构建 `dist/nfo-to-vsmeta-<版本>.zip`；
3. 生成 SHA256 校验和（SHA256SUMS 附件）并验证发布包解压后 `--version` 与版本号一致；
4. 创建 GitHub Release：正式版（`vX.Y.Z`）或预发布版（`vX.Y.Z-rcN`，标记 Prerelease），notes 自动取自 CHANGELOG。

- [ ] 确认 release 工作流运行成功，Release 页面出现发布包与 SHA256SUMS 附件
- [ ] 下载发布包的用户可用 `sha256sum -c SHA256SUMS` 校验完整性
- [ ] CI（test.yml）在 main 上的最近一次运行全部通过

## 预发布（测试环境先行）

新功能需要先验证时，使用预发布 tag（版本号仍按正式版递增，tag 带 `-rcN`）：

```bash
python3 scripts/release.py --bump minor
git tag v1.3.0-rc1 && git push origin main v1.3.0-rc1   # 触发 Prerelease
```

预发布 Release 会标记为 Prerelease，不影响正式版下载；验证通过后正式发布：

```bash
git push origin main v1.3.0   # 正式 tag（release.py 已打），触发正式 Release
```

## 版本兼容性检查

- **运行时兼容**：CI 在 Python 3.8–3.12 五个版本上跑全部单元测试 + CLI smoke，任一版本失败即阻断发布；
- **依赖兼容**：脚本无强制第三方依赖（Pillow 为可选，未安装自动降级），`check_release.py --run-tests` 在无依赖环境运行即验证；
- **发布包自检**：release 工作流解压发布包并执行 `--version`，确保打包内容与仓库一致。

## 性能基准对比

发布前后对比转换性能（固定参数保证可比）：

```bash
python3 scripts/benchmark.py --files 200 --workers 4
```

输出文件数 / 总耗时 / 吞吐（文件/秒）/ 单文件平均耗时。图片压缩场景加 `--with-images`。
基线建议：记录每次发版的 `--files 200 --workers 4` 结果，关注吞吐量是否明显回退。

## 发布回滚方案

发布后发现严重问题时，按严重程度选择：

| 场景 | 操作 |
| --- | --- |
| 功能缺陷（不影响主流程） | 记录到 `[Unreleased]` → 修复 → 发 patch 版（`--bump patch`） |
| 严重问题需立即恢复 | 用上一版本 tag 重发：`git checkout vX.Y.Z-1`（上一版本 tag）→ `git push origin vX.Y.Z-1:refs/tags/vX.Y.Z-1` 已存在则直接用 GitHub 页面把上一 Release 标为 Latest |
| Release 附件错误 | GitHub Release 页面编辑，替换附件后重新发布 |
| 代码本身错误已合入 main | `git revert <坏commit>` 推送修复（走 PR + 审查），再发 patch 版；**不要**删除远端 tag 或 force push |

> 约定：tag 一旦推送即视为不可变，回滚通过"发布新版本"而不是"删除旧版本"完成。

## 常见失败与处理

| 失败项 | 原因 | 处理 |
| --- | --- | --- |
| `CHANGELOG 最新条目 != version.py` | 版本号不同步 | 二选一保持一致，重新运行验证 |
| `含未允许的分类` | 分类名称写错 | 改为：新增/修复/改进/废弃/移除/安全 |
| `git tag 不存在` | 忘了打 tag | `git tag vX.Y.Z` 后重跑（或用 release.py 一键完成） |
| `单元测试未通过` | 代码回归 | 修复后重跑，禁止带失败发布 |
| release 工作流失败 | 发布门禁未过 | 查看 Actions 日志，按失败项修复后重新打 tag |
