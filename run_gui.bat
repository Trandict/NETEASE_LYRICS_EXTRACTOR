@echo off
title 网易云音乐歌词与字幕提取工具
cd /d "%~dp0"
python main.py
if %errorlevel% neq 0 (
    echo.
    echo [提示] 启动遇到错误，请确认已安装 Python 环境并添加至系统环境变量 PATH。
    echo 按任意键退出...
    pause >nul
)
