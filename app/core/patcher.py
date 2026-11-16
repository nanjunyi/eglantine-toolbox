"""把 eglantine.exe 的 Qt 资源路径重定向到程序目录下的 languages 文件夹。

程序里的语言路径是 UTF-16LE 的 QStringLiteral。历史形态：
    旧版两处  ":/languages"（语言下拉框遍历目录） + ":/languages/"（QTranslator 拼 <语言码>.qm）
    新版一处  ":/languages"（daily-20261114 起，另一处变成不带冒号的 "/languages"）
把命中处首字符 ':' 改成 '.'（0x003A → 0x002E）即变成相对路径：
    ":/languages" → "./languages"
长度完全不变，不动任何代码逻辑，因此可以逐字节还原。

本模块按「锚点出现几次就改几次」工作，**不假设固定数量**：上游随时可能增删这处字面量，
数量对不上不该让整次安装失败。一处都找不到时视为该版本无需改写（中文由 exe 内嵌的
官方语言包提供），照常继续。
"""

from __future__ import annotations

import shutil
from pathlib import Path

# UTF-16LE 的 ":/languages"
ANCHOR = bytes.fromhex("3A00" + "2F006C0061006E00670075006100670065007300")
# 同一位置改成 './languages'
PATCHED = bytes.fromhex("2E00" + ANCHOR[2:].hex())

# 兼容旧名（外部只引用了 BACKUP_SUFFIX / PatchError，这里保留别名以防遗漏）
ORIGINAL = ANCHOR

BACKUP_SUFFIX = ".zhbak"

_STATE_CACHE: dict[tuple[str, float, int], str] = {}


class PatchError(RuntimeError):
    pass


def backup_path(exe: Path) -> Path:
    exe = Path(exe)
    return exe.with_suffix(exe.suffix + BACKUP_SUFFIX)


def counts(data: bytes) -> tuple[int, int]:
    """返回 (未重定向处数, 已重定向处数)。"""
    return data.count(ANCHOR), data.count(PATCHED)


def probe(exe: Path) -> dict:
    """只读探测：计数 + 状态，不写盘。"""
    exe = Path(exe)
    if not exe.exists():
        return {"orig": 0, "patched": 0, "state": "missing"}
    orig, patched = counts(exe.read_bytes())
    return {"orig": orig, "patched": patched, "state": _classify(orig, patched)}


def _classify(orig: int, patched: int) -> str:
    if orig == 0 and patched == 0:
        return "no-anchor"
    if patched >= 1 and orig == 0:
        return "patched"
    if orig >= 1 and patched == 0:
        return "vanilla"
    return "unknown"  # 两种形态同时存在：外部改动过，状态可疑


def is_patched(exe: Path) -> bool:
    exe = Path(exe)
    if not exe.exists():
        return False
    return _classify(*counts(exe.read_bytes())) == "patched"


def state(exe: Path) -> str:
    """'patched' / 'vanilla' / 'no-anchor' / 'unknown' / 'missing'"""
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
    result = _classify(*counts(exe.read_bytes()))
    _STATE_CACHE.clear()
    _STATE_CACHE[key] = result
    return result


def apply_patch(exe: Path, log=print) -> int:
    """打补丁；返回写入的处数。

    - 已打过 → 0
    - 找不到锚点（该版本可能已改为从程序目录读取）→ 0，只记日志，不中止
    - 首次改写前自动备份为 .zhbak
    """
    exe = Path(exe)
    if not exe.exists():
        raise PatchError(f"找不到 {exe.name}")

    data = bytearray(exe.read_bytes())
    orig, patched = counts(bytes(data))

    if orig == 0 and patched == 0:
        log("这个版本里没有「语言路径」特征，跳过改写（界面中文由程序内嵌语言包提供）")
        return 0
    if patched >= 1 and orig == 0:
        log("补丁已存在，无需重复处理")
        return 0
    if patched:
        raise PatchError(
            f"检测到 {patched} 处已重定向、{orig} 处未重定向，文件状态可疑，已中止。"
            "可先用「还原为官方原版」恢复后再试。"
        )

    bak = backup_path(exe)
    if not bak.exists():
        shutil.copy2(exe, bak)
        log(f"已备份官方原版 → {bak.name}")
    else:
        log(f"沿用已有备份 {bak.name}")

    offsets: list[int] = []
    start = 0
    while True:
        idx = data.find(ANCHOR, start)
        if idx < 0:
            break
        data[idx] = 0x2E  # ':' -> '.'
        offsets.append(idx)
        start = idx + len(ANCHOR)

    exe.write_bytes(bytes(data))
    log(
        f"已重定向 {len(offsets)} 处语言路径"
        f"（偏移 {', '.join(hex(i) for i in offsets)}）"
    )
    return len(offsets)


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
    if patched == 0:
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
