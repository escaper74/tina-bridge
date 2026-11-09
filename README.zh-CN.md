# TINA Bridge

让支持 MCP 的 AI 客户端读取、编辑和仿真 **TINA-TI 原生工程**的 Windows 本地桥接器。它读取真实器件与网表，修改 `.TSC` 副本，调用 TINA 求解，再取回数值与原生结果文件。

[英文主页](README.md) · [完整安装说明](plugins/tina-bridge/README.md) · [中文操作参考](docs/reference.zh-CN.md) · [完整参数示例](plugins/tina-bridge/references/usage.md)

## 适用环境

- 已实测：Windows 登录桌面、**简体中文 TINA-TI 9.3.150.328SF-TI**、Python 3.13.7。
- 安装器要求 Python 3.11+，检查 TINA 文件版本；其他版本会被拒绝。
- 其他语言、其他 TINA 版本、第二台实体电脑仍未验证。需要原生桌面，不是无窗口求解器。
- TINA 请从 [TI 官方页面](https://www.ti.com/tool/TINA-TI)单独安装。包内不含 TINA、本机配置、厂商芯片模型、手册或厂商示例工程。

## 安装

解压 [Release](https://github.com/escaper74/tina-bridge/releases/latest)，保留 `.agents` 隐藏目录。在解压根目录执行：

```powershell
py -3.13 .\plugins\tina-bridge\setup.py --tina-exe '<已安装 tina.exe 的完整路径>'
& "$env:LOCALAPPDATA\TinaBridge\venv\Scripts\python.exe" .\plugins\tina-bridge\check.py --mcp
codex plugin marketplace add .
codex plugin add tina-bridge@tina-bridge
```

若安装发现能定位唯一 TINA，可省略 `--tina-exe`。刷新或重启客户端，在新聊天使用。安装器只创建独立 Python 环境、设置和配置片段，**不会自动更改 Codex 全局配置**。不用插件的 MCP 客户端可按完整安装说明接入同一 stdio 服务。GitHub 开源与 Release 发布不等于已进入 OpenAI 公共插件目录。

## 已实现功能

32 个 MCP 工具、15 种原生器件模板，具体字段以当前 schema 和 `tina_catalog` 为准：

| 类别 | 能力 |
| --- | --- |
| 读图 | 器件、参数、位置、线段、节点、宏端口；结构化查询和快照比较 |
| 原生编辑 | 增删器件/导线、按引脚接线、改名、移动、旋转、镜像、改外围参数、另存 |
| 器件与波形 | 本机宏插入；六类分立器件库内选型与有限实例字段；正弦/方波/单脉冲/PWL |
| 分析 | 瞬态、AC、DC 扫描、工作点、温度、输出噪声谱、Fourier 原生图 |
| 数据与实验 | 原始数值、时间加权统计、纹波/阈值/稳定时间等；参数批次、容差、敏感度与边界候选 |
| 会话 | 独立进程、工程/结果页管理、持久作业、重连接续与取消 |

正常操作通过进程内窗口消息和可访问性接口完成，不依赖全局鼠标键盘、剪贴板或截图识读。图的电气连接以原生导出为准，画面只辅助看布局。

## 必须明确的限制

含加密芯片宏的工程不能走 XML 导入往返；使用原生编辑，工厂宏内部保持不变。Fourier 目前只有原生 TDR 图，**没有可靠数值谐波系数导出**。噪声只验证输出幅度谱密度，不能宣传为已支持输入/总噪声或 SNR。批次案例目前只支持外围数值和已有 PWL 的修改，不能任意改变拓扑。`pulse` 是单次脉冲，`square` 是围绕直流电平的 50% 双极性方波。

同一进程一次只运行一个分析；查询并收集前一作业后再运行。实验使用自己的进程和新输出文件，不接管其他人的 TINA 窗口。

## 验证与贡献

公开版继承 0.2.0 已有真实验证，包括独立包读取 TPS40200、修改外围并增加并联负载、保存重开、0–1.5 ms 瞬态和数据读取。原内部离线套件记录为 75 项；公开仓库提供 **68 项可独立运行的测试**，不分发另 7 项依赖的私有原生导出。安装/协议检查、真实电路验证和第二台机器验证分别说明，详见 [验证记录](docs/validation.md)。

同类调研发现商业版 TINA 已有 Python/AI 功能，LTspice/ngspice 也已有多种开源 MCP。本项目的贡献定位是免费 TINA-TI 9.3 原生工程的结构化操作。2026-11-09 的检索范围内未发现直接等价的公开适配器，**不宣称全球唯一**。链接与维护情况见 [调研记录](docs/related-work.md)。

自有代码采用 [MIT](LICENSE)。依赖和厂商资产保持各自许可，见 [第三方说明](THIRD_PARTY_NOTICES.md)。欢迎提供可公开的最小复现、实际 TINA 版本、界面语言和工具报错；请先移除模型、路径与数据中的隐私内容。
