# QuotaBoard — AI 额度悬浮窗

Windows 桌面悬浮窗小工具，实时展示 ChatGPT / 豆包 / 智谱清言 / OpenAI / Kimi / 火山方舟 等平台的额度与用量。PySide6 实现，单文件 exe / MSI 安装包交付。

## 功能

**API 余额（自动）**

| 平台 | 方式 | 说明 |
| --- | --- | --- |
| OpenAI | API Key | 余额查询接口 |
| 智谱 GLM | API Key | 连接校验走 `GET /api/paas/v4/models`；余额接口已于 2026-11 下线（`/api/paas/v4/balance` 返回 404，控制台内部余额端点不对 API Key 开放），条目改显示提示 |
| Kimi | API Key | 余额查询接口 |
| 火山方舟 | AK/SK | 官方签名（HMAC-SHA256）调用 GetUsageDetails |

**订阅额度（自动）**

| 平台 | 方式 | 说明 |
| --- | --- | --- |
| ChatGPT 用量（5h/周） | 官方 codex 本地协议 | 通过 ChatGPT Windows 应用内置的 Codex（或 npm Codex CLI）JSON-RPC 读取账号 5 小时与每周限额，悬浮窗以双环形图展示；鉴权由已登录账号处理，不接触凭据 |
| ChatGPT Plus | 登录 Token | backend-api accounts/check 试点接入 |
| 智谱清言会员 | 本地登录态 | 自动读取客户端登录 Cookie（`chatglm_token`），DPAPI 加密缓存到本机；客户端运行中自动回退缓存；支持设置页手动粘贴 Token；展示会员等级、剩余 Token 百分比、到期时间 |
| 豆包订阅（5h/周+活动赠送） | 登录会话自动发现 | 自动检测豆包客户端登录会话（sessionid + x-tt-multi-sids，内存只读扫描），调用订阅配额接口读取 5 小时 / 周双窗口用量与活动赠送额度，双环形图展示；读取成功加密缓存，客户端关闭也能显示；支持设置页手动粘贴 sessionid |

**手动维护（蓝色条目）**

- 任意自定义条目（如无自动接口的平台）

## UI

- 桌面悬浮窗：绿（≥75%）/ 黄（30–74%）/ 红（<30%）状态色；点击折叠/展开
- 设置页：滚动布局、屏幕自适应；凭据经 Windows DPAPI 加密后仅存本机 `%APPDATA%\QuotaBoard\config.json`
- 默认 1 分钟自动刷新，托盘菜单含开机自启

## 安装

- **MSI 安装包**（推荐）：`dist/QuotaBoard.msi`，安装后开始菜单/桌面快捷方式启动
- **绿色版**：`dist/QuotaBoard.exe`，单文件直接运行
- 最新发布版：GitHub Releases `Othrik/QuotaBoard`（https://github.com/Othrik/QuotaBoard/releases）
- 首次使用智谱清言会员额度：**关闭智谱清言客户端**再打开 QuotaBoard 一次，程序自动读取登录态并缓存，之后客户端可常开
- 豆包额度：打开豆包客户端并登录即可自动检测；读取成功后加密缓存，客户端关闭也能显示

## 开发

```bash
pip install -r requirements.txt
python main.py              # 运行
python tests_smoke.py       # 冒烟测试
python -m PyInstaller QuotaBoard.spec   # 打包 exe
```

MSI 构建（需 WiX Toolset 3.14）：

```bash
candle QuotaBoard.wxs
light -ext WixUIExtension QuotaBoard.wixobj -o dist/QuotaBoard.msi
```

## 隐私

- 所有凭据（API Key / Token）用 Windows DPAPI 加密后仅存本机，不上传任何数据
- ChatGPT 用量读取仅调用本机官方 codex 协议，不经手任何账号凭据


## 内置任务栏额度（1.1.29）

只需安装/启动 QuotaBoard，在设置 → 通用或托盘菜单中开启“任务栏常驻额度”。不需要单独安装 Taskbar Widgets 或导入扩展包。内置 QuotaBoard.TaskbarHost 辅助进程由主程序管理，没有独立托盘、设置窗口、更新服务或网络请求；退出主程序或关闭功能时自动退出。任务栏右键打开 QuotaBoard 设置，拖动位置会保存。

