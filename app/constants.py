"""品牌与仓库信息的唯一来源。

这个模块只放字面量，**不导入 PySide6、不导入其它 app 模块**，
因此 `core/` 层可以安全地 `from ..constants import ...` 而不引入 Qt 依赖。
"""

VERSION = "2.1.1"

# 便携配置文件名 = f"{APP_NAME}.json"（放在 exe 同级目录）
APP_NAME = "Eglantine工具箱"
# %LOCALAPPDATA%\EglantineToolbox：配置兜底、单实例锁、版本缓存、游戏列表缓存
APP_ID = "EglantineToolbox"

# 界面显示名（窗口标题、关于页、日志）
DISPLAY_NAME = "Eglantine 工具箱"
# 侧边栏顶部品牌字：栏宽 208px，放全名会挤
SIDEBAR_BRAND = "Eglantine"

# 2.0.x 及更早版本的命名，仅用于配置迁移
LEGACY_APP_NAME = "Eglantine汉化工具"
LEGACY_APP_ID = "EglantineZhCN"

REPO_OWNER = "nanjunyi"
REPO_NAME = "eglantine-toolbox"
REPO = f"{REPO_OWNER}/{REPO_NAME}"
REPO_URL = f"https://github.com/{REPO}"

# 上游模拟器（更新下载源），与本工具仓库无关
UPSTREAM_REPO = "Eglantine-Community/Eglantine"

USER_AGENT = f"{APP_ID}/{VERSION} (+windows)"
COPYRIGHT = f"MIT License · Copyright (c) 2026 {REPO_OWNER}"
