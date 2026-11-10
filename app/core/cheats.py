"""金手指文件管理。

Eden 沿用 yuzu 的约定：``load\\<TitleID>\\cheats\\<build_id>.txt``，
而且**每个 TitleID 只认一个活动文件** —— 所以"每个 txt 一个开关"行不通。

这里采取的方式：
* ``cheats\\`` 下允许多份任意命名的 txt（相当于片段/方案）；
* 把某一份"启用"＝复制成 ``<build_id>.txt``，上一份自动降级为 ``.disabled``；
* 编辑、导入、删除都只动这个目录，绝不碰同级的 ``romfs`` / ``exe­fs``（mod）。

build_id 不能从 .nsp 里读（NCA 头是加密的），只能从 Eden 日志里拿：
``build_id=659CB288...`` / ``No cheats file found for title_id=..., build_id=...``。
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from . import eden

_BOOT = re.compile(r"Booting game: ([0-9A-Fa-f]{16})")
_LINE_TID = re.compile(r"title_id[=: ]+([0-9A-Fa-f]{16})", re.IGNORECASE)
_PAIR = re.compile(
    r"title_id[=: ]+([0-9A-Fa-f]{16})[^\n]{0,80}?build_id[=: ]+([0-9A-Fa-f]{8,40})", re.IGNORECASE
)
_BUILD = re.compile(r"build_id[=: ]+([0-9A-Fa-f]{8,40})", re.IGNORECASE)
_TID = re.compile(r"([0-9A-Fa-f]{16})")

CODE_LINE = re.compile(r"^[0-9A-Fa-f]{8}(\s+[0-9A-Fa-f]{8})+")
GROUP_LINE = re.compile(r"^\[.*\]$")


@dataclass
class CheatFile:
    path: Path
    enabled: bool = False

    @property
    def label(self) -> str:
        name = self.path.name
        if name.lower().endswith(".disabled"):
            name = name[: -len(".disabled")]
        return name[:-4] if name.lower().endswith(".txt") else name


# --------------------------------------------------------------------------- 路径
def game_dir(title_id: str) -> Path:
    return eden.load_dir() / title_id.upper()


def cheats_dir(title_id: str, create: bool = False) -> Path:
    path = game_dir(title_id) / "cheats"
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def list_cheats(title_id: str) -> list[CheatFile]:
    folder = cheats_dir(title_id)
    if not folder.is_dir():
        return []
    out: list[CheatFile] = []
    for item in sorted(folder.iterdir()):
        if not item.is_file():
            continue
        low = item.name.lower()
        if low.endswith(".txt"):
            out.append(CheatFile(item, enabled=True))
        elif low.endswith(".txt.disabled"):
            out.append(CheatFile(item, enabled=False))
    return out


def active(title_id: str, build_id: str = "") -> CheatFile | None:
    folder = cheats_dir(title_id)
    if not folder.is_dir():
        return None
    if build_id:
        candidate = folder / f"{build_id}.txt"
        if candidate.exists():
            return CheatFile(candidate, True)
    for item in list_cheats(title_id):
        if item.enabled:
            return item
    return None


# --------------------------------------------------------------------------- build id
def build_ids_from_log() -> dict[str, str]:
    """从 Eden 日志里找「游戏 → build_id」。

    日志顺序是：``PatchExeFS: ... title_id=04003F40...`` → 若干
    ``HasNSOPatch: Querying ... build_id=... , name=main`` → 最后才 ``Booting game``。
    所以要用「最近一次出现的 title_id」来归属，不能等 Booting 行；
    同一游戏有多个 NSO，只认 ``name=main`` 那条。
    """
    mapping: dict[str, str] = {}
    guesses: dict[str, str] = {}
    folder = eden.log_dir()
    for name in ("eden_log.txt.old.txt", "eden_log.txt"):
        path = folder / name
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        current = ""
        for line in text.splitlines():
            pair = _PAIR.search(line)
            if pair:
                mapping[pair.group(1).upper()] = pair.group(2).upper()
                continue
            tid = _LINE_TID.search(line)
            if tid:
                current = tid.group(1).upper()
            boot = _BOOT.search(line)
            if boot:
                current = boot.group(1).upper()
            found = _BUILD.search(line)
            if found and current:
                build = found.group(1).upper()
                if "name=main" in line:
                    mapping[current] = build
                else:
                    guesses.setdefault(current, build)
    for key, value in guesses.items():
        mapping.setdefault(key, value)
    return mapping


def resolve_build_id(title_id: str, manual: str = "") -> str:
    if manual:
        return manual.strip().upper()
    mapping = build_ids_from_log()
    if title_id.upper() in mapping:
        return mapping[title_id.upper()]
    folder = cheats_dir(title_id)
    if folder.is_dir():
        for item in folder.glob("*.txt"):
            stem = item.stem
            if re.fullmatch(r"[0-9A-Fa-f]{8,40}", stem):
                return stem.upper()
    return ""


# --------------------------------------------------------------------------- 读写
def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def validate(text: str) -> list[str]:
    """返回可疑行（行号 + 内容），只提示不阻止保存。"""
    problems: list[str] = []
    for i, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith((";", "#", "//", "{")):
            continue
        if GROUP_LINE.match(line):
            continue
        if CODE_LINE.match(line):
            continue
        problems.append(f"第 {i} 行：{line[:40]}")
    return problems


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text.replace("\r\n", "\n"), encoding="utf-8", newline="\n")
    tmp.replace(path)


def _disabled_path(path: Path) -> Path:
    return path if path.name.lower().endswith(".disabled") else path.with_name(path.name + ".disabled")


def set_enabled(title_id: str, item: CheatFile, build_id: str) -> Path:
    """启用某一份：内容复制成 ``<build_id>.txt``，其余 ``.txt`` 降级为 ``.disabled``。

    Eden 每个 TitleID 只读一个 ``cheats\\<build_id>.txt``，所以"生效"只能靠文件名，
    不能靠目录或开关文件。
    """
    build_id = build_id.strip().upper()
    if not build_id:
        raise ValueError("还没有 build_id，无法确定文件名")
    folder = cheats_dir(title_id, create=True)
    target = folder / f"{build_id}.txt"

    # 先复制再降级，否则源文件已被改名，复制出来会是空的
    if item.path != target:
        if not item.path.exists():
            raise FileNotFoundError(item.path.name)
        shutil.copy2(item.path, target)

    for other in list_cheats(title_id):
        if not other.enabled:
            continue
        if other.path == target or other.path.stem.upper() == build_id:
            continue
        other.path.rename(_disabled_path(other.path))

    if item.path != target and item.path.exists():
        item.path.rename(_disabled_path(item.path))
    return target


def disable(title_id: str, build_id: str = "") -> bool:
    folder = cheats_dir(title_id)
    if not folder.is_dir():
        return False
    changed = False
    for item in list_cheats(title_id):
        if not item.enabled:
            continue
        if build_id and item.path.stem.upper() != build_id.upper():
            continue
        item.path.rename(_disabled_path(item.path))
        changed = True
    return changed


def create(title_id: str, name: str, text: str = "") -> Path:
    folder = cheats_dir(title_id, create=True)
    safe = re.sub(r'[\\/:*?"<>|]', "_", name.strip()) or "新金手指"
    path = folder / f"{safe}.txt"
    index = 1
    while path.exists():
        path = folder / f"{safe}-{index}.txt"
        index += 1
    write(path, text or "# 在这里粘贴金手指代码\n# 格式：\n# [组名]\n# 04000000 00000000 00000000\n")
    return path


def import_file(title_id: str, source: Path) -> Path:
    folder = cheats_dir(title_id, create=True)
    target = folder / source.name
    index = 1
    while target.exists():
        target = folder / f"{source.stem}-{index}{source.suffix}"
        index += 1
    shutil.copy2(source, target)
    return target


def remove(title_id: str, item: CheatFile) -> None:
    try:
        item.path.unlink()
    except OSError:
        pass


def summary(text: str) -> tuple[int, int]:
    """(组数, 代码行数)"""
    groups = 0
    codes = 0
    for raw in text.splitlines():
        line = raw.strip()
        if GROUP_LINE.match(line):
            groups += 1
        elif CODE_LINE.match(line):
            codes += 1
    return groups, codes


def game_ids_with_data() -> list[str]:
    """有 mod/金手指目录的游戏 TitleID。"""
    root = eden.load_dir()
    if not root.is_dir():
        return []
    return sorted(p.name.upper() for p in root.iterdir() if p.is_dir() and _TID.fullmatch(p.name))
