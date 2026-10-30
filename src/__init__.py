"""
NetEase Lyrics & Subtitle Extractor
====================================
A tool to extract, format, and align bilingual/trilingual NetEase Cloud Music lyrics.
"""

__version__ = "1.0.0"
__author__ = "NetEase Lyrics Extractor Contributors"

from src.core import (
    SongInfo,
    AlignedBlock,
    LAYOUT_OPTIONS,
    LAYOUT_MAP,
    NetEaseLyricFetcher
)

__all__ = [
    "SongInfo",
    "AlignedBlock",
    "LAYOUT_OPTIONS",
    "LAYOUT_MAP",
    "NetEaseLyricFetcher"
]
