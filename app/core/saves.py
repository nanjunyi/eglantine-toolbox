"""存档备份 / 还原 / 导入 / 导出。

Eden 的存档层级（实测）：``nand\\user\\save\\<16位容器>\\<32位用户ID>\\<16位TitleID>\\``。
比 yuzu 多一层用户 ID，不能写死。``nand\\user\\save\\cache`` 与 ``nand\\system\\save``
不属于游戏存档，本模块不碰。

还原用「同卷临时目录 + 改名」三段式，失败能反向回滚；
还原前必定先自动做一份 ``_auto-before-restore`` 快照。
"""

from __future__ import annotations

import json
import os
import shutil
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from ..constants import DISPLAY_NAME

from . import eden
from .common import human_size

CONTAINER = "0000000000000000"
TMP_PREFIX = ".egl-tmp-"
BAK_PREFIX = ".egl-bak-"
AUTO_PREFIX = "_auto-before-restore-"


class SaveError(RuntimeError):
    pass


@dataclass
class SaveEntry:
    title_id: str
    uid: str
    path: Path
    size: int = 0
    files: int = 0
    mtime: float = 0.0


@dataclass
class Backup:
    path: Path
    title_id: str = ""
    uid: str = ""
    created: float = 0.0
    size: int = 0
    files: int = 0
    note: str = ""
    auto: bool = False

    @property
    def when(self) -> str:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.created or self.path.stat().st_mtime))


@dataclass
class RestoreResult:
    path: Path
    files: int = 0
    snapshot: Path | None = None
    previous: Path | None = None


# --------------------------------------------------------------------------- 定位
def container_dir() -> Path:
    return eden.save_root() / CONTAINER


def user_ids() -> list[str]:
    root = container_dir()
    if not root.is_dir():
        return []
    out = []
    for entry in root.iterdir():
        if entry.is_dir() and len(entry.name) == 32 and entry.name.upper() == entry.name:
            out.append(entry.name)
    return out or []


def _dir_stats(path: Path) -> tuple[int, int]:
    size = files = 0
    for base, _dirs, names in os.walk(path):
        for name in names:
            try:
                size += (Path(base) / name).stat().st_size
                files += 1
            except OSError:
                continue
    return size, files


def list_saves() -> list[SaveEntry]:
    out: list[SaveEntry] = []
    root = container_dir()
    if not root.is_dir():
        return out
    for uid in user_ids():
        uid_dir = root / uid
        for game_dir in sorted(p for p in uid_dir.iterdir() if p.is_dir()):
            if not game_dir.name or game_dir.name.startswith("."):
                continue
            size, files = _dir_stats(game_dir)
            out.append(
                SaveEntry(
                    title_id=game_dir.name.upper(),
                    uid=uid,
                    path=game_dir,
                    size=size,
                    files=files,
                    mtime=game_dir.stat().st_mtime,
                )
            )
    out.sort(key=lambda e: e.mtime, reverse=True)
    return out


def save_path(title_id: str, uid: str | None = None) -> Path | None:
    title_id = title_id.upper()
    root = container_dir()
    if not root.is_dir():
        return None
    if uid:
        candidate = root / uid / title_id
        return candidate if candidate.is_dir() else None
    for uid_name in user_ids():
        candidate = root / uid_name / title_id
        if candidate.is_dir():
            return candidate
    return None


# --------------------------------------------------------------------------- 备份
def backup_root(custom: str | os.PathLike | None = None) -> Path:
    if custom:
        return Path(custom)
    from .common import app_dir

    return app_dir() / "backups" / "saves"


def backup_dir(title_id: str, custom=None) -> Path:
    path = backup_root(custom) / title_id.upper()
    path.mkdir(parents=True, exist_ok=True)
    return path


