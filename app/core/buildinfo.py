"""从 eglantine.exe 内嵌的构建信息块识别精确版本。

exe 里有一段 ASCII 构建信息（不受汉化补丁影响）。以每日构建为例：

    78743f30c251f66bd77e6eea6c28d8632d642d6f\\0\\0\\0\\x01\\x01\\0\\0\\0daily-20261109\\0\\0
    78743f30c2-daily-20261109\\0\\0\\0\\0\\0\\0\\0Eglantine Nightly\\0...
    2026-11-09T10:30:54Z\\0\\0\\0\\0Eglantine Nightly 78743f30c2-daily-20261109 \\0...
    MSVC 19.51.36260.0

正式版则形如 `<commit>` + 8 个 NUL + `v0.1.0-rc3` + `Eglantine` + ISO 时间 + `Eglantine v0.1.0-rc3 ` + `MSVC ...`。

**不要用「全文件找第一个 v1.2.3」那种做法**：官方包里还嵌着 NVIDIA Streamline 的下载网址
（`.../download/v2.14.16/streamline-sdk-v2.14.16.zip`），旧实现就是被它带偏，把 rc3 读成了 v2.14.16。

所以这里按可靠性从高到低四级定位，全部失败就返回空 tag，绝不编造：
1. 摘要串 `Eglantine [Nightly] <commit前10位>-<tag>`（两个已知版本里都唯一）
2. 编译器指纹 `MSVC 19.51...` 前 2048 字节的 NUL 分隔字段
3. 全文 `daily-YYYYMMDD`
4. 空
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# 摘要串：Eglantine [可选 1-2 个单词] [可选 <10位commit>-] <tag>，后面紧跟 NUL 或空格
_SUMMARY = re.compile(
    rb"Eglantine (?:[A-Za-z]+ ){0,2}(?:[0-9a-f]{7,12}-)?"
    rb"([A-Za-z0-9][A-Za-z0-9._\-]{2,119})(?=[\x00 ])"
)
_TAG_DAILY = re.compile(rb"daily-\d{8}")
_TAG_ANY = re.compile(rb"(?:branch-[A-Za-z0-9._\-]+|v\d+\.\d+[A-Za-z0-9.\-]*)")
_COMMIT = re.compile(rb"[0-9a-f]{40}")
_BUILD_TIME = re.compile(rb"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
_COMPILER = re.compile(rb"(?:MSVC|clang|GCC|AppleClang)[ /][\d.]+")
# 打印期字段（NUL 分隔）里的 tag 形状
_TAG_SHAPE = re.compile(r"^(?:v\d+\.\d+[A-Za-z0-9.\-]*|daily-\d{8}|branch-[A-Za-z0-9._\-]{3,119})$")

_CACHE: dict[tuple[str, float, int], "BuildInfo"] = {}


@dataclass
class BuildInfo:
    tag: str = ""
    commit: str = ""
    name: str = "Eglantine"
    build_time: datetime | None = None
    compiler: str = ""
    channel: str = "unknown"  # daily / branch / release / unknown
    origin: Path | None = None
    extra: dict = field(default_factory=dict)

    @property
    def short_commit(self) -> str:
        return self.commit[:10]

    @property
    def is_daily(self) -> bool:
        return self.channel == "daily"

    @property
    def date_text(self) -> str:
        if not self.build_time:
            return "—"
        return self.build_time.astimezone().strftime("%Y-%m-%d %H:%M")

    def describe(self) -> str:
        if self.tag:
            return f"{self.tag} · {self.short_commit}" if self.commit else self.tag
        return "未知版本"


def _parse_iso(raw: bytes) -> datetime | None:
    try:
        return datetime.strptime(raw.decode("ascii"), "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except Exception:
        return None


def _tag_ok(tag: str) -> bool:
    return bool(tag) and bool(_TAG_SHAPE.match(tag))


def channel_of(tag: str) -> str:
    if not tag:
        return "unknown"
    if tag.startswith("daily-"):
        return "daily"
    if tag.startswith("branch-"):
        return "branch"
    if tag.startswith("v"):
        return "release"
    return "unknown"


def _last(pattern: re.Pattern, data: bytes, start: int, end: int) -> bytes:
    best = b""
    for m in pattern.finditer(data, start, end):
        best = m.group()
    return best


def _from_summary(data: bytes) -> tuple[str, bytes, bytes, str] | None:
    """摘要串定位：返回 (tag, commit, iso, 摘要文本)。"""
    for m in _SUMMARY.finditer(data):
        tag = m.group(1).decode("ascii", "replace")
        if not _tag_ok(tag):
            continue
        head = max(0, m.start() - 320)
        commit = _last(_COMMIT, data, head, m.end())
        iso = _last(_BUILD_TIME, data, head, m.end() + 400)
        return tag, commit, iso, m.group(0).decode("ascii", "replace").strip()
    return None


def _printable_fields(data: bytes, start: int, end: int) -> list[str]:
    out: list[str] = []
    for chunk in data[start:end].split(b"\x00"):
        text = chunk.strip(b"\x01\x02\x03\x04\x05\x06\x07\x08\t\n\r ")
        if not text or len(text) > 160:
            continue
        try:
            out.append(text.decode("ascii"))
        except UnicodeDecodeError:
            continue
    return out


def _from_compiler(data: bytes) -> tuple[str, bytes, bytes, str] | None:
    """编译器指纹定位：MSVC 前面 2 KB 的字段里找 commit + tag + 时间。"""
    m = _COMPILER.search(data)
    if not m:
        return None
    start = max(0, m.start() - 2048)
    fields = _printable_fields(data, start, m.start())
    commit = b""
    tag = ""
    iso = b""
    for i, text in enumerate(fields):
        if re.fullmatch(r"[0-9a-f]{40}", text):
            commit = text.encode()
            # tag 通常在 commit 之后的几个字段里
            for nxt in fields[i + 1 : i + 6]:
                if _tag_ok(nxt):
                    tag = nxt
                    break
        if not iso and re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", text):
            iso = text.encode()
        if tag and iso and commit:
            break
    if not tag:
        return None
    summary = next((f for f in fields if f.startswith("Eglantine ")), "")
    return tag, commit, iso, summary


def _from_daily(data: bytes) -> tuple[str, bytes, bytes, str] | None:
    m = _TAG_DAILY.search(data)
    if not m:
        return None
    tag = m.group().decode()
    head = max(0, m.start() - 320)
    commit = _last(_COMMIT, data, head, m.end())
    iso = _last(_BUILD_TIME, data, head, m.end() + 400)
    return tag, commit, iso, ""


def _name_of(summary: str, tag: str) -> str:
    if "Nightly" in summary:
        return "Eglantine Nightly"
    if "Development" in summary:
        return "Eglantine Development"
    if "Canary" in summary:
        return "Eglantine Canary"
    return "Eglantine"


def clear_cache() -> None:
    _CACHE.clear()


def read_build_info(exe: Path) -> BuildInfo:
    exe = Path(exe)
    if not exe.exists():
        raise FileNotFoundError(f"找不到 {exe.name}")

    stat = exe.stat()
    key = (str(exe), stat.st_mtime, stat.st_size)
    if key in _CACHE:
        return _CACHE[key]

    data = exe.read_bytes()
    info = BuildInfo(origin=exe)

    hit = None
    for source, finder in (
        ("summary", _from_summary),
        ("compiler", _from_compiler),
        ("daily", _from_daily),
    ):
        hit = finder(data)
        if hit:
            info.extra["source"] = source
            break

    if hit:
        tag, commit, iso, summary = hit
        info.tag = tag
        info.channel = channel_of(tag)
        info.commit = commit.decode("ascii", "replace")
        info.build_time = _parse_iso(iso) if iso else None
        info.name = _name_of(summary, tag)
        if summary:
            info.extra["summary"] = summary

    if not info.build_time:
        # 最后兜底：全文最后一个 ISO 时间（一定要有，否则界面显示 "—"）
        iso = _last(_BUILD_TIME, data, 0, len(data))
        info.build_time = _parse_iso(iso) if iso else None

    comp = _COMPILER.search(data)
    info.compiler = comp.group().decode(errors="replace") if comp else ""

    _CACHE[key] = info
    return info


def find_install_dir(start: Path | None = None) -> Path | None:
    """从给定目录（默认工具所在目录）向上/向下找含 eglantine.exe 的目录。"""
    base = Path(start) if start else Path.cwd()
    for candidate in (base, base.parent, base / "eglantine"):
        if (candidate / "eglantine.exe").exists():
            return candidate.resolve()
    return None
