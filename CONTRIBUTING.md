# Contributing

欢迎为本项目贡献代码。本项目遵循以下协作约定，请先阅读。

## 开发环境

```bash
git clone https://github.com/1525745393/nfo-to-vsmeta.git
cd nfo-to-vsmeta
python3 -m unittest discover -s tests   # 运行全部测试（无需第三方依赖）
pip install ruff mypy                   # 可选：Lint / 类型检查（CI 使用）
ruff check . && mypy
```

## 提交规范

Commit message 使用约定式前缀，格式：`<type>: <描述>`

- `feat:` 新功能
- `fix:` 缺陷修复
- `ci:` CI/CD 相关
- `docs:` 文档
- `refactor:` 重构（无行为变化）
- `test:` 测试
- `release:` 发版（版本号 + CHANGELOG + tag）

## 变更流程

1. 新功能/修复**必须附带单元测试**（`tests/`），并保证 `python3 -m unittest discover -s tests` 全过；
2. 运行 `ruff check .`、`ruff format --check .`、`mypy` 无报错；
3. 行为变化（新参数/新配置/默认值调整）需同步更新 `README.md`、`使用教程v1.0`；
4. 用户可见变更写入 `CHANGELOG.md` 的 `[Unreleased]` 段（分类：新增/修复/改进/废弃/移除/安全）；
5. 通过 PR 合并到 `main`。main 分支有保护：CI 状态检查（Lint & Type Check、Test on Python 3.12）必须通过，禁止 force push。

## 发布流程

见 [RELEASING.md](RELEASING.md)。核心命令：

```bash
python3 scripts/release.py --bump minor   # 一键：版本号 → CHANGELOG → 验证 → 提交 → 打 tag
git push origin main --tags               # 触发自动发布
```
