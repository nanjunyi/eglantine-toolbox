"""查询上游版本、比对、下载安装包（续传 / SHA-256 / 代理 / 加速源）。

支持的版本通道：
    daily-YYYYMMDD           每日构建
    branch-<分支>-<commit>   实验分支构建
    vX.Y.Z[-rcN]             正式版本
只取 Windows 平台的非 PGO 包：eglantine-windows-x86_64.zip
"""

from __future__ import annotations

import json
import re
import socket
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from http.client import HTTPException
from pathlib import Path

from ..constants import USER_AGENT
from .common import Cancelled, human_size, human_speed, sha256_file

API_BASE = "https://api.github.com/repos/Eglantine-Community/Eglantine/releases"
ASSET_NAME = "eglantine-windows-x86_64.zip"

_DAILY_TAG = re.compile(r"^daily-(\d{8})$")
_BODY_COMMIT = re.compile(r"at `([0-9a-f]{7,40})`")
_CACHE_TTL = 600  # 秒


class ReleaseError(RuntimeError):
    pass


class NetConfig:
    """全局网络设置（供 GUI 修改）。"""

    use_system_proxy: bool = True
    mirror: str = ""


def set_net(use_system_proxy: bool | None = None, mirror: str | None = None) -> None:
    if use_system_proxy is not None:
        NetConfig.use_system_proxy = bool(use_system_proxy)
    if mirror is not None:
        NetConfig.mirror = (mirror or "").strip()


def describe_net() -> str:
    proxy = "系统代理" if NetConfig.use_system_proxy else "直连"
    mirror = NetConfig.mirror or "无加速源"
    return f"{proxy} · {mirror}"


@dataclass
class Asset:
    name: str
    size: int
    url: str
    digest: str = ""

    @property
    def sha256(self) -> str:
        d = (self.digest or "").lower()
        return d.split(":", 1)[1] if d.startswith("sha256:") else ""


@dataclass
class Release:
    tag: str
    name: str
    published: datetime | None
    body: str = ""
    prerelease: bool = False
    assets: list[Asset] = field(default_factory=list)

    @property
    def commit(self) -> str:
        m = _BODY_COMMIT.search(self.body or "")
        return m.group(1) if m else ""

    @property
    def channel(self) -> str:
        if _DAILY_TAG.match(self.tag):
            return "daily"
        if self.tag.startswith("branch-"):
            return "branch"
        if self.tag.startswith("v"):
            return "release"
        return "other"

    @property
    def channel_label(self) -> str:
        return {
            "daily": "每日构建",
            "branch": "实验分支",
            "release": "正式版",
        }.get(self.channel, "其他")

    @property
    def date_text(self) -> str:
        d = _tag_date(self.tag) or (
            self.published.astimezone() if self.published else None
        )
        return d.strftime("%Y-%m-%d") if d else "—"

    @property
    def branch_name(self) -> str:
        if self.channel != "branch":
            return ""
        parts = self.tag.split("-")
        return "-".join(parts[1:-1]) if len(parts) > 2 else ""

    def asset(self, name: str = ASSET_NAME) -> Asset | None:
        for a in self.assets:
            if a.name.lower() == name.lower():
                return a
        return None

    @property
    def windows_asset(self) -> Asset | None:
        return self.asset(ASSET_NAME)

    @property
    def title(self) -> str:
        if self.channel == "branch" and self.branch_name:
            return f"{self.tag}  ({self.branch_name})"
        return self.tag

    def combo_text(self) -> str:
        if self.channel == "branch":
            suffix = self.tag.rsplit("-", 1)[-1]
            name = self.branch_name or "实验分支"
            return f"{name} @ {suffix}  ·  {self.date_text}"
        return f"{self.tag}  ·  {self.channel_label}  ·  {self.date_text}"


def _tag_date(tag: str) -> datetime | None:
    m = _DAILY_TAG.match(tag)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y%m%d")
    except ValueError:
        return None


# --------------------------------------------------------------------------- 网络

_SSL_CONTEXTS: list[ssl.SSLContext] | None = None


def _ssl_contexts() -> list[ssl.SSLContext]:
    global _SSL_CONTEXTS
    if _SSL_CONTEXTS is None:
        strict = ssl.create_default_context()
        loose = ssl.create_default_context()
        loose.check_hostname = False
        loose.verify_mode = ssl.CERT_NONE
        _SSL_CONTEXTS = [strict, loose]
    return _SSL_CONTEXTS


def mirror_url(url: str) -> str:
    """把 GitHub 下载链接改写成加速源链接（接口请求不走加速源）。"""
    m = (NetConfig.mirror or "").strip()
    if not m:
        return url
    if "api.github.com" in url:
        return url
    if "{url}" in m:
        return m.replace("{url}", url)
    return m.rstrip("/") + "/" + url


