"""
NetEase Cloud Music Lyric & Subtitle Extractor (GUI Module)
Modern, professional desktop interface with interactive track reordering,
live previews, and clean format exports.
"""

import os
import sys
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# Windows 高 DPI 适配
try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

try:
    from src.core import (
        NetEaseLyricFetcher,
        SongInfo,
        AlignedBlock
    )
except ImportError:
    from core import (
        NetEaseLyricFetcher,
        SongInfo,
        AlignedBlock
    )


class NetEaseLyricGUI:
    TRACK_DEFINITIONS = {
        "orig": {"name": "原文"},
        "roma": {"name": "读音"},
        "trans": {"name": "译文"},
    }

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("网易云音乐歌词与字幕提取器")
        self.root.geometry("1060x740")
        self.root.minsize(940, 650)

        # 数据状态
        self.current_song_info = None
        self.current_raw_lyrics = {}
        self.current_aligned_blocks = []
        self.fetching = False
        self.msg_queue = queue.Queue()

        # 动态轨道卡片数据列表：每个元素为字典 {key, name, enabled_var, frame_widget}
        self.track_items = []
        self.drag_start_idx = None

        self._init_styles()
        self._build_ui()
        self._schedule_queue_check()

    def _init_styles(self):
        self.style = ttk.Style()
        available_themes = self.style.theme_names()
        if 'vista' in available_themes:
            self.style.theme_use('vista')
        elif 'clam' in available_themes:
            self.style.theme_use('clam')

        self.font_main = ("Microsoft YaHei", 9)
        self.font_bold = ("Microsoft YaHei", 9, "bold")
        self.font_title = ("Microsoft YaHei", 12, "bold")
        self.font_mono = ("Consolas", 10)

        self.root.option_add("*Font", self.font_main)

    def _schedule_queue_check(self):
        self._process_queue()
        self.root.after(80, self._schedule_queue_check)

    def _process_queue(self):
        while not self.msg_queue.empty():
            try:
                msg_type, payload = self.msg_queue.get_nowait()
                if msg_type == "success":
                    info, raw, aligned = payload
                    self._on_fetch_success(info, raw, aligned)
                elif msg_type == "error":
                    self._on_fetch_error(payload)
            except queue.Empty:
                break

    def _build_ui(self):
        header_frame = tk.Frame(self.root, bg="#F8FAFC", height=0, highlightthickness=1, highlightbackground="#E2E8F0")
        header_frame.pack(fill=tk.X, side=tk.TOP)
        header_frame.pack_propagate(False)

        title_label = tk.Label(
            header_frame,
            text="",
            bg="#F8FAFC",
            fg="#1E293B",
            font=("Microsoft YaHei", 12, "bold")
        )
        title_label.pack(side=tk.LEFT, padx=18, pady=14)

        subtitle_label = tk.Label(
            header_frame,
            text="",
            bg="#F8FAFC",
            fg="#64748B",
            font=("Microsoft YaHei", 9)
        )
        subtitle_label.pack(side=tk.LEFT, padx=4, pady=16)

        # 主工作区 (左右分割)
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 左侧控制面板
        left_panel = ttk.Frame(main_paned, width=440)
        main_paned.add(left_panel, weight=0)

        # 右侧预览面板
        right_panel = ttk.Frame(main_paned, width=600)
        main_paned.add(right_panel, weight=1)

        self._build_left_panel(left_panel)
        self._build_right_panel(right_panel)

        # 底部状态栏
        self.status_var = tk.StringVar(value="就绪。请输入网易云歌曲链接或 ID。")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W, padding=(6, 3))
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def _build_left_panel(self, parent):
        # 1. 输入区域
        input_group = ttk.LabelFrame(parent, text=" 歌曲输入 ", padding=10)
        input_group.pack(fill=tk.X, padx=5, pady=4)

        ttk.Label(input_group, text="歌曲链接、分享文案或歌曲 ID:").pack(anchor=tk.W, pady=(0, 4))

        input_box_frame = ttk.Frame(input_group)
        input_box_frame.pack(fill=tk.X, pady=(0, 6))

        self.input_entry = ttk.Entry(input_box_frame)
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        self.input_entry.bind("<Return>", lambda e: self.start_fetch_lyrics())

        paste_btn = ttk.Button(input_box_frame, text="粘贴", width=5, command=self.paste_from_clipboard)
        paste_btn.pack(side=tk.LEFT, padx=(0, 4))

        clear_btn = ttk.Button(input_box_frame, text="清空", width=5, command=self.clear_input)
        clear_btn.pack(side=tk.LEFT)

        self.fetch_btn = ttk.Button(input_group, text="获取并解析歌词", command=self.start_fetch_lyrics)
        self.fetch_btn.pack(fill=tk.X, pady=(2, 0))

        # 2. 歌曲信息展示（纯净简洁，无多余标签）
        self.info_group = ttk.LabelFrame(parent, text=" 歌曲信息 ", padding=10)
        self.info_group.pack(fill=tk.X, padx=5, pady=4)

        self.lbl_song_title = ttk.Label(self.info_group, text="歌名：-", font=self.font_bold)
        self.lbl_song_title.pack(anchor=tk.W, pady=1)

        self.lbl_song_artist = ttk.Label(self.info_group, text="歌手：-")
        self.lbl_song_artist.pack(anchor=tk.W, pady=1)

        self.lbl_song_album = ttk.Label(self.info_group, text="专辑：-")
        self.lbl_song_album.pack(anchor=tk.W, pady=1)

        # 3. 语言排版板（动态轨道块容器，可拖拽、可开关）
        self.board_group = ttk.LabelFrame(parent, text=" 内容轨道与顺序 ", padding=10)
        self.board_group.pack(fill=tk.X, padx=5, pady=4)

        self.board_container = ttk.Frame(self.board_group)
        self.board_container.pack(fill=tk.X, pady=2)

        # 获取前占位提示（未获取歌词前无块）
        self.empty_board_label = tk.Label(
            self.board_container,
            text="",
            fg="#94A3B8",
            bg="#F8FAFC",
            relief=tk.GROOVE,
            padx=12,
            pady=16,
            justify=tk.CENTER
        )
        self.empty_board_label.pack(fill=tk.X)

        # 4. 导出格式与配置
        options_group = ttk.LabelFrame(parent, text=" 导出与格式设置 ", padding=10)
        options_group.pack(fill=tk.X, padx=5, pady=4)

        # 格式单选
        fmt_frame = ttk.Frame(options_group)
        fmt_frame.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(fmt_frame, text="导出格式:").pack(side=tk.LEFT, padx=(0, 8))

        self.format_var = tk.StringVar(value="lrc")
        lrc_radio = ttk.Radiobutton(
            fmt_frame, text="LRC 歌词 (.lrc)", variable=self.format_var, value="lrc", command=self.on_format_changed
        )
        lrc_radio.pack(side=tk.LEFT, padx=6)

        srt_radio = ttk.Radiobutton(
            fmt_frame, text="SRT 字幕 (.srt)", variable=self.format_var, value="srt", command=self.on_format_changed
        )
        srt_radio.pack(side=tk.LEFT, padx=6)

        # SRT 单句最长保留时间（仅在选择 SRT 时才显示，用户直接输入浮点数）
        self.srt_options_frame = ttk.Frame(options_group)
        # 初始默认是 LRC，不显示
        vcmd = (self.root.register(self._validate_float_input), '%P')
        ttk.Label(self.srt_options_frame, text="单句最长保留时间:").pack(side=tk.LEFT)
        self.srt_dur_var = tk.StringVar(value="5.0")
        self.srt_dur_entry = ttk.Entry(
            self.srt_options_frame,
            textvariable=self.srt_dur_var,
            width=6,
            validate="key",
            validatecommand=vcmd
        )
        self.srt_dur_entry.pack(side=tk.LEFT, padx=6)
        ttk.Label(self.srt_options_frame, text="秒").pack(side=tk.LEFT)
        self.srt_dur_entry.bind("<KeyRelease>", lambda e: self.update_preview())
        self.srt_dur_entry.bind("<FocusOut>", lambda e: self.update_preview())

        # LRC 排版模式选项
        self.lrc_style_frame = ttk.Frame(options_group)
        self.lrc_style_frame.pack(fill=tk.X, pady=3)
        ttk.Label(self.lrc_style_frame, text="LRC 展现样式:").pack(side=tk.LEFT)
        self.lrc_style_combo = ttk.Combobox(
            self.lrc_style_frame,
            values=["多行同时间戳 (播放器推荐)", "单行合并 (带斜杠分隔符)"],
            state="readonly",
            width=22
        )
        self.lrc_style_combo.current(0)
        self.lrc_style_combo.pack(side=tk.LEFT, padx=6)
        self.lrc_style_combo.bind("<<ComboboxSelected>>", lambda e: self.update_preview())

    def _build_right_panel(self, parent):
        # 顶部操作工具栏
        action_bar = ttk.Frame(parent)
        action_bar.pack(fill=tk.X, pady=(0, 6))

        self.lbl_preview_info = ttk.Label(action_bar, text="歌词与字幕预览", font=self.font_bold)
        self.lbl_preview_info.pack(side=tk.LEFT, pady=4)

        btn_box = ttk.Frame(action_bar)
        btn_box.pack(side=tk.RIGHT)

        btn_copy = ttk.Button(btn_box, text="复制内容", command=self.copy_preview_content)
        btn_copy.pack(side=tk.LEFT, padx=4)

        btn_save = ttk.Button(btn_box, text="导出当前文件", command=self.save_current_file)
        btn_save.pack(side=tk.LEFT, padx=4)

        btn_save_all = ttk.Button(btn_box, text="同时导出 LRC+SRT", command=self.save_both_files)
        btn_save_all.pack(side=tk.LEFT, padx=4)

        # 预览文本框及滚动条
        preview_container = ttk.Frame(parent)
        preview_container.pack(fill=tk.BOTH, expand=True)

        y_scroll = ttk.Scrollbar(preview_container, orient=tk.VERTICAL)
        x_scroll = ttk.Scrollbar(preview_container, orient=tk.HORIZONTAL)

        self.preview_text = tk.Text(
            preview_container,
            wrap=tk.NONE,
            font=self.font_mono,
            yscrollcommand=y_scroll.set,
            xscrollcommand=x_scroll.set,
            bg="#FAFAFA",
            fg="#1E293B",
            padx=10,
            pady=10,
            undo=True,
            autoseparators=True,
            maxundo=-1
        )

        # 快捷键绑定：Ctrl+Z 撤销，Ctrl+Y / Ctrl+Shift+Z 重做
        self.preview_text.bind("<Control-z>", self._on_undo)
        self.preview_text.bind("<Control-Z>", self._on_undo)
        self.preview_text.bind("<Control-y>", self._on_redo)
        self.preview_text.bind("<Control-Y>", self._on_redo)
        self.preview_text.bind("<Control-Shift-z>", self._on_redo)
        self.preview_text.bind("<Control-Shift-Z>", self._on_redo)

        y_scroll.config(command=self.preview_text.yview)
        x_scroll.config(command=self.preview_text.xview)

        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        x_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.preview_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.preview_text.insert(
            tk.END,
            "# 请在左侧输入网易云歌曲链接或歌曲 ID，点击【获取并解析歌词】。\n"
            "# 获取后，左侧将自动生成这首歌实际包含的内容块（原文/译文/读音），\n"
            "# 您可自由拖拽或点击箭头调整排列顺序，并可随时勾选启用/关闭某一层。\n"
        )
        self.preview_text.edit_reset()

    def _on_undo(self, event=None):
        try:
            self.preview_text.edit_undo()
        except tk.TclError:
            pass
        return "break"

    def _on_redo(self, event=None):
        try:
            self.preview_text.edit_redo()
        except tk.TclError:
            pass
        return "break"

    def _validate_float_input(self, new_val: str) -> bool:
        if new_val == "" or new_val == ".":
            return True
        try:
            val = float(new_val)
            return val >= 0
        except ValueError:
            return False

    def on_format_changed(self):
        fmt = self.format_var.get()
        if fmt == "srt":
            self.lrc_style_frame.pack_forget()
            self.srt_options_frame.pack(fill=tk.X, pady=3)
        else:
            self.srt_options_frame.pack_forget()
            self.lrc_style_frame.pack(fill=tk.X, pady=3)
        self.update_preview()

    def paste_from_clipboard(self):
        try:
            content = self.root.clipboard_get()
            if content:
                self.input_entry.delete(0, tk.END)
                self.input_entry.insert(0, content.strip())
        except Exception:
            pass

    def clear_input(self):
        self.input_entry.delete(0, tk.END)

    def start_fetch_lyrics(self):
        if self.fetching:
            return
        input_val = self.input_entry.get().strip()
        if not input_val:
            messagebox.showwarning("提示", "请输入网易云歌曲链接、分享文案或歌曲数字 ID。")
            return

        song_id = NetEaseLyricFetcher.extract_song_id(input_val)
        if not song_id:
            messagebox.showerror("格式错误", "未能从输入内容中识别出有效的歌曲 ID，请检查链接格式。")
            return

        self.fetching = True
        self.fetch_btn.config(state=tk.DISABLED)
        self.status_var.set(f"正在获取歌曲 ID: {song_id} 的信息与歌词...")

        thread = threading.Thread(target=self._fetch_worker, args=(song_id,), daemon=True)
        thread.start()

    def _fetch_worker(self, song_id: int):
        try:
            info = NetEaseLyricFetcher.fetch_song_info(song_id)
            raw = NetEaseLyricFetcher.fetch_raw_lyrics(song_id)
            aligned = NetEaseLyricFetcher.align_lyrics(raw)
            self.msg_queue.put(("success", (info, raw, aligned)))
        except Exception as e:
            self.msg_queue.put(("error", str(e)))

    def _on_fetch_error(self, err_msg: str):
        self.fetching = False
        self.fetch_btn.config(state=tk.NORMAL)
        self.status_var.set(f"获取失败：{err_msg}")
        messagebox.showerror("获取失败", f"无法获取歌词：\n{err_msg}")

    def _on_fetch_success(self, info: SongInfo, raw: dict, aligned: list):
        self.fetching = False
        self.fetch_btn.config(state=tk.NORMAL)
        self.current_song_info = info
        self.current_raw_lyrics = raw
        self.current_aligned_blocks = aligned

        self.lbl_song_title.config(text=f"歌名：{info.title}")
        self.lbl_song_artist.config(text=f"歌手：{info.artist_str}")
        self.lbl_song_album.config(text=f"专辑：{info.album if info.album else '单曲'}")

        # 根据歌曲实际含有的轨道，动态构建排版板（有哪些块就显示哪些块，没有的不显示）
        has_orig = bool(raw.get('orig'))
        has_roma = bool(raw.get('roma'))
        has_trans = bool(raw.get('trans'))

        available_keys = []
        if has_orig:
            available_keys.append("orig")
        if has_roma:
            available_keys.append("roma")
        if has_trans:
            available_keys.append("trans")

        self._rebuild_track_board(available_keys)
        self.status_var.set(f"解析成功！已载入《{info.title}》，共对齐 {len(aligned)} 行歌词。")
        self.update_preview()

    def _rebuild_track_board(self, available_keys: list):
        # 清除现有卡片或空提示
        for widget in self.board_container.winfo_children():
            widget.destroy()
        self.track_items.clear()

        if not available_keys:
            self.empty_board_label = tk.Label(
                self.board_container,
                text="该歌曲未检索到可用文本歌词",
                fg="#94A3B8",
                bg="#F8FAFC",
                pady=16
            )
            self.empty_board_label.pack(fill=tk.X)
            return

        # 为每一个实际存在的轨道构建交互卡片块
        for key in available_keys:
            track_def = self.TRACK_DEFINITIONS.get(key, {"name": key, "desc": ""})
            item_data = {
                "key": key,
                "name": track_def["name"],
                "enabled": tk.BooleanVar(value=True),
                "frame": None
            }
            self.track_items.append(item_data)

        self._render_track_blocks()

    def _render_track_blocks(self):
        for widget in self.board_container.winfo_children():
            widget.destroy()

        for idx, item in enumerate(self.track_items):
            block_frame = tk.Frame(
                self.board_container,
                bg="#FFFFFF",
                relief=tk.SOLID,
                bd=1,
                cursor="hand2"
            )
            block_frame.pack(fill=tk.X, pady=3, padx=2)
            item["frame"] = block_frame

            # 拖拽抓手手柄
            grip_label = tk.Label(
                block_frame,
                text=" ↕ ",
                font=("Consolas", 11, "bold"),
                fg="#94A3B8",
                bg="#FFFFFF",
                cursor="fleur"
            )
            grip_label.pack(side=tk.LEFT, padx=(6, 4), pady=6)

            # 复选开关
            cb = ttk.Checkbutton(
                block_frame,
                text=f"{item['name']}",
                variable=item["enabled"],
                command=self.update_preview
            )
            cb.pack(side=tk.LEFT, padx=4, pady=6)

            # 说明文本
            desc_lbl = tk.Label(
                block_frame,
                font=("Microsoft YaHei", 8),
                fg="#64748B",
                bg="#FFFFFF"
            )
            desc_lbl.pack(side=tk.LEFT, padx=6)

            # 右侧操作按钮：上移、下移
            btn_box = tk.Frame(block_frame, bg="#FFFFFF")
            btn_box.pack(side=tk.RIGHT, padx=6)

            btn_up = tk.Button(
                btn_box,
                text="▲",
                font=("Microsoft YaHei", 7),
                width=2,
                height=1,
                relief=tk.FLAT,
                bg="#F1F5F9",
                fg="#475569",
                command=lambda i=idx: self._move_track(i, -1)
            )
            btn_up.pack(side=tk.LEFT, padx=1)

            btn_down = tk.Button(
                btn_box,
                text="▼",
                font=("Microsoft YaHei", 7),
                width=2,
                height=1,
                relief=tk.FLAT,
                bg="#F1F5F9",
                fg="#475569",
                command=lambda i=idx: self._move_track(i, 1)
            )
            btn_down.pack(side=tk.LEFT, padx=1)

            # 绑定拖拽事件（在卡片背景与手柄上均生效）
            for target_widget in (block_frame, grip_label, desc_lbl):
                target_widget.bind("<Button-1>", lambda e, i=idx: self._on_drag_start(e, i))
                target_widget.bind("<B1-Motion>", self._on_drag_motion)
                target_widget.bind("<ButtonRelease-1>", self._on_drag_end)

    def _move_track(self, index: int, offset: int):
        target = index + offset
        if 0 <= target < len(self.track_items):
            self.track_items[index], self.track_items[target] = self.track_items[target], self.track_items[index]
            self._render_track_blocks()
            self.update_preview()

    def _on_drag_start(self, event, index: int):
        self.drag_start_idx = index
        if index < len(self.track_items):
            frame = self.track_items[index]["frame"]
            if frame and frame.winfo_exists():
                frame.config(bg="#EFF6FF", bd=2)

    def _on_drag_motion(self, event):
        if self.drag_start_idx is None:
            return
        # 检测当前鼠标 y 落在哪个卡片上
        container_y = self.board_container.winfo_rooty()
        mouse_y = event.y_root - container_y

        total_y = 0
        hover_idx = None
        for i, item in enumerate(self.track_items):
            f = item["frame"]
            if not f or not f.winfo_exists():
                continue
            h = f.winfo_height()
            if total_y <= mouse_y <= total_y + h:
                hover_idx = i
                break
            total_y += h + 6  # 包含 pady

        if hover_idx is not None and hover_idx != self.drag_start_idx:
            # 交换位置
            item = self.track_items.pop(self.drag_start_idx)
            self.track_items.insert(hover_idx, item)
            self.drag_start_idx = hover_idx
            self._render_track_blocks()

    def _on_drag_end(self, event):
        self.drag_start_idx = None
        self._render_track_blocks()
        self.update_preview()

    def get_active_tracks(self) -> list:
        # 按照当前卡片面板里的上下排列顺序，提取所有被勾选启用的轨道 key
        return [item["key"] for item in self.track_items if item["enabled"].get()]

    def update_preview(self):
        if not self.current_aligned_blocks:
            return

        fmt = self.format_var.get()
        tracks = self.get_active_tracks()

        # 解析用户输入的 SRT 单句保留时长浮点数
        try:
            max_dur = float(self.srt_dur_var.get().strip())
            if max_dur <= 0:
                max_dur = 5.0
        except ValueError:
            max_dur = 5.0

        if not tracks:
            self.preview_text.delete("1.0", tk.END)
            self.preview_text.insert(tk.END, "# 提示：所有内容轨道均已停用，请至少在左侧勾选开启一个内容层。")
            self.preview_text.edit_reset()
            self.lbl_preview_info.config(text="预览 (未选择任何内容层)")
            return

        if fmt == "lrc":
            style_idx = self.lrc_style_combo.current()
            style = "multiline" if style_idx == 0 else "inline"
            content = NetEaseLyricFetcher.generate_lrc(
                self.current_aligned_blocks,
                tracks=tracks,
                style=style,
                remove_empty=True
            )
            order_names = " / ".join([self.TRACK_DEFINITIONS.get(t, {}).get("name", t) for t in tracks])
            info_text = f"LRC 歌词预览 [{order_names}] (共 {len(content.splitlines())} 行)"
        else:
            content = NetEaseLyricFetcher.generate_srt(
                self.current_aligned_blocks,
                tracks=tracks,
                max_duration_sec=max_dur,
                remove_empty=True
            )
            blocks_cnt = len([b for b in content.split("\n\n") if b.strip()])
            order_names = " / ".join([self.TRACK_DEFINITIONS.get(t, {}).get("name", t) for t in tracks])
            info_text = f"SRT 字幕预览 [{order_names}] (共 {blocks_cnt} 条字幕)"

        self.lbl_preview_info.config(text=info_text)
        self.preview_text.delete("1.0", tk.END)
        self.preview_text.insert(tk.END, content)
        self.preview_text.edit_reset()

    def copy_preview_content(self):
        content = self.preview_text.get("1.0", tk.END).strip()
        if not content:
            messagebox.showinfo("提示", "当前无预览内容可复制。")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        self.status_var.set("已复制当前预览文本到系统剪贴板。")
        messagebox.showinfo("复制成功", "歌词/字幕内容已成功复制到剪贴板。")

    def save_current_file(self):
        if not self.current_song_info or not self.current_aligned_blocks:
            messagebox.showwarning("提示", "请先解析一首歌曲后再导出。")
            return

        fmt = self.format_var.get()
        ext = f".{fmt}"
        default_filename = f"{self.current_song_info.safe_filename}{ext}"

        file_types = [("LRC 歌词文件", "*.lrc")] if fmt == "lrc" else [("SRT 字幕文件", "*.srt")]
        file_types.append(("所有文件", "*.*"))

        save_path = filedialog.asksaveasfilename(
            title=f"导出 {fmt.upper()} 文件",
            initialfile=default_filename,
            defaultextension=ext,
            filetypes=file_types
        )
        if not save_path:
            return

        content = self.preview_text.get("1.0", tk.END).strip()
        try:
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(content + "\n")
            self.status_var.set(f"保存成功：{save_path}")
            messagebox.showinfo("导出成功", f"文件已保存至：\n{save_path}")
        except Exception as e:
            messagebox.showerror("保存失败", f"写入文件时出错：\n{e}")

    def save_both_files(self):
        if not self.current_song_info or not self.current_aligned_blocks:
            messagebox.showwarning("提示", "请先解析一首歌曲后再导出。")
            return

        target_dir = filedialog.askdirectory(title="选择保存目录")
        if not target_dir:
            return

        tracks = self.get_active_tracks()
        style_idx = self.lrc_style_combo.current()
        style = "multiline" if style_idx == 0 else "inline"

        try:
            max_dur = float(self.srt_dur_var.get().strip())
            if max_dur <= 0:
                max_dur = 5.0
        except ValueError:
            max_dur = 5.0

        lrc_content = NetEaseLyricFetcher.generate_lrc(
            self.current_aligned_blocks,
            tracks=tracks,
            style=style,
            remove_empty=True
        )
        srt_content = NetEaseLyricFetcher.generate_srt(
            self.current_aligned_blocks,
            tracks=tracks,
            max_duration_sec=max_dur,
            remove_empty=True
        )

        base_name = self.current_song_info.safe_filename
        lrc_path = os.path.join(target_dir, f"{base_name}.lrc")
        srt_path = os.path.join(target_dir, f"{base_name}.srt")

        try:
            with open(lrc_path, "w", encoding="utf-8") as f:
                f.write(lrc_content + "\n")
            with open(srt_path, "w", encoding="utf-8") as f:
                f.write(srt_content + "\n")

            self.status_var.set(f"已导出全部文件至：{target_dir}")
            messagebox.showinfo("批量导出成功", f"已在目标目录保存：\n1. {base_name}.lrc\n2. {base_name}.srt")
        except Exception as e:
            messagebox.showerror("导出失败", f"保存文件失败：\n{e}")


def main():
    root = tk.Tk()
    app = NetEaseLyricGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
