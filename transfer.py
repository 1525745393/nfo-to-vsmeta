#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
nfo-to-vsmeta 轻量版（transfer.py 修复版）
将 Emby/Jellyfin/TinyMediaManager 等刮削生成的 .nfo 元数据，
转换为群晖 Video Station 专用 .vsmeta 元数据文件。

修复内容（相对原版）：
1. 路径不再硬编码，支持 config.json 配置（可用 --config 指定），命令行参数可覆盖；
2. 图片压缩函数修复资源泄漏问题，压缩逻辑更健壮；
3. 异常处理改用 logging 输出，信息更清晰；
4. 未识别文件仅打印提示，不影响主流程。

用法：
    python3 transfer.py [--config config.json] [--directory /path/to/videos]
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

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# 默认配置（与原版硬编码值一致）
DEFAULT_CONFIG = {
    "directory": "/volume1/video/Links/Movie/",  # 需要扫描的目录
    "poster_suffix": "-poster.jpg",              # 封面文件后缀（带番号）
    "fanart_suffix": "-fanart.jpg",              # 背景文件后缀（带番号）
    "video_extensions": [".mkv", ".mp4", ".rmvb", ".avi", ".wmv", ".ts"],
    "ignore_extensions": [".vsmeta", ".jpg", ".nfo", ".srt", ".ass", ".ssa", ".png", ".db"],
    "delete_vsmeta": False,                      # 是否先删除已有的 vsmeta 再重新转换
    "compress_kb": 200                           # 图片压缩目标大小（KB）
}


def load_config(config_file: str = "config.json") -> dict:
    """加载配置，合并默认值；配置文件不存在时使用默认配置"""
    config = dict(DEFAULT_CONFIG)
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
            config.update(user_config)
            logging.info(f"已加载配置文件: {config_file}")
        except (json.JSONDecodeError, IOError) as e:
            logging.warning(f"配置文件 {config_file} 读取失败，使用默认配置: {e}")
    else:
        logging.warning(f"配置文件 {config_file} 不存在，使用默认配置")
    return config


def check_all_files(directory: str, convert_list: list, poster: str, fanart: str, config: dict):
    """扫描目录并转换所有视频文件"""
    video_ext = [e.lower() for e in config['video_extensions']]
    ignore_ext = [e.lower() for e in config['ignore_extensions']]

    for root, _, files in os.walk(directory):
        if '@eaDir' in root:
            continue
        for filename in files:
            _, ext = os.path.splitext(filename)
            ext = ext.lower()

            if ext in video_ext:
                vsmeta_path = os.path.join(root, filename + '.vsmeta')
                base_name = os.path.splitext(filename)[0]
                poster_path = os.path.join(root, base_name + poster)
                fanart_path = os.path.join(root, base_name + fanart)

                if config.get('delete_vsmeta') and os.path.exists(vsmeta_path):
                    try:
                        os.remove(vsmeta_path)
                        logging.info(f"删除已有 vsmeta 文件: {vsmeta_path}")
                    except OSError as e:
                        logging.error(f"无法删除 vsmeta 文件 {vsmeta_path}: {e}")

                if not os.path.exists(vsmeta_path):
                    nfo_path = os.path.join(root, base_name + '.nfo')
                    convert_list.append(nfo_path)
                    if os.path.exists(nfo_path):
                        try:
                            action(nfo_path, vsmeta_path, poster_path, fanart_path, config)
                        except Exception as e:
                            logging.error(f"处理文件 {nfo_path} 时出错: {e}", exc_info=True)
            elif ext not in ignore_ext:
                # 用于检查缺少的视频文件格式后缀，需要忽略的文件格式后缀请在配置中自行增加
                logging.info(f"未识别文件: {os.path.join(root, filename)}")


