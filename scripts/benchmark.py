#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/benchmark.py — 转换性能基准（Benchmark）

在临时目录生成合成 nfo（可选图片）并测量 nfo→vsmeta 转换吞吐，
用于跨版本/跨配置的性能对比。

用法：
    python3 scripts/benchmark.py                 # 默认 50 个文件、单线程、无图片
    python3 scripts/benchmark.py --files 200 --workers 4
    python3 scripts/benchmark.py --with-images   # 生成小图并压缩（需要 Pillow）

输出：文件数 / 总耗时 / 吞吐（文件/秒）/ 单文件平均耗时（毫秒）。
不同版本对比时建议固定 --files 与 --workers 参数。
"""

import argparse
import importlib.util
import os
import shutil
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_main_script():
    path = os.path.join(ROOT, "nfo-to-vsmeta.1.0.py")
    spec = importlib.util.spec_from_file_location("nfo2vsmeta_bench", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_nfo(path: str, index: int) -> None:
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?><movie>'
        f"<title>测试电影 {index:04d}</title>"
        f"<plot>这是用于基准测试的简介内容 {index}。</plot>"
        f"<year>2020</year><premiered>2020-01-01</premiered>"
        f"<rating>8.5</rating><mpaa>G</mpaa>"
        f"<genre>动作</genre><genre>科幻</genre>"
        f"<actor><name>演员A</name></actor><actor><name>演员B</name></actor>"
        f"<director>导演X</director><studio>工作室Y</studio></movie>"
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(xml)


def make_image(path: str, size: int = 800) -> None:
    try:
        from PIL import Image
    except ImportError:
        return
    img = Image.new("RGB", (size, int(size * 1.5)), (30, 60, 120))
    img.save(path, "JPEG", quality=85)


def main():
    parser = argparse.ArgumentParser(description="nfo→vsmeta 转换性能基准")
    parser.add_argument("--files", type=int, default=50, help="生成文件数（默认 50）")
    parser.add_argument("--workers", type=int, default=1, help="并发线程数（默认 1）")
    parser.add_argument(
        "--with-images", action="store_true", help="生成海报/背景图并压缩（需 Pillow）"
    )
    args = parser.parse_args()

    n2v = load_main_script()
    workdir = tempfile.mkdtemp(prefix="nfo2vsmeta-bench-")
    try:
        print(f"生成 {args.files} 个合成文件...")
        for i in range(args.files):
            make_nfo(os.path.join(workdir, f"m{i:04d}.nfo"), i)
            open(os.path.join(workdir, f"m{i:04d}.mkv"), "wb").write(b"x")
            if args.with_images:
                make_image(os.path.join(workdir, f"m{i:04d}-poster.jpg"))
                make_image(os.path.join(workdir, f"m{i:04d}-fanart.jpg"))

        cfg = {
            "directory": workdir,
            "poster_suffix": "-poster.jpg",
            "fanart_suffix": "-fanart.jpg",
            "video_extensions": [".mkv"],
            "ignore_extensions": [],
            "delete_vsmeta": True,
            "max_workers": args.workers,
            "compress_image": args.with_images,
            "compress_kb": 200,
        }

        print("预热 1 轮...")
        n2v.process_files(dict(cfg), verify=False)
        # 清理生成的 vsmeta，重新计时
        for fn in os.listdir(workdir):
            if fn.endswith(".vsmeta"):
                os.remove(os.path.join(workdir, fn))

        start = time.perf_counter()
        stats = n2v.process_files(cfg, verify=False)
        elapsed = time.perf_counter() - start

        per_file = elapsed / max(stats["success"], 1) * 1000
        print("\n=== 基准结果 ===")
        print(
            f"文件数      : {stats['total']}（成功 {stats['success']}，失败 {stats['failed']}，跳过 {stats['skipped']}）"
        )
        print(f"总耗时      : {elapsed:.3f} 秒")
        print(f"吞吐        : {stats['success'] / elapsed:.1f} 文件/秒")
        print(f"单文件平均  : {per_file:.1f} 毫秒")
        if args.with_images:
            print("（含图片压缩）")
        return 0
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
