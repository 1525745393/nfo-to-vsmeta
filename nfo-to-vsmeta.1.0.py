#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
nfo-to-vsmeta v1.0（修复版）
将 Emby/Jellyfin/TinyMediaManager 等刮削生成的 .nfo 元数据，
转换为群晖 Video Station 专用 .vsmeta 元数据文件，实现刮削数据复用。

修复内容（相对原版）：
1. 修复原版只写入标题、海报、背景图，丢失简介/年份/日期/分级/评分/类型/演员/导演/编剧等字段的问题；
2. 修复背景图（fanart）二进制结构写错的问题（原版用 0x0A 前缀，群晖无法正确识别）；
3. 海报/背景图编码改为 76 字符换行的 Base64（与群晖 Video Station 期望格式一致）；
4. 支持图片压缩（已安装 Pillow 时自动压缩至 200KB 以内，否则原样编码）；
5. 支持多目录扫描（config.json 的 directory 可为字符串或列表）；
6. 修复可变默认参数、日志文件路径等细节问题。

用法：
    python3 nfo-to-vsmeta.1.0.py [--config config.json]
"""

import os
import io
import json
import time
import logging
import hashlib
import argparse
import base64
import xml.dom.minidom as xmldom
from concurrent.futures import ThreadPoolExecutor

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# 示例配置内容
DEFAULT_CONFIG = {
    "directory": "./videos",                # 需要扫描的目录（也可填列表，如 ["./videos", "./movies"]）
    "poster_suffix": "-poster.jpg",         # 海报文件的后缀
    "fanart_suffix": "-fanart.jpg",         # 背景文件的后缀
    "video_extensions": [".mkv", ".mp4", ".rmvb", ".avi", ".wmv", ".ts"],  # 支持的视频文件扩展名
    "delete_vsmeta": False,                 # 是否先删除已有的 vsmeta 文件再重新转换
    "max_workers": 4,                       # 多线程并发数
    "compress_image": True,                 # 是否压缩图片（需要安装 Pillow，未安装时自动跳过压缩）
    "compress_kb": 200,                     # 图片压缩目标大小（KB）
    "log_file": "process.log"               # 日志文件路径
}


def setup_logging(log_file: str = "process.log"):
    """配置日志输出到文件与终端"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )


def create_default_config(config_file: str):
    """创建默认配置文件"""
    try:
        with open(config_file, 'w', encoding='utf-8') as file:
            json.dump(DEFAULT_CONFIG, file, ensure_ascii=False, indent=4)
        logging.info(f"默认配置文件已创建: {config_file}")
    except IOError as e:
        logging.error(f"无法创建默认配置文件: {e}")


def load_config(config_file: str = "config.json") -> dict:
    """从 config.json 文件加载配置"""
    if not os.path.exists(config_file):
        logging.warning(f"配置文件 {config_file} 不存在，创建默认配置文件...")
        create_default_config(config_file)
    with open(config_file, 'r', encoding='utf-8') as file:
        config = json.load(file)
    # 合并默认值，避免配置项缺失时报错
    for key, value in DEFAULT_CONFIG.items():
        config.setdefault(key, value)
    return config


def get_video_files(directory: str, video_extensions: list) -> iter:
    """获取指定目录及其子目录中符合视频扩展名的文件"""
    for root, _, files in os.walk(directory, topdown=True):
        if '@eaDir' in root:
            continue
        for filename in files:
            _, ext = os.path.splitext(filename)
            if ext.lower() in video_extensions:
                yield root, filename


def process_files_multithreaded(config: dict) -> list:
    """多线程处理文件"""
    directories = config['directory']
    if isinstance(directories, str):
        directories = [directories]
    max_workers = int(config.get('max_workers', 4))

    tasks = []
    for directory in directories:
        if not os.path.isdir(directory):
            logging.warning(f"扫描目录不存在，已跳过: {directory}")
            continue
        tasks.extend(list(get_video_files(directory, config['video_extensions'])))

    if not tasks:
        logging.info("没有找到需要处理的视频文件")
        return []

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(process_single_file, root, filename, config)
            for root, filename in tasks
        ]
        for future in futures:
            result = future.result()
            if result:
                results.append(result)
    return results


