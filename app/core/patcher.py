"""把 eglantine.exe 的 Qt 资源路径重定向到程序目录下的 languages 文件夹。

程序里两处 QStringLiteral（UTF-16LE）：
    ":/languages"   语言下拉框用它遍历目录
    ":/languages/"  QTranslator 用它拼接 <语言码>.qm
把每处首字符 ':' 改成 '.'（0x003A → 0x002E）即变成相对路径：
    "./languages" / "./languages/"
长度完全不变，不动任何代码逻辑，因此可以逐字节还原。
"""

from __future__ import annotations

import shutil
from pathlib import Path

# UTF-16LE 的 ":/languages"
ORIGINAL = bytes.fromhex("3A00" + "2F006C0061006E00670075006100670065007300")
PATCHED = bytes.fromhex("2E00" + ORIGINAL[2:].hex())

BACKUP_SUFFIX = ".zhbak"

_STATE_CACHE: dict[tuple[str, float, int], str] = {}


class PatchError(RuntimeError):
    pass


def backup_path(exe: Path) -> Path:
    exe = Path(exe)
    return exe.with_suffix(exe.suffix + BACKUP_SUFFIX)


def counts(data: bytes) -> tuple[int, int]:
    return data.count(ORIGINAL), data.count(PATCHED)


def is_patched(exe: Path) -> bool:
    exe = Path(exe)
    if not exe.exists():
        return False
    orig, patched = counts(exe.read_bytes())
    return patched >= 2 and orig == 0


def state(exe: Path) -> str:
    """'patched' / 'vanilla' / 'unknown' / 'missing'"""
    exe = Path(exe)
    if not exe.exists():
        return "missing"
    try:
        st = exe.stat()
    except OSError:
        return "missing"
    key = (str(exe), st.st_mtime, st.st_size)
    cached = _STATE_CACHE.get(key)
    if cached:
        return cached
    orig, patched = counts(exe.read_bytes())
    if patched >= 2 and orig == 0:
        result = "patched"
    elif orig >= 2 and patched == 0:
        result = "vanilla"
    else:
        result = "unknown"
    _STATE_CACHE.clear()
    _STATE_CACHE[key] = result
    return result


def apply_patch(exe: Path, log=print) -> int:
    """打补丁；返回写入的处数（已打过则返回 0）。首次自动备份为 .zhbak。"""
    exe = Path(exe)
    if not exe.exists():
        raise PatchError(f"找不到 {exe.name}")

    data = bytearray(exe.read_bytes())
    orig, patched = counts(bytes(data))

    if patched >= 2 and orig == 0:
        log("补丁已存在，无需重复处理")
        return 0
    if orig < 2:
        raise PatchError(
            f"只在 exe 中找到 {orig} 处语言路径特征（预期 2 处），可能是新版改动了实现。"
            "已中止，未修改文件。"
        )
    if patched:
        raise PatchError(
            f"检测到 {patched} 处已重定向、{orig} 处未重定向，文件状态可疑，已中止。"
        )

    bak = backup_path(exe)
    if not bak.exists():
        shutil.copy2(exe, bak)
        log(f"已备份官方原版 → {bak.name}")
    else:
        log(f"沿用已有备份 {bak.name}")

    hits = 0
    start = 0
    while True:
        idx = data.find(ORIGINAL, start)
        if idx < 0:
            break
        data[idx] = 0x2E  # ':' -> '.'
        hits += 1
        start = idx + len(ORIGINAL)

    exe.write_bytes(bytes(data))
    log(f"已重定向 {hits} 处语言路径（偏移 {', '.join(hex(i) for i in _offsets(exe))}）")
    return hits


def _offsets(exe: Path) -> list[int]:
    data = Path(exe).read_bytes()
    out, start = [], 0
    while True:
        idx = data.find(PATCHED, start)
        if idx < 0:
            break
        # 只认完整字面量起点：前一字节不是 UTF-16 的字符低位
        out.append(idx)
        start = idx + len(PATCHED)
    return out


def restore(exe: Path, log=print) -> str:
    """还原为官方原版，返回还原方式说明。"""
    exe = Path(exe)
    if not exe.exists():
        raise PatchError(f"找不到 {exe.name}")

    bak = backup_path(exe)
    if bak.exists():
        if exe.read_bytes() == bak.read_bytes():
            log("当前 exe 与官方备份完全一致，无需还原")
            return "already"
        shutil.copy2(bak, exe)
        log(f"已从备份还原 {exe.name}")
        return "backup"

    # 没有备份时，反向替换（把 './languages' 改回 ':/languages'）
    data = bytearray(exe.read_bytes())
    orig, patched = counts(bytes(data))
    if patched < 2:
        log("没有备份，且当前文件未打补丁，视为官方原版")
        return "already"
    hits = 0
    start = 0
    while True:
        idx = data.find(PATCHED, start)
        if idx < 0:
            break
        data[idx] = 0x3A  # '.' -> ':'
        hits += 1
        start = idx + len(PATCHED)
    exe.write_bytes(bytes(data))
    log(f"没有备份文件，已通过反向替换还原 {hits} 处路径")
    return "reverse"
