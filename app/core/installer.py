"""更新安装、汉化、还原的完整流程。"""

from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import zipfile
from ctypes import wintypes
from pathlib import Path

from . import builder, extract, patcher, release as rel
from .common import Cancelled, human_size
from .config import qt_config_ini

EXE = "eglantine.exe"
UPDATE_DIR = "_update"
#: 用户会自己改的文件：升级时不覆盖，把新版另存为 .new
PRESERVE = ("nx2_switches.txt",)


class InstallError(RuntimeError):
    pass


# --------------------------------------------------------------------------- 进程


def emulator_pids() -> list[int]:
    TH32CS_SNAPPROCESS = 0x00000002
    INVALID = ctypes.c_void_p(-1).value

    class PROCESSENTRY32(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", ctypes.c_char * 260),
        ]

    k32 = ctypes.windll.kernel32
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == INVALID:
        return []
    pids: list[int] = []
    try:
        entry = PROCESSENTRY32()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
        ok = k32.Process32First(snap, ctypes.byref(entry))
        while ok:
            name = entry.szExeFile.decode("mbcs", "ignore").lower()
            if name in ("eglantine.exe", "eden.exe"):
                pids.append(int(entry.th32ProcessID))
            ok = k32.Process32Next(snap, ctypes.byref(entry))
    finally:
        k32.CloseHandle(snap)
    return pids


def emulator_running() -> bool:
    return bool(emulator_pids())


def close_emulator(log=print) -> bool:
    pids = emulator_pids()
    if not pids:
        return True
    for pid in pids:
        subprocess.run(
            ["taskkill", "/F", "/PID", str(pid)],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            capture_output=True,
        )
    log("已关闭正在运行的模拟器")
    return not emulator_running()


def launch_emulator(install_dir: Path, rom: Path | None = None) -> None:
    """启动模拟器；给了 rom 就直接进游戏（Eden 支持把游戏路径当第一个参数）。"""
    exe = Path(install_dir) / EXE
    if not exe.exists():
        raise InstallError("目录里还没有 eglantine.exe，请先点「安装并汉化」")
    args = [str(exe)]
    if rom is not None:
        args.append(str(rom))
    subprocess.Popen(args, cwd=str(install_dir))


# --------------------------------------------------------------------------- 磁盘


def free_space(path: Path) -> int:
    """所在卷的剩余空间；路径还不存在时向上找第一个存在的祖先。"""
    p = Path(path)
    for candidate in (p, *p.parents):
        try:
            return shutil.disk_usage(str(candidate)).free
        except Exception:
            continue
    return 0


# --------------------------------------------------------------------------- 解压


def extract_zip(zip_path: Path, dest: Path, progress) -> int:
    dest = Path(dest)
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True, exist_ok=True)
    count = 0
    with zipfile.ZipFile(zip_path) as zf:
        members = [m for m in zf.infolist() if not m.is_dir()]
        total = len(members)
        root = os.path.realpath(dest)
        for i, info in enumerate(members, 1):
            progress.check_cancel()
            target = os.path.realpath(os.path.join(dest, info.filename))
            if not target.startswith(root + os.sep) and target != root:
                raise InstallError(f"安装包内含异常路径：{info.filename}")
            out = Path(target)
            out.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, out.open("wb") as dst:
                shutil.copyfileobj(src, dst, 1 << 20)
            try:
                import time as _time

                stamp = _time.mktime(tuple(info.date_time) + (0, 0, -1))
                os.utime(out, (stamp, stamp))
            except Exception:
                pass
            count += 1
            progress.progress(i, total, f"解压安装包（{i}/{total}）")
    return count


# --------------------------------------------------------------------------- 覆盖安装