def list_backups(title_id: str, custom=None) -> list[Backup]:
    folder = backup_root(custom) / title_id.upper()
    if not folder.is_dir():
        return []
    out: list[Backup] = []
    for item in folder.glob("*.zip"):
        info = _read_manifest(item)
        out.append(
            Backup(
                path=item,
                title_id=info.get("title_id", title_id.upper()),
                uid=info.get("uid", ""),
                created=float(info.get("created") or item.stat().st_mtime),
                size=item.stat().st_size,
                files=int(info.get("files") or 0),
                note=info.get("note", ""),
                auto=item.name.startswith(AUTO_PREFIX),
            )
        )
    out.sort(key=lambda b: b.created, reverse=True)
    return out


def _read_manifest(zip_path: Path) -> dict:
    try:
        with zipfile.ZipFile(zip_path) as zf:
            with zf.open("manifest.json") as fp:
                return json.loads(fp.read().decode("utf-8"))
    except Exception:
        return {}


def _stamp() -> str:
    return time.strftime("%Y%m%d-%H%M%S")


def backup(title_id: str, uid: str | None = None, custom=None, note: str = "", progress=None,
           name_prefix: str = "") -> Backup:
    source = save_path(title_id, uid)
    if source is None:
        raise SaveError(f"找不到 {title_id} 的存档目录")
    uid = source.parent.name
    size, files = _dir_stats(source)

    folder = backup_dir(title_id, custom)
    target = folder / f"{name_prefix}{_stamp()}.zip"
    index = 1
    while target.exists():
        target = folder / f"{name_prefix}{_stamp()}-{index}.zip"
        index += 1

    manifest = {
        "title_id": title_id.upper(),
        "uid": uid,
        "created": time.time(),
        "files": files,
        "bytes": size,
        "note": note,
        "tool": DISPLAY_NAME,
    }

    tmp = target.with_suffix(".zip.part")
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
            zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            done = 0
            for base, _dirs, names in os.walk(source):
                for name in names:
                    full = Path(base) / name
                    rel = full.relative_to(source).as_posix()
                    zf.write(full, rel)
                    done += 1
                    if progress is not None and files:
                        progress.progress(done, files, f"备份存档（{done}/{files}）")
        if progress is not None:
            progress.check_cancel()
        os.replace(tmp, target)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise

    if progress is not None:
        progress.log(f"已备份到 {target.name}（{human_size(size)} / {files} 个文件）")
    cleanup_old(title_id, custom)
    return Backup(
        path=target,
        title_id=title_id.upper(),
        uid=uid,
        created=manifest["created"],
        size=target.stat().st_size,
        files=files,
        note=note,
        auto=bool(name_prefix),
    )


def cleanup_old(title_id: str, custom=None, keep: int = 20) -> int:
    items = [b for b in list_backups(title_id, custom) if not b.auto]
    removed = 0
    for old in items[keep:]:
        try:
            old.path.unlink()
            removed += 1
        except OSError:
            continue
    return removed