def process_single_file(root: str, filename: str, config: dict) -> str:
    """处理单个文件"""
    poster_suffix = config['poster_suffix']
    fanart_suffix = config['fanart_suffix']
    delete_vsmeta = config.get('delete_vsmeta', False)

    vsmeta_path = os.path.join(root, filename + '.vsmeta')
    base_name = os.path.splitext(filename)[0]
    poster_path = os.path.join(root, base_name + poster_suffix)
    fanart_path = os.path.join(root, base_name + fanart_suffix)

    # 删除已有的 vsmeta 文件
    if delete_vsmeta and os.path.exists(vsmeta_path):
        try:
            logging.info(f"删除已有 vsmeta 文件: {vsmeta_path}")
            os.remove(vsmeta_path)
        except OSError as e:
            logging.error(f"无法删除 vsmeta 文件 {vsmeta_path}: {e}")

    # 检查 nfo 文件并处理
    nfo_path = os.path.join(root, base_name + '.nfo')
    if os.path.exists(nfo_path) and not os.path.exists(vsmeta_path):
        try:
            create_vsmeta(nfo_path, vsmeta_path, poster_path, fanart_path, config)
            return nfo_path
        except Exception as e:
            logging.error(f"处理文件 {nfo_path} 时出错: {e}", exc_info=True)
    return ""


def create_vsmeta(nfo_path: str, target_path: str, poster_path: str, fanart_path: str, config: dict):
    """根据 nfo 文件创建 vsmeta 文件"""
    doc = xmldom.parse(nfo_path)
    metadata = extract_metadata(doc)
    buf = build_vsmeta_content(metadata, poster_path, fanart_path, config)

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
        'sorttitle': get_node(doc, 'sorttitle', ''),
        'tagline': get_node(doc, 'tagline', ''),
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


def build_vsmeta_content(metadata: dict, poster_path: str, fanart_path: str, config: dict) -> bytearray:
    """根据元数据构建 vsmeta 文件内容（与群晖 Video Station 可识别的二进制格式一致）"""
    buf, group = bytearray(), bytearray()

    # 文件头
    write_byte(buf, 0x08)
    write_byte(buf, 0x01)

    # 标题
    title = metadata['title']
    sorttitle = metadata['sorttitle'] or title
    tagline = metadata['tagline'] or title
    write_byte(buf, 0x12)
    write_string(buf, title)

    write_byte(buf, 0x1A)
    write_string(buf, sorttitle)

    write_byte(buf, 0x22)
    write_string(buf, tagline)

    # 年份
    write_byte(buf, 0x28)
    write_int(buf, int(metadata['year']))

    # 上映/首播日期
    write_byte(buf, 0x32)
    write_string(buf, metadata['date'])

    # 锁定标志
    write_byte(buf, 0x38)
    write_byte(buf, 0x01)

    # 简介
    write_byte(buf, 0x42)
    write_string(buf, metadata['plot'])

    # 剧集元数据 JSON（保留 null）
    write_byte(buf, 0x4A)
    write_string(buf, 'null')

    # 人员分组（演员/导演/类型/编剧）
    for a in metadata['actors']:
        write_byte(group, 0x0A)
        write_string(group, a)

    for d in metadata['directors']:
        write_byte(group, 0x12)
        write_string(group, d)

    for g in metadata['genre']:
        write_byte(group, 0x1A)
        write_string(group, g)

    for w in metadata['writers']:
        write_byte(group, 0x22)
        write_string(group, w)

    write_byte(buf, 0x52)
    write_int(buf, len(group))
    buf.extend(group)
    group.clear()

    # 分级
    write_byte(buf, 0x5A)
    write_string(buf, metadata['level'])

    # 评分（0-10 放大 10 倍存储）
    try:
        rate_value = int(float(metadata['rate']) * 10)
    except ValueError:
        rate_value = 0
    write_byte(buf, 0x60)
    write_int(buf, rate_value)

    # 海报（0x8A + 0x01 标志 + base64 数据 + 0x92 + 0x01 标志 + md5）
    if os.path.exists(poster_path):
        write_byte(buf, 0x8A)
        write_byte(buf, 0x01)
        poster_final = to_base64(poster_path, config)
        poster_md5 = to_md5(poster_final)
        write_string(buf, poster_final)
        write_byte(buf, 0x92)
        write_byte(buf, 0x01)
        write_string(buf, poster_md5)

    # 背景图（0xAA + 0x01 标志 + 嵌套分组 {0x0A 数据, 0x12 md5, 0x18 时间戳}）
    if os.path.exists(fanart_path):
        write_byte(buf, 0xAA)
        write_byte(buf, 0x01)
        fanart_final = to_base64(fanart_path, config)
        fanart_md5 = to_md5(fanart_final)
        write_byte(group, 0x0A)
        write_string(group, fanart_final)
        write_byte(group, 0x12)
        write_string(group, fanart_md5)
        write_byte(group, 0x18)
        write_int(group, int(time.time()))
        write_int(buf, len(group))
        buf.extend(group)
        group.clear()

    return buf


