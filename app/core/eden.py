"""Eden 用户目录、配置解析、游戏扫描。

本机实测的几条规则（不要照 yuzu 常识猜）：

* 数据根目录名可能是 ``eden`` 或 ``eglantine``（后者常是指向 eden 的 junction），
  以 ``qt-config.ini`` 里的 ``nand_directory`` / ``load_directory`` 为准；
* 存档比 yuzu 多一层：``nand\\user\\save\\<16位容器>\\<32位用户ID>\\<TitleID>``；
* 游戏目录在 ``Paths\\gamedirs\\N\\path``，**没有 0 号且不连续**，
  还混着 ``SDMC`` / ``UserNAND`` / ``SysNAND`` 三个伪目录；
* 标题名没有缓存（``icons\\`` 为空、``*.pv.txt`` 只有 mod 标签），只能从文件名解析。
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from .config import config_dir

ROM_EXTS = {".nsp", ".xci", ".nup", ".nsz", ".xcz"}
PSEUDO_DIRS = {"sdmc", "usernand", "sysnand"}
SKIP_DIR_HINTS = ("firmware", "cache", "contents", "registered", "placehld")

# 扫描结果的结构版本：字段/规则一变就 +1，让旧 gamelist.json 自动失效
SCHEMA = 2
CACHE_TTL = 300  # 秒；子目录里加文件不会改父目录 mtime，只能靠 TTL 兜一下

_TID = re.compile(r"\[([0-9A-Fa-f]{16})\]")
_TID16 = re.compile(r"^[0-9A-Fa-f]{16}$")
# 日志里最干净的来源：``Loading HWAoI (04003F40232DE000) ...``
_LOG_LOAD = re.compile(r"Loading (.+?) \(([0-9A-Fa-f]{16})\)")
# 备选：``Booting game: 04003F40232DE000 | HWAoI (64 位) |``
_LOG_BOOT = re.compile(r"Booting game:\s*([0-9A-Fa-f]{16})\s*\|\s*([^|]+)")
_ARCH = re.compile(r"\s*\((?:64|32)\s*位\)\s*$")
_names_cache: dict[str, str] = {}
_names_stamp = ""


# --------------------------------------------------------------------------- 配置
def read_qt_config() -> dict[str, str]:
    """把 qt-config.ini 读成扁平字典（键保留 ``Paths\\gamedirs\\1\\path`` 这种写法）。"""
    path = qt_config_ini()
    out: dict[str, str] = {}
    if not path.exists():
        return out
    try:
        text = path.read_text(encoding="utf-8", errors="surrogateescape")
    except Exception:
        return out
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(("[", ";", "#")) or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip().strip('"')
    return out


def qt_config_ini() -> Path:
    """优先找 eden / eglantine 两个候选里的 config\\qt-config.ini。"""
    roaming = os.environ.get("APPDATA")
    if not roaming:
        return Path.home() / "eden" / "config" / "qt-config.ini"
    best = None
    for name in ("eden", "eglantine", "Eglantine"):
        candidate = Path(roaming) / name / "config" / "qt-config.ini"
        if candidate.exists():
            if name == "eden":
                return candidate
            best = best or candidate
    return best or (Path(roaming) / "eden" / "config" / "qt-config.ini")


def data_root() -> Path:
    """模拟器用户数据根目录（含 nand / load / log 的那个）。"""
    cfg = read_qt_config()
    for key in ("nand_directory", "load_directory"):
        raw = cfg.get(key, "")
        if raw:
            p = Path(raw)
            if p.name.lower() == "nand":
                return p.parent
            if p.name.lower() == "load":
                return p.parent
    return qt_config_ini().parent.parent


def nand_dir() -> Path:
    cfg = read_qt_config()
    raw = cfg.get("nand_directory", "")
    return Path(raw) if raw else data_root() / "nand"


def load_dir() -> Path:
    cfg = read_qt_config()
    raw = cfg.get("load_directory", "")
    return Path(raw) if raw else data_root() / "load"


def save_root() -> Path:
    return nand_dir() / "user" / "save"


def log_dir() -> Path:
    return data_root() / "log"


# --------------------------------------------------------------------------- 游戏目录
def game_dirs() -> list[Path]:
    cfg = read_qt_config()
    out: list[Path] = []
    for key, value in cfg.items():
        if not key.lower().startswith("paths\\gamedirs\\") or not key.lower().endswith("\\path"):
            continue
        if value.strip().lower() in PSEUDO_DIRS:
            continue
        if not value or not Path(value).is_dir():
            continue
        p = Path(value)
        if p not in out:
            out.append(p)
    return out


def recent_files() -> list[Path]:
    cfg = read_qt_config()
    raw = cfg.get("Paths\\recentFiles", "")
    out: list[Path] = []
    for chunk in raw.split(","):
        item = chunk.strip().strip('"')
        if not item:
            continue
        p = Path(item)
        if p.exists() and p not in out:
            out.append(p)
    return out


# --------------------------------------------------------------------------- 扫描
@dataclass
class RomFile:
    path: Path
    title_id: str = ""
    kind: str = "base"  # base / update / dlc / unknown
    size: int = 0

    @property
    def title(self) -> str:
        return pretty_title(self.path.name)


@dataclass
class Game:
    key: str
    title_id: str = ""
    title: str = ""
    base: RomFile | None = None
    updates: list[RomFile] = field(default_factory=list)
    dlcs: list[RomFile] = field(default_factory=list)
    others: list[RomFile] = field(default_factory=list)
    play_time: int = 0
    last_played: int = 0
    # 是否被模拟器自己识别过（pv 缓存 / 启动记录 / 游玩时长 / 日志）。
    # 只在 load_games() 返回后赋值，**不写进缓存**，否则每玩一个新游戏缓存就失效。
    recognized: bool = False

    @property
    def size(self) -> int:
        files = ([self.base] if self.base else []) + self.updates + self.dlcs + self.others
        return sum(f.size for f in files)

    @property
    def launch_path(self) -> Path | None:
        if self.base is not None:
            return self.base.path
        for group in (self.updates, self.dlcs, self.others):
            if group:
                return group[0].path
        return None

    @property
    def installed(self) -> bool:
        return self.base is not None


def parse_title_id(name: str) -> str:
    hits = _TID.findall(name)
    return hits[-1].upper() if hits else ""


def base_id(title_id: str) -> str:
    try:
        value = int(title_id, 16)
    except ValueError:
        return title_id
    return f"{value - value % 0x1000:016X}"


def kind_of(title_id: str) -> str:
    try:
        value = int(title_id, 16)
    except ValueError:
        return "unknown"
    offset = value % 0x1000
    if offset == 0:
        return "base"
    if offset == 0x800:
        return "update"
    return "dlc"


_NOISE = re.compile(
    r"[\(\[][^\)\]]*(?:base|update|upd|dlc|v\d|\d+g)\b[^\)\]]*[\)\]]", re.IGNORECASE
)


def pretty_title(filename: str) -> str:
    text = Path(filename).stem
    text = re.sub(r"\[[^\]]*\]", " ", text)
    text = _NOISE.sub(" ", text)
    text = re.sub(r"\([^)]*\)$", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" -_.")
    return text or Path(filename).stem


def _walk(directory: Path, depth: int = 3, limit: int = 3000) -> list[Path]:
    found: list[Path] = []
    stack = [(directory, 0)]
    while stack and len(found) < limit:
        current, level = stack.pop()
        try:
            entries = list(os.scandir(current))
        except OSError:
            continue
        for entry in entries:
            if len(found) >= limit:
                break
            try:
                if entry.is_dir(follow_symlinks=False):
                    name = entry.name.lower()
                    if level + 1 < depth and not any(h in name for h in SKIP_DIR_HINTS):
                        stack.append((Path(entry.path), level + 1))
                elif entry.name.lower().endswith(tuple(ROM_EXTS)):
                    found.append(Path(entry.path))
            except OSError:
                continue
    return found


def scan_roms(dirs: list[Path] | None = None) -> list[RomFile]:
    roms: list[RomFile] = []
    seen: set[str] = set()
    for directory in dirs or game_dirs():
        for path in _walk(directory):
            key = str(path).lower()
            if key in seen or not path.is_file():
                continue
            seen.add(key)
            tid = parse_title_id(path.name)
            try:
                size = path.stat().st_size
            except OSError:
                size = 0
            roms.append(RomFile(path=path, title_id=tid, kind=kind_of(tid) if tid else "unknown", size=size))
    for path in recent_files():
        key = str(path).lower()
        if key in seen or not path.exists():
            continue
        seen.add(key)
        tid = parse_title_id(path.name)
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        roms.append(RomFile(path=path, title_id=tid, kind=kind_of(tid) if tid else "unknown", size=size))
    return roms


def launched() -> dict[str, dict]:
    path = data_root() / "cache" / "launched.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def play_times() -> dict[str, int]:
    """playtime.bin：每条 16 字节，TitleID(u64 LE) + 秒数(u64 LE)。"""
    path = data_root() / "play_time" / "playtime.bin"
    out: dict[str, int] = {}
    try:
        raw = path.read_bytes()
    except Exception:
        return out
    for i in range(0, len(raw) - 15, 16):
        chunk = raw[i : i + 16]
        tid = int.from_bytes(chunk[:8], "little")
        secs = int.from_bytes(chunk[8:], "little")
        if tid:
            out[f"{tid:016X}"] = secs
    return out


def title_names_from_log() -> dict[str, str]:
    """从模拟器日志里挖 TitleID → 名字。

    ``core\\core.cpp: Loading HWAoI (04003F40232DE000) ...`` 是最干净的来源；
    退一步用 ``Booting game: 04003F40232DE000 | HWAoI (64 位) |``。
    文件名不带 TitleID 的游戏（.nup）只能靠这个拿到名字。
    """
    global _names_cache, _names_stamp
    folder = log_dir()
    paths: list[Path] = []
    stamp: list[str] = []
    for name in ("eden_log.txt.old.txt", "eden_log.txt"):
        path = folder / name
        try:
            st = path.stat()
        except OSError:
            continue
        paths.append(path)
        stamp.append(f"{name}:{st.st_size}:{int(st.st_mtime)}")
    key = "|".join(stamp)
    if key == _names_stamp:
        return _names_cache

    out: dict[str, str] = {}
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for line in text.splitlines():
            hit = _LOG_LOAD.search(line)
            if hit:
                name = hit.group(1).strip()
                if name:
                    out[hit.group(2).upper()] = name
                continue
            boot = _LOG_BOOT.search(line)
            if boot:
                name = _ARCH.sub("", boot.group(2)).strip()
                if name:
                    out[boot.group(1).upper()] = name
    _names_cache, _names_stamp = out, key
    return out


def recognized_ids() -> set[str]:
    """模拟器自己“见过”的 TitleID 集合。

    四个来源取并集：``cache\\game_list\\<tid>.pv.txt``（文件存在即算，内容可能是空的）、
    ``cache\\launched.json`` 的键、``play_time`` 里时长 > 0 的、日志里出现过的。
    """
    ids: set[str] = set()
    try:
        for path in (data_root() / "cache" / "game_list").glob("*.pv.txt"):
            name = path.name.split(".")[0].upper()
            if _TID16.match(name):
                ids.add(name)
    except OSError:
        pass
    for tid in launched():
        if _TID16.match(str(tid)):
            ids.add(str(tid).upper())
    for tid, secs in play_times().items():
        if secs > 0:
            ids.add(tid.upper())
    ids.update(title_names_from_log().keys())
    return ids


def collect_games(roms: list[RomFile] | None = None) -> list[Game]:
    """把文件按 Base TitleID 合并成「一个游戏一行」。

    TitleID 的算术关系只对 Base/Update 可靠（Update = Base | 0x800）；
    DLC 是 ``Base + 0x1000 * n``，光看低 12 位会和 Base 撞车
    （``...11F000`` 是 DLC，低 12 位却是 0）。所以两遍走：
    先建 Base/Update 的家族，再把 DLC 往前减 0x1000 找父级。
    """
    roms = roms if roms is not None else scan_roms()
    launch_cache = launched()
    play_cache = play_times()

    games: dict[str, Game] = {}
    pending_dlc: list[RomFile] = []

    for rom in roms:
        if not rom.title_id:
            key = f"file:{str(rom.path).lower()}"
            game = games.setdefault(key, Game(key=key))
            game.others.append(rom)
            continue
        if rom.kind == "dlc":
            pending_dlc.append(rom)
            continue
        key = base_id(rom.title_id)
        game = games.setdefault(key, Game(key=key, title_id=key))
        if rom.kind == "base" and game.base is None:
            game.base = rom
        else:
            game.updates.append(rom)

    base_ids = {int(k, 16) for k in games if _TID16.match(k)}
    for rom in pending_dlc:
        parent = _parent_of(rom.title_id, base_ids)
        if parent is None:
            key = base_id(rom.title_id)
            game = games.setdefault(key, Game(key=key, title_id=key))
            game.dlcs.append(rom)
        else:
            key = f"{parent:016X}"
            game = games.setdefault(key, Game(key=key, title_id=key))
            game.dlcs.append(rom)

    for key, game in games.items():
        if game.title_id:
            game.title = game.title or _title_from(game)
            stat = launch_cache.get(game.title_id) or {}
            game.last_played = int(stat.get("timestamp") or 0)
            game.play_time = int(play_cache.get(game.title_id) or 0)
        else:
            game.title = game.title or (game.launch_path.stem if game.launch_path else key)
    items = list(games.values())
    items.sort(key=lambda g: (g.last_played, g.play_time, g.title.lower()), reverse=True)
    return items


def _parent_of(title_id: str, base_ids: set[int]) -> int | None:
    """DLC → Base：先对齐到 0x1000 边界，再一档档往前找。

    实测 DLC 是 ``Base + 0x1000`` 再带小序号（``...11F001`` / ``...11F002``），
    直接按 0x1000 递减永远碰不到 Base，必须先抹掉低位。
    """
    try:
        value = int(title_id, 16)
    except ValueError:
        return None
    floor = value - value % 0x1000
    for step in range(0, 32):
        candidate = floor - 0x1000 * step
        if candidate < 0:
            break
        if candidate in base_ids:
            return candidate
    return None


def _title_from(game: Game) -> str:
    for candidate in [game.base, *game.updates, *game.dlcs, *game.others]:
        if candidate is not None:
            text = candidate.title
            if text:
                return text
    return game.title_id


# --------------------------------------------------------------------------- 缓存
def _cache_file() -> Path:
    return config_dir() / "gamelist.json"


def _mark_recognized(games: list[Game]) -> list[Game]:
    try:
        ids = recognized_ids()
    except Exception:
        ids = set()
    for game in games:
        game.recognized = bool(game.title_id and game.title_id.upper() in ids)
    return games


def load_games(use_cache: bool = True) -> list[Game]:
    dirs = game_dirs()
    stamp = [f"v{SCHEMA}"]
    for d in dirs:
        try:
            st = d.stat()
            stamp.append(f"{d}|{int(st.st_mtime)}")
        except OSError:
            stamp.append(f"{d}|0")
    key = "||".join(stamp)

    cache = _cache_file()
    if use_cache and cache.exists():
        try:
            raw = json.loads(cache.read_text(encoding="utf-8"))
            fresh = time.time() - int(raw.get("at", 0)) < CACHE_TTL
            if raw.get("key") == key and fresh:
                games = [g for g in (_game_from_dict(i) for i in raw.get("games", [])) if g]
                if games:
                    return _mark_recognized(games)
        except Exception:
            pass

    games = collect_games()
    if not games:
        # 空结果不写缓存：网络盘掉线 / 权限异常时否则会永久返回空列表
        return games
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(
            json.dumps(
                {"key": key, "at": int(time.time()), "games": [_game_to_dict(g) for g in games]},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    except Exception:
        pass
    return _mark_recognized(games)


def _game_to_dict(game: Game) -> dict:
    def dump(rom: RomFile | None):
        if rom is None:
            return None
        return {
            "path": str(rom.path),
            "title_id": rom.title_id,
            "kind": rom.kind,
            "size": rom.size,
        }

    return {
        "key": game.key,
        "title_id": game.title_id,
        "title": game.title,
        "base": dump(game.base),
        "updates": [dump(r) for r in game.updates],
        "dlcs": [dump(r) for r in game.dlcs],
        "others": [dump(r) for r in game.others],
        "play_time": game.play_time,
        "last_played": game.last_played,
    }


def _rom_from_dict(raw: dict | None) -> RomFile | None:
    if not raw:
        return None
    path = raw.get("path")
    if not path:
        return None
    return RomFile(
        path=Path(path),
        title_id=raw.get("title_id", ""),
        kind=raw.get("kind", "unknown"),
        size=int(raw.get("size", 0)),
    )


def _game_from_dict(raw: dict) -> Game:
    return Game(
        key=raw.get("key", ""),
        title_id=raw.get("title_id", ""),
        title=raw.get("title", ""),
        base=_rom_from_dict(raw.get("base")),
        updates=[r for r in (_rom_from_dict(x) for x in raw.get("updates", [])) if r],
        dlcs=[r for r in (_rom_from_dict(x) for x in raw.get("dlcs", [])) if r],
        others=[r for r in (_rom_from_dict(x) for x in raw.get("others", [])) if r],
        play_time=int(raw.get("play_time", 0)),
        last_played=int(raw.get("last_played", 0)),
    )
