# TINA Bridge 调用示例

以下是 MCP 工具参数。路径、PID、器件名、探针名和数值都要换成当前实验实际值。先用 `tina_sessions` / `tina_read_circuit` / `tina_catalog` 取得依据；PID 不跨软件重启沿用。原生事务输出必须是新的 `.TSC` 路径。

## 原生器件与波形

`tina_native_edit_circuit` 的 `operations` 是顺序执行的操作列表。例如在现有电压发生器 VG1 上设置 0～5 V 的原生 50% 方波：

```json
{
  "pid": 12345,
  "source_tsc": "<源工程绝对路径.TSC>",
  "save_path": "<新工程绝对路径.TSC>",
  "include_connectivity": true,
  "operations": [
    {"op":"set_waveform","component":"VG1","waveform":"square","parameters":{"amplitude":"2.5","frequency":"20k","rise_fall":"10n"},"dc_level":"2.5"}
  ]
}
```

`sine` 使用 `amplitude/frequency/phase`（V/Hz/deg）；`square` 使用 `amplitude/frequency/rise_fall`；`pulse` 使用 `amplitude/width`（V/s），是单次脉冲；`pwl` 使用 `{"text":"0 0\n1m 0\n2m 5\n10m 5"}`。省略 `dc_level` 保留旧值。square 的 `rise_fall` 是原生 τ，完整边沿跨度是 2τ；不能把它当作占空比。

先通过 `tina_catalog.native_templates` 选择模板。原生添加和连接的示例操作：

```json
[
  {"op":"add_component","template":"resistor","reference":"R_TEST","position":[800,320],"orientation":90,"parameters":{"0":"100"}},
  {"op":"connect","a":{"component":"R7","pin":"1"},"b":{"component":"R_TEST","pin":"1"}},
  {"op":"connect","a":{"component":"R7","pin":"2"},"b":{"component":"R_TEST","pin":"2"}}
]
```

引脚与坐标来自当前快照；示例不能证明这些位置适用于另一张图。`connect.via` 可给正交经过点。未接完时用 `include_connectivity=false`，接完再读完整网表。移动、删除和连续线段索引都按当前顺序解释。

分立器件先调用 `tina_device_models(pid, component)` 读取当前库族、实际型号清单及 `public_fields`，再在事务中使用：

```json
[
  {"op":"set_device_model","component":"Q1","model":"<该器件实际型号清单中的名字>"},
  {"op":"set_device_instance","component":"Q1","field":"temperature_delta_C","value":"0"}
]
```

支持 D/Schottky/NPN/PNP/NMOS/PMOS 的公开实例字段；D/BJT 的 `area_factor`、MOS 的 `multiplicity` 以返回的 `public_fields` 为准。不会修改库模型常数或工厂宏内部。`add_macro` 使用本机已有 `.TSM` 文件：`macro_file`、`position`、可选 `orientation`；插入后再读取新引用和端子，不假定编号。

## 分析设置

单次 `tina_run_analysis` 将设置直接放在工具参数里；批次则放入 `analysis.settings`：

| kind | 设置字段 |
| --- | --- |
| transient | `start`、`end`、`initial` |
| ac | `start`、`end`、`points`、`sweep` |
| dc | `source`、`start`、`end`、`points` |
| operating_point | 无覆盖项，批次用 `settings:{}` |
| temperature | `start`、`end`、`points`；温度 °C |
| noise | `start`、`end`、`points`、`signal_amplitude`；仅输出噪声 |
| fourier | `signal`、`start`、`fundamental`、`samples`、`harmonics`、`initial` |

时间、频率、幅度等通常用 TINA 数值字符串（如 `20m`、`100k`）；`points/samples/harmonics` 用整数。`initial` 为 `zero/use/operating_point`，`sweep` 为 `log/linear`。运行后继续查询返回的 `job_file`，同一进程一次一个作业。

Fourier 仅返回原生 TDR，没有可用的数值谐波系数；批次用 `measurements:[]`。其一个周期采样窗必须落在原生 Transient 时间范围内，必要时先运行所需 transient 区间。输出噪声是幅度谱密度，电压输出已验证为 V/√Hz；原始 `-phase` 辅助列不是噪声相位，普通曲线 RMS 也不是有效噪声。复制噪声结果时保留同目录 `job.json`，让 `tina_read_result` 正确识别分析类型。

## 一次批量实验

先把拓扑、波形类型与器件型号设置好，保存为基线。**当前批次 `operations` 只支持外部 `set_parameter` 和已有 PWL 的 `set_pwl`；不能将整个原生拓扑事务放进案例。** 每例都从冻结基线开始。