def install_stage(stage: Path, install: Path, progress) -> dict:
    stage = Path(stage)
    install = Path(install)
    if not (stage / EXE).exists():
        raise InstallError("安装包里没有 eglantine.exe，可能下载到了错误的文件")
    install.mkdir(parents=True, exist_ok=True)

    files = [p for p in stage.rglob("*") if p.is_file()]
    total = len(files)
    copied = added = preserved = 0

    for i, src in enumerate(files, 1):
        progress.check_cancel()
        rel_path = src.relative_to(stage)
        dst = install / rel_path
        if rel_path.as_posix().lower() == EXE:
            continue  # exe 最后原子替换
        if rel_path.as_posix() in PRESERVE and dst.exists():
            if dst.read_bytes() != src.read_bytes():
                (dst.parent / (dst.name + ".new")).write_bytes(src.read_bytes())
                preserved += 1
                progress.log(f"保留你修改过的 {dst.name}，新版内容另存为 {dst.name}.new")
                continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        existed = dst.exists()
        shutil.copy2(src, dst)
        copied += 1
        if not existed:
            added += 1
        if i % 5 == 0 or i == total:
            progress.progress(i, total, f"写入文件（{i}/{total}）")

    tmp = install / (EXE + ".new")
    shutil.copy2(stage / EXE, tmp)
    had_exe = (install / EXE).exists()
    try:
        os.replace(tmp, install / EXE)
    except PermissionError as exc:
        tmp.unlink(missing_ok=True)
        raise InstallError(
            "无法替换 eglantine.exe，请确认模拟器已完全退出（必要时在任务管理器结束进程）"
        ) from exc
    copied += 1
    if not had_exe:
        added += 1

    # 官方原版留档，供还原与后续补丁使用
    shutil.copy2(stage / EXE, patcher.backup_path(install / EXE))

    return {"copied": copied, "added": added, "preserved": preserved, "total": total}


# --------------------------------------------------------------------------- 配置


def set_language(value: str, log=print) -> Path | None:
    """改写 qt-config.ini 的 Paths\\language（只动这一个键）。"""
    ini = qt_config_ini()
    try:
        ini.parent.mkdir(parents=True, exist_ok=True)
        exists = ini.exists()
        text = ini.read_text(encoding="utf-8", errors="surrogateescape") if exists else ""
        bak = ini.with_suffix(ini.suffix + ".eghl.bak")
        if exists and not bak.exists():
            shutil.copy2(ini, bak)

        newline = "\r\n" if "\r\n" in text else "\n"
        lines = text.splitlines()
        key = "Paths\\language"
        replaced = False
        out: list[str] = []
        for line in lines:
            if line.startswith(key + "="):
                out.append(f"{key}={value}")
                replaced = True
            else:
                out.append(line)
        if not replaced:
            insert_at = _ui_section_end(lines)
            payload = [f"{key}\\default=false", f"{key}={value}"]
            if insert_at is None:
                # 没有 [UI] 段（首次安装、ini 全新）时必须自己写段头，
                # 否则键落在根段，Qt 的 UI/Paths\language 读不到，界面仍是英文
                if out:
                    out.append("")
                out.append("[UI]")
                out.extend(payload)
            else:
                out = lines[:insert_at] + payload + lines[insert_at:]
        ini.write_text(newline.join(out) + newline, encoding="utf-8", errors="surrogateescape")
        log(f"界面语言已设为 {value}")
        return ini
    except Exception as exc:
        log(f"写入界面语言失败：{exc}")
        return None


def _ui_section_end(lines: list[str]) -> int | None:
    """返回 [UI] 段最后一个非空行的位置（用于插入新键）。"""
    start = None
    for i, line in enumerate(lines):
        if line.strip() == "[UI]":
            start = i + 1
            break
    if start is None:
        return None
    end = len(lines)
    for j in range(start, len(lines)):
        if lines[j].startswith("["):
            end = j
            break
    while end > start and not lines[end - 1].strip():
        end -= 1
    return end


def current_language() -> str:
    ini = qt_config_ini()
    if not ini.exists():
        return ""
    try:
        for line in ini.read_text(encoding="utf-8", errors="surrogateescape").splitlines():
            if line.startswith("Paths\\language="):
                return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return ""


# --------------------------------------------------------------------------- 状态


