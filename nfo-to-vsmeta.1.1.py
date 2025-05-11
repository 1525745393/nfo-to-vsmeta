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

# 日志配置
LOG_FILE = f"process-{time.strftime('%Y%m%d%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
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

    with open(config_file, 'r', encoding='utf-8') as file:
        config = json.load(file)
    
    if not validate_config(config):
        raise ValueError("配置文件验证失败")
    
    return config

def get_video_files(directory: str, video_extensions: list[str]) -> iter:
    """获取指定目录及其子目录中符合视频扩展名的文件"""
    for root, _, files in os.walk(directory, topdown=True):
        if '@eaDir' in root:
            continue
        for filename in files:
            _, ext = os.path.splitext(filename)
            if ext.lower() in video_extensions:
                yield root, filename

def process_files_multithreaded(config: dict) -> list[str]:
    """多线程处理文件"""
    max_workers = config.get('max_workers', os.cpu_count())
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(process_single_file, root, filename, config)
            for root, filename in get_video_files(config['directory'], config['video_extensions'])
        ]
    return [future.result() for future in futures if future.result()]

def process_single_file(root: str, filename: str, config: dict) -> str:
    """处理单个文件"""
    poster_suffix = config['poster_suffix']
    fanart_suffix = config['fanart_suffix']
    delete_vsmeta = config.get('delete_vsmeta', False)

    vsmeta_path = os.path.join(root, filename + '.vsmeta')
    poster_path = os.path.join(root, os.path.splitext(filename)[0] + poster_suffix)
    fanart_path = os.path.join(root, os.path.splitext(filename)[0] + fanart_suffix)

    # 删除已有的 vsmeta 文件
    if delete_vsmeta and os.path.exists(vsmeta_path):
        try:
            logging.info(f"删除已有 vsmeta 文件: {vsmeta_path}")
            os.remove(vsmeta_path)
        except PermissionError as e:
            logging.error(f"权限错误，无法删除文件 {vsmeta_path}: {e}")
        except OSError as e:
            logging.error(f"无法删除 vsmeta 文件 {vsmeta_path}: {e}")

    # 检查 nfo 文件并处理
    nfo_path = os.path.join(root, os.path.splitext(filename)[0] + '.nfo')
    if os.path.exists(nfo_path) and not os.path.exists(vsmeta_path):
        try:
            create_vsmeta(nfo_path, vsmeta_path, poster_path, fanart_path)
            return nfo_path
        except FileNotFoundError as e:
            logging.error(f"文件未找到: {e}")
        except PermissionError as e:
            logging.error(f"权限错误: {e}")
        except Exception as e:
            logging.error(f"处理文件 {nfo_path} 时出现未知错误: {e}")
    return ""

def create_vsmeta(nfo_path: str, target_path: str, poster_path: str, fanart_path: str):
    """根据 nfo 文件创建 vsmeta 文件"""
    doc = xmldom.parse(nfo_path)
    metadata = extract_metadata(doc)
    buf = build_vsmeta_content(metadata, poster_path, fanart_path)

    try:
        with open(target_path, 'wb') as op:
            op.write(buf)
        logging.info(f"成功创建 vsmeta 文件: {target_path}")
    except IOError as e:
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

def build_vsmeta_content(metadata: dict, poster_path: str, fanart_path: str) -> bytearray:
    """根据元数据构建 vsmeta 文件内容"""
    buf, group = bytearray(), bytearray()
    write_byte(buf, 0x08)
    write_byte(buf, 0x01)

    write_byte(buf, 0x12)
    write_string(buf, metadata['title'])

    if os.path.exists(poster_path):
        process_image(poster_path, buf, group, 0x8A)

    if os.path.exists(fanart_path):
        process_image(fanart_path, buf, group, 0x0A)

    return buf

def process_image(image_path: str, buf: bytearray, group: bytearray, byte_prefix: int):
    """处理图片文件并写入到缓冲区"""
    try:
        image_final = to_base64(image_path)
        image_md5 = to_md5(image_final)
        write_byte(buf, byte_prefix)
        write_string(buf, image_final)
        write_byte(buf, byte_prefix + 0x08)
        write_string(buf, image_md5)
    except Exception as e:
        logging.error(f"处理图片文件 {image_path} 时出错: {e}", exc_info=True)

def write_byte(ba: bytearray, t: int):
    """将一个字节写入字节数组"""
    ba.extend(bytes([int(str(t))]))

def write_string(ba: bytearray, string: str):
    """将字符串写入字节数组"""
    byte = string.encode('utf-8')
    length = len(byte)
    write_int(ba, length)
    ba.extend(byte)

def write_int(ba: bytearray, length: int):
    """以变长整数格式写入字节数组"""
    while length > 128:
        write_byte(ba, length % 128 + 128)
        length = length // 128
    write_byte(ba, length)

def get_node(doc: xmldom.Document, tag: str, default: str = '') -> str:
    """获取 XML 节点值"""
    nd = doc.getElementsByTagName(tag)
    return nd[0].firstChild.nodeValue if len(nd) > 0 and nd[0].hasChildNodes() else default

def get_node_list(doc: xmldom.Document, tag: str, child_tag: str = '', default: list = []) -> list:
    """获取 XML 节点列表"""
    nds = doc.getElementsByTagName(tag)
    if len(child_tag) == 0:
        return [nd.firstChild.nodeValue for nd in nds if nd.hasChildNodes()]
    return [get_node(nd, child_tag, '') for nd in nds]

def to_base64(pic_path: str) -> str:
    """将图片编码为 Base64"""
    with open(pic_path, "rb") as p:
        return base64.b64encode(p.read()).decode('utf-8')

def to_md5(content: str) -> str:
    """计算 MD5 哈希值"""
    return hashlib.md5(content.encode("utf-8")).hexdigest()

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
