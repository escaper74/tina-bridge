# TINA Bridge 操作参考

## 一次完整操作

1. `tina_sessions` 发现进程；开发或批次用 `tina_create_session` 建立自己的进程。同一 PID 顺序操作，不接管其他聊天的实例。
2. `tina_project(open)` 打开 `.TSC`，`tina_read_circuit` 取得快照。未接完的电路用 `include_connectivity=false`，先查看器件和布局，避免为不完整网络触发网表 ERC。
3. 用 `tina_query_circuit` 查询器件、节点或模型引脚，再用原生编辑或普通 XML 编辑生成新的 `.TSC`。读取修改后的快照，以 `tina_compare_circuits` 核对变化。
4. 打开工程后用 `tina_analysis_parameters` 设置当前求解参数；`tina_run_analysis` 返回持久 `job_file`，继续 `tina_job_status`，完成并收集后才启动下一次分析。
5. `tina_read_result` 离线读取统计或指定区间的原始采样；`tina_measure_result` 计算所需指标。傅里叶返回原生图，不能当作数值波形文件使用。
6. `tina_documents` / `tina_select_document` 管理电路页，`tina_result_pages` / `tina_select_result_page` 管理图表页。保存自己的工程和结果后，按需 `tina_project(close)` 或 `tina_exit_session`。

普通编辑保留输出页供查看；批量实验默认在成功保存后收起自己的案例页。TINA 关闭最后一页可能再生成“未命名”页，退出专属进程时可保存这张自有空白页后直接退出。接口不会丢弃未保存修改，也不会强杀进程。

## 用结构化数据看电路

`tina_read_circuit` 返回实际 XML、网表、器件参数、位置/方向、线段、宏接口和模型哈希；完整读取还生成 `snapshot.json`、`circuit-view.json` 与 `circuit.txt`。因此后续查电路不必重新扫描整个 GUI。

- `tina_query_circuit(snapshot, component="R1", depth=1)` 查询器件及邻接网络；也可按 `net`、`pin` 或公开子电路的 `hierarchy` 查询。
- `tina_compare_circuits(before, after)` 比较器件、参数、布局和端点连接。纯数字节点重新编号不当作断线，命名网络变化仍保留。
- 引脚编号指模型端子顺序，不自动等于芯片封装脚号；静态连通关系也不等于某一瞬间的电流方向。加密宏保持不透明，未知网表语句保留为 `unparsed`，返回覆盖范围。

## 编辑与搭建

`tina_native_edit_circuit` 从原生 `.TSC` 打开私有副本，逐项操作并读回，保存到新的目标路径。它支持：

| 操作 | 用法 |
| --- | --- |
| `add_component` / `remove_component` | 插入实时 catalog 提供的模板，或删除明确器件 |
| `rename` / `layout` | 改参考名、移动、正交旋转、镜像 |
| `add_wire` / `remove_wire` / `connect` | 编辑正交线段；`connect` 可用器件/模型引脚或坐标，`via` 指定经过点 |
| `set_parameter` / `set_pwl` / `set_waveform` | 改外部属性、已有 PWL 文本或电压源波形 |
| `add_macro` | 插入本机已存在的 `.TSM` 宏文件，返回新器件引用、ID 和源文件哈希 |
| `set_device_model` / `set_device_instance` | 选择当前库族中的分立型号，或改工具明确公开的实例属性 |

模板和可编辑属性以 `tina_catalog` 的 `native_templates`、`native_waveforms` 及工具 schema 为准。`tina_find_library` 查找本机示例、宏和模型文件。`add_macro` 使用 `macro_file/position/orientation`，不改写厂商模型；已完成本机 UA741 宏的原生插入和接线，其他宏仍按实际接口和读回结果核对。

`tina_device_models(pid, component)` 读取现有 D/Schottky/NPN/PNP/NMOS/PMOS 的当前库族、可选型号和 `public_fields`。`set_device_model(component, model)` 选择其中已有型号；`set_device_instance(component, field, value)` 支持温差 `temperature_delta_C`、D/BJT 面积系数 `area_factor`、MOS 倍数 `multiplicity`。普通 `set_parameter` 对这些类型会引导使用专用操作；不修改库内模型常数或加密宏内部。

例如，在已经读回并确认端子的 R7 两端并接一个测试电阻：

```json
{
  "tool":"tina_native_edit_circuit",
  "arguments":{
    "pid":12345,
    "source_tsc":"<source.TSC>",
    "save_path":"<with-test-load.TSC>",
    "operations":[
      {"op":"add_component","template":"resistor","reference":"R_TEST","position":[1200,312],"orientation":90,"parameters":{"0":"100"}},
      {"op":"connect","a":{"component":"R7","pin":"1"},"b":{"component":"R_TEST","pin":"1"}},
      {"op":"connect","a":{"component":"R7","pin":"2"},"b":{"component":"R_TEST","pin":"2"}}
    ]
  }
}
```

示例中的 PID、源文件、器件名、引脚和坐标要来自当前工程。原生移动或删除可能改变邻接线段几何；实际电气连接以网表读回为准。线段索引按当前顺序解释，连续删除时索引会变化。未接完的搭建可暂用 `include_connectivity=false`，接完后再读完整网表。