def _candidates(url: str) -> list[str]:
    mirrored = mirror_url(url)
    return [mirrored, url] if mirrored != url else [url]


def _opener(ctx: ssl.SSLContext):
    handlers = [urllib.request.HTTPSHandler(context=ctx)]
    if NetConfig.use_system_proxy:
        handlers.append(urllib.request.ProxyHandler())  # 读取系统/环境代理
    else:
        handlers.append(urllib.request.ProxyHandler({}))
    return urllib.request.build_opener(*handlers)


def _open(url: str, headers: dict | None = None, timeout: int = 25, retries: int = 1):
    hdrs = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if headers:
        hdrs.update(headers)

    last: Exception | None = None
    for candidate in _candidates(url):
        for attempt in range(retries + 1):
            for ctx in _ssl_contexts():
                req = urllib.request.Request(candidate, headers=hdrs)
                try:
                    return _opener(ctx).open(req, timeout=timeout)
                except ssl.SSLError as exc:
                    last = exc
                    continue
                except urllib.error.HTTPError as exc:
                    last = exc
                    break
                except (urllib.error.URLError, socket.timeout, OSError, HTTPException) as exc:
                    last = exc
                    break
            if attempt < retries:
                time.sleep(1.0 * (attempt + 1))
    raise ReleaseError(_friendly_error(last))


def _friendly_error(exc: Exception | None) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        if exc.code == 403:
            return "GitHub 接口访问被限制（403，可能触发频率限制），请稍后再试"
        if exc.code == 404:
            return "接口或文件不存在（404），请检查加速源是否支持该链接"
        return f"服务器返回 HTTP {exc.code}"
    if isinstance(exc, ssl.SSLError):
        return "TLS 证书校验失败，请检查网络代理设置"
    if isinstance(exc, socket.timeout):
        return "连接超时，请检查网络或代理"
    if isinstance(exc, urllib.error.URLError):
        return f"网络不可用：{exc.reason}"
    if isinstance(exc, (HTTPException, json.JSONDecodeError, UnicodeDecodeError)):
        return "响应数据不完整（网络中断或代理截断），请重试"
    return f"网络请求失败：{exc}" if exc else "网络请求失败"


def ping(timeout: int = 10) -> str:
    """连通性自检，返回描述文字。"""
    t0 = time.monotonic()
    with _open(
        "https://api.github.com/rate_limit",
        {"Accept": "application/vnd.github+json"},
        timeout=timeout,
        retries=0,
    ) as resp:
        resp.read()
    ms = int((time.monotonic() - t0) * 1000)
    return f"连接正常 · {ms} ms · {describe_net()}"


# --------------------------------------------------------------------------- 版本


def _cache_file() -> Path:
    from .config import config_dir

    return config_dir() / "releases_cache.json"


