# QuotaBoard — AI 额度悬浮窗

Windows 桌面悬浮窗小工具，实时展示 ChatGPT / 豆包 / 智谱清言 / OpenAI / Kimi / 火山方舟 等平台的额度与用量。PySide6 实现，单文件 exe / MSI 安装包交付。

## 功能

**API 余额（自动）**

| 平台 | 方式 | 说明 |
| --- | --- | --- |
| OpenAI | API Key | 余额查询接口 |
| 智谱 GLM | API Key | 余额查询接口 |
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

- 桌面悬浮窗：绿（≥30%）/ 黄（<30%）/ 红（<10%）状态色；点击折叠/展开
- 设置页：滚动布局、屏幕自适应；凭据经 Windows DPAPI 加密后仅存本机 `%APPDATA%\QuotaBoard\config.json`
- 默认 30 分钟自动刷新，托盘菜单含开机自启

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
