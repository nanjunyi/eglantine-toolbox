# 更新日志

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [2.1.1] - 2026-11-10

### 修复
- 游戏列表与存档列表点文字选不中（行内标签吃掉了鼠标事件，连带双击启动也只在行尾生效）
- 存档页把 TitleID 当成游戏名显示（现在从模拟器日志里取名字，可右键改名）
- 右键没有反应（列表项的右键事件被行内控件截断）

### 新增
- 启动页默认只显示**模拟器识别过**的游戏，可勾选「显示未识别」查看全部；一个都没识别时自动降级为显示全部
- 右键菜单：重命名 / 恢复原名 / 置顶 / 上移 / 下移 / 隐藏 / 关联 TitleID / 复制 TitleID / 打开所在文件夹
- 「已隐藏的条目」面板：恢复显示或给没有 TitleID 的文件（.nup 等）关联 TitleID
- 存档页右键：重命名 / 打开存档所在目录；改名按 TitleID 保存，启动页与金手指页共用
- 列表行高亮与悬停样式、右键菜单深色样式

## [2.1.0] - 2026-11-10

首个开源版本。

### 变更
- 项目更名为「Eglantine 工具箱」，程序名改为 `Eglantine工具箱.exe`，配置文件名同步
- 归属信息集中到 `app/constants.py`：版本、显示名、仓库地址、UA 从此一处修改
- 界面「关于」增加工具仓库入口

### 新增
- 旧版配置 `Eglantine汉化工具.json`（含 `%LOCALAPPDATA%\EglantineZhCN\config.json`）自动迁移，升级不丢设置
- `README.md`、`CHANGELOG.md`、`LICENSE`（MIT）
- `requirements.txt` / `requirements-dev.txt`

### 移除
- 无用文件：`app/main_1_1_2.py.bak`、`app/settings_dialog.py`、`app/pages/placeholder.py`

## [2.0.1]

### 修复
- 窗口标题栏跟随暗色主题（`DwmSetWindowAttribute`，不支持的系统自动跳过）

## [2.0.0]

### 新增
- 从单页汉化工具改造为侧边栏工具箱：启动模拟器 / 游戏存档 / 金手指 / 更新与汉化 / 设置
- 游戏列表按 TitleID 合并 Base / 更新 / DLC，双击启动
- 存档 zip 备份 / 还原 / 导入 / 导出，还原前自动快照
- 金手指多方案管理（`load\<TitleID>\cheats\<build_id>.txt`）
- 全局任务总线、状态栏、可折叠日志抽屉

## [1.1.2]

### 新增
- 支持往空目录全新安装（不再要求目录里已有 `eglantine.exe`）

### 修复
- 磁盘空间检查在路径不存在时失效
- `qt-config.ini` 没有 `[UI]` 段时语言键写错位置，导致装完仍是英文

## [1.1.0]

### 新增
- 全新安装、还原官方原版、启动模拟器、深色主题

## [1.0.0]

首个可用版本：下载上游安装包、生成中文语言包、补丁 exe。