def fetch_releases(use_cache: bool = True, log=print) -> list[Release]:
    cache = _cache_file()
    stale: list | None = None
    if cache.exists():
        try:
            raw = json.loads(cache.read_text(encoding="utf-8"))
            stale = raw.get("releases") or None
            if use_cache and time.time() - float(raw.get("ts", 0)) < _CACHE_TTL:
                return [_release_from_json(r) for r in stale or []]
        except Exception:
            stale = None

    try:
        payload = _fetch_payload(log)
    except ReleaseError:
        if stale:
            log("网络请求失败，改用上次缓存的版本列表（可能不是最新）")
            return [_release_from_json(r) for r in stale]
        raise

    releases = [_release_from_json(r) for r in payload if isinstance(r, dict)]
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(
            json.dumps({"ts": time.time(), "releases": payload}, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass
    log(f"已从仓库获取 {len(releases)} 个版本记录")
    return releases


def _fetch_payload(log) -> list:
    last_error: Exception | None = None
    # 每条 release 都带完整 changelog，页数越大响应越大；网络不稳时自动降页重试
    for per_page in (15, 8, 4):
        url = f"{API_BASE}?per_page={per_page}"
        try:
            log(f"正在查询 GitHub Releases（取前 {per_page} 条）…")
            with _open(url, {"Accept": "application/vnd.github+json"}, timeout=25) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (HTTPException, json.JSONDecodeError, UnicodeDecodeError) as exc:
            last_error = exc
            time.sleep(0.8)
        except ReleaseError as exc:
            raise ReleaseError(str(exc)) from exc
    raise ReleaseError(_friendly_error(last_error))


def _release_from_json(raw: dict) -> Release:
    pub = None
    if raw.get("published_at"):
        try:
            pub = datetime.fromisoformat(raw["published_at"].replace("Z", "+00:00"))
        except Exception:
            pub = None
    assets = [
        Asset(
            name=a.get("name", ""),
            size=int(a.get("size") or 0),
            url=a.get("browser_download_url", ""),
            digest=a.get("digest") or "",
        )
        for a in raw.get("assets", [])
        if isinstance(a, dict)
    ]
    return Release(
        tag=raw.get("tag_name", ""),
        name=raw.get("name") or raw.get("tag_name", ""),
        published=pub,
        body=raw.get("body") or "",
        prerelease=bool(raw.get("prerelease")),
        assets=assets,
    )


def latest_daily(releases: list[Release]) -> Release | None:
    dailies = [r for r in releases if _DAILY_TAG.match(r.tag)]
    if not dailies:
        return None
    return max(dailies, key=lambda r: _tag_date(r.tag) or datetime.min)


def selectable(releases: list[Release], limit: int = 10) -> list[Release]:
    """可安装的版本：有 Windows 非 PGO 包，按时间从新到旧。"""
    items = [r for r in releases if r.windows_asset is not None]
    items.sort(key=lambda r: (r.published or _tag_date(r.tag) or datetime.min), reverse=True)
    return items[:limit]


def normalize_tag(tag: str) -> str:
    """比较用：去空白、统一小写、去掉开头的 v。"""
    t = (tag or "").strip().lower()
    if t.startswith("v") and len(t) > 1 and t[1].isdigit():
        t = t[1:]
    return t


def same_tag(a: str, b: str) -> bool:
    na, nb = normalize_tag(a), normalize_tag(b)
    return bool(na) and na == nb


def same_release(local_tag: str, rel: Release) -> bool:
    """判定口径只看 tag。

    同一个 commit 的 daily 与正式版是两次不同的编译（体积、内容都不同），
    所以不能用 commit 判等，否则会出现「选了正式版却提示已是最新」。
    """
    return same_tag(local_tag, rel.tag)


# --------------------------------------------------------------------------- 下载


def _verify(dest: Path, digest: str, progress) -> Path:
    if digest:
        progress.log("校验安装包完整性…")
        actual = sha256_file(dest)
        if actual.lower() != digest.lower():
            dest.unlink(missing_ok=True)
            raise ReleaseError("安装包校验失败（SHA-256 不匹配），文件已删除，请重试")
        progress.log("安装包校验通过")
    return dest


def download(asset: Asset, dest: Path, progress, expected_sha256: str = "") -> Path:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    have = dest.stat().st_size if dest.exists() else 0
    total = asset.size or 0
    if total and have > total:
        have = 0
        dest.unlink(missing_ok=True)

    digest = expected_sha256 or asset.sha256

    # 上次已经下完整：不能再发 Range: bytes=<total>-（服务器会回 416），直接复用并校验
    if total and have == total:
        if digest:
            progress.progress(have, total, f"复用已下载的安装包 · {human_size(have)}")
            progress.log(f"已有完整安装包（{human_size(have)}），跳过下载直接校验")
            return _verify(dest, digest, progress)
        have = 0
        dest.unlink(missing_ok=True)

    headers = {}
    if have:
        headers["Range"] = f"bytes={have}-"

    if NetConfig.mirror and not progress.cancelled():
        progress.log(f"使用加速源：{NetConfig.mirror}")

    resp = _open(asset.url, headers, timeout=30)
    status = getattr(resp, "status", 200)
    if have and status != 206:
        resp.close()
        have = 0
        dest.unlink(missing_ok=True)
        resp = _open(asset.url, {}, timeout=30)

    length = int(resp.headers.get("Content-Length") or 0)
    if not total:
        total = have + length

    progress.progress(have, total, f"下载 {asset.name}")
    started = time.monotonic()
    base = have
    last_emit = 0.0
    mode = "ab" if have else "wb"
    try:
        with dest.open(mode) as fp:
            while True:
                progress.check_cancel()
                chunk = resp.read(128 * 1024)
                if not chunk:
                    break
                fp.write(chunk)
                have += len(chunk)
                now = time.monotonic()
                if now - last_emit > 0.15:
                    speed = (have - base) / max(now - started, 0.05)
                    progress.progress(
                        have, total, f"下载 {asset.name} · {human_speed(speed)}"
                    )
                    last_emit = now
    finally:
        resp.close()

    progress.progress(have, total or have, f"下载完成 · {human_size(have)}")

    if total and have < total:
        raise ReleaseError(
            f"下载不完整（{human_size(have)} / {human_size(total)}），请重试（支持断点续传）"
        )

    return _verify(dest, digest, progress)
