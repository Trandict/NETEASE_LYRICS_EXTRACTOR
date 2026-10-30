"""
NetEase Cloud Music Lyric & Subtitle Extractor (CLI Module)
Supports both interactive terminal wizard and automated command-line flags.
"""

import sys
import os
import argparse

# Windows 控制台编码防护
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

try:
    from src.core import NetEaseLyricFetcher, LAYOUT_OPTIONS, LAYOUT_MAP
except ImportError:
    from core import NetEaseLyricFetcher, LAYOUT_OPTIONS, LAYOUT_MAP


def interactive_mode():
    print("=" * 60)
    print("      网易云音乐歌词与字幕提取工具 (命令行交互)")
    print("=" * 60)

    url_input = input("\n请输入网易云歌曲链接、分享文案或歌曲数字 ID：\n> ").strip()
    if not url_input:
        print("[-] 输入为空，程序退出。")
        return

    song_id = NetEaseLyricFetcher.extract_song_id(url_input)
    if not song_id:
        print("[-] 无法识别有效的歌曲 ID，请检查链接格式。")
        return

    print(f"\n[+] 正在查询歌曲 ID: {song_id} ...")
    try:
        info = NetEaseLyricFetcher.fetch_song_info(song_id)
        print(f"[OK] 歌名: {info.title}")
        print(f"[OK] 歌手: {info.artist_str}")
        print(f"[OK] 专辑: {info.album}")

        raw = NetEaseLyricFetcher.fetch_raw_lyrics(song_id)
        aligned = NetEaseLyricFetcher.align_lyrics(raw)
    except Exception as e:
        print(f"[-] 获取失败: {e}")
        return

    # 选择格式
    print("\n请选择导出格式：")
    print("1. LRC 歌词文件 (.lrc)")
    print("2. SRT 字幕文件 (.srt)")
    print("3. 同时导出 LRC 和 SRT")
    fmt_choice = input("请输入选项编号 [默认 1]: ").strip() or "1"
    fmt = "lrc" if fmt_choice == "1" else ("srt" if fmt_choice == "2" else "both")

    # 选择排版
    print("\n请选择语言内容排列方式：")
    for idx, opt in enumerate(LAYOUT_OPTIONS, 1):
        print(f"[{idx}] {opt['name']} ({opt['desc']})")

    layout_choice = input("请输入选项编号 [默认 1]: ").strip() or "1"
    try:
        sel_idx = int(layout_choice) - 1
        selected_opt = LAYOUT_OPTIONS[sel_idx]
    except Exception:
        selected_opt = LAYOUT_OPTIONS[0]

    tracks = selected_opt["tracks"]

    # 询问保存目录
    save_dir = input("\n请输入文件保存目录 [回车保存在当前目录]: ").strip() or "."
    os.makedirs(save_dir, exist_ok=True)

    base_name = info.safe_filename

    if fmt in ("lrc", "both"):
        lrc_content = NetEaseLyricFetcher.generate_lrc(aligned, tracks=tracks)
        lrc_path = os.path.join(save_dir, f"{base_name}.lrc")
        with open(lrc_path, "w", encoding="utf-8") as f:
            f.write(lrc_content + "\n")
        print(f"[OK] 已成功生成 LRC: {lrc_path}")

    if fmt in ("srt", "both"):
        srt_content = NetEaseLyricFetcher.generate_srt(aligned, tracks=tracks, max_duration_sec=5.0)
        srt_path = os.path.join(save_dir, f"{base_name}.srt")
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt_content + "\n")
        print(f"[OK] 已成功生成 SRT: {srt_path}")

    print("\n处理完成！")


def main():
    if len(sys.argv) == 1:
        interactive_mode()
        return

    parser = argparse.ArgumentParser(
        description="网易云音乐歌词与字幕提取工具"
    )
    parser.add_argument("input", help="网易云歌曲链接、分享文案或歌曲数字 ID")
    parser.add_argument(
        "--format", "-f",
        choices=["lrc", "srt", "both"],
        default="lrc",
        help="导出文件格式：lrc (默认), srt, 或 both"
    )
    parser.add_argument(
        "--layout", "-l",
        choices=list(LAYOUT_MAP.keys()),
        default="orig_trans",
        help="排版方案，例如：orig_trans (原上译下), trans_orig (译上原下), orig_roma_trans (三语), only_orig (仅原文) 等"
    )
    parser.add_argument(
        "--lrc-style",
        choices=["multiline", "inline"],
        default="multiline",
        help="LRC 格式样式：multiline (多行同时间戳，默认), inline (单行合并)"
    )
    parser.add_argument(
        "--srt-dur",
        type=float,
        default=5.0,
        help="SRT 字幕单句最长保留时间（秒，支持浮点数，默认 5.0）"
    )
    parser.add_argument(
        "--output", "-o",
        default=".",
        help="输出目录或指定文件路径"
    )

    args = parser.parse_args()

    song_id = NetEaseLyricFetcher.extract_song_id(args.input)
    if not song_id:
        print(f"[-] 错误：无法从输入 '{args.input}' 解析出有效的网易云歌曲 ID", file=sys.stderr)
        sys.exit(1)

    try:
        info = NetEaseLyricFetcher.fetch_song_info(song_id)
        raw = NetEaseLyricFetcher.fetch_raw_lyrics(song_id)
        aligned = NetEaseLyricFetcher.align_lyrics(raw)
    except Exception as e:
        print(f"[-] 错误：{e}", file=sys.stderr)
        sys.exit(1)

    tracks = LAYOUT_MAP.get(args.layout, {}).get("tracks", ("orig", "trans"))

    out_path = args.output
    if not os.path.splitext(out_path)[1]:
        os.makedirs(out_path, exist_ok=True)

    if os.path.isdir(out_path):
        base_name = info.safe_filename
        out_lrc = os.path.join(out_path, f"{base_name}.lrc")
        out_srt = os.path.join(out_path, f"{base_name}.srt")
    else:
        out_lrc = out_path if out_path.endswith(".lrc") else out_path + ".lrc"
        out_srt = out_path if out_path.endswith(".srt") else out_path + ".srt"

    if args.format in ("lrc", "both"):
        content = NetEaseLyricFetcher.generate_lrc(
            aligned, tracks=tracks, style=args.lrc_style
        )
        with open(out_lrc, "w", encoding="utf-8") as f:
            f.write(content + "\n")
        print(f"[OK] LRC 文件已保存: {out_lrc}")

    if args.format in ("srt", "both"):
        content = NetEaseLyricFetcher.generate_srt(
            aligned, tracks=tracks, max_duration_sec=args.srt_dur
        )
        with open(out_srt, "w", encoding="utf-8") as f:
            f.write(content + "\n")
        print(f"[OK] SRT 文件已保存: {out_srt}")


if __name__ == "__main__":
    main()
