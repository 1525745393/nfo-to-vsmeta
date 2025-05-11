#!/usr/bin/env python

import os
import json
import logging
import time
import hashlib
import xml.dom.minidom as xmldom
import base64
from concurrent.futures import ThreadPoolExecutor
import argparse
from pathlib import Path
from functools import lru_cache

# 日志配置
LOG_FILE = f"process-{time.strftime('%Y%m%d%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [Thread-%(thread)d] - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
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
    """验证配置文件内容"""
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
    """获取指定目录及其子目录中符合视频扩展名的文件"""
    for root, _, files in os.walk(directory, topdown=True):
        if '@eaDir' in root:  # 忽略无用目录
            continue
        for filename in files:
            _, ext = os.path.splitext(filename)
            if is_valid_video_file(ext, video_extensions):
                yield root, filename

def process_files_multithreaded(config: dict) -> list[str]:
    """多线程处理文件"""
    max_workers = config.get('max_workers', os.cpu_count())
    errors = []
    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_single_file, root, filename, config): (root, filename)
            for root, filename in get_video_files(config['directory'], config['video_extensions'])
        }

        for future in futures:
            try:
                result = future.result()
                if result:
                    results.append(result)
            except Exception as e:
                root, filename = futures[future]
                errors.append((root, filename, str(e)))

    if errors:
        logging.error(f"以下文件处理失败: {errors}")
    
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
        try:
            logging.info(f"删除已有 vsmeta 文件: {vsmeta_path}")
            vsmeta_path.unlink()
        except PermissionError as e:
            logging.error(f"权限错误，无法删除文件 {vsmeta_path}: {e}")
        except OSError as e:
            logging.error(f"无法删除 vsmeta 文件 {vsmeta_path}: {e}")

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
        doc = xmldom.parse(str(nfo_path))
        metadata = extract_metadata(doc)
        buf = build_vsmeta_content(metadata, poster_path, fanart_path)

        with open(target_path, 'wb') as op:
            op.write(buf)
        logging.info(f"成功创建 vsmeta 文件: {target_path}")
    except Exception as e:
        logging.error(f"写入 vsmeta 文件 {target_path} 时出错: {e}")

def extract_metadata(doc: xmldom.Document) -> dict:
    """从 nfo 文件中提取元数据"""
    return {
        'title': get_node(doc, 'title', '无标题'),
        'sorttitle': get_node(doc, 'sorttitle', '无标题'),
        'tagline': get_node(doc, 'tagline', '无标题'),
        'plot': get_node(doc, 'plot'),
        'year': get_node(doc, 'year', '1900'),
        'level': get_node(doc, 'mpaa', 'G'),
        'date': get_node(doc, 'premiered', '1900-01-01'),
        'rate': get_node(doc, 'rating', '0'),
        'genre': get_node_list(doc, 'genre'),
        'actors': get_node_list(doc, 'actor', 'name'),
        'directors': get_node_list(doc, 'director'),
        'writers': get_node_list(doc, 'writer'),
    }

# 省略中间重复函数...

def main():
    parser = argparse.ArgumentParser(description="处理 nfo 文件生成 vsmeta 文件")
    parser.add_argument('--config', type=str, default="config.json", help="指定配置文件路径")
    args = parser.parse_args()

    try:
        config = load_config(args.config)
        logging.info("加载配置成功")
        process_files_multithreaded(config)
    except Exception as e:
        logging.error(f"程序运行出错: {e}")

if __name__ == '__main__':
    main()
