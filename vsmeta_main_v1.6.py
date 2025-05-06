import os
import json
import argparse
from datetime import datetime
from pathlib import Path
import jsonschema
from jsonschema import validate

# 加载配置文件
def load_config(config_path):
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    # 默认值填充 + 注释建议 + 更改后果
    defaults = {
        "scan_root": "./JAV_output",  # 扫描目录 # 建议设为视频根目录 # 错误路径将导致无法扫描文件
        "output_vsmeta_dir": "",  # vsmeta 输出目录 # 设为空表示与视频文件同目录 # 指定路径建议用于缓存盘
        "thread_count": 4,  # 线程数 # 建议 4～8，根据群晖性能决定 # 过高会导致资源占满
        "skip_existing": True,  # 是否跳过已存在的 vsmeta 文件 # false 表示总是覆盖原文件
        "rename_video": False,  # 启用视频重命名功能 # 改为 true 可自动整理文件名
        "rename_keep_original": True,  # 是否保留原文件名副本 # false 表示不保留备份，建议谨慎
        "rename_skip_well_named": True,  # 跳过已命名规范的视频文件 # false 表示强制重命名所有文件
        "log_dir": "./logs",  # 日志目录 # 建议为独立文件夹，便于清理
        "nfo_dir": "",  # nfo 输入目录 # 预留功能，未来支持 nfo -> vsmeta 转换
        "python_path": ""  # 指定 Python 路径 # 建议留空自动检测，也可设为 "/usr/local/bin/python3"
    }

    for k, v in defaults.items():
        if k not in config:
            config[k] = v
            print(f"[警告] 缺失配置项 '{k}'，已填入默认值: {v}")

    return config

# 校验配置文件合法性
def validate_config_schema(config, schema_path="config_schema.json"):
    try:
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema = json.load(f)
        validate(instance=config, schema=schema)
        return True
    except jsonschema.exceptions.ValidationError as ve:
        print(f"[配置校验失败] 字段错误: {ve.message}")
        print(f"出错路径: {' -> '.join(map(str, ve.absolute_path))}")
        return False
    except Exception as e:
        print(f"[配置校验失败] 其他错误: {e}")
        return False

# 自动识别 Python 路径
def find_python_path(user_path):
    if user_path and Path(user_path).exists():
        return user_path
    for p in ["/usr/local/bin/python3", "/usr/bin/python3", "/bin/python3"]:
        if Path(p).exists():
            return p
    return "python3"  # fallback：使用系统默认路径

# 主处理逻辑
def process_videos(config):
    scan_path = Path(config["scan_root"])
    output_dir = Path(config["output_vsmeta_dir"]) if config["output_vsmeta_dir"] else None
    log_path = Path(config["log_dir"])
    log_path.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = log_path / f"log_{timestamp}.txt"
    log_summary = {
        "total": 0,
        "success": 0,
        "failed": 0
    }

    with open(log_file, 'w', encoding='utf-8') as log:
        for root, _, files in os.walk(scan_path):
            for file in files:
                if file.endswith((".mp4", ".mkv", ".avi", ".mov", ".wmv")):  # 支持更多视频格式
                    log_summary["total"] += 1
                    video_path = Path(root) / file
                    try:
                        # 元数据处理和 vsmeta 生成逻辑（此处留空）
                        log.write(f"[成功] {video_path}\n")
                        log_summary["success"] += 1
                    except Exception as e:
                        log.write(f"[失败] {video_path}，原因：{str(e)}\n")
                        log_summary["failed"] += 1

        log.write(f"\n处理统计：共 {log_summary['total']}，成功 {log_summary['success']}，失败 {log_summary['failed']}\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VSmeta 视频元数据生成工具 v1.6")
    parser.add_argument("--config", type=str, default="config.json", help="配置文件路径（默认 config.json）")
    args = parser.parse_args()

    config = load_config(args.config)
    if not validate_config_schema(config):
        print("[终止运行] 配置文件未通过校验，请修改后重试。")
        exit(1)

    config["python_path"] = find_python_path(config.get("python_path", ""))
    process_videos(config)