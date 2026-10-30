"""
NetEase Cloud Music Lyric Core Processing Module
Includes:
- Link & Song ID Resolver
- Lyrics Fetcher (Original, Translation, Pronunciation/Romaji)
- Dual-pass Timestamp Alignment Engine
- Robust Credits (Metadata) Detector
- Dynamic Track Formatter for LRC & SRT
"""

import re
import json
import urllib.request
from typing import List, Dict, Optional, Tuple, Sequence


class SongInfo:
    def __init__(self, song_id: int, title: str, artists: List[str], album: str):
        self.id = song_id
        self.title = title
        self.artists = artists
        self.album = album

    @property
    def artist_str(self) -> str:
        return "/".join(self.artists) if self.artists else "未知歌手"

    @property
    def safe_filename(self) -> str:
        name = f"{self.artist_str} - {self.title}"
        return re.sub(r'[\\/*?:"<>|]', '_', name)

    def __repr__(self):
        return f"<SongInfo {self.id}: {self.artist_str} - {self.title}>"


class AlignedBlock:
    def __init__(
        self,
        time_ms: int,
        orig: Optional[str] = None,
        trans: Optional[str] = None,
        roma: Optional[str] = None,
        is_credit: bool = False
    ):
        self.time_ms = time_ms
        self.orig = orig
        self.trans = trans
        self.roma = roma
        self.is_credit = is_credit

    def get_track(self, track_name: str) -> Optional[str]:
        if track_name == 'orig':
            return self.orig
        elif track_name == 'trans':
            return self.trans
        elif track_name == 'roma':
            return self.roma
        return None

    def has_any_text(self, tracks: Sequence[str]) -> bool:
        return any(bool(self.get_track(t)) for t in tracks)


# 预设的常用排版（用于 CLI 默认及自动化支持）
LAYOUT_OPTIONS = [
    {"id": "orig_trans", "name": "原文在上，译文在下", "tracks": ("orig", "trans"), "desc": "常见双语"},
    {"id": "trans_orig", "name": "译文在上，原文在下", "tracks": ("trans", "orig"), "desc": "中文在上"},
    {"id": "orig_roma_trans", "name": "原文、读音、译文", "tracks": ("orig", "roma", "trans"), "desc": "经典三语"},
    {"id": "orig_roma", "name": "原文在上，读音在下", "tracks": ("orig", "roma"), "desc": "读音发音"},
    {"id": "only_orig", "name": "仅原文", "tracks": ("orig",), "desc": "纯原文"},
    {"id": "only_trans", "name": "仅译文", "tracks": ("trans",), "desc": "纯译文"},
    {"id": "only_roma", "name": "仅读音", "tracks": ("roma",), "desc": "纯读音"},
]
LAYOUT_MAP = {opt["id"]: opt for opt in LAYOUT_OPTIONS}


