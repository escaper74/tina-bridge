# 成组实验与数值测量

批次复用现有原生参数编辑、分析与结果接口。每个 case 从冻结的 TSC 基线开始，清单保存改动、实际求解参数、作业路径、结果和指标。一个明确 PID 顺序运行，没有另建后台调度服务。当前批次操作是原生外部参数/PWL 编辑，不能把全部拓扑操作直接塞进案例 `operations`。

## 最短使用链

MCP 入口为 `tina_experiment_design`、`tina_batch_prepare`、`tina_batch_advance`、`tina_batch_status`、`tina_measure_result`。对应 Python 调用如下：

```python
from experiments import grid_cases, prepare_batch, advance_batch

cases = grid_cases([
    {"name": "input_V", "component": "V1", "index": 0,
     "values": ["10", "12"]},
    {"name": "load_ohm", "component": "R1", "index": 0,
     "values": ["1k", "2k", "3k"]},
])
batch = prepare_batch(
    source_tsc, output_directory, cases,
    analysis={"kind": "operating_point", "settings": {}},
    measurements=[{"signal": "VOUT"}],
    close_completed=True,
)
state = advance_batch(batch["manifest"], pid)
```

源文件、全新输出目录和 PID 由调用者明确选择；开发用独立进程。`prepare` 只冻结文件和计划，不操作软件。每次 `advance` 推进一个阶段：准备私有案例 → 设置并启动 → 查询/收集 → 计算指标。`running` 时继续查询；当前案例完成后，下一次才准备下一例。`batch_status` 只读 manifest。

案例可给出 `id`、`operations`、`values`，并覆盖 `analysis`、`solver_parameters`、`measurements`。全局分析设置用 `{"kind": ..., "settings": {...}}`；七种单次分析的字段见 [README](reference.zh-CN.md)。瞬态需明确 `start/end/initial`，AC 明确 `start/end/points/sweep`，DC 明确 `source/start/end/points`，温度明确 `start/end/points`；噪声、Fourier 同样应给出完整实验设置，不能借用上一个案例的临时对话框内容。

第一个案例打开后记录原生求解参数基准，后续每例恢复基准再应用全局/案例覆盖。`actual_solver_parameters` 保存在清单中，job 另存本次分析设置。工程文件可能保留旧的分析元数据，以这两份实际回读为准。

## 页面保留与恢复

新批次默认 `close_completed=true`。结果和指标落盘后，仅当当前编辑器仍是该 case、且文档名唯一匹配时，另存 `*-final.TSC` 并关闭这一页。结果在 `case.cleanup` 中：成功时有 `closed=true`、`final_circuit_file`；活动页变化、同名歧义或关闭失败时保留页面并给出 `kept_reason`。已成功的仿真结果不会因此抹掉或重跑。

需要留页面比较时设 `close_completed=false`。旧 manifest 没有该字段时不会追溯自动关闭。原先用户页、失败案例页和其他进程不属于清理范围；没有 CloseAll，也不因批次结束自动退出 PID。TINA 最后可能生成空白页；结束自己的进程时，保存这张自有页后直接退出即可，不必反复关闭空白页。

客户端重启后，已有 `job_file` 的案例继续查询同一作业，不重复完成案例。返回 `attention` 时先看具体对话框、活动文档或错误；解除阻塞后可继续轮询已记录作业。若恰好中断在原生修改或启动期间，`preparing/starting` 会保留现场，接口不会盲目重试。批次绑定 PID 及创建时间，软件退出后不能把新 PID 当作旧进程续跑；可用剩余案例建立新批次，原数据保留。

## 数值测量

```python
from metrics import measure_file

report = measure_file(
    text_path, "VOUT", start=0.002, end=0.003,
    target=3.3, relative_band=0.05,
)
```

波形指标包含平均值、RMS、去均值 RMS、峰峰值和极值。给出 `target` 后计算超调，以及记录区间内最后进入目标带的时刻；记录结束后是否仍稳定不作推断。`absolute_band` 可指定绝对带宽，零目标需使用它。`initial` 可指定阶跃前值，默认取窗口首值；超调百分比按目标与初值之差归一化。

积分使用原始非均匀采样的分段线性函数，RMS 对其平方精确积分；窗口边界必要时线性插值，并返回 `interpolated_boundaries`。不超出记录区间外推，重复时间点作为零时长跳变保留，不进行静默重采样或额外 FFT。

`crossing_level` 查阈值的全部交点。AC 常用 `crossing_axis="log"`：频率轴对数插值、幅度按原数值插值，dB/degree 单位仍按原生列名解释；平台单列为 `plateaus`。同名信号在多个块出现时用 `block` 区分。DC 工作点则返回选定原生行的 SI 数值、单位、节点顺序，没有波形窗口选项。

Fourier 仅有原生 TDR，批次应保持 `measurements=[]`，不能对其调用数值指标。输出噪声是频率域幅度谱密度，通用曲线 RMS 不等于时域有效噪声；原始文本中的 `-phase` 是辅助列，不作噪声相位。详细限制见 [更多分析边界](analyses.zh-CN.md)。

## 生成实验案例

| 函数 / `tina_experiment_design.kind` | 行为 |
| --- | --- |
| `grid_cases` / `grid` | 外部参数取值的笛卡尔积，每例保留实际轴值 |
| `sensitivity_cases` / `sensitivity` | 名义值加各参数单独的低/高扰动，其余参数每例显式恢复名义值 |
| `tolerance_cases` / `tolerance` | 固定种子的独立均匀/正态扰动，保存分布与全部具体取值 |
| `boundary_candidate` / `boundary` | 从已测得的 `[参数, 指标]` 对选择唯一跨越目标的区间，并提出中点；本身不运行仿真 |

容差参数含 `component/index/nominal/relative`。均匀分布的 `relative` 为相对半宽，正态分布为相对标准差且不截断；物理取值范围由实验设计决定。`sensitivity_estimate(low, nominal, high)` 用三个真实测量对给出局部割线与归一化敏感度，不声称已经收敛。边界搜索未形成区间或存在多个区间时明确返回状态；加入新 TINA 结果后再调用，不假设区间内单调。
