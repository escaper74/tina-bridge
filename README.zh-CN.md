# TINA Bridge

**让 AI 帮你读 TINA 电路、改器件和接线、跑仿真、分析结果。**

TINA Bridge 把 Codex 接到你电脑上的 TINA-TI。装好后，直接告诉 AI 想改什么、想测什么，它就能操作电路并取回仿真数据。修改后保存的仍是 `.TSC` 工程，你可以在 TINA 里继续打开和编辑。

[English](README.md) · [下载](https://github.com/escaper74/tina-bridge/releases/latest) · [安装说明](plugins/tina-bridge/README.md)

## 可以怎么用

你可以直接这样说：

> 打开这个 TSC 文件，帮我看看输出端和反馈回路是怎么接的。

> 把 R1 改成 2kΩ，另存一份，再跑 20ms 瞬态仿真。

> 分别用 1kΩ、2kΩ、4kΩ 的负载跑一遍，比较输出电压和纹波。

你用自然语言交代任务，AI 通过插件在 TINA 中完成操作。

| 想做的事 | 插件能帮你做什么 |
| --- | --- |
| 看懂电路 | 读取器件、参数、引脚和节点，查连接关系，比较修改前后的电路 |
| 改图、搭图 | 增删器件和导线、按引脚接线、移动和旋转器件、修改参数、保存工程 |
| 配置信号源和器件 | 设置正弦、方波、单脉冲和 PWL，插入本机宏，选择库中的器件型号 |
| 跑仿真 | 瞬态、AC、DC 扫描、工作点、温度扫描、输出噪声谱、傅里叶图 |
| 看结果 | 读取波形数据，计算平均值、有效值、纹波、超调、稳定时间和阈值交点 |
| 做参数对比 | 扫描多组参数，做容差和敏感度实验，保存各组结果供比较 |

## 安装

准备好 **Windows、TINA-TI、Python 3.11 以上版本和 Codex**。本插件基于 **TINA-TI 9.3 简体中文版**开发。

1. 安装 [TINA-TI](https://www.ti.com/tool/TINA-TI)。
2. 从 [Release](https://github.com/escaper74/tina-bridge/releases/latest) 下载 ZIP，完整解压，保留其中的 `.agents` 文件夹。
3. 在解压后的根目录打开 PowerShell，执行：

```powershell
py -3 .\plugins\tina-bridge\setup.py --tina-exe '<tina.exe 的完整路径>'
codex plugin marketplace add .
codex plugin add tina-bridge@tina-bridge
```

把路径换成你电脑上 `tina.exe` 的位置。如果安装程序能自动找到 TINA，可以省略 `--tina-exe` 和后面的路径。

重启 Codex，在新聊天中给它一个 `.TSC` 文件，就可以开始用了。第一次可以先试：

> 用 TINA Bridge 打开这个电路，列出里面的器件和连接关系。

也可以把仓库地址发给 Codex，让它按照[安装说明](plugins/tina-bridge/README.md)帮你完成接入。

## 它是怎么工作的

插件在本机运行一个 MCP 服务，读取 TINA 导出的电路信息，操作原生编辑器和分析窗口，再取回求解结果。修改后的电路另存为新文件，仿真数据也保存在本机。

目前有 32 个工具和 15 种原生器件模板。需要自己写脚本调用时，可以查[工具表](docs/tools.md)和[参数示例](plugins/tina-bridge/references/usage.md)。

## 更多资料

- [安装与配置](plugins/tina-bridge/README.md)
- [电路编辑与操作参考](docs/reference.zh-CN.md)
- [分析与测量细节](docs/analyses.zh-CN.md)
- [测试和实际 TINA 案例](docs/validation.md)
- [开发与打包](docs/development.md)
- [同类项目](docs/related-work.md)

[MIT 许可证](LICENSE) · [第三方说明](THIRD_PARTY_NOTICES.md)
