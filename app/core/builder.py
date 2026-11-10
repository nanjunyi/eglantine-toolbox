"""用「官方内置 zh_CN.qm + 本工具增量译文」生成 languages/zh_CN.qm。"""

from __future__ import annotations

import json
from pathlib import Path

from . import extract, qm_format as Q

LANG = "zh_CN"


def load_overrides(path: Path) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [m for m in raw.get("messages", []) if not m.get("disabled")]


def build(exe: Path, out: Path, overrides_path: Path, log=print) -> dict:
    packs = extract.extract_packs(exe)
    if LANG not in packs:
        raise LookupError(
            f"{Path(exe).name} 中没有内嵌简体中文语言包，无法生成汉化文件。"
        )

    qm = Q.parse(packs[LANG])
    index = {(m.context, m.source, m.comment): m for m in qm.messages}

    overrides = load_overrides(overrides_path)
    replaced = added = 0
    for item in overrides:
        key = (item.get("context", ""), item["source"], item.get("comment", ""))
        if key in index:
            index[key].translations = [item["translation"]]
            replaced += 1
        else:
            msg = Q.Message(context=key[0], source=key[1], comment=key[2])
            msg.translations = [item["translation"]]
            qm.messages.append(msg)
            added += 1

    qm.language = qm.language or LANG
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(Q.encode(qm))

    missing = _missing(packs, overrides)
    stats = {
        "total": len(qm.messages),
        "replaced": replaced,
        "added": added,
        "size": out.stat().st_size,
        "missing": missing,
    }
    log(
        f"中文词条 {stats['total']} 条（覆盖 {replaced}、新增 {added}，"
        f"{stats['size'] / 1024:.0f} KB）"
    )
    if missing:
        log(f"官方仍未汉化的条目 {len(missing)} 条（将以英文显示）")
    return stats


def _missing(packs: dict[str, bytes], overrides: list[dict]) -> list[tuple[str, str]]:
    """其它语言有、中文没有的词条；en_US 只是复数辅助包且上下文是旧类名，排除。"""
    have = {(m.context, m.source, m.comment) for m in Q.parse(packs[LANG]).messages}
    have |= {
        (m.get("context", ""), m["source"], m.get("comment", "")) for m in overrides
    }
    full: set[tuple[str, str, str]] = set()
    for lang, blob in packs.items():
        if lang in (LANG, "en_US"):
            continue
        try:
            full |= {(m.context, m.source, m.comment) for m in Q.parse(blob).messages}
        except Exception:
            continue
    return sorted((c, s) for c, s, _ in (full - have))
