#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
nfo-to-vsmeta（统一版）
将 Emby/Jellyfin/TinyMediaManager 等刮削生成的 .nfo 元数据，
转换为群晖 Video Station 专用 .vsmeta 元数据文件，实现刮削数据复用。

版本号由同目录 version.py 提供（唯一权威源），运行 --version 查看。

用法：
    python3 nfo-to-vsmeta.1.0.py [--config config.json] [--dry-run] [--verify] [--log-file LOG] [--version]
"""

import os
import io
import re
import json
import time
import logging
import hashlib
import argparse
import base64
import xml.dom.minidom as xmldom
from concurrent.futures import ThreadPoolExecutor
from logging.handlers import RotatingFileHandler
from typing import Union

try:
    from version import __version__
except ImportError:
    __version__ = "unknown"

try:
    from PIL import Image

    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# 示例配置内容
DEFAULT_CONFIG = {
    "directory": "./videos",  # 需要扫描的目录（也可填列表，如 ["./videos", "./movies"]）
    "poster_suffix": "-poster.jpg",  # 海报文件的后缀
    "fanart_suffix": "-fanart.jpg",  # 背景文件的后缀
    "video_extensions": [".mkv", ".mp4", ".rmvb", ".avi", ".wmv", ".ts"],  # 支持的视频文件扩展名
    "ignore_extensions": [
        ".vsmeta",
        ".jpg",
        ".jpeg",
        ".nfo",
        ".srt",
        ".ass",
        ".ssa",
        ".png",
        ".db",
        ".log",
    ],  # 扫描时忽略的文件扩展名
    "delete_vsmeta": False,  # 是否先删除已有的 vsmeta 文件再重新转换
    "max_workers": 4,  # 多线程并发数
    "compress_image": True,  # 是否压缩图片（需要安装 Pillow，未安装时自动跳过压缩）
    "compress_kb": 200,  # 图片压缩目标大小（KB）
    "log_file": "process.log",  # 日志文件路径
    "log_max_bytes": 1048576,  # 日志文件最大字节数（默认 1MB），超过后轮转
    "log_backup_count": 3,  # 日志轮转保留的备份份数
    "studio_as_tagline": False,  # vsmeta 无独立 studio 字段，True 时把制片厂合并进 tagline
    "parse_episode_from_trailing_digits": False,  # 是否从结尾2位数字解析集号（如 Show.02）；JAV 番号类命名请保持关闭
}

# vsmeta 二进制 tag 定义（参考 VideoStation VsMeta File Format）
TAG_HEADER = 0x08
TAG_SHOW_TITLE = 0x12
TAG_SHOW_TITLE2 = 0x1A
TAG_EPISODE_TITLE = 0x22
TAG_YEAR = 0x28
TAG_EPISODE_RELEASE_DATE = 0x32
TAG_EPISODE_LOCKED = 0x38
TAG_CHAPTER_SUMMARY = 0x42
TAG_EPISODE_META_JSON = 0x4A
TAG_GROUP1 = 0x52
TAG_CLASSIFICATION = 0x5A
TAG_RATING = 0x60
TAG_EPISODE_THUMB_DATA = 0x8A
TAG_EPISODE_THUMB_MD5 = 0x92
TAG_GROUP2 = 0x9A  # 剧集分组：season/episode/tvshow 信息
TAG_FANART = 0xAA  # 本脚本使用的背景图分组
TAG1_CAST = 0x0A
TAG1_DIRECTOR = 0x12
TAG1_GENRE = 0x1A
TAG1_WRITER = 0x22
TAG2_SEASON = 0x08
TAG2_EPISODE = 0x10
TAG3_BACKDROP_DATA = 0x0A
TAG3_BACKDROP_MD5 = 0x12
TAG3_TIMESTAMP = 0x18

INT_TAGS = (TAG_HEADER, TAG_YEAR, TAG_EPISODE_LOCKED, TAG_RATING, TAG3_TIMESTAMP)
GROUP_TAGS = (TAG_GROUP1, TAG_GROUP2, TAG_FANART)


def setup_logging(log_file: str = "process.log", max_bytes: int = 1048576, backup_count: int = 3):
    """配置日志输出到文件（轮转）与终端"""
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    file_handler = RotatingFileHandler(
        log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    root.addHandler(file_handler)
    root.addHandler(stream_handler)


def create_default_config(config_file: str):
    """创建默认配置文件"""
    try:
        with open(config_file, "w", encoding="utf-8") as file:
            json.dump(DEFAULT_CONFIG, file, ensure_ascii=False, indent=4)
        logging.info(f"默认配置文件已创建: {config_file}")
    except IOError as e:
        logging.error(f"无法创建默认配置文件: {e}")


def load_config(config_file: str = "config.json") -> dict:
    """从 config.json 文件加载配置"""
    if not os.path.exists(config_file):
        logging.warning(f"配置文件 {config_file} 不存在，创建默认配置文件...")
        create_default_config(config_file)
    with open(config_file, "r", encoding="utf-8") as file:
        config = json.load(file)
    # 合并默认值，避免配置项缺失时报错
    for key, value in DEFAULT_CONFIG.items():
        config.setdefault(key, value)
    return config


def scan_directory(directory: str, config: dict) -> list:
    """递归扫描目录，返回 (root, filename) 视频任务列表；未识别文件仅提示"""
    video_ext = [e.lower() for e in config["video_extensions"]]
    ignore_ext = [e.lower() for e in config.get("ignore_extensions", [])]
    tasks = []
    for root, _, files in os.walk(directory):
        if "@eaDir" in root:
            continue
        for filename in files:
            _, ext = os.path.splitext(filename)
            ext = ext.lower()
            if ext in video_ext:
                tasks.append((root, filename))
            elif ext not in ignore_ext:
                logging.info(f"未识别文件: {os.path.join(root, filename)}")
    return tasks


def process_files(config: dict, dry_run: bool = False, verify: bool = False) -> dict:
    """多线程处理文件，返回统计信息"""
    directories = config["directory"]
    if isinstance(directories, str):
        directories = [directories]
    max_workers = int(config.get("max_workers", 4))

    tasks = []
    for directory in directories:
        if not os.path.isdir(directory):
            logging.warning(f"扫描目录不存在，已跳过: {directory}")
            continue
        tasks.extend(scan_directory(directory, config))

    if not tasks:
        logging.info("没有找到需要处理的视频文件")
        return {"total": 0, "success": 0, "failed": 0, "skipped": 0}

    results = []
    if dry_run or max_workers <= 1:
        for root, filename in tasks:
            results.append(process_single_file(root, filename, config, dry_run, verify))
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(process_single_file, root, filename, config, dry_run, verify)
                for root, filename in tasks
            ]
            for future in futures:
                results.append(future.result())

    stats = {"total": len(results), "success": 0, "failed": 0, "skipped": 0}
    for status in results:
        stats[status] = stats.get(status, 0) + 1
    return stats


def process_single_file(
    root: str, filename: str, config: dict, dry_run: bool = False, verify: bool = False
) -> str:
    """处理单个文件，返回状态：success / failed / skipped"""
    poster_suffix = config["poster_suffix"]
    fanart_suffix = config["fanart_suffix"]
    delete_vsmeta = config.get("delete_vsmeta", False)

    vsmeta_path = os.path.join(root, filename + ".vsmeta")
    base_name = os.path.splitext(filename)[0]
    poster_path = os.path.join(root, base_name + poster_suffix)
    fanart_path = os.path.join(root, base_name + fanart_suffix)
    nfo_path = os.path.join(root, base_name + ".nfo")

    # 删除已有的 vsmeta 文件
    if delete_vsmeta and os.path.exists(vsmeta_path):
        try:
            logging.info(f"删除已有 vsmeta 文件: {vsmeta_path}")
            os.remove(vsmeta_path)
        except OSError as e:
            logging.error(f"无法删除 vsmeta 文件 {vsmeta_path}: {e}")

    if os.path.exists(vsmeta_path):
        return "skipped"

    if not os.path.exists(nfo_path):
        logging.warning(f"缺少 .nfo 文件，已跳过: {nfo_path}")
        return "skipped"

    try:
        if dry_run:
            logging.info(f"[dry-run] 将转换: {nfo_path} -> {vsmeta_path}")
            return "success"

        metadata = parse_nfo(nfo_path)
        season, episode = parse_season_episode(
            filename, config.get("parse_episode_from_trailing_digits", False)
        )
        buf = build_vsmeta_content(metadata, poster_path, fanart_path, config, season, episode)

        with open(vsmeta_path, "wb") as op:
            op.write(buf)
        logging.info(f"成功创建 vsmeta 文件: {vsmeta_path}")

        if verify:
            ok, issues = verify_vsmeta(bytes(buf), metadata, season, episode)
            if ok:
                logging.info(f"自检通过: {vsmeta_path}")
            else:
                logging.error(f"自检失败: {vsmeta_path} -> {'; '.join(issues)}")
        return "success"
    except Exception as e:
        logging.error(f"处理文件 {nfo_path} 时出错: {e}", exc_info=True)
        return "failed"


def parse_nfo(nfo_path: str) -> dict:
    """解析 nfo 文件（自动处理编码与 CDATA），返回元数据字典"""
    with open(nfo_path, "rb") as f:
        raw = f.read()
    # 编码探测：UTF-8（含 BOM）→ GB18030 → Latin-1（兜底，保证不崩溃）
    text = None
    for encoding in ("utf-8-sig", "gb18030", "latin-1"):
        try:
            text = raw.decode(encoding)
            break
        except (UnicodeDecodeError, LookupError):
            continue
    if text is None:
        text = raw.decode("utf-8", errors="replace")

    try:
        doc = xmldom.parseString(text)
    except Exception as e:
        raise ValueError(f"XML 解析失败: {e}")

    return {
        "title": get_node(doc, "title", "无标题"),
        "sorttitle": get_node(doc, "sorttitle", ""),
        "tagline": get_node(doc, "tagline", ""),
        "plot": get_node(doc, "plot"),
        "year": get_node(doc, "year", "1900"),
        "level": get_node(doc, "mpaa", "G"),
        "date": get_node(doc, "premiered", "1900-01-01"),
        "rate": get_node(doc, "rating", "0"),
        "genre": get_node_list(doc, "genre"),
        "actors": get_node_list(doc, "actor", "name"),
        "directors": get_node_list(doc, "director"),
        "writers": get_node_list(doc, "writer"),
        "studio": get_node_list(doc, "studio"),
    }


def parse_season_episode(filename: str, enable_trailing_digits: bool = False):
    """从文件名解析剧集季/集号，支持 S01E02 / 1x2 / 结尾2位数字（需 enable_trailing_digits）；
    无法识别返回 (None, None)"""
    base = os.path.splitext(os.path.basename(filename))[0]

    m = re.search(r"[Ss](\d{1,2})[Ee](\d{1,3})", base)
    if m:
        return int(m.group(1)), int(m.group(2))

    m = re.search(r"(\d{1,2})[xX](\d{1,3})", base)
    if m:
        return int(m.group(1)), int(m.group(2))

    # 结尾 2 位数字（如 xxx.02 / xxx - 12），视为第 1 季的集号。
    # 默认关闭：JAV 番号（如 ABP-998、STARS-061）与少数电影名会误判为剧集，
    # 仅当配置 parse_episode_from_trailing_digits=true 时启用。
    if enable_trailing_digits:
        m = re.search(r"[ _\-.]\d{2}$", base)
        if m:
            return 1, int(m.group(0).strip(" _-. "))

    return None, None


def build_vsmeta_content(
    metadata: dict, poster_path: str, fanart_path: str, config: dict, season=None, episode=None
) -> bytearray:
    """根据元数据构建 vsmeta 文件内容（与群晖 Video Station 可识别的二进制格式一致）"""
    buf, group = bytearray(), bytearray()

    # 文件头
    write_byte(buf, TAG_HEADER)
    write_byte(buf, 0x01)

    # 标题
    title = metadata["title"]
    sorttitle = metadata["sorttitle"] or title
    tagline = metadata["tagline"] or title
    if config.get("studio_as_tagline") and metadata.get("studio"):
        tagline = (tagline + " · " + " / ".join(metadata["studio"])).strip(" ·")

    write_byte(buf, TAG_SHOW_TITLE)
    write_string(buf, title)

    write_byte(buf, TAG_SHOW_TITLE2)
    write_string(buf, sorttitle)

    write_byte(buf, TAG_EPISODE_TITLE)
    write_string(buf, tagline)

    # 年份
    write_byte(buf, TAG_YEAR)
    write_int(buf, int(metadata["year"]))

    # 上映/首播日期
    write_byte(buf, TAG_EPISODE_RELEASE_DATE)
    write_string(buf, metadata["date"])

    # 锁定标志
    write_byte(buf, TAG_EPISODE_LOCKED)
    write_byte(buf, 0x01)

    # 简介
    write_byte(buf, TAG_CHAPTER_SUMMARY)
    write_string(buf, metadata["plot"])

    # 剧集元数据 JSON（保留 null）
    write_byte(buf, TAG_EPISODE_META_JSON)
    write_string(buf, "null")

    # 人员分组（演员/导演/类型/编剧）
    for a in metadata["actors"]:
        write_byte(group, TAG1_CAST)
        write_string(group, a)

    for d in metadata["directors"]:
        write_byte(group, TAG1_DIRECTOR)
        write_string(group, d)

    for g in metadata["genre"]:
        write_byte(group, TAG1_GENRE)
        write_string(group, g)

    for w in metadata["writers"]:
        write_byte(group, TAG1_WRITER)
        write_string(group, w)

    write_byte(buf, TAG_GROUP1)
    write_int(buf, len(group))
    buf.extend(group)
    group.clear()

    # 分级
    write_byte(buf, TAG_CLASSIFICATION)
    write_string(buf, metadata["level"])

    # 评分（0-10 放大 10 倍存储）
    try:
        rate_value = int(float(metadata["rate"]) * 10)
    except ValueError:
        rate_value = 0
    write_byte(buf, TAG_RATING)
    write_int(buf, rate_value)

    # 海报（0x8A 0x01 + base64 数据 + 0x92 0x01 + md5）
    if os.path.exists(poster_path):
        write_byte(buf, TAG_EPISODE_THUMB_DATA)
        write_byte(buf, 0x01)
        poster_final = to_base64(poster_path, config)
        poster_md5 = to_md5(poster_final)
        write_string(buf, poster_final)
        write_byte(buf, TAG_EPISODE_THUMB_MD5)
        write_byte(buf, 0x01)
        write_string(buf, poster_md5)

    # 背景图（0xAA 0x01 + 嵌套分组 {0x0A 数据, 0x12 md5, 0x18 时间戳}）
    if os.path.exists(fanart_path):
        write_byte(buf, TAG_FANART)
        write_byte(buf, 0x01)
        fanart_final = to_base64(fanart_path, config)
        fanart_md5 = to_md5(fanart_final)
        write_byte(group, TAG3_BACKDROP_DATA)
        write_string(group, fanart_final)
        write_byte(group, TAG3_BACKDROP_MD5)
        write_string(group, fanart_md5)
        write_byte(group, TAG3_TIMESTAMP)
        write_int(group, int(time.time()))
        write_int(buf, len(group))
        buf.extend(group)
        group.clear()

    # 剧集季/集号（GROUP2，仅当从文件名解析到季集时写入）
    if season is not None and episode is not None:
        write_byte(buf, TAG_GROUP2)
        write_byte(buf, 0x01)  # 0x9A 的 varint 延续字节（同 0x8A/0x92/0xAA 写法）
        g2 = bytearray()
        write_byte(g2, TAG2_SEASON)
        write_int(g2, season)
        write_byte(g2, TAG2_EPISODE)
        write_int(g2, episode)
        write_int(buf, len(g2))
        buf.extend(g2)

    return buf


def verify_vsmeta(data: bytes, metadata: dict, season=None, episode=None):
    """回读解析 vsmeta，校验关键字段，返回 (ok, issues)"""
    issues = []
    try:
        fields = parse_vsmeta_fields(data)
    except Exception as e:
        return False, [f"vsmeta 解析失败: {e}"]

    tag_values = {tag: vals for tag, vals in fields.items()}

    # 标题必须存在且非空
    if not tag_values.get(TAG_SHOW_TITLE):
        issues.append("缺少标题字段")

    # 年份校验
    if metadata.get("year") and metadata["year"] != "1900":
        try:
            expected = int(metadata["year"])
        except (ValueError, TypeError):
            issues.append(f"年份格式异常: {metadata['year']!r}")
        else:
            if TAG_YEAR not in tag_values or tag_values[TAG_YEAR][0] != expected:
                issues.append(f"年份不符: 期望 {expected}")

    # 评分校验
    if metadata.get("rate"):
        try:
            expected = int(float(metadata["rate"]) * 10)
            if TAG_RATING not in tag_values or tag_values[TAG_RATING][0] != expected:
                issues.append(f"评分不符: 期望 {expected}")
        except ValueError:
            pass

    # 季/集校验
    if season is not None and episode is not None:
        g2_values = tag_values.get(TAG_GROUP2)
        if not g2_values:
            issues.append("缺少剧集季/集分组")
        else:
            g2_fields = parse_group2(g2_values[0])
            if g2_fields.get(TAG2_SEASON) != season:
                issues.append(f"季号不符: 期望 {season}")
            if g2_fields.get(TAG2_EPISODE) != episode:
                issues.append(f"集号不符: 期望 {episode}")

    return (len(issues) == 0), issues


def parse_group2(data: bytes) -> dict:
    """解析 GROUP2 子字段（season/episode，均为 varint 整数值）"""
    fields = {}
    pos = 0
    while pos < len(data):
        tag, pos = read_varint(data, pos)
        val, pos = read_varint(data, pos)
        fields[tag] = val
    return fields


def parse_vsmeta_fields(data):
    """解析 vsmeta 二进制，返回 {tag: [values]}；分组字段的值为原始子串 bytes"""
    fields = {}
    pos = 0
    while pos < len(data):
        tag, pos = read_varint(data, pos)
        if tag in INT_TAGS:
            val, pos = read_varint(data, pos)
            fields.setdefault(tag, []).append(val)
        elif tag in GROUP_TAGS:
            length, pos = read_varint(data, pos)
            sub = data[pos : pos + length]
            pos += length
            fields.setdefault(tag, []).append(sub)
        else:
            length, pos = read_varint(data, pos)
            pos += length
            fields.setdefault(tag, []).append(length)
    return fields


def write_byte(ba: bytearray, t: int):
    ba.extend(bytes([t]))


def write_string(ba: bytearray, string: str):
    byte = string.encode("utf-8")
    length = len(byte)
    write_int(ba, length)
    ba.extend(byte)


def write_int(ba: bytearray, length: int):
    while length >= 128:  # 注意边界：128 需编码为 [0x80, 0x01]，不能用单字节 0x80
        write_byte(ba, length % 128 + 128)
        length = length // 128
    write_byte(ba, length)


def read_varint(data: bytes, pos: int):
    """读取 varint，返回 (值, 新位置)"""
    result = 0
    shift = 0
    while True:
        if pos >= len(data):
            raise ValueError("varint 越界")
        b = data[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        if b < 0x80:
            return result, pos
        shift += 7


def get_node(doc: Union[xmldom.Document, xmldom.Element], tag: str, default: str = "") -> str:
    """提取节点文本，拼接所有文本/CDATA 子节点（兼容混合内容）"""
    nd = doc.getElementsByTagName(tag)
    if len(nd) == 0:
        return default
    node = nd[0]
    parts = []
    for child in node.childNodes:
        if child.nodeType in (xmldom.Node.TEXT_NODE, xmldom.Node.CDATA_SECTION_NODE):
            parts.append(child.nodeValue)
    text = "".join(parts).strip()
    return text if text else default


def get_node_list(
    doc: Union[xmldom.Document, xmldom.Element], tag: str, child_tag: str = "", default=None
) -> list:
    if default is None:
        default = []
    nds = doc.getElementsByTagName(tag)
    if len(nds) == 0:
        return default
    if len(child_tag) == 0:
        result = []
        for nd in nds:
            parts = []
            for child in nd.childNodes:
                if child.nodeType in (xmldom.Node.TEXT_NODE, xmldom.Node.CDATA_SECTION_NODE):
                    parts.append(child.nodeValue)
            text = "".join(parts).strip()
            if text:
                result.append(text)
        return result
    return [get_node(nd, child_tag, "") for nd in nds if get_node(nd, child_tag, "")]


def to_base64(pic_path: str, config: dict) -> str:
    """图片转 Base64，可选压缩至目标大小以内，并按 76 字符换行（群晖期望格式）"""
    with open(pic_path, "rb") as p:
        pic_bytes = p.read()

    if config.get("compress_image", True) and HAS_PIL:
        try:
            pic_bytes = compress_pic(pic_bytes, int(config.get("compress_kb", 200)))
        except Exception as e:
            logging.warning(f"图片压缩失败，使用原图: {pic_path} ({e})")

    pic_base64 = base64.b64encode(pic_bytes).decode("utf-8")
    splitleng = 76
    pic_list = [pic_base64[i : i + splitleng] for i in range(0, len(pic_base64), splitleng)]
    return "\n".join(pic_list)


def compress_pic(bytes_data: bytes, kb: int = 200, k: float = 0.8) -> bytes:
    """将图片压缩到目标大小以内（KB），返回压缩后的图片字节"""
    if len(bytes_data) // 1024 <= kb:
        return bytes_data

    img: "Image.Image" = Image.open(io.BytesIO(bytes_data))
    try:
        # Resampling 枚举自 Pillow 9.1 引入，旧版本用模块级常量 LANCZOS
        resample = getattr(Image, "Resampling", Image).LANCZOS
        while len(bytes_data) // 1024 > kb:
            x, y = img.size
            img = img.resize((max(1, int(x * k)), max(1, int(y * k))), resample)
            out = io.BytesIO()
            img.save(out, "jpeg")
            bytes_data = out.getvalue()
        return bytes_data
    finally:
        img.close()


def to_md5(content: str) -> str:
    return hashlib.md5(content.encode("utf-8")).hexdigest()


def format_update_message(latest: str, current: str) -> str:
    """根据最新版本号生成升级提示；无需提示时返回空字符串"""
    latest = latest.lstrip("v").strip()
    if not latest or current in ("unknown", latest):
        return ""
    return (
        f"发现新版本 v{latest}（当前 v{current}）。"
        f"查看 https://github.com/1525745393/nfo-to-vsmeta/releases"
    )


def check_update():
    """查询 GitHub Releases 最新版本并提示（联网失败静默，不影响正常使用）"""
    import urllib.request

    try:
        req = urllib.request.Request(
            "https://api.github.com/repos/1525745393/nfo-to-vsmeta/releases/latest",
            headers={"User-Agent": "nfo-to-vsmeta", "Accept": "application/vnd.github+json"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.load(resp)
        msg = format_update_message(data.get("tag_name", ""), __version__)
        if msg:
            logging.info(msg)
        elif __version__ != "unknown":
            logging.info(f"已是最新版本 v{__version__}")
    except Exception as e:
        logging.info(f"检查更新失败（忽略）: {e}")


def main():
    parser = argparse.ArgumentParser(description="nfo 转 vsmeta（统一版）")
    parser.add_argument("--version", action="version", version=f"nfo-to-vsmeta {__version__}")
    parser.add_argument("--config", type=str, default="config.json", help="指定配置文件路径")
    parser.add_argument(
        "--log-file", type=str, default=None, help="指定日志文件路径（覆盖配置文件）"
    )
    parser.add_argument("--directory", type=str, default=None, help="指定扫描目录（覆盖配置文件）")
    parser.add_argument("--poster", type=str, default=None, help="海报文件后缀（覆盖配置文件）")
    parser.add_argument("--fanart", type=str, default=None, help="背景文件后缀（覆盖配置文件）")
    parser.add_argument(
        "--dry-run", action="store_true", help="干跑模式：只打印将转换的文件，不写盘"
    )
    parser.add_argument("--verify", action="store_true", help="转换后回读自检 vsmeta 字段完整性")
    parser.add_argument(
        "--check-update",
        action="store_true",
        help="检查 GitHub 是否有新版本（联网失败静默，不影响转换）",
    )
    args = parser.parse_args()

    try:
        config = load_config(args.config)
        setup_logging(
            args.log_file or config.get("log_file", "process.log"),
            int(config.get("log_max_bytes", 1048576)),
            int(config.get("log_backup_count", 3)),
        )
        if args.check_update:
            check_update()
        if args.directory:
            config["directory"] = args.directory
        if args.poster:
            config["poster_suffix"] = args.poster
        if args.fanart:
            config["fanart_suffix"] = args.fanart

        logging.info("加载配置成功")
        if args.dry_run:
            logging.info("=== 干跑模式：不会写入任何文件 ===")
        stats = process_files(config, dry_run=args.dry_run, verify=args.verify)
        action = "将转换" if args.dry_run else "成功生成"
        logging.info(
            f"本次处理完成：共 {stats['total']} 个文件，{action} {stats.get('success', 0)} 个，"
            f"失败 {stats.get('failed', 0)} 个，跳过 {stats.get('skipped', 0)} 个"
        )
    except Exception as e:
        logging.error(f"程序运行出错: {e}", exc_info=True)


if __name__ == "__main__":
    main()