调用 `tina_batch_prepare`，以下是两例 RC 参数对照的完整形状：

```json
{
  "source_tsc":"<已完成电路的绝对路径.TSC>",
  "directory":"<新的批次输出目录绝对路径>",
  "cases":[
    {"id":"r-1k","values":{"R1_ohm":1000},"operations":[{"op":"set_parameter","component":"R1","index":0,"value":"1k"}]},
    {"id":"r-2k","values":{"R1_ohm":2000},"operations":[{"op":"set_parameter","component":"R1","index":0,"value":"2k"}]}
  ],
  "analysis":{"kind":"transient","settings":{"start":"0","end":"20m","initial":"zero"}},
  "solver_parameters":{"25":"1m","30":"1u"},
  "measurements":[{"signal":"VOUT","start":0.01,"end":0.02}],
  "close_completed":true
}
```

这里的值只是示例，不是推荐的电路或求解参数。`index` 来自器件快照；求解参数 25 是瞬态相对误差，30 是最大步长。测量窗口必须落在实际记录范围，信号名要与原生导出完全相符。

随后调用 `tina_batch_advance`：`{"manifest":"<prepare返回的manifest>","pid":12345}`。每次只推进一例的一个阶段：准备 → 启动 → 查询/收集 → 指标。继续同一个 manifest，直到所有案例 succeeded。`tina_batch_status` 只读进度；已完成案例不重复运行。`attention/preparing/starting` 的异常先检查现场，不盲目重新启动求解。

单个 case 可覆盖 `analysis`、`solver_parameters`、`measurements`。`values` 仅记录实验轴值，实际修改由 `operations` 决定。`close_completed=true` 会在保存结果和指标后，仅保存并关闭仍然活动且名称唯一的自有 case 页；其他页保留。批次不会自动退出进程。

## experiment-design 的 specification

工具只生成案例或提出下一点，不运行 TINA。返回的 `cases` 可原样放入 `tina_batch_prepare`。

网格（笛卡尔积）：

```json
{"kind":"grid","specification":{"axes":[{"name":"R1_ohm","component":"R1","index":0,"values":["1k","2k"]},{"name":"C1_F","component":"C1","index":0,"values":["1u","2u"]}]}}
```

独立容差抽样：

```json
{"kind":"tolerance","specification":{"parameters":[{"name":"R1_ohm","component":"R1","index":0,"nominal":"1k","relative":0.05}],"count":20,"seed":2026,"distribution":"uniform"}}
```

`uniform.relative` 是相对半宽；`normal.relative` 是相对标准差，正态分布不截断。参数有效范围由实验设计确定。`seed` 和所有具体取值会保留。

局部敏感度（名义点与每个参数单独低/高扰动）：

```json
{"kind":"sensitivity","specification":{"parameters":[{"name":"R1_ohm","component":"R1","index":0,"nominal":"1k"}],"relative_step":0.01}}
```

前三种设计均可带 `base_operations`，它会放在每例的参数修改前。各轴／参数的 `name` 可省略，此时使用 `component:index`；同名或重复目标不允许。

边界搜索（必须输入实际测量的参数—指标对）：

```json
{"kind":"boundary","specification":{"samples":[[1000,4.0],[2000,2.0]],"target":3.0}}
```

只有唯一跨越目标的区间才返回一个候选中点；需要另建案例实际求解，再加入测量点。`unbracketed/multiple_brackets/observed_target` 都是有意义的状态，不隐含单调性证明。

## 数值测量

独立调用 `tina_measure_result`：

```json
{"path":"<实际result.txt绝对路径>","signal":"VOUT","options":{"start":0.01,"end":0.02,"target":3.3,"relative_band":0.05}}
```

独立工具将选项放在 `options`；批次 `measurements` 中则把 `start/end/target/...` 直接与 `signal` 并列。其余选项有 `absolute_band`、`initial`、`block`、`crossing_level`、`crossing_axis`（`linear/log`）。零目标应使用正的绝对带宽；同名信号多块时指定 `block`。DC 工作点行只给精确 `signal` 名，不传时间窗口选项。

平均值和 RMS 对原始非均匀采样的分段线性曲线积分，边界插值会报告，不静默重采样。超调以目标与初值之差归一化；稳定时间仅说明记录区间内最后进入指定带宽的位置。AC 阈值可选频率轴对数插值，但 dB/deg 单位仍按原始信号名解释。