class NetEaseLyricFetcher:
    CREDIT_KEYWORDS = (
        r'制作|出品|监制|发行|统筹|企划|作词|作詞|作曲|编曲|編曲|混音|录音|母带|缩混|'
        r'吉他|贝斯|鼓|键盘|钢琴|弦乐|管乐|伴唱|和声|和音|合唱|演奏|乐团|交响|乐队|'
        r'人声|主唱|演唱|歌手|声乐|音频|音效|剪辑|工程|录音棚|录音室|工作室|版权|'
        r'词曲|翻唱|原唱|翻译|听写|校对|整理|配唱|'
        r'Lyricist|Composer|Arranger|Producer|Vocals|Mixed|Mastered|Recording|Mastering|'
        r'Studio|Guitar|Bass|Drums|Keyboard|Strings|OP|SP|Chorus|Sound|Director|Executive|Engineer|Artist'
    )
    CREDIT_REGEX = re.compile(
        rf'^([^:：]{{0,15}}(?:{CREDIT_KEYWORDS})[^:：]{{0,15}})\s*[:：]',
        re.IGNORECASE
    )

    @classmethod
    def is_credit_line(cls, text: str) -> bool:
        if not text:
            return False
        stripped = text.strip()
        if cls.CREDIT_REGEX.search(stripped):
            return True
        # 兼容例如 "Written by ...", "Produced by ..."
        if re.search(r'^(?:written|produced|mixed|mastered|performed)\s+by\s*[:：]?', stripped, re.IGNORECASE):
            return True
        return False

    @classmethod
    def extract_song_id(cls, input_str: str) -> Optional[int]:
        if not input_str:
            return None
        input_str = input_str.strip()
        if re.fullmatch(r'\d+', input_str):
            return int(input_str)
        m = re.search(r'(?:id=|\/song\/|\/song\?id=)(\d+)', input_str)
        if m:
            return int(m.group(1))
        # 针对手机端分享短链等，进行重定向跟随抓取真实URL
        url_match = re.search(r'https?://[^\s]+', input_str)
        if url_match:
            try:
                req = urllib.request.Request(
                    url_match.group(0),
                    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
                )
                opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler)
                with opener.open(req, timeout=6) as resp:
                    final_url = resp.geturl()
                    m2 = re.search(r'(?:id=|\/song\/)(\d+)', final_url)
                    if m2:
                        return int(m2.group(1))
            except Exception:
                pass
        return None

    @classmethod
    def fetch_song_info(cls, song_id: int) -> SongInfo:
        url = f"https://music.163.com/api/song/detail/?id={song_id}&ids=[{song_id}]"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode('utf-8', errors='replace'))
        songs = data.get('songs', [])
        if not songs:
            raise ValueError(f"未找到 ID 为 {song_id} 的歌曲信息")
        song = songs[0]
        title = song.get('name', f'歌曲_{song_id}')
        artists = [a.get('name', '未知') for a in song.get('artists', [])]
        album = song.get('album', {}).get('name', '')
        return SongInfo(song_id, title, artists, album)

    @classmethod
    def fetch_raw_lyrics(cls, song_id: int) -> Dict[str, str]:
        url = f"https://music.163.com/api/song/lyric?id={song_id}&lv=1&kv=1&tv=-1&rv=-1"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode('utf-8', errors='replace'))
        if data.get('nolyric'):
            raise ValueError("该歌曲为纯音乐或无歌词")
        
        orig_lrc = data.get('lrc', {}).get('lyric', '') or ''
        trans_lrc = data.get('tlyric', {}).get('lyric', '') or ''
        roma_lrc = data.get('romalrc', {}).get('lyric', '') or ''

        if not orig_lrc and not trans_lrc and not roma_lrc:
            raise ValueError("未获取到该歌曲的歌词内容")

        return {
            'orig': orig_lrc,
            'trans': trans_lrc,
            'roma': roma_lrc,
        }

    @classmethod
    def parse_lrc_lines(cls, lrc_text: str) -> List[Tuple[int, str]]:
        if not lrc_text:
            return []
        items = []
        for line in lrc_text.splitlines():
            line_str = line.strip()
            if not line_str:
                continue
            timestamps = re.findall(r'\[(\d+):(\d+(?:\.\d+)?)\]', line_str)
            if not timestamps:
                continue
            content = re.sub(r'\[\d+:\d+(?:\.\d+)?\]', '', line_str).strip()
            for m_str, s_str in timestamps:
                try:
                    m = int(m_str)
                    s = float(s_str)
                    ms = int(m * 60000 + s * 1000)
                    items.append((ms, content))
                except ValueError:
                    continue
        items.sort(key=lambda x: x[0])
        return items

    @classmethod
    def _match_track(
        cls,
        orig_lines: List[Tuple[int, str]],
        target_lines: List[Tuple[int, str]],
        tolerance_exact: int = 50,
        tolerance_loose: int = 350
    ) -> Tuple[Dict[int, int], set]:
        matched: Dict[int, int] = {}
        used_target: set = set()

        # 第一轮：精确匹配非制作人名单歌词 (<= 50ms)
        for o_idx, (o_ms, o_text) in enumerate(orig_lines):
            is_credit = cls.is_credit_line(o_text)
            if is_credit:
                continue
            best_t = None
            best_diff = tolerance_exact + 1
            for t_idx, (t_ms, t_text) in enumerate(target_lines):
                if t_idx in used_target:
                    continue
                diff = abs(o_ms - t_ms)
                if diff <= tolerance_exact and diff < best_diff:
                    best_diff = diff
                    best_t = t_idx
            if best_t is not None:
                matched[o_idx] = best_t
                used_target.add(best_t)

        # 第二轮：模糊容差匹配剩余未对齐行 (<= 350ms)
        for o_idx, (o_ms, o_text) in enumerate(orig_lines):
            if o_idx in matched:
                continue
            is_credit = cls.is_credit_line(o_text)
            if is_credit:
                continue
            best_t = None
            best_diff = tolerance_loose + 1
            for t_idx, (t_ms, t_text) in enumerate(target_lines):
                if t_idx in used_target:
                    continue
                diff = abs(o_ms - t_ms)
                if diff <= tolerance_loose and diff < best_diff:
                    best_diff = diff
                    best_t = t_idx
            if best_t is not None:
                matched[o_idx] = best_t
                used_target.add(best_t)

        return matched, used_target

    @classmethod
    def align_lyrics(cls, raw_lyrics: Dict[str, str], tolerance_ms: int = 500) -> List[AlignedBlock]:
        orig_lines = cls.parse_lrc_lines(raw_lyrics.get('orig', ''))
        trans_lines = cls.parse_lrc_lines(raw_lyrics.get('trans', ''))
        roma_lines = cls.parse_lrc_lines(raw_lyrics.get('roma', ''))

        matched_trans, used_trans = cls._match_track(orig_lines, trans_lines)
        matched_roma, used_roma = cls._match_track(orig_lines, roma_lines)

        aligned: List[AlignedBlock] = []

        for o_idx, (ms, orig_text) in enumerate(orig_lines):
            is_credit = cls.is_credit_line(orig_text)
            t_idx = matched_trans.get(o_idx)
            r_idx = matched_roma.get(o_idx)

            matched_trans_text = trans_lines[t_idx][1] if t_idx is not None else None
            matched_roma_text = roma_lines[r_idx][1] if r_idx is not None else None

            aligned.append(AlignedBlock(
                time_ms=ms,
                orig=orig_text if orig_text else None,
                trans=matched_trans_text if matched_trans_text else None,
                roma=matched_roma_text if matched_roma_text else None,
                is_credit=is_credit
            ))

        # 处理可能完全未与原文对齐的额外翻译行
        for idx, (t_ms, t_text) in enumerate(trans_lines):
            if idx not in used_trans and t_text:
                aligned.append(AlignedBlock(
                    time_ms=t_ms,
                    trans=t_text,
                    is_credit=cls.is_credit_line(t_text)
                ))

        # 处理可能完全未与原文对齐的额外读音行
        for idx, (r_ms, r_text) in enumerate(roma_lines):
            if idx not in used_roma and r_text:
                aligned.append(AlignedBlock(
                    time_ms=r_ms,
                    roma=r_text,
                    is_credit=cls.is_credit_line(r_text)
                ))

        aligned.sort(key=lambda x: x.time_ms)
        return aligned

    @staticmethod
    def ms_to_lrc(ms: int) -> str:
        minutes = ms // 60000
        seconds = (ms % 60000) // 1000
        hundredths = (ms % 1000) // 10
        return f"[{minutes:02d}:{seconds:02d}.{hundredths:02d}]"

    @staticmethod
    def ms_to_srt(ms: int) -> str:
        hours = ms // 3600000
        minutes = (ms % 3600000) // 60000
        seconds = (ms % 60000) // 1000
        millis = ms % 1000
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"

    @classmethod
    def generate_lrc(
        cls,
        aligned_blocks: List[AlignedBlock],
        tracks: Sequence[str],
        style: str = "multiline",  # 'multiline' or 'inline'
        inline_sep: str = " / ",
        filter_credits: bool = False,
        remove_empty: bool = True
    ) -> str:
        output_lines = []
        for block in aligned_blocks:
            text_items = []
            for track in tracks:
                val = block.get_track(track)
                if val:
                    text_items.append(val)

            if not text_items:
                if remove_empty:
                    continue
                else:
                    text_items = [""]

            ts = cls.ms_to_lrc(block.time_ms)
            if style == "multiline":
                for item in text_items:
                    output_lines.append(f"{ts}{item}")
            else:
                combined = inline_sep.join(text_items)
                output_lines.append(f"{ts}{combined}")

        return "\n".join(output_lines)

    @classmethod
    def generate_srt(
        cls,
        aligned_blocks: List[AlignedBlock],
        tracks: Sequence[str],
        max_duration_sec: float = 5.0,
        filter_credits: bool = False,
        remove_empty: bool = True
    ) -> str:
        valid_items = []
        for block in aligned_blocks:
            text_items = []
            for track in tracks:
                val = block.get_track(track)
                if val:
                    text_items.append(val)
            if not text_items and remove_empty:
                continue
            valid_items.append((block.time_ms, text_items))

        if not valid_items:
            return ""

        srt_blocks = []
        max_dur_ms = int(max(0.5, max_duration_sec) * 1000)

        for i, (start_ms, lines) in enumerate(valid_items):
            if i + 1 < len(valid_items):
                next_start_ms = valid_items[i + 1][0]
                gap = next_start_ms - start_ms
                if gap <= 0:
                    gap = 2000
                duration = min(gap, max_dur_ms)
                end_ms = start_ms + duration
            else:
                end_ms = start_ms + max_dur_ms

            time_header = f"{cls.ms_to_srt(start_ms)} --> {cls.ms_to_srt(end_ms)}"
            content = "\n".join(lines)
            srt_blocks.append(f"{i + 1}\n{time_header}\n{content}")

        return "\n\n".join(srt_blocks)
