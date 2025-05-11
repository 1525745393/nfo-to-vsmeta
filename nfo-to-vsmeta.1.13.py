#!/usr/bin/env python

import os
import json
import logging
import time
import hashlib
import xml.etree.ElementTree as ET
import base64
from multiprocessing import Pool
import argparse
from pathlib import Path
from logging.handlers import RotatingFileHandler
from functools import lru_cache

# 日志配置
LOG_FILE = f"process-{time.strftime('%Y%m%d%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [Process-%(process)d] - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=5)，  # 每5MB轮转，保留5个备份
        logging.StreamHandler()
    ]
)

# 示例配置内容
DEFAULT_CONFIG = {
    "directory": "./videos",               # 需要扫描的目录
    "poster_suffix": "-poster.jpg",        # 海报文件的后缀
    "fanart_suffix": "-fanart.jpg",        # 背景文件的后缀
    "video_extensions": [".mp4", ".mkv"], # 支持的视频文件扩展名
    "delete_vsmeta": False,                # 是否删除已有的 vsmeta 文件
    "max_workers": 4                       # 最大线程数
}

def create_default_config(config_file: str):
    """创建默认配置文件"""
    try:
        with open(config_file, 'w', encoding='utf-8') as file:
            json.dump(DEFAULT_CONFIG, file, ensure_ascii=False, indent=4)
        logging.info(f"默认配置文件已创建: {config_file}")
    except IOError as e:
        logging.error(f"无法创建默认配置文件: {e}")

def validate_config(config: dict) -> bool:
    """
    验证配置文件内容是否完整
    Args:
        config (dict): 配置字典
    Returns:
        bool: 验证是否成功
    """
    required_keys = ["directory", "poster_suffix", "fanart_suffix", "video_extensions", "delete_vsmeta"]
    for key in required_keys:
        if key not in config:
            logging.error(f"配置文件缺少必要的字段: {key}")
            return False
    return True

def load_config(config_file: str = "config.json") -> dict:
    """从配置文件加载并验证配置"""
    if not os.path.exists(config_file):
        logging.warning(f"配置文件 {config_file} 不存在，创建默认配置文件...")
        create_default_config(config_file)

    try:
        with open(config_file, 'r', encoding='utf-8') as file:
            config = json.load(file)
    except json.JSONDecodeError as e:
        logging.error(f"配置文件 {config_file} 格式错误: {e}")
        raise

    if not validate_config(config):
        raise ValueError("配置文件验证失败")
    
    return config

@lru_cache(maxsize=None)
def is_valid_video_file(ext: str, video_extensions: list[str]) -> bool:
    """检查是否为有效的视频文件扩展名"""
    return ext.lower() in video_extensions

def get_video_files(directory: str, video_extensions: list[str]) -> iter[tuple[str, str]]:
    """使用 pathlib 简化文件遍历"""
    directory_path = Path(directory)
    for file_path in directory_path.rglob('*'):
        if file_path.suffix.lower() in video_extensions:
            yield file_path.parent, file_path.name

def delete_file(file_path: Path):
    """删除文件并处理异常"""
    try:
        file_path.unlink()
        logging.info(f"删除文件: {file_path}")
    except PermissionError as e:
        logging.error(f"权限错误，无法删除文件 {file_path}: {e}")
    except OSError as e:
        logging.error(f"无法删除文件 {file_path}: {e}")

def process_files_multiprocessing(config: dict) -> list[str]:
    """多进程处理文件"""
    with Pool(processes=min(config.get('max_workers', os.cpu_count() + 4), 32)) as pool:
        results = pool.starmap(
            process_single_file,
            [(root, filename, config) for root, filename in get_video_files(config['directory'], config['video_extensions'])]
        )
    return results

def process_single_file(root: str, filename: str, config: dict) -> str:
    """处理单个文件"""
    poster_suffix = config['poster_suffix']
    fanart_suffix = config['fanart_suffix']
    delete_vsmeta = config.get('delete_vsmeta', False)

    root_path = Path(root)
    vsmeta_path = root_path / f"{filename}.vsmeta"
    poster_path = root_path / f"{Path(filename).stem}{poster_suffix}"
    fanart_path = root_path / f"{Path(filename).stem}{fanart_suffix}"

    if delete_vsmeta and vsmeta_path.exists():
        delete_file(vsmeta_path)

    nfo_path = root_path / f"{Path(filename).stem}.nfo"
    if nfo_path.exists() and not vsmeta_path.exists():
        try:
            create_vsmeta(nfo_path, vsmeta_path, poster_path, fanart_path)
            return str(nfo_path)
        except Exception as e:
            logging.error(f"处理文件 {nfo_path} 时出错: {e}")
    
    return ""

def create_vsmeta(nfo_path: Path, target_path: Path, poster_path: Path, fanart_path: Path):
    """根据 nfo 文件创建 vsmeta 文件"""
    try:
        metadata = extract_metadata(nfo_path)
        buf = build_vsmeta_content(metadata, poster_path, fanart_path)

        with open(target_path, 'wb') as op:
            op.write(buf)
        logging.info(f"成功创建 vsmeta 文件: {target_path}")
    except Exception as e:
        logging.error(f"写入 vsmeta 文件 {target_path} 时出错: {e}")

def extract_metadata(nfo_path: Path) -> dict:
    """
    使用 ElementTree 提取元数据
    Args:
        nfo_path (Path): NFO 文件路径
    Returns:
        dict: 提取的元数据
    """
    tree = ET.parse(nfo_path)
    root = tree.getroot()
    return {
        'title': root.findtext('title', '无标题'),
        'sorttitle': root.findtext('sorttitle', '无标题'),
        'plot': root.findtext('plot'),
        'year': root.findtext('year', '1900'),
    }

def main():
    parser = argparse.ArgumentParser(description="处理 nfo 文件生成 vsmeta 文件")
    parser.add_argument('--config', type=str, default="config.json", help="指定配置文件路径")
    args = parser.parse_args()

    try:
        config = load_config(args.config)
        logging.info("加载配置成功")
        process_files_multiprocessing(config)
    except Exception as e:
        logging.error(f"程序运行出错: {e}")

if __name__ == '__main__':
    main()
