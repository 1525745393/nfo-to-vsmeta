#!/usr/bin/env python

import os
import json
import logging
import time
import io
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


def check_all_files(config, convert_list):
    """
    遍历目录，处理所有符合条件的文件
    """
    directory = config['directory']
    poster_suffix = config['poster_suffix']
    fanart_suffix = config['fanart_suffix']
    video_extensions = config['video_extensions']
    delete_vsmeta = config.get('delete_vsmeta', False)  # 默认为 False

    for root, _, files in os.walk(directory):
        for filename in files:
            if '@eaDir' in root:
                continue
            _, ext = os.path.splitext(filename)
            if ext.lower() in video_extensions:  # 检查是否为支持的视频格式
                vsmeta_path = os.path.join(root, filename + '.vsmeta')

                # 如果启用，删除已有的 .vsmeta 文件
                if delete_vsmeta and os.path.exists(vsmeta_path):
                    logging.info(f"删除已有的 .vsmeta 文件: {vsmeta_path}")
                    os.remove(vsmeta_path)

                # 构造封面和背景图路径
                poster_path = os.path.join(root, os.path.splitext(filename)[0] + poster_suffix)
                fanart_path = os.path.join(root, os.path.splitext(filename)[0] + fanart_suffix)

                if not os.path.exists(vsmeta_path):  # 如果 .vsmeta 文件不存在
                    nfo_path = os.path.join(root, os.path.splitext(filename)[0] + '.nfo')
                    convert_list.append(nfo_path)
                    if os.path.exists(nfo_path):
                        try:
                            process_file(nfo_path, vsmeta_path, poster_path, fanart_path)
                        except Exception as e:
                            logging.error(f"处理文件 {nfo_path} 时出错: {e}")
            elif ext.lower() not in ['.vsmeta', '.jpg', '.nfo', '.srt', '.ass', '.ssa', '.png', '.db']:
                logging.warning(f"未识别的文件类型: {os.path.join(root, filename)}")


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
        if os.path.exists(poster_path):
            write_image_metadata(buf, poster_path, 0x8A)

        # 处理背景图
        if os.path.exists(fanart_path):
            write_image_metadata(buf, fanart_path, 0xAA)

        with open(target_path, 'wb') as op:
            op.write(buf)
        logging.info(f"成功生成 vsmeta 文件: {target_path}")
    except Exception as e:
        logging.error(f"生成 vsmeta 文件时出错: {e}")


def write_image_metadata(buf, image_path, prefix):
    """写入图片的元数据"""
    write_byte(buf, prefix)
    write_byte(buf, 0x01)

    image_data = to_base64(image_path)
    image_md5 = to_md5(image_data)

    write_string(buf, image_data)
    write_byte(buf, prefix + 0x08)
    write_byte(buf, 0x01)
    write_string(buf, image_md5)


def write_byte(ba, t):
    """写入单字节"""
    ba.extend(bytes([int(str(t))]))


def write_string(ba, string):
    """写入字符串"""
    byte = string.encode('utf-8')
    length = len(byte)
    write_int(ba, length)
    ba.extend(byte)


def write_int(ba, length):
    """写入整数"""
    while length > 128:
        write_byte(ba, length % 128 + 128)
        length = length // 128
    write_byte(ba, length)


def get_node(doc, tag, default=''):
    """从 XML 节点获取值"""
    nd = doc.getElementsByTagName(tag)
    if len(nd) < 1 or not nd[0].hasChildNodes():
        return default
    return nd[0].firstChild.nodeValue


def get_node_list(doc, tag, child_tag='', default=[]):
    """从 XML 节点获取列表值"""
    nds = doc.getElementsByTagName(tag)
    if len(nds) < 1 or not nds[0].hasChildNodes():
        return default
    if len(child_tag) == 0:
        return [nd.firstChild.nodeValue for nd in nds]
    else:
        return [get_node(nd, child_tag, '') for nd in nds]


def to_base64(pic_path):
    """将图片转为 Base64"""
    with open(pic_path, "rb") as p:
        pic_bytes = p.read()
    return base64.b64encode(pic_bytes).decode('utf-8')


def to_md5(pic_final):
    """计算 MD5 值"""
    return hashlib.md5(pic_final.encode("utf-8")).hexdigest()


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
