# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：单文件、无控制台。

构建：
    python -m PyInstaller build/build.spec --noconfirm

产物：dist/Eglantine工具箱.exe
"""

from pathlib import Path

ROOT = Path(SPECPATH).parent  # eglantine-toolbox
RES = ROOT / "app" / "resources"

EXCLUDES = [
    "tkinter",
    "unittest",
    "pydoc",
    "doctest",
    "numpy",
    "PIL",
    "pandas",
    "matplotlib",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineQuick",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuickWidgets",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DRender",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtNetworkAuth",
    "PySide6.QtBluetooth",
    "PySide6.QtSql",
    "PySide6.QtTest",
    "PySide6.QtDesigner",
    "PySide6.QtHelp",
    "PySide6.QtOpenGL",
]

a = Analysis(
    [str(ROOT / "tool_entry.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(RES / "zh_CN.json"), "app/resources"),
        (str(RES / "icon.ico"), "app/resources"),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Eglantine工具箱",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(RES / "icon.ico"),
    version=str(ROOT / "build" / "version_info.txt"),
)
