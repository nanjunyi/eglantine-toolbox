"""Qt6 .qm 文件解析与编码（纯 Python，无需 Qt 工具链）

格式要点（依据 qtbase/src/corelib/kernel/qtranslator.cpp）：
    文件 = 16 字节 magic + 若干 section + 结尾 0x00
    section = tag(1) + blockLen(4, BE) + data(blockLen)
        tag 0x2f = Contexts      （名称表，可省略）
        tag 0x42 = Hashes        （每条 8 字节：hash(4) + messageOffset(4)，按 hash 升序）
        tag 0x69 = Messages      （消息记录区）
        tag 0x88 = NumerusRules
        tag 0x96 = Dependencies
        tag 0xa7 = Language      （UTF-8）
    消息记录 = 若干 [tag(1) + len(4, BE) + data(len)]，以 Tag_End(0x01) 单字节结束
        tag 3 = Translation   data = UTF-16BE，len 为字节数（必须偶数），复数时按序多条
        tag 6 = SourceText    data = UTF-8
        tag 7 = Context       data = UTF-8
        tag 8 = Comment       data = UTF-8
        tag 5 = Obsolete1     跳过 4 字节
    hash = elfHash(sourceText + comment)，为 0 时取 1
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

MAGIC = bytes.fromhex("3cb86418caef9c95cd211cbf60a1bddd")

TAG_END_SECTION = 0x00
TAG_CONTEXTS = 0x2F
TAG_HASHES = 0x42
TAG_MESSAGES = 0x69
TAG_NUMERUS = 0x88
TAG_DEPS = 0x96
TAG_LANGUAGE = 0xA7

T_END = 1
T_SOURCE16 = 2
T_TRANSLATION = 3
T_CONTEXT16 = 4
T_OBSOLETE1 = 5
T_SOURCE = 6
T_CONTEXT = 7
T_COMMENT = 8
T_OBSOLETE2 = 9


@dataclass
class Message:
    context: str = ""
    source: str = ""
    comment: str = ""
    translations: list[str] = field(default_factory=list)

    @property
    def translation(self) -> str:
        return self.translations[0] if self.translations else ""


@dataclass
class QmFile:
    language: str = ""
    messages: list[Message] = field(default_factory=list)
    numerus_rules: bytes = b""
    dependencies: list[str] = field(default_factory=list)


def _u32(b: bytes, i: int) -> int:
    return struct.unpack_from(">I", b, i)[0]


def _u16(b: bytes, i: int) -> int:
    return struct.unpack_from(">H", b, i)[0]


def elf_hash(source: str, comment: str = "") -> int:
    h = 0
    for part in (source, comment):
        for ch in part.encode("utf-8"):
            h = ((h << 4) + ch) & 0xFFFFFFFF
            g = h & 0xF0000000
            if g:
                h ^= g >> 24
            h &= ~g & 0xFFFFFFFF
    return h or 1


# --------------------------------------------------------------------------- 解析


def _parse_record(data: bytes, pos: int) -> tuple[Message | None, int]:
    msg = Message()
    n = len(data)
    while pos < n:
        tag = data[pos]
        pos += 1
        if tag == T_END:
            return (msg if msg.source or msg.translations else None), pos
        if tag == T_OBSOLETE1:
            pos += 4
            continue
        if pos + 4 > n:
            return None, n
        length = _u32(data, pos)
        pos += 4
        chunk = data[pos : pos + length]
        pos += length
        if tag == T_TRANSLATION:
            if length % 2:
                msg.translations.append(chunk.decode("utf-16-be", "replace"))
            else:
                msg.translations.append(chunk.decode("utf-16-be", "replace"))
        elif tag == T_SOURCE:
            msg.source = chunk.decode("utf-8", "replace")
        elif tag == T_CONTEXT:
            msg.context = chunk.decode("utf-8", "replace")
        elif tag == T_COMMENT:
            msg.comment = chunk.decode("utf-8", "replace")
        elif tag in (T_SOURCE16, T_CONTEXT16, T_OBSOLETE2):
            continue
        else:
            # 未知 tag：认为该记录结束
            return (msg if msg.source else None), pos
    return (msg if msg.source else None), n


def parse(blob: bytes) -> QmFile:
    if not blob.startswith(MAGIC):
        raise ValueError("不是合法的 .qm 文件（magic 不匹配）")

    qm = QmFile()
    hashes = b""
    messages = b""

    pos = 16
    while pos + 5 <= len(blob):
        tag = blob[pos]
        if tag == TAG_END_SECTION:
            break
        length = _u32(blob, pos + 1)
        body = blob[pos + 5 : pos + 5 + length]
        if tag == TAG_LANGUAGE:
            qm.language = body.decode("utf-8", "replace")
        elif tag == TAG_HASHES:
            hashes = body
        elif tag == TAG_MESSAGES:
            messages = body
        elif tag == TAG_NUMERUS:
            qm.numerus_rules = body
        elif tag == TAG_DEPS:
            qm.dependencies = _parse_dependencies(body)
        pos += 5 + length

    # 按 offset 顺序解析消息记录
    seen: list[int] = []
    count = len(hashes) // 8
    for i in range(count):
        off = _u32(hashes, i * 8 + 4)
        if off not in seen:
            seen.append(off)
    for off in sorted(seen):
        msg, _ = _parse_record(messages, off)
        if msg is not None:
            qm.messages.append(msg)
    return qm


def _parse_dependencies(body: bytes) -> list[str]:
    """Dependencies 段用 QDataStream 序列化的 QString（UTF-16BE，u32 长度=字符数）。"""
    out = []
    pos = 0
    while pos + 4 <= len(body):
        n = _u32(body, pos)
        pos += 4
        if n == 0xFFFFFFFF or pos + n * 2 > len(body):
            break
        out.append(body[pos : pos + n * 2].decode("utf-16-be", "replace"))
        pos += n * 2
    return out


# --------------------------------------------------------------------------- 编码


def _enc_translation(text: str) -> bytes:
    raw = text.encode("utf-16-be")
    return bytes([T_TRANSLATION]) + struct.pack(">I", len(raw)) + raw


def _enc_utf8(field_tag: int, text: str) -> bytes:
    raw = text.encode("utf-8")
    return bytes([field_tag]) + struct.pack(">I", len(raw)) + raw


def encode(qm: QmFile) -> bytes:
    # 1) 生成消息记录区，并记录每条记录的 (hash, offset)
    msg_buf = bytearray()
    entries: list[tuple[int, int]] = []

    ordered = sorted(
        qm.messages,
        key=lambda m: (elf_hash(m.source, m.comment), m.context, m.source),
    )
    for msg in ordered:
        if not msg.translations and not msg.source:
            continue
        offset = len(msg_buf)
        rec = bytearray()
        for tr in msg.translations:
            rec += _enc_translation(tr)
        if msg.comment:
            rec += _enc_utf8(T_COMMENT, msg.comment)
        if msg.source:
            rec += _enc_utf8(T_SOURCE, msg.source)
        if msg.context:
            rec += _enc_utf8(T_CONTEXT, msg.context)
        rec.append(T_END)
        msg_buf += rec
        entries.append((elf_hash(msg.source, msg.comment), offset))

    entries.sort()

    hash_buf = bytearray()
    for h, off in entries:
        hash_buf += struct.pack(">II", h, off)

    out = bytearray(MAGIC)
    out += bytes([TAG_HASHES]) + struct.pack(">I", len(hash_buf)) + hash_buf
    out += bytes([TAG_MESSAGES]) + struct.pack(">I", len(msg_buf)) + bytes(msg_buf)
    if qm.numerus_rules:
        out += bytes([TAG_NUMERUS]) + struct.pack(">I", len(qm.numerus_rules)) + qm.numerus_rules
    if qm.dependencies:
        dep = bytearray()
        for d in qm.dependencies:
            raw = d.encode("utf-16-be")
            dep += struct.pack(">I", len(raw) // 2) + raw
        out += bytes([TAG_DEPS]) + struct.pack(">I", len(dep)) + bytes(dep)
    if qm.language:
        raw = qm.language.encode("utf-8")
        out += bytes([TAG_LANGUAGE]) + struct.pack(">I", len(raw)) + raw
    out.append(TAG_END_SECTION)
    return bytes(out)


def load(path) -> QmFile:
    from pathlib import Path

    return parse(Path(path).read_bytes())


def save(qm: QmFile, path) -> None:
    from pathlib import Path

    Path(path).write_bytes(encode(qm))
