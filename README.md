# nfo to vsmeta

通过 Emby/Jellyfin/TinyMediaManager 等刮削到的 nfo 元数据，转换成群晖 Video Station 专用 vsmeta 元数据，实现刮削数据共享复用。

> 感谢原版大佬建议，更改代码自用版。

## 仓库内容

| 文件 | 说明 |
| --- | --- |
| `nfo-to-vsmeta.1.0.py` | **推荐使用**。增强版：支持 config.json 配置、多线程、多目录扫描、完整元数据字段、可选图片压缩 |
| `transfer.py` | 轻量版：单目录扫描，逻辑简单直观，含图片压缩（需 Pillow） |
| `config.json` | 配置文件（示例见 `config.json 示例`） |
| `使用教程v1.0` | 详细使用教程 |

## 使用方法（推荐：nfo-to-vsmeta.1.0.py）

1. 将 `nfo-to-vsmeta.1.0.py` 和 `config.json` 保存到群晖任意目录；
2. 编辑 `config.json`，将 `directory` 改为视频文件实际目录（建议配合 NasTool 使用硬链目录），海报/背景图后缀与刮削结果一致；
3. 确认目录下每个视频有同名 `.nfo` 文件，以及同名海报/背景图（如 `xxx-poster.jpg`、`xxx-fanart.jpg`，可在配置中修改后缀）；
4. 在群晖控制面板 > 任务计划，新增 > 计划的任务 > 用户定义的脚本；
5. 计划名称、执行时间、执行频率按需设置；
6. 自定义脚本栏输入命令（注意修改路径为实际保存脚本的路径）：

   ```bash
   python3 /volume1/xxx/nfo-to-vsmeta.1.0.py --config /volume1/xxx/config.json
   ```

7. 已转换过的不会重复转换。如需重置，可将 `config.json` 中 `delete_vsmeta` 改为 `true` 再运行一次（会自动删除所有 `.vsmeta` 并重新转换），之后建议改回 `false`；重置后需手动点 设置 > 视频库 > 再次搜索所有视频信息 刷新元数据缓存。

### 使用 transfer.py（轻量版）

```bash
python3 transfer.py --directory /volume1/video/Links/Movie/
```

也支持 `--config`、`--poster`、`--fanart` 参数，未指定时读取同目录 `config.json`。

## 环境要求

- Python 3.8 或更高版本
- 可选依赖（图片压缩）：`pip install Pillow`（未安装时自动跳过压缩，功能不受影响）

## 使用效果

![image](https://github.com/JuanWoo/nfo-to-vsmeta/assets/4869539/5c089d2c-8064-4c94-bf42-c6e3117e2492)

---

## 更新日志（CHANGELOG）

### v1.0.1（修复版）— 2025-05-06

**修复**

- 修复增强版只写入标题/海报/背景图，丢失简介、年份、日期、分级、评分、类型、演员、导演、编剧等字段的问题；
- 修复背景图（fanart）二进制结构写错导致群晖无法识别的问题；
- 海报/背景图改为 76 字符换行 Base64 编码，与群晖 Video Station 期望格式一致；
- 修复字段长度恰好为 128 字节时 varint 编码写出非法字节，导致整个文件后续字段错位的问题；
- 修复图片压缩函数资源泄漏问题；
- 修复可变默认参数等代码隐患。

**新增**

- 支持多目录扫描（`directory` 可为字符串或列表）；
- 支持 `max_workers`（并发线程数）、`compress_image` / `compress_kb`（图片压缩开关与目标大小）、`log_file`（日志文件路径）等配置；
- 配置文件自动合并默认值，缺失字段不再报错；
- 未安装 Pillow 时自动降级为不压缩，功能不受影响。

### v1.0 — 2025-05-01

初始版本功能：

- 将 .nfo 转换为 .vsmeta；
- 支持递归扫描目录；
- 自动识别影片名称与封面；
- 基础 CLI 参数支持；
- 支持群晖 Video Station 索引识别格式。