def install_state(install_dir: Path) -> dict:
    install = Path(install_dir)
    exe = install / EXE
    qm = install / "languages" / "zh_CN.qm"
    patched = patcher.state(exe) == "patched"
    zh_exists = qm.exists()
    lang = current_language()
    return {
        "exists": exe.exists(),
        "patched": patched,
        "zh_pack": zh_exists,
        "language": lang,
        "localized": patched and zh_exists and lang.lower() in ("zh_cn", "zh-cn", "zh"),
    }


# --------------------------------------------------------------------------- 汉化


def localize(install_dir: Path, overrides: Path, progress) -> dict:
    install = Path(install_dir)
    exe = install / EXE
    if not exe.exists():
        raise InstallError(f"找不到 {exe}")

    progress.stage("应用汉化补丁")
    patcher.apply_patch(exe, log=progress.log)

    progress.stage("生成中文语言包")
    out = install / "languages" / "zh_CN.qm"
    stats = builder.build(exe, out, overrides, log=progress.log)

    progress.stage("设置界面语言")
    set_language("zh_CN", progress.log)
    now = current_language()
    if now.lower() in ("zh_cn", "zh-cn", "zh"):
        progress.log(f"界面语言已确认：{now}")
    else:
        progress.log(
            f"界面语言未能确认（当前为 {now or '空'}）——若启动后仍是英文，请再点一次「仅应用汉化」"
        )
    return stats


# --------------------------------------------------------------------------- 还原


def restore_original(install_dir: Path, progress) -> dict:
    install = Path(install_dir)
    exe = install / EXE
    if not exe.exists():
        raise InstallError(f"找不到 {exe}")

    progress.stage("还原官方 exe")
    mode = patcher.restore(exe, log=progress.log)

    progress.stage("界面语言改回英文")
    set_language("en", progress.log)

    progress.stage("移除中文语言包")
    qm = install / "languages" / "zh_CN.qm"
    removed = False
    if qm.exists():
        qm.unlink()
        removed = True
    try:
        if qm.parent.exists() and not any(qm.parent.iterdir()):
            qm.parent.rmdir()
    except Exception:
        pass
    progress.log("已移除 languages\\zh_CN.qm" if removed else "没有残留的中文语言包")
    return {"mode": mode, "removed_pack": removed}


# --------------------------------------------------------------------------- 更新


def _check_staged_version(stage: Path, target: "rel.Release", zip_path: Path, progress) -> None:
    """核对包内 exe 的版本号，防止 CDN / 加速源返回了旧包。

    规则只有一条：包内 tag 能读到且与目标不同 → 判定串包（清掉安装包后中止）；
    读不到 tag 就记日志放行（下载时 SHA-256 已经校验过）。
    **不再用 commit 兜底**：正式版的 release body 里往往没有 commit，
    而同一个 commit 的 daily 与正式版是两次不同的编译。
    """
    try:
        from .buildinfo import read_build_info

        info = read_build_info(stage / EXE)
    except Exception as exc:  # noqa: BLE001
        progress.log(f"读取包内版本失败（{exc}），跳过版本比对")
        return

    detail = info.tag or "未识别"
    if info.commit:
        detail += f" · {info.short_commit}"
    if info.build_time:
        detail += f" · {info.date_text}"
    progress.log(f"包内版本 {detail}")

    if not info.tag:
        progress.log("包内版本无法识别，跳过版本比对（安装包 SHA-256 已校验）")
        return
    if rel.same_tag(target.tag, info.tag):
        return

    zip_path.unlink(missing_ok=True)
    raise InstallError(
        f"安装包版本不一致：包内为 {info.tag}，期望 {target.tag}。\n"
        "可能是加速源或 CDN 返回了旧的安装包，已清除该包，请重新点安装重试。"
    )


