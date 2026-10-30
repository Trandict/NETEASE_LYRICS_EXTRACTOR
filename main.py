"""
NetEase Cloud Music Lyric & Subtitle Extractor
Main Application Entry Point.

- Run without arguments -> Launches Graphical User Interface (GUI)
- Run with arguments or '--cli' -> Routes to Command Line Interface (CLI)
"""

import sys
import os

# 将当前根目录添加到 sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)


def main():
    # 显式参数判断
    if len(sys.argv) > 1:
        if sys.argv[1] == "--cli":
            from src.cli import interactive_mode
            interactive_mode()
            return
        from src.cli import main as cli_main
        cli_main()
        return

    # 无参数默认启动 GUI，若环境不支持 Tkinter 则降级至 CLI
    try:
        from src.gui import main as gui_main
        gui_main()
    except Exception as e:
        print(f"[Warning] 启动图形界面失败 ({e})，正在自动切换至命令行模式...\n")
        from src.cli import interactive_mode
        interactive_mode()


if __name__ == "__main__":
    main()