def write_byte(ba: bytearray, t: int):
    ba.extend(bytes([t]))


def write_string(ba: bytearray, string: str):
    byte = string.encode('utf-8')
    length = len(byte)
    write_int(ba, length)
    ba.extend(byte)


def write_int(ba: bytearray, length: int):
    while length > 128:
        write_byte(ba, length % 128 + 128)
        length = length // 128
    write_byte(ba, length)


def get_node(doc: xmldom.Document, tag: str, default: str = '') -> str:
    nd = doc.getElementsByTagName(tag)
    if len(nd) > 0 and nd[0].hasChildNodes():
        return nd[0].firstChild.nodeValue
    return default


def get_node_list(doc: xmldom.Document, tag: str, child_tag: str = '', default=None) -> list:
    if default is None:
        default = []
    nds = doc.getElementsByTagName(tag)
    if len(child_tag) == 0:
        return [nd.firstChild.nodeValue for nd in nds if nd.hasChildNodes()]
    return [get_node(nd, child_tag, '') for nd in nds]


def to_base64(pic_path: str, config: dict) -> str:
    """图片转 Base64，可选压缩至 200KB 以内，并按 76 字符换行（群晖期望格式）"""
    with open(pic_path, "rb") as p:
        pic_bytes = p.read()

    if config.get('compress_image', True) and HAS_PIL:
        try:
            pic_bytes = compress_pic(pic_bytes, int(config.get('compress_kb', 200)))
        except Exception as e:
            logging.warning(f"图片压缩失败，使用原图: {pic_path} ({e})")

    pic_base64 = base64.b64encode(pic_bytes).decode('utf-8')
    splitleng = 76
    pic_list = [pic_base64[i:i + splitleng] for i in range(0, len(pic_base64), splitleng)]
    return '\n'.join(pic_list)


def compress_pic(bytes_data: bytes, kb: int = 200, k: float = 0.8) -> bytes:
    """将图片压缩到目标大小以内（KB），返回压缩后的图片字节"""
    if len(bytes_data) // 1024 <= kb:
        return bytes_data

    img = Image.open(io.BytesIO(bytes_data))
    try:
        while len(bytes_data) // 1024 > kb:
            x, y = img.size
            img = img.resize((max(1, int(x * k)), max(1, int(y * k))), Image.LANCZOS)
            out = io.BytesIO()
            img.save(out, 'jpeg')
            bytes_data = out.getvalue()
        return bytes_data
    finally:
        img.close()


def to_md5(content: str) -> str:
    return hashlib.md5(content.encode("utf-8")).hexdigest()


def main():
    parser = argparse.ArgumentParser(description="处理 nfo 文件生成 vsmeta 文件")
    parser.add_argument('--config', type=str, default="config.json", help="指定配置文件路径")
    parser.add_argument('--log-file', type=str, default=None, help="指定日志文件路径（覆盖配置文件）")
    args = parser.parse_args()

    try:
        config = load_config(args.config)
        setup_logging(args.log_file or config.get('log_file', 'process.log'))
        logging.info("加载配置成功")
        results = process_files_multithreaded(config)
        logging.info(f"本次处理完成：共 {len(results)} 个文件成功生成 .vsmeta")
    except Exception as e:
        logging.error(f"程序运行出错: {e}", exc_info=True)


if __name__ == '__main__':
    main()
