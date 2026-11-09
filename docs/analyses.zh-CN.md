# TINA-TI 原生温度、噪声与傅里叶分析

本模块针对本机 **TINA-TI 9.3.150.328SF-TI**，使用已有的进程绑定 Win32 接口和原生求解器。实现位于 `analysis_extra.py`，已接入 `service.py` 与 MCP；公共入口统一使用 `tina_run_analysis` → `tina_job_status`，不需要绕过 MCP 调用内部函数。

## 可交付范围

| 分析 | 启动函数 | 收集结果 | 本轮验证 |
|---|---|---|---|
| DC 温度扫描 | `start_temperature(tina, start=None, end=None, points=None)` | `collect_pages(tina, job, directory)` | 12 V 分压器含 R1 线性温度系数，-20～80°C 的真实输出与公式一致 |
| 输出噪声谱 | `start_noise(tina, start=None, end=None, points=None, signal_amplitude=None, outputs=None)` | `collect_pages`，数值用 `read_output_noise(path)` | 1 kΩ / 1 µF RC，10 Hz～100 kHz，在 27°C、77°C 均符合热噪声及 RC 传递函数 |
| 原生傅里叶级数图 | `start_fourier(tina, signal, start=None, fundamental=None, samples=4096, harmonics=16, initial=None)` | `poll_fourier` → `collect_fourier` | 100 Hz 双极性方波经过 RC，原生图有非零且递减的奇次谐波；仅交付 TDR，不提供数值系数 |

所有启动函数返回已有 job 结构：PID、可执行文件、分析类型、原生对话框设置回读值、当前电路标题、先前结果页状态、开始时间。调用方应像现有分析一样记录 `solver_parameters` 和 `job_file`。

`points` 保留原生对话框语义；本轮 Points=100 的温度扫描得到 101 点，Points=121 的噪声扫描得到 122 点，不把 UI 的点数直接当作导出样本数。

## 单位与实际限制

- 温度扫描横轴为 **°C**，返回页元数据 `axis_unit="degC"`。输出曲线仍是电路中实际选定的电压/电流探针；原生文本列名未必带输出单位，不能仅凭自定义探针名猜单位。
- 噪声频率横轴为 **Hz**。电压输出的 `-abs` 列已实测确认为 **V/√Hz 的幅度谱密度**。其他输出类型的单位没有在本轮验证，接口没有统一强行标成 V/√Hz。
- 原生噪声文本还带 `-phase (deg)` 列。本例它是与频率无关的辅助数组，不作为物理“噪声相位”解释。`read_output_noise` 只返回 `-abs` 信号，辅助列名保留在 `auxiliary_native_columns`，原始列仍保存在文本文件中。
- **输入噪声、总噪声、SNR 没有开放数值接口。** 本机分别选择这些原生图，甚至单独启动输入噪声，文本仍导出相同的输出噪声底层数组，不能当作对应变换后的数值。`start_noise` 只接受默认值或 `outputs=["output"]`，其他值在触碰 UI 前拒绝。
- 噪声分析需要 TINA 可识别的输入源；只有直流电池的分压器不满足本版的原生分析输入要求。本轮用电压信号发生器验证。
- 傅里叶格式固定为原生 `D * cos(kwt + fi)`；`samples` 从原生列表中选择（128～65536 的二次幂），`harmonics` 为 2～16，`signal` 必须是原生下拉框中的名字。`initial` 使用已有的 `zero / use / operating_point`。
- **傅里叶只交原生图。** 它的柱线对象没有作为谐波数组出现在文本导出中；得到的是坐标占位点，不是谐波系数。返回 `native_only=true`、`numeric_export_supported=false`，没有伪造 `text_path/data`。
- **首次没有 TR 结果也可启动 Fourier**，已在全新进程中经 MCP 验证，`previous_results=[]`。但采样区间 `[start, start+1/fundamental]` 必须位于原生 Transient 对话框设置的时间窗内；不能仅设置 Fourier 起点就隐含扩大原生瞬态求解时间。本轮一份 RC 文件的原生范围为 0～10 ms，请求 50 ms 起点会报 `50m - 无效数!`，改用 0～10 ms 后直接成功。若需要稳态后窗口，可先用现有 transient 接口运行所需区间。每次 Fourier Calculate 仍会产生自己的 TR 页。

## 已集成的调用链

`tina_run_analysis` 的 `kind` 分别取 `temperature/noise/fourier`，设置字段直接放在工具参数中。温度使用 `start/end/points`；噪声使用 `start/end/points/signal_amplitude`，公共接口固定输出噪声，不提供 `outputs` 切换；Fourier 使用 `signal/start/fundamental/samples/harmonics/initial`。完整七种分析见 [操作参考](reference.zh-CN.md)。

`service.run_analysis` 分派到上表启动函数。温度与噪声完成后由 `collect_pages` 收集新增页，返回页名称、实际设置、横轴单位、文本与整个原生 TDR；Fourier 使用 `collect_fourier`，返回选定页、TDR 和数值导出限制。调用方不能假定每种分析都含 `text_path/data`。

普通轮询已将 `TTempAnalDlg`、`TNoiseAnalDlg` 视为启动过渡状态，避免刚点击 OK 尚未关闭时报告 attention。

**Fourier 必须用专门轮询。** 本机 Fourier 求解期间 `TApplication` 标题仍为 TINA，Draw 按钮始终 enabled，`TPercentageDlg` 开始时存在但隐藏。`poll_fourier` 检查所有进程窗口中的进度窗（包括隐藏窗口），并排除把前置 TR 页当作 Fourier 完成。`start_fourier` 等待原生进度窗或新 TR 页确认启动，不依赖固定延时猜测完成。

`tina_cancel_job` 已为 Fourier 分派 `request_cancel_fourier`，对进程内的原生进度窗发送局部 Escape；若算完但尚未绘图则关闭待绘制表。取消标记持久化后继续 `tina_job_status` 等到 cancelled。该路径已真实验证。

`tina_read_result` 依据文本同目录 `job.json` 中的分析类型识别噪声，调用 `read_output_noise`，返回密度信号及辅助列说明。不能仅凭 `-abs/-phase` 文件头猜测，因为 AC 也使用这些名字。离线复制结果时保留 job 元数据；单独的原始文本仍可能含这些辅助数组。内部直接读取可用 `read_output_noise(path)` 后再 `results.select(...)`。

## 多坐标图文本导出

`export_text_diagrams(tina, path)` 只发送一次原生“导出为文本”，并完成它触发的全部 `Save diagram` 对话框。第二个及以后文件命名为 `*-diagram-2.txt` 等，返回每个实际文件路径和字节数。它不承诺每种图形的文本都能解析成数值。

Fourier 的幅度/相位两个坐标图会触发两个保存框，旧导出曾在第一个文件落盘后提前返回。`Tina.export_result` 现已使用多坐标处理函数；对 Fourier 数值导出则直接给出限制，`tina_export_results` 改为保存 TDR。温度、输出噪声及已测普通瞬态单坐标页均只触发一个框；不据此假定所有 AC/其他图都只有一个框。

原生 `.tdr` 保存整个图表文档，可能包含旧页；`collect_pages.pages` 只列本 job 新增的文本页，`collect_fourier.page.selected` 标出应看的 Fourier 页。若在已有图表窗口中重新打开 TDR，TINA 追加这些页；选择索引应加上原有页数。