仅改外部数值时可用较小的 `tina_native_parameters`，已验证 R/C/L、VG、电池的正交旋转与镜像定位。普通**未加密**电路也可用 `tina_edit_circuit(source_xml, operations, save_path)`；`tina_catalog.empty_xml` 可作为空白起点，`clone_component` 可复制普通器件及其引用子电路。XML 布局修改不会自动重布线。

**含加密宏的工程使用原生编辑。** 本版 TINA 的 XML 导入会静默丢失加密 TPS40200，接口因此拒绝这类导入；读取 XML/网表仍可用。原生路径保留原厂宏及其内部子电路，保存前核对模型、连接和未请求修改的器件。器件数值变化导致的未启用扫描范围默认值调整，会在 `native_adjustments` 中单列。这里的接口验证不替代芯片手册与物理行为验证。

## 信号源

在 `tina_native_edit_circuit.operations` 中使用 `set_waveform`；波形类型与字段从 `tina_catalog.native_waveforms` 读取。例如：

```json
{"op":"set_waveform","component":"VG1","waveform":"square","parameters":{"amplitude":"2.5","frequency":"20k","rise_fall":"10n"},"dc_level":"2.5"}
```

这表示以 2.5 V 为中心、幅度 ±2.5 V 的原生 50% 方波。`sine` 使用幅值/频率/角度相位；`square.rise_fall` 是原生 τ，完整 −A 到 +A 跃迁占 2τ；`pulse` 是从零时刻开始的单脉冲，不能当周期 PWM；`pwl` 使用时间/电压对，当前没有周期重复扩展。省略 `dc_level` 保留原直流值。

本版 XML 导出曾使运行中顶层正弦 VG 的相位增加 90°，即使导出文件仍写原相位。`bridge.export_xml` 现已在导出后通过原生控件还原并读回，恢复记录在导出回执中；只处理顶层原生 VG，不遍历或改动厂商宏内部。

## 分析、结果与批量实验

| `kind` | 本次运行设置 | 返回内容 |
| --- | --- | --- |
| `transient` | `start/end/initial` | 各信号原始时间采样、文本与 TDR |
| `ac` | `start/end/points/sweep` | 原生频率、dB/degree 列与 TDR |
| `dc` | `source/start/end/points` | DC 扫描曲线与 TDR |
| `operating_point` | 无覆盖项 | 原生 DC 表、SI 数值、单位及节点顺序 |
| `temperature` | `start/end/points`，温度为 °C | DC 温度曲线与 TDR |
| `noise` | `start/end/points/signal_amplitude` | 输出噪声幅度谱密度；电压输出为 V/√Hz |
| `fourier` | `signal/start/fundamental/samples/harmonics/initial` | `native_only=true` 的 TDR；无数值谐波系数 |

`initial` 为 `zero/use/operating_point`，`sweep` 为 `log/linear`。对话框设置不保证写回工程，打开 TSC 后显式配置每次运行。`tina_analysis_parameters` 返回十个实际生效参数，`job.json` 同时记录设置与回读值；其中 **DC 相对误差索引 4、瞬态相对误差索引 25、最大时间步长索引 30**。不能用导出文件中的旧值冒充当前设置。`points` 沿用原生字段，实际样本数看结果。

首次没有 TR 历史也能运行 Fourier，但采样区间 `[start, start+1/fundamental]` 必须落在原生 Transient 设置的时间窗内。需要更晚的稳态窗口时，先用 transient 接口运行所需区间。Fourier 线谱的文本导出只有坐标占位点，不能作为系数；`tina_job_status` 与 `tina_export_results` 均按原生图返回。噪声只开放输出谱；输入/总噪声/SNR 的原生文本变换未保真，原始 `-phase` 辅助列不能解释为噪声相位。细节见 [analyses.zh-CN.md](analyses.zh-CN.md)。

文本保留各信号独立采样网格，`tina_read_result` 不静默抽点；读取噪声作业目录中的文本时依据同目录 `job.json` 识别类型、返回密度与辅助列说明，不能仅按 `-abs/-phase` 列名猜测。多坐标图的连续保存框会逐个完成；TDR 包含整个图表文档，可能有旧页，按结果中的页索引选择。`tina_open_results` 追加页面，索引需计入原有页数。

`tina_cancel_job` 请求原生取消后继续查询，确认 `cancelled`；部分结果不算完整分析。错误以 MCP `isError` 或 job `attention` 返回；`tina_dismiss_errors` 只确认 Error/ERC，不处理未保存或覆盖提示。

成组实验使用 `tina_experiment_design` 生成网格、容差或敏感度案例，再 `tina_batch_prepare` → `tina_batch_advance`。冻结基线、改动、实际参数、作业和指标都留在 manifest 中，客户端重连后继续同一作业。新批次默认 `close_completed=true`：结果与指标保存后，仅另存并关闭仍为当前活动、名称唯一匹配的自有 case 页；`false` 可保留对照。原先页面不动，批次不自动退出进程。详见 [experiments.zh-CN.md](experiments.zh-CN.md)。