def update_and_localize(
    install_dir: Path,
    target: rel.Release,
    overrides: Path,
    progress,
    launch_after: bool = False,
) -> dict:
    install = Path(install_dir)
    exe = install / EXE
    fresh = not exe.exists()

    asset = target.asset()
    if asset is None:
        raise InstallError(f"该版本没有 Windows 安装包（{rel.ASSET_NAME}）")

    install.mkdir(parents=True, exist_ok=True)
    need = (asset.size or 0) * 3
    if free_space(install) < need:
        raise InstallError(
            f"磁盘空间不足：更新需要约 {human_size(need)}，当前仅剩 {human_size(free_space(install))}"
        )

    work = install / UPDATE_DIR
    work.mkdir(parents=True, exist_ok=True)
    zip_path = work / "pkg.zip"
    stage = work / "stage"
    backup = work / "backup"

    progress.stage(f"准备更新到 {target.tag}")
    progress.log(f"目标版本 {target.tag} · {target.name} · 安装包 {human_size(asset.size)}")
    if fresh:
        known = sum(1 for p in install.iterdir() if p.name != UPDATE_DIR)
        progress.log("目录里没有 eglantine.exe，将执行全新安装")
        if known:
            progress.log(f"目录里另有 {known} 个文件/文件夹，安装会覆盖同名文件，不会删除它们")

    # 0) 清掉上次失败残留的解压目录
    shutil.rmtree(stage, ignore_errors=True)

    # 1) 下载 + 校验
    rel.download(asset, zip_path, progress)

    old_exe: Path | None = None
    old_bak: Path | None = None
    try:
        # 2) 解压
        progress.stage("解压安装包")
        extract_zip(zip_path, stage, progress)

        # 3) 校验包内版本，避免 CDN / 加速源串版本
        _check_staged_version(stage, target, zip_path, progress)

        # 4) 备份当前状态（全新安装没有旧版本可备份）
        if fresh:
            progress.stage("全新安装（无需备份）")
        else:
            progress.stage("备份当前版本")
            backup.mkdir(parents=True, exist_ok=True)
            old_exe = backup / EXE
            old_bak = backup / (EXE + patcher.BACKUP_SUFFIX)
            shutil.copy2(exe, old_exe)
            if patcher.backup_path(exe).exists():
                shutil.copy2(patcher.backup_path(exe), old_bak)
            else:
                old_bak = None

        # 5) 覆盖安装
        progress.stage("安装新版本")
        result = install_stage(stage, install, progress)

        # 6) 汉化（失败则回滚）
        try:
            stats = localize(install, overrides, progress)
        except Exception:
            if old_exe is not None and old_exe.exists():
                progress.log("汉化失败，正在回滚 exe…")
                try:
                    shutil.copy2(old_exe, exe)
                    if old_bak is not None and old_bak.exists():
                        shutil.copy2(old_bak, patcher.backup_path(exe))
                except Exception as exc:
                    progress.log(f"回滚失败：{exc}")
            else:
                progress.log("汉化失败，正在回退为官方原版…")
                try:
                    if exe.exists():
                        patcher.restore(exe, log=progress.log)
                    qm = install / "languages" / "zh_CN.qm"
                    qm.unlink(missing_ok=True)
                    progress.log("已回退为官方原版（不含中文包），可再次点「安装并汉化」重试")
                except Exception as exc:
                    progress.log(f"回退失败：{exc}")
            raise
    except Exception as exc:
        shutil.rmtree(stage, ignore_errors=True)
        keep = "重试会复用该安装包" if zip_path.exists() else "安装包已清除，重试会重新下载"
        if isinstance(exc, Cancelled):
            progress.log(f"已取消；解压目录已清理，{keep}")
        else:
            progress.log(f"安装未完成；解压目录已清理，{keep}")
            if backup.exists():
                progress.log(f"本次的旧版本备份在 {backup}")
        raise

    # 7) 清理
    progress.stage("清理临时文件")
    shutil.rmtree(stage, ignore_errors=True)
    zip_path.unlink(missing_ok=True)
    shutil.rmtree(backup, ignore_errors=True)

    new_info = None
    try:
        from .buildinfo import read_build_info

        new_info = read_build_info(exe)
    except Exception:
        pass

    if launch_after:
        progress.log("启动模拟器…")
        launch_emulator(install)

    return {
        "version": new_info,
        "install": result,
        "zh": stats,
    }
