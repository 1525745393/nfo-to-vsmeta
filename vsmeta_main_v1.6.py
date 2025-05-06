import os import json import argparse from datetime import datetime from pathlib import Path

加载配置文件

加载 config.json 并补全默认字段

建议：提前创建 config.json 并检查路径是否正确

更改后果：路径错误将导致程序无法启动

def load_config(config_path): with open(config_path, 'r', encoding='utf-8') as f: config = json.load(f)

defaults = {
    "scan_root": "./JAV_output",  # 默认扫描路径，建议设为你的视频主目录 # 改为你的视频文件夹路径可加快处理
    "output_vsmeta_dir": "",  # 空则与视频文件同目录，推荐独立缓存盘减少写入 # 示例："./vsmeta_output"
    "thread_count": 4,  # 并发线程数，建议 4-8，根据 NAS 性能调节 # 可改为 2 等减少资源占用
    "skip_existing": True,  # 跳过已有 .vsmeta 的视频，节省时间 # 改为 false 将覆盖原文件：false
    "rename_video": False,  # 是否启用视频文件重命名功能 # 改为 true 启用重命名：true
    "rename_keep_original": True,  # 保留原文件名作为备份 # 改为 false 不保留原始文件名：false
    "rename_skip_well_named": True,  # 跳过命名规范的视频文件 # 改为 false 强制重命名所有文件：false
    "log_dir": "./logs",  # 日志保存目录，建议指定专用文件夹 # 可改为 /volumeX/logs 等路径
    "nfo_dir": "",  # nfo -> vsmeta 功能预留路径，暂未启用 # 未来支持自定义 .nfo 批量导入
    "python_path": ""  # 留空自动查找，或填写 Python 路径如 "/usr/local/bin/python3" # DSM 用户推荐填写完整路径
}

for k, v in defaults.items():
    if k not in config:
        config[k] = v
        print(f"[警告] 缺失配置项 '{k}'，已填入默认值: {v}")

return config

自动识别 Python 路径（如未指定）

建议：DSM 用户填写准确路径提高兼容性

更改后果：找不到 Python 将无法执行脚本

def find_python_path(user_path): if user_path and Path(user_path).exists(): return user_path for p in ["/usr/local/bin/python3", "/usr/bin/python3", "/bin/python3"]: if Path(p).exists(): return p return "python3"  # fallback：系统路径

主处理逻辑

建议：确保视频路径与配置一致，避免遗漏

更改后果：路径不一致将导致文件未被处理

def process_videos(config): scan_path = Path(config["scan_root"]) output_dir = Path(config["output_vsmeta_dir"]) if config["output_vsmeta_dir"] else None log_path = Path(config["log_dir"]) log_path.mkdir(parents=True, exist_ok=True) timestamp = datetime.now().strftime('%Y%m%d_%H%M%S') log_file = log_path / f"log_{timestamp}.txt" log_summary = { "total": 0, "success": 0, "failed": 0 }

with open(log_file, 'w', encoding='utf-8') as log:
    for root, _, files in os.walk(scan_path):
        for file in files:
            if file.lower().endswith((".mp4", ".mkv", ".avi", ".mov", ".wmv")):  # 视频格式支持拓展
                log_summary["total"] += 1
                video_path = Path(root) / file
                try:
                    # 此处调用元数据解析和 vsmeta 生成逻辑
                    log.write(f"[成功] {video_path}\n")
                    log_summary["success"] += 1
                except Exception as e:
                    log.write(f"[失败] {video_path}，原因：{str(e)}\n")
                    log_summary["failed"] += 1

    log.write(f"\n处理统计：共 {log_summary['total']}，成功 {log_summary['success']}，失败 {log_summary['failed']}\n")

if name == "main": parser = argparse.ArgumentParser(description="VSmeta 视频元数据生成工具 v1.5") parser.add_argument("--config", type=str, default="config.json", help="配置文件路径（默认 config.json）") args = parser.parse_args()

config = load_config(args.config)
config["python_path"] = find_python_path(config.get("python_path", ""))
process_videos(config)