任务栏保持透明背景，每5秒轮换已启用的 AI。图标、额度颜色、耗尽后的重置提示复用展示板逻辑，悬停查看当前 AI 详情。凭据仍只由 QuotaBoard 读取，任务栏组件只读取无凭据的布局和额度数据。辅助组件文件和运行数据保存在 QuotaBoard 配置目录的 Taskbar 子目录中。

内部组件基于 MIT 许可的 Taskbar Widgets 修改，许可随程序分发。构建来源和 SHA-256 记录在 assets/taskbar/build.json，构建补丁在 tools/patch_taskbar_*.py。开发打包前，从该记录对应的构建产物取得 QuotaBoard.TaskbarHost.exe 并放到 assets/taskbar/；二进制不存入 Git。任务栏嵌入仍依赖 Windows 私有界面，需要持续适配系统更新。

从旧双软件方案迁移时，应先退出独立 Taskbar Widgets，再启用 QuotaBoard 内置显示，避免两套组件同时控制任务栏。迁移后的首次显示可能需要重启资源管理器以清除旧组件。


### 1.1.30 显示与设置更新

- 修复原生空白文字被替换为重复横线的问题，悬停卡片只生成实际存在的详情行。
- 默认任务栏位置向左调整，设置 → 通用与显示可左右微调或恢复左侧位置。
- 5h / 周标签与百分比使用独立的固定间隔块，保留各额度独立颜色和耗尽后的重置提示。
- 设置默认打开通用页；平台侧栏显示启用状态；排序支持拖动和上移/下移。
- 连接测试在后台执行，结果显示在当前页面；已保存凭据留空保留，更改保存后统一刷新。


### 1.1.31 点击详情、字体与轮播更新

- 点击详情由 QuotaBoard 自身的白色窗口显示，限制在屏幕可见范围内；长内容可滚动，Esc 或点击其他位置关闭。
- 详情保留被点击 AI 的信息，不随任务栏轮播跳到其他平台；修复点击与拖动冲突及重复打开设置的问题。
- 名称与额度默认统一使用微软雅黑 UI 粗体，设置中可调整字体、粗细及字号，并预览效果。
- 请求失败的平台立即暂停轮播，成功后自动恢复；全部失败时额度条暂时隐藏，仍按设置周期继续查询。
- 智谱 GLM 更换为用户提供的 Z.AI 图标，智谱清言图标保持不变。


### 1.1.32 天气小组件字体、Z.AI 图标与设置面板

- 名称与额度字体可分别设置：新增「AI 名称」（默认 Segoe UI Variable Text 常规 12px）与「额度数字」（默认 Segoe UI Variable Display 较粗 15px）两组，各带字体、粗细、字号；一键「应用天气小组件风格」复刻 Windows 11 任务栏天气小组件的 Text + Display 光学尺寸组合。
- 字体族扩展为微软雅黑 UI / 微软雅黑 / 等线 / Segoe UI Variable 全系列（Text、Display 及 Semilight、Light、Semibold 变体），任务栏额度条与展示板共用同一套组合字体。
- 智谱 GLM 图标替换为用户提供的 `zai.svg` 渲染结果，智谱清言沿用原图标；同步更新原生任务栏组件的图标映射。
- 设置面板不再强制置顶，也不再以悬浮窗为父窗口；点击「保存并刷新」后面板保持打开、显示保存状态并立即刷新额度，关闭需点「关闭」。
- 智谱开放平台余额接口失效的提示更明确：Key 与域名连通正常（`/models` 可访问），余额端点为 404 时提示到控制台查看。


### 1.1.33 消除悬停小窗闪烁

- 修复刷新时悬停提示小窗连续弹出又消失：一轮刷新里每个平台返回都会重绘一次，原先每次都销毁并重建全部行，鼠标下的行反复重建导致提示窗反复弹出。现在同一次事件循环内的多次重绘合并为一次。
- 指针停在面板上时推迟重建行，等指针离开再重绘，悬停期间提示窗只显示一次、不再闪烁；点击头部「刷新」则立即重绘，操作即时可见。
- 悬停卡片文本未变化时不再重复 `show()/raise_()`；离开行时延迟 140 ms 才隐藏，指针在相邻控件间移动不会再闪成多次。
- 任务栏托管模式下同样的重绘合并生效，悬停展开的小窗同样稳定。
