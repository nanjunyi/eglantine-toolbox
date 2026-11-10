"""从 eglantine.exe 提取内嵌的 Qt 翻译包（.qm）。

Qt 的 .qm 结构：16 字节 magic + 若干 [tag:u8][len:u32 BE][data] 段 + 结尾 0x00。
rcc 打包时文件未压缩，因此按 magic 定位、按段表走一遍即可拿到完整字节流。
"""

from __future__ import annotations

import struct
from pathlib import Path

MAGIC = bytes.fromhex("3cb86418caef9c95cd211cbf60a1bddd")

TAG_CONTEXTS = 0x69   # rcc/extract 视角：Messages 段（历史命名沿用）
TAG_MESSAGES = 0x42
TAG_NUMERUS = 0x2F
TAG_DEPS = 0x88
TAG_LANGUAGE = 0xA7
TAG_END = 0x00

KNOWN_TAGS = {TAG_CONTEXTS, TAG_MESSAGES, TAG_NUMERUS, TAG_DEPS, TAG_LANGUAGE, TAG_END}


def walk_qm(data: bytes, offset: int, limit: int = 8 * 1024 * 1024):
    if data[offset : offset + 16] != MAGIC:
        return None, 0
    sections: dict[int, bytes] = {}
    pos = offset + 16
    end = len(data)
    while pos + 5 <= end:
        tag = data[pos]
        if tag not in KNOWN_TAGS:
            return None, 0
        if tag == TAG_END:
            return sections, (pos - offset) + 1
        length = struct.unpack(">I", data[pos + 1 : pos + 5])[0]
        if length <= 0 or length > limit or pos + 5 + length > end:
            return None, 0
        sections.setdefault(tag, data[pos + 5 : pos + 5 + length])
        pos += 5 + length
    return None, 0


def find_all_qm(data: bytes):
    found = []
    start = 0
    while True:
        idx = data.find(MAGIC, start)
        if idx < 0:
            break
        sections, size = walk_qm(data, idx)
        if sections is not None:
            lang = sections.get(TAG_LANGUAGE, b"").decode("utf-8", "replace") or "unknown"
            found.append((idx, size, lang, sections))
            start = idx + max(size, 16)
        else:
            start = idx + 16
    return found


def extract_packs(exe: Path) -> dict[str, bytes]:
    """返回 {语言码: qm 字节}；同语言多个副本时取第一个。"""
    data = Path(exe).read_bytes()
    packs: dict[str, bytes] = {}
    for offset, size, lang, _sections in find_all_qm(data):
        packs.setdefault(lang, data[offset : offset + size])
    return packs


def extract_pack(exe: Path, lang: str = "zh_CN") -> bytes:
    packs = extract_packs(exe)
    if lang not in packs:
        raise LookupError(f"{Path(exe).name} 中没有内嵌 {lang}.qm（该版本可能未内置翻译）")
    return packs[lang]