def action(nfo_path: str, target_path: str, poster_path: str, fanart_path: str, config: dict):
    """解析 nfo 并写入 vsmeta"""
    doc = xmldom.parse(nfo_path)
    title = get_node(doc, 'title', '无标题')
    sorttitle = get_node(doc, 'sorttitle', title)
    tagline = get_node(doc, 'tagline', title)
    plot = get_node(doc, 'plot')
    year = get_node(doc, 'year', '1900')
    level = get_node(doc, 'mpaa', 'G')
    date = get_node(doc, 'premiered', '1900-01-01')
    rate = get_node(doc, 'rating', '0')
    genre = get_node_list(doc, 'genre')
    act = get_node_list(doc, 'actor', 'name')
    direc = get_node_list(doc, 'director')
    writ = get_node_list(doc, 'writer')

    buf, group = bytearray(), bytearray()

    write_byte(buf, 0x08)
    write_byte(buf, 0x01)

    write_byte(buf, 0x12)
    write_string(buf, title)

    write_byte(buf, 0x1A)
    write_string(buf, sorttitle)

    write_byte(buf, 0x22)
    write_string(buf, tagline)

    write_byte(buf, 0x28)
    write_int(buf, int(year))

    write_byte(buf, 0x32)
    write_string(buf, date)

    write_byte(buf, 0x38)
    write_byte(buf, 0x01)

    write_byte(buf, 0x42)
    write_string(buf, plot)

    write_byte(buf, 0x4A)
    write_string(buf, 'null')

    for a in act:
        write_byte(group, 0x0A)
        write_string(group, a)

    for d in direc:
        write_byte(group, 0x12)
        write_string(group, d)

    for g in genre:
        write_byte(group, 0x1A)
        write_string(group, g)

    for w in writ:
        write_byte(group, 0x22)
        write_string(group, w)

    write_byte(buf, 0x52)
    write_int(buf, len(group))
    buf.extend(group)
    group.clear()

    write_byte(buf, 0x5A)
    write_string(buf, level)

    try:
        rate_value = int(float(rate) * 10)
    except ValueError:
        rate_value = 0
    write_byte(buf, 0x60)
    write_int(buf, rate_value)

    if os.path.exists(poster_path):
        write_byte(buf, 0x8A)
        write_byte(buf, 0x01)
        poster_final = to_base64(poster_path, config)
        poster_md5 = to_md5(poster_final)
        write_string(buf, poster_final)
        write_byte(buf, 0x92)
        write_byte(buf, 0x01)
        write_string(buf, poster_md5)

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

    with open(target_path, 'wb') as op:
        op.write(buf)
    logging.info(f"成功创建 vsmeta 文件: {target_path}")


def write_byte(ba: bytearray, t: int):
    ba.extend(bytes([t]))


def write_string(ba: bytearray, string: str):
    byte = string.encode('utf-8')
    length = len(byte)
    write_int(ba, length)
    ba.extend(byte)


def write_int(ba: bytearray, length: int):
    while length >= 128:  # 注意边界：128 需编码为 [0x80, 0x01]，不能用单字节 0x80
        write_byte(ba, length % 128 + 128)
        length = length // 128
    write_byte(ba, length)


def get_node(doc: xmldom.Document, tag: str, default: str = '') -> str:
    nd = doc.getElementsByTagName(tag)
    if len(nd) < 1 or not nd[0].hasChildNodes():
        return default
    return nd[0].firstChild.nodeValue


def get_node_list(doc: xmldom.Document, tag: str, child_tag: str = '', default=None) -> list:
    if default is None:
        default = []
    nds = doc.getElementsByTagName(tag)
    if len(nds) < 1 or not nds[0].hasChildNodes():
        return default
    if len(child_tag) == 0:
        return [nd.firstChild.nodeValue for nd in nds]
    return [get_node(nd, child_tag, '') for nd in nds]


def to_base64(pic_path: str, config: dict) -> str:
    """图片转 Base64：可选压缩至目标大小以内，并按 76 字符换行（群晖期望格式）"""
    with open(pic_path, "rb") as p:
        pic_bytes = p.read()

    if HAS_PIL:
        try:
            pic_bytes = compress_pic(pic_bytes, int(config.get('compress_kb', 200)))
        except Exception as e:
            logging.warning(f"图片压缩失败，使用原图: {pic_path} ({e})")
    else:
        logging.warning("未安装 Pillow，跳过图片压缩（pip install Pillow 可启用）")

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


def to_md5(pic_final: str) -> str:
    return hashlib.md5(pic_final.encode("utf-8")).hexdigest()


def main():
    parser = argparse.ArgumentParser(description="nfo 转 vsmeta（轻量版）")
    parser.add_argument('--config', type=str, default="config.json", help="指定配置文件路径")
    parser.add_argument('--directory', type=str, default=None, help="指定扫描目录（覆盖配置文件）")
    parser.add_argument('--poster', type=str, default=None, help="封面文件后缀（覆盖配置文件）")
    parser.add_argument('--fanart', type=str, default=None, help="背景文件后缀（覆盖配置文件）")
    args = parser.parse_args()

    config = load_config(args.config)
    if args.directory:
        config['directory'] = args.directory
    if args.poster:
        config['poster_suffix'] = args.poster
    if args.fanart:
        config['fanart_suffix'] = args.fanart

    convert_list = []
    check_all_files(config['directory'], convert_list, config['poster_suffix'], config['fanart_suffix'], config)

    logging.info(f"扫描完成，共处理 {len(convert_list)} 个视频文件")
    # for item in convert_list:
    #     logging.info(item)


if __name__ == '__main__':
    main()
