# 版本更新检查清单（RELEASING）

发布新版本前的完整操作清单。按顺序执行，每步都有对应验证命令。

## 版本号规则（SemVer）

| 变更类型 | 版本增量 | 示例 |
| --- | --- | --- |
| 不兼容的重大变更 | 主版本 +1 | 1.2.0 → 2.0.0 |
| 向后兼容的新功能 | 次版本 +1 | 1.2.0 → 1.3.0 |
| 向后兼容的缺陷修复 | 修订版本 +1 | 1.2.0 → 1.2.1 |

版本号唯一权威源：`version.py` 的 `__version__`。

## 发布前检查清单

### 1. 确认变更已全部完成并自测

- [ ] 功能/修复按预期工作，本机端到端验证通过（如 `--dry-run` → 正式转换 → `--verify`）
- [ ] 新增/修改的代码有对应单元测试

### 2. 更新版本号

- [ ] 在 `version.py` 中按上表规则递增 `__version__`
- [ ] 确认主脚本通过 `from version import __version__` 引用（保持单源）

### 3. 更新 CHANGELOG.md

- [ ] 把 `[Unreleased]` 段落中的全部变更移动到新版本条目 `## [X.Y.Z] - YYYY-MM-DD`
- [ ] 变更按分类归档：新增 / 修复 / 改进 / 废弃 / 移除 / 安全
- [ ] 空分类不要保留标题（只保留实际有内容的分类）
- [ ] 在文末链接区添加 `[X.Y.Z]: <compare/releases 链接>`，并把 `[Unreleased]` 链接的 compare 目标改为新版本

### 4. 发布前自动验证

```bash
# 基本校验：版本号格式 + CHANGELOG 结构与一致性
python3 scripts/check_release.py

# 完整校验：以上 + 单元测试 + git tag
python3 scripts/check_release.py --run-tests --check-tag
```

必须全部 `[ok]`，任何 `[FAIL]` 都禁止发布。

### 5. 回归测试

```bash
python3 -m unittest discover -s tests -v
```

### 6. 文档同步

- [ ] README.md 若引用版本号/新功能，同步更新
- [ ] 使用教程若涉及命令行参数/配置变化，同步更新
- [ ] 部署注意事项核对（version.py 需与主脚本同目录）

### 7. 提交

```bash
git add -A
git commit -m "release: vX.Y.Z ..."
```

### 8. 打 tag 并推送

```bash
git tag vX.Y.Z
git push origin main --tags
```

> tag 名称必须是 `v` + 版本号（如 `v1.2.0`），`check_release.py --check-tag` 依赖此约定。

### 9. 发布后确认（自动发布）

推送 `v*` 标签后，GitHub Actions `release` 工作流自动执行：

1. 发布前验证（版本号/CHANGELOG/单元测试/git tag）；
2. `scripts/build_release.py` 构建 `dist/nfo-to-vsmeta-<版本>.zip`；
3. 创建 GitHub Release，附上发布包，notes 自动取自 CHANGELOG 对应版本条目。

- [ ] 确认 release 工作流运行成功，Release 页面出现发布包附件
- [ ] CI（test.yml）在 main 上的最近一次运行全部通过

## 快速发布（无新功能时）

仅修复缺陷（修订版本 +1）：

```bash
python3 scripts/check_release.py --run-tests   # 全部 ok
git add -A && git commit -m "release: v1.2.1 ..."
git tag v1.2.1 && git push origin main --tags
```

## 常见失败与处理

| 失败项 | 原因 | 处理 |
| --- | --- | --- |
| `CHANGELOG 最新条目 != version.py` | 版本号不同步 | 二选一保持一致，重新运行验证 |
| `含未允许的分类` | 分类名称写错 | 改为：新增/修复/改进/废弃/移除/安全 |
| `git tag 不存在` | 忘了打 tag | `git tag vX.Y.Z` 后重跑 |
| `单元测试未通过` | 代码回归 | 修复后重跑，禁止带失败发布 |
