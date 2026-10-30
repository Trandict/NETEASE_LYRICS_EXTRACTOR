@echo off
title 打包网易云音乐歌词与字幕提取器为单文件EXE
cd /d "%~dp0"

echo ============================================================
echo      网易云音乐歌词与字幕提取工具 - 独立EXE打包程序
echo ============================================================
echo.

python -c "import PyInstaller" 2>nul
if %errorlevel% neq 0 (
    echo [提示] 检测到当前 Python 环境尚未安装 PyInstaller。
    echo 正在为您自动安装 PyInstaller...
    python -m pip install pyinstaller
    if %errorlevel% neq 0 (
        echo [错误] PyInstaller 安装失败，请检查网络连接或 pip 配置。
        pause
        exit /b 1
    )
)

echo.
echo [1/2] 正在调用 PyInstaller 执行单文件打包，请稍候...
python -m PyInstaller --onefile --windowed --clean --name "网易云音乐歌词与字幕提取器" main.py

if %errorlevel% neq 0 (
    echo.
    echo [错误] 打包过程发生异常，请检查上方控制台报错信息。
    pause
    exit /b 1
)

echo.
echo [2/2] 打包完成！独立运行程序已生成至: dist\网易云音乐歌词与字幕提取器.exe
echo.
pause
