"""界面偏好：自定义游戏名、置顶、手动顺序、隐藏、TitleID 关联。

全部数据都存在工具配置（`Eglantine工具箱.json`）里，键名统一 `game_*`。
本模块不依赖 Qt，方便单独测试；修改后由调用方执行 `state.save()`。
"""

from __future__ import annotations

from typing import Iterable, Sequence

from . import eden

TITLES_KEY = "game_titles"
PINS_KEY = "game_pinned"
ORDER_KEY = "game_order"
HIDDEN_KEY = "game_hidden"
ASSOC_KEY = "game_assoc"
SHOW_ALL_KEY = "game_show_all"
SORT_KEY = "game_sort"

SORT_CUSTOM = 0
SORT_RECENT = 1
SORT_NAME = 2
SORT_SIZE = 3
DEFAULT_SORT = SORT_RECENT


# --------------------------------------------------------------------------- 基础
def _list(cfg: dict, key: str) -> list[str]:
    raw = cfg.get(key)
    if not isinstance(raw, list):
        return []
    return [str(x) for x in raw if isinstance(x, (str, int))]


def _map(cfg: dict, key: str) -> dict:
    raw = cfg.get(key)
    return dict(raw) if isinstance(raw, dict) else {}


def _norm(title_id: str) -> str:
    return (title_id or "").strip().upper()


# --------------------------------------------------------------------------- 名字
def display_title(cfg: dict, title_id: str, fallback: str = "") -> str:
    """自定义名 → 扫描出的标题 → 模拟器日志名 → 「未知游戏」。"""
    tid = _norm(title_id)
    if tid:
        custom = _map(cfg, TITLES_KEY).get(tid)
        if isinstance(custom, str) and custom.strip():
            return custom.strip()
    if fallback:
        return fallback
    if tid:
        name = eden.title_names_from_log().get(tid)
        if name:
            return name
        return f"未知游戏（{tid[:8]}…）"
    return "未知游戏"


def custom_title(cfg: dict, title_id: str) -> str:
    return _map(cfg, TITLES_KEY).get(_norm(title_id), "")


def set_title(cfg: dict, title_id: str, name: str) -> None:
    tid = _norm(title_id)
    if not tid:
        return
    titles = _map(cfg, TITLES_KEY)
    name = (name or "").strip()
    if name:
        titles[tid] = name
    else:
        titles.pop(tid, None)
    cfg[TITLES_KEY] = titles


def clear_title(cfg: dict, title_id: str) -> None:
    set_title(cfg, title_id, "")


# --------------------------------------------------------------------------- 置顶
def is_pinned(cfg: dict, key: str) -> bool:
    return key in _list(cfg, PINS_KEY)


def pin(cfg: dict, key: str) -> None:
    pins = _list(cfg, PINS_KEY)
    if key not in pins:
        pins.append(key)
    cfg[PINS_KEY] = pins


def unpin(cfg: dict, key: str) -> None:
    cfg[PINS_KEY] = [k for k in _list(cfg, PINS_KEY) if k != key]


# --------------------------------------------------------------------------- 顺序
def set_order(cfg: dict, keys: Sequence[str]) -> None:
    cfg[ORDER_KEY] = list(dict.fromkeys(keys))


def hide(cfg: dict, key: str) -> None:
    items = _list(cfg, HIDDEN_KEY)
    if key not in items:
        items.append(key)
    cfg[HIDDEN_KEY] = items


def unhide(cfg: dict, key: str) -> None:
    cfg[HIDDEN_KEY] = [k for k in _list(cfg, HIDDEN_KEY) if k != key]


def hidden(cfg: dict) -> set[str]:
    return set(_list(cfg, HIDDEN_KEY))


def show_all(cfg: dict) -> bool:
    return bool(cfg.get(SHOW_ALL_KEY))


def set_show_all(cfg: dict, value: bool) -> None:
    cfg[SHOW_ALL_KEY] = bool(value)


def sort_mode(cfg: dict) -> int:
    try:
        mode = int(cfg.get(SORT_KEY, DEFAULT_SORT))
    except (TypeError, ValueError):
        return DEFAULT_SORT
    return mode if mode in (SORT_CUSTOM, SORT_RECENT, SORT_NAME, SORT_SIZE) else DEFAULT_SORT


def set_sort(cfg: dict, mode: int) -> None:
    cfg[SORT_KEY] = int(mode)


# --------------------------------------------------------------------------- 关联
def assoc_tid(cfg: dict, path) -> str:
    return _map(cfg, ASSOC_KEY).get(str(path).lower(), "")


def set_assoc(cfg: dict, path, title_id: str) -> None:
    table = _map(cfg, ASSOC_KEY)
    key = str(path).lower()
    tid = _norm(title_id)
    if tid:
        table[key] = tid
    else:
        table.pop(key, None)
    cfg[ASSOC_KEY] = table


# --------------------------------------------------------------------------- 排序
def _auto_key(mode: int):
    if mode == SORT_NAME:
        return lambda g: (g.title.lower(), g.key)
    if mode == SORT_SIZE:
        return lambda g: (-g.size, g.key)
    if mode == SORT_CUSTOM:
        return lambda g: (0,)
    return lambda g: (-g.last_played, -g.play_time, g.key)


def order_games(games: Sequence, cfg: dict, mode: int) -> list:
    """置顶组（按置顶先后）→ 手动顺序表 → 其余按 mode 自动排序。"""
    pin_index = {k: i for i, k in enumerate(_list(cfg, PINS_KEY))}
    manual = {k: i for i, k in enumerate(_list(cfg, ORDER_KEY))}
    auto = list(games) if mode == SORT_CUSTOM else sorted(games, key=_auto_key(mode))
    auto_pos = {id(g): i for i, g in enumerate(auto)}

    def rank(game):
        if game.key in pin_index:
            return (0, pin_index[game.key], auto_pos[id(game)])
        if game.key in manual:
            return (1, manual[game.key], auto_pos[id(game)])
        return (2, auto_pos[id(game)])

    return sorted(games, key=rank)


# --------------------------------------------------------------------------- 清理
def prune(cfg: dict, keys: Iterable[str]) -> bool:
    """删掉已不存在的 key（只在扫描成功且非空时调用）。返回是否有改动。

    关联表（assoc）按文件路径存，与这里的 key 不同域，不做清理：
    文件只是临时离线时把关联删掉，用户得重新指定一次。
    """
    alive = set(keys)
    changed = False
    for name in (PINS_KEY, ORDER_KEY, HIDDEN_KEY):
        items = _list(cfg, name)
        kept = [k for k in items if k in alive]
        if kept != items:
            cfg[name] = kept
            changed = True
    return changed
