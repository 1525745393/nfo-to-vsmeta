#!/usr/bin/env python

import os
import json
import logging
import time
from pathlib import Path
from PIL import Image
import hashlib
import xml.dom.minidom as xmldom
import base64

# 日志配置
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def load_config(config_file="config.json"):
    """
    从配置文件加载参数
    """
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"配置文件 {config_file} 不存在，请创建配置文件并设置参数。")
    with open(config_file, 'r', encoding='utf-8') as file:
        return json.load(file)


def normalize_path(path):
    """
    规范化路径，确保路径中不存在问题字符
    """
    return Path(os.path.normpath(path))


def check_special_characters(path):
    """
    检查路径中是否存在特殊字符
    """
    special_chars = ['#', ' ', '[', ']', '&', '!', '@']
    for char in special_chars:
        if char in str(path):
            logging.warning(f"路径包含特殊字符: {char} in {path}")
            return True
    return False


def check_all_files(config, convert_list):
    """
    遍历目录，处理所有符合条件的文件
    """
    directory = normalize_path(config['directory'])
    poster_suffix = config['poster_suffix']
    fanart_suffix = config['fanart_suffix']
    video_extensions = config['video_extensions']
    delete_vsmeta = config.get('delete_vsmeta', False)  # 默认为 False

    for root, _, files in os.walk(directory):
        for filename in files:
            # 跳过特殊系统目录
            if '@eaDir' in root:
                continue

            root = normalize_path(root)
            file_path = root / filename

            # 检查路径中的特殊字符
            if check_special_characters(file_path):
                logging.info(f"检测到特殊字符，可能需要处理路径: {file_path}")

            _, ext = os.path.splitext(filename)
            if ext.lower() in video_extensions:  # 检查是否为支持的视频格式
                vsmeta_path = file_path.with_suffix(file_path.suffix + '.vsmeta')

                # 如果启用，删除已有的 .vsmeta 文件
                if delete_vsmeta and vsmeta_path.exists():
                    logging.info(f"删除已有的 .vsmeta 文件: {vsmeta_path}")
                    os.remove(vsmeta_path)

                # 构造封面和背景图路径
                poster_path = file_path.with_name(file_path.stem + poster_suffix)
                fanart_path = file_path.with_name(file_path.stem + fanart_suffix)

                if not vsmeta_path.exists():  # 如果 .vsmeta 文件不存在
                    nfo_path = file_path.with_name(file_path.stem + '.nfo')
                    convert_list.append(nfo_path)
                    if nfo_path.exists():
                        try:
                            process_file(nfo_path, vsmeta_path, poster_path, fanart_path)
                        except Exception as e:
                            logging.error(f"处理文件 {nfo_path} 时出错: {e}")
            elif ext.lower() not in ['.vsmeta', '.jpg', '.nfo', '.srt', '.ass', '.ssa', '.png', '.db']:
                logging.warning(f"未识别的文件类型: {file_path}")


def process_file(nfo_path, target_path, poster_path, fanart_path):
    """
    根据 nfo 文件生成 vsmeta 文件
    """
    try:
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
        actors = get_node_list(doc, 'actor', 'name')
        directors = get_node_list(doc, 'director')
        writers = get_node_list(doc, 'writer')

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

        for actor in actors:
            write_byte(group, 0x0A)
            write_string(group, actor)

        for director in directors:
            write_byte(group, 0x12)
            write_string(group, director)

        for g in genre:
            write_byte(group, 0x1A)
            write_string(group, g)

        for writer in writers:
            write_byte(group, 0x22)
            write_string(group, writer)

        write_byte(buf, 0x52)
        write_int(buf, len(group))
        buf.extend(group)
        group.clear()

        write_byte(buf, 0x5A)
        write_string(buf, level)

        write_byte(buf, 0x60)
        write_int(buf, int(float(rate) * 10))

        # 处理封面图
        if poster_path.exists():
            write_image_metadata(buf, poster_path, 0x8A)

        # 处理背景图
        if fanart_path.exists():
            write_image_metadata(buf, fanart_path, 0xAA)

        with open(target_path, 'wb') as op:
            op.write(buf)
        logging.info(f"成功生成 vsmeta 文件: {target_path}")
    except Exception as e:
        logging.error(f"生成 vsmeta 文件时出错: {e}")


# 其他辅助函数保持不变...

def main():
    try:
        config = load_config()
        logging.info("加载配置成功")
        convert_list = []
        check_all_files(config, convert_list)
        logging.info(f"处理完成，共处理 {len(convert_list)} 个文件")
        print(f"处理完成，共处理 {len(convert_list)} 个文件")
    except Exception as e:
        logging.error(f"程序运行出错: {e}")


if __name__ == '__main__':
    main()