# --------------------------------------------------------------------------- 还原
def restore(zip_path: Path, progress=None, uid: str | None = None) -> RestoreResult:
    zip_path = Path(zip_path)
    if not zip_path.exists():
        raise SaveError(f"找不到备份文件：{zip_path}")
    info = _read_manifest(zip_path)
    title_id = (info.get("title_id") or "").upper()
    if not title_id:
        raise SaveError("这个 zip 不是本工具做的存档备份（缺少 manifest.json）")

    root = container_dir()
    target_uid = uid or info.get("uid") or ""
    if not target_uid:
        ids = user_ids()
        if not ids:
            raise SaveError("找不到模拟器用户目录，请先启动一次模拟器")
        target_uid = ids[0]
    if uid and info.get("uid") and uid != info["uid"]:
        raise SaveError(
            f"备份属于用户 {info['uid']}，与当前选择的 {uid} 不一致，已拒绝还原"
        )

    root.mkdir(parents=True, exist_ok=True)
    profile = root / target_uid
    profile.mkdir(parents=True, exist_ok=True)

    snapshot = None
    current = profile / title_id
    if current.is_dir():
        if progress is not None:
            progress.stage("还原前自动快照")
        snapshot = backup(title_id, target_uid, note="还原前自动快照", progress=progress,
                          name_prefix=AUTO_PREFIX).path

    tmp = profile / f"{TMP_PREFIX}{_stamp()}"
    if tmp.exists():
        shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    try:
        with zipfile.ZipFile(zip_path) as zf:
            members = [m for m in zf.infolist() if not m.is_dir() and m.filename != "manifest.json"]
            root_real = os.path.realpath(tmp)
            for i, member in enumerate(members, 1):
                if progress is not None:
                    progress.check_cancel()
                    progress.progress(i, len(members), f"解压存档（{i}/{len(members)}）")
                out = os.path.realpath(os.path.join(tmp, member.filename))
                if not out.startswith(root_real + os.sep) and out != root_real:
                    raise SaveError(f"备份里含异常路径：{member.filename}")
                Path(out).parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as src, open(out, "wb") as dst:
                    shutil.copyfileobj(src, dst, 1 << 20)
        files = sum(1 for _ in tmp.rglob("*") if _.is_file())
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise

    previous = None
    try:
        if current.exists():
            previous = profile / f"{BAK_PREFIX}{title_id}-{_stamp()}"
            os.replace(current, previous)
        os.replace(tmp, current)
    except Exception:
        # 反向回滚
        if previous is not None and previous.exists() and not current.exists():
            os.replace(previous, current)
        shutil.rmtree(tmp, ignore_errors=True)
        raise

    if progress is not None:
        progress.log(f"已还原 {title_id}（{files} 个文件）")
        if previous is not None:
            progress.log(f"还原前的旧存档留在 {previous.name}")
    return RestoreResult(path=current, files=files, snapshot=snapshot, previous=previous)


# --------------------------------------------------------------------------- 导入导出
def export(zip_path: Path, target: Path) -> Path:
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(zip_path, target)
    return target


def import_zip(source: Path, custom=None, progress=None) -> Backup:
    """把外部 zip 收进备份目录（不直接覆盖，用户还要手动点还原）。"""
    source = Path(source)
    info = _read_manifest(source)
    title_id = (info.get("title_id") or "").upper()
    if not title_id:
        # 允许通用 zip：用文件名里的 TitleID 兜底
        from .eden import parse_title_id

        title_id = parse_title_id(source.name)
    if not title_id:
        raise SaveError("无法识别这个 zip 属于哪个游戏（既没有 manifest.json，文件名里也没有 TitleID）")
    folder = backup_dir(title_id, custom)
    target = folder / f"imported-{_stamp()}.zip"
    index = 1
    while target.exists():
        target = folder / f"imported-{_stamp()}-{index}.zip"
        index += 1
    if progress is not None:
        progress.stage("导入备份")
    shutil.copy2(source, target)
    return Backup(path=target, title_id=title_id, uid=info.get("uid", ""), created=time.time(),
                  size=target.stat().st_size, files=int(info.get("files") or 0), note="导入")


# --------------------------------------------------------------------------- 残留
def leftovers() -> list[Path]:
    """上次还原中断留下的临时/备份目录。"""
    root = container_dir()
    if not root.is_dir():
        return []
    out: list[Path] = []
    for uid_dir in root.iterdir():
        if not uid_dir.is_dir():
            continue
        for item in uid_dir.iterdir():
            if item.is_dir() and (item.name.startswith(TMP_PREFIX) or item.name.startswith(BAK_PREFIX)):
                out.append(item)
    return out


def repair_leftovers(progress=None) -> int:
    """删掉临时目录；备份目录若对应游戏缺失则恢复回去。"""
    fixed = 0
    for item in leftovers():
        if item.name.startswith(TMP_PREFIX):
            shutil.rmtree(item, ignore_errors=True)
            fixed += 1
            if progress is not None:
                progress.log(f"清理临时目录 {item.name}")
            continue
        # .egl-bak-<titleid>-<stamp>
        rest = item.name[len(BAK_PREFIX) :]
        title_id = rest.split("-")[0]
        target = item.parent / title_id
        if not target.exists():
            os.replace(item, target)
            fixed += 1
            if progress is not None:
                progress.log(f"恢复被中断的存档 {title_id}")
        else:
            shutil.rmtree(item, ignore_errors=True)
            fixed += 1
    return fixed
