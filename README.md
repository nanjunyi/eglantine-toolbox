# Eglantine 工具箱 · Eglantine Toolbox

给 [Eglantine](https://github.com/Eglantine-Community/Eglantine)（Switch 2 模拟器 · Eden 分支）的一体化 Windows 工具：
**下载安装 · 汉化 · 游戏启动 · 存档备份 · 金手指管理**，五页一个窗口搞定。

> An all-in-one Windows companion for the Eglantine (Eden) Switch 2 emulator — install & update, Chinese localization, game launcher, save backup, and cheat manager.

![release](https://img.shields.io/github/v/release/nanjunyi/eglantine-toolbox?display_name=tag)
![license](https://img.shields.io/github/license/nanjunyi/eglantine-toolbox)
![platform](https://img.shields.io/badge/platform-Windows%2010%2B-0078D4)
![python](https://img.shields.io/badge/python-3.9%2B-3776AB)

---

## 功能

| 页面 | 能做什么 |
|---|---|
| **启动模拟器** | 读 `qt-config.ini` 里登记的游戏目录，扫描 `.nsp/.xci/.nup/.nsz`，按 TitleID 把 Base / 更新 / DLC 合并成一行；显示大小、最近游玩、累计时长；双击直接启动 |
| **游戏存档** | 枚举 `nand\user\save\<容器>\<用户ID>\<TitleID>`，zip 快照备份 / 还原 / 导入 / 导出；还原前自动留一份快照，替换用「同卷临时目录 + 改名」，失败可回滚 |
| **金手指** | 按游戏管理 `load\<TitleID>\cheats\<build_id>.txt`；多套方案并存、随时切换生效、启停不产生垃圾文件；build_id 自动从模拟器日志推断，也可手填 |
| **更新与汉化** | 查上游每日构建 / 发行版，断点续传 + SHA-256 校验 + 加速源；装完自动生成中文语言包。支持对**空目录**全新安装 |
| **设置** | 网络（系统代理 / 加速源 / 测试连接）、路径（模拟器目录 / 备份目录 / 数据目录）、维护（清理更新缓存、修复存档残留）、关于 |

底部是全局状态栏与可折叠日志抽屉，五页共用；任务统一走后台线程，下载中可取消。

## 快速开始

1. 到 [Releases](https://github.com/nanjunyi/eglantine-toolbox/releases) 下载最新的 exe（`Eglantine-Toolbox-v2.1.0.exe`，运行后程序名是 `Eglantine工具箱`）
2. 放进模拟器目录（和 `eglantine.exe` 同级），或者随便找个目录放都行
3. 双击运行。首次启动会让你选模拟器目录；目录是空的也没关系，工具会走「全新安装」

> 首次运行 Windows 可能弹「已保护你的电脑」—— 因为没做代码签名。点「更多信息」→「仍要运行」即可。Release 页附了 SHA-256，可自行校验。

系统要求：Windows 10/11 64 位。存档、按键、图形设置都在 `%APPDATA%\eden`，工具不碰也不迁移。

## 从源码运行

```bash
git clone https://github.com/nanjunyi/eglantine-toolbox.git
cd eglantine-toolbox
python -m pip install -r requirements-dev.txt
python _dev/run.py
```

Python 3.9+（推荐 3.11/3.12）。本项目**只支持 Windows**：单实例锁、进程枚举、深色标题栏都走 Win32 API。

## 打包

```bash
python -m PyInstaller build/build.spec --noconfirm --clean --distpath dist --workpath build/work
```

产物 `dist/Eglantine工具箱.exe`，单文件、无控制台，约 45 MB。
版本号要改两处：`app/constants.py` 的 `VERSION`、`build/version_info.txt` 的四元组。

发布：`gh release create vX.Y.Z "dist/Eglantine工具箱.exe" --title "vX.Y.Z"`。

## 配置与目录

| 位置 | 内容 | 说明 |
|---|---|---|
| `Eglantine工具箱.json`（exe 同级） | 安装目录、选中版本、网络设置、备份目录、窗口大小 | 便携配置；目录不可写时退到 `%LOCALAPPDATA%\EglantineToolbox\config.json` |
| `logs\tool-YYYYMMDD.log` | 运行日志 | 出问题时先看这个 |
| `backups\saves\<TitleID>\` | 存档快照 zip | 默认在工具目录，可在设置页改 |
| `_update\` | 更新下载与解压临时目录 | 装完自动清理 |

**从 2.0.x 升级**：旧配置 `Eglantine汉化工具.json` 会被自动读取并写入新名字，设置不会丢；旧文件和 `%LOCALAPPDATA%\EglantineZhCN\` 都可以手动删掉（缓存会重建）。

## 与上游的关系

- 本工具**不包含、不分发**模拟器本体、游戏 ROM、密钥文件，安装时从上游 GitHub Release 现下现装
- 汉化方式是生成 `languages\zh_CN.qm` 并改官方 exe 里两字节的资源路径，不改逻辑；还原官方原版随时可点
- 更新源固定为 `Eglantine-Community/Eglantine`，与本仓库无关
- 请遵守上游项目的许可证与所在地区法律，仅用于个人学习研究

## 更多

详细用法（每个功能的操作步骤、常见问题）见 [`使用说明.md`](使用说明.md)。改动记录见 [`CHANGELOG.md`](CHANGELOG.md)。

## 许可

[MIT](LICENSE)
