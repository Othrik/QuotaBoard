# QuotaBoard

Windows 桌面小工具，把常用 AI 服务的额度与用量汇总到一个悬浮窗里，随时瞄一眼就知道还剩多少。

## 支持的平台

| 平台 | 展示内容 |
| --- | --- |
| ChatGPT | 5 小时 / 每周限额 |
| 豆包 | 5 小时 / 每周额度 |
| Gemini | 5 小时 / 每周额度 |
| 智谱清言 | 会员积分 |
| DeepSeek、DMXAPI | 账户余额 |
| OpenAI、Kimi、智谱 GLM | API 余额（接口可用时） |
| 其他 | 可手动添加任意条目 |

## 特性

- 双环形图与进度条，绿色 / 黄色 / 红色表示剩余状态
- 可折叠成小条，贴在桌面角落或任务栏上方
- AI 名称与额度数字的字体、粗细、字号可分别调整
- 后台定时刷新，托盘常驻，支持开机自启
- 可选「任务栏常驻额度」，把额度直接放进任务栏，点击查看详情

## 安装

- **MSI 安装包**（推荐）：从 [Releases](https://github.com/Othrik/QuotaBoard/releases) 下载，安装后在开始菜单启动
- **绿色版**：单文件 exe，直接运行
- 系统要求：Windows 10 / 11（64 位）

## 使用提示

- 智谱清言、豆包：先在对应客户端登录一次，QuotaBoard 会自动读取登录态并存到本机，之后客户端关掉也能显示
- 其他平台：在设置里填入 API Key，可先点「测试连接」确认可用
- 任务栏常驻、开机自启、刷新间隔等都在设置页或托盘菜单里切换

## 隐私

- 凭据加密后仅保存在本机配置文件，不上传任何服务器
- 只有查询额度时会向对应服务商发请求，不收集使用数据

## 开发

```bash
pip install -r requirements.txt
python main.py                              # 运行
python -m tests.tests_smoke                 # 冒烟测试
python -m PyInstaller QuotaBoard.spec       # 打包 exe
```

MSI 安装包需要 WiX Toolset 3.14。

## 版本

最新版本与完整变更记录见 [Releases](https://github.com/Othrik/QuotaBoard/releases)。
