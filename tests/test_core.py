import os
import sys
import unittest

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.core import NetEaseLyricFetcher, LAYOUT_OPTIONS


class TestNetEaseLyricCore(unittest.TestCase):
    def test_extract_song_id(self):
        cases = [
            ("536622304", 536622304),
            ("https://music.163.com/#/song?id=536622304", 536622304),
            ("https://music.163.com/song?id=536622304&userid=123", 536622304),
            ("https://y.music.163.com/m/song?id=186016", 186016),
            ("https://y.music.163.com/m/song/186016/", 186016),
            ("分享米津玄師的单曲《Lemon》https://music.163.com/song?id=536622304 (来自@网易云音乐)", 536622304),
        ]
        for inp, expected in cases:
            self.assertEqual(NetEaseLyricFetcher.extract_song_id(inp), expected)

    def test_ms_conversions(self):
        ms = 68851  # 1分08秒851毫秒
        self.assertEqual(NetEaseLyricFetcher.ms_to_lrc(ms), "[01:08.85]")
        self.assertEqual(NetEaseLyricFetcher.ms_to_srt(ms), "00:01:08,851")

    def test_full_lyrics_retention(self):
        raw = {
            'orig': (
                '[00:00.00]音乐制作 : ChiliChill乐团\n'
                '[00:00.92]作曲 : ChiliChill乐团\n'
                '[00:01.84]作词 : ChiliChill乐团\n'
                '[00:11.46]第一句正文歌词今天天气真好'
            ),
            'trans': '',
            'roma': '',
        }
        aligned = NetEaseLyricFetcher.align_lyrics(raw)
        lrc_out = NetEaseLyricFetcher.generate_lrc(aligned, ('orig',))
        # 完整保留制作人员名单与正文
        self.assertIn("音乐制作 : ChiliChill乐团", lrc_out)
        self.assertIn("作曲 : ChiliChill乐团", lrc_out)
        self.assertIn("第一句正文歌词今天天气真好", lrc_out)

    def test_srt_custom_float_duration(self):
        raw = {
            'orig': '[00:01.00]Hello world\n[00:10.00]Next sentence',
            'trans': '',
            'roma': '',
        }
        aligned = NetEaseLyricFetcher.align_lyrics(raw)
        # 传入浮点数时长 3.5 秒
        srt_out = NetEaseLyricFetcher.generate_srt(aligned, ('orig',), max_duration_sec=3.5)
        self.assertIn("00:00:01,000 --> 00:00:04,500", srt_out)

    def test_live_song_fetch(self):
        song_id = 536622304
        info = NetEaseLyricFetcher.fetch_song_info(song_id)
        self.assertEqual(info.title, "Lemon")
        self.assertTrue(len(info.artists) > 0)

        raw = NetEaseLyricFetcher.fetch_raw_lyrics(song_id)
        self.assertTrue(bool(raw['orig']))
        self.assertTrue(bool(raw['trans']))
        self.assertTrue(bool(raw['roma']))

        aligned = NetEaseLyricFetcher.align_lyrics(raw)
        self.assertTrue(len(aligned) > 30)


if __name__ == '__main__':
    unittest.main()
