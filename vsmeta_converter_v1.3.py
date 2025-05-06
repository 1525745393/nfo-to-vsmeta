import os
import argparse
import datetime
from pathlib import Path

def log(msg, file=None):
    print(msg)
    if file:
        with open(file, 'a', encoding='utf-8') as f:
            f.write(msg + '\n')

def process_nfo(nfo_path, vsmeta_path, overwrite, logf):
    if not nfo_path.exists():
        log(f"[跳过] 找不到 .nfo 文件：{nfo_path}", logf)
        return False, "缺少 .nfo 文件"

    if vsmeta_path.exists() and not overwrite:
        log(f"[跳过] 已存在 .vsmeta，未启用覆盖：{vsmeta_path}", logf)
        return False, "已存在 .vsmeta"

    try:
        with open(nfo_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 示例转换（简化处理）
        title = "未知标题"
        for line in content.splitlines():
            if '<title>' in line:
                title = line.strip().replace('<title>', '').replace('</title>', '')
                break

        vsmeta = f'{{"title": "{title}"}}'

        vsmeta_path.write_text(vsmeta, encoding='utf-8')
        log(f"[成功] 生成：{vsmeta_path}", logf)
        return True, ""
    except Exception as e:
        log(f"[失败] {vsmeta_path}，错误：{e}", logf)
        return False, str(e)

def scan_video_dirs(root_dirs, recursive=True):
    video_exts = {'.mp4', '.mkv', '.avi'}
    for root in root_dirs:
        root_path = Path(root).expanduser().resolve()
        if not root_path.exists():
            yield root_path, None
            continue

        for dirpath, _, filenames in os.walk(root_path):
            for file in filenames:
                if Path(file).suffix.lower() in video_exts:
                    yield Path(dirpath) / file, root_path
            if not recursive:
                break

def load_root_paths(args):
    paths = set(args.root or [])
    if args.root_file:
        with open(args.root_file, 'r', encoding='utf-8') as f:
            for line in f:
                path = line.strip()
                if path:
                    paths.add(path)
    return list(paths)

def main():
    parser = argparse.ArgumentParser(description="将 Video Station 的 .nfo 转为 .vsmeta 文件")
    parser.add_argument('--root', action='append', help='扫描的主目录，可重复使用')
    parser.add_argument('--root-file', help='包含多个根目录路径的文件')
    parser.add_argument('--overwrite-vsmeta', action='store_true', default=False, help='是否覆盖已有的 .vsmeta')
    parser.add_argument('--only-missing', action='store_true', help='只转换缺失 .vsmeta 的视频')
    parser.add_argument('--no-recursive', action='store_true', help='不递归子目录')
    parser.add_argument('--log-dir', default='logs', help='日志输出目录')
    args = parser.parse_args()

    root_dirs = load_root_paths(args)
    recursive = not args.no_recursive

    # 创建日志文件
    Path(args.log_dir).mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    log_path = Path(args.log_dir) / f'vsmeta_log_{timestamp}.txt'

    total = success = failed = 0
    fail_reasons = {}

    for video_path, base in scan_video_dirs(root_dirs, recursive):
        if base is None or not video_path.exists():
            log(f"[错误] 无效路径：{video_path}", log_path)
            continue

        nfo_path = video_path.with_suffix('.nfo')
        vsmeta_path = video_path.with_suffix('.vsmeta')

        if args.only_missing and vsmeta_path.exists():
            log(f"[跳过] 已存在 .vsmeta：{vsmeta_path}", log_path)
            continue

        total += 1
        ok, reason = process_nfo(nfo_path, vsmeta_path, args.overwrite_vsmeta, log_path)
        if ok:
            success += 1
        else:
            failed += 1
            fail_reasons[reason] = fail_reasons.get(reason, 0) + 1

    # 统计信息
    log("\n===== 执行统计 =====", log_path)
    log(f"总数：{total}", log_path)
    log(f"成功：{success}", log_path)
    log(f"失败：{failed}", log_path)
    for reason, count in fail_reasons.items():
        log(f"失败原因 [{reason}]：{count} 项", log_path)

if __name__ == '__main__':
    main()