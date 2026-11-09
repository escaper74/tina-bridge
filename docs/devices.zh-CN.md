# 原生离散器件型号与实例参数

`device_models.py` 为 TINA-TI 9.3.150.328SF-TI 提供一个小范围的原生接口：读取器件当前库/模型族中的已有型号，从该列表选择型号，或修改已确认的公开实例字段。它不编辑目录右侧的器件模型常数，不创建新模型，也不替换加密宏的内部模型。

目前支持普通二极管 `23`、肖特基二极管 `64`、NPN `87`、PNP `88`、增强型 NMOS `89`、增强型 PMOS `90`。仅在当前库/模型族内选型；跨库、切换模型族、绝对温度模式没有开放。

## 最小集成

从新导出的 XML 获取器件，再使用现有 `Tina(pid)` 对象。调用方仍负责私有 TSC 副本、整体读回、另存与进程所有权。

```python
from device_models import read_models, select_model, set_instance

# 读完后取消目录和属性两个对话框；不改变电路。
catalog = read_models(tina, component_xml, query='1N400', limit=50)

# model 必须匹配原生列表里的一个已有型号；不接受任意型号文本。
receipt = select_model(tina, component_xml, model='1N4007')

# 每次操作后重新导出 XML，下一次调用传入新的器件节点。
receipt = set_instance(tina, fresh_component_xml, field='temperature_delta_C', value='15')
```

`read_models` 返回当前库、模型族、当前型号、匹配列表、完整匹配数、当前族总条目数，以及可编辑实例字段。搜索结果只截到显式 `limit`，不会把截断后的长度当成总数。

主线现已提供 `tina_device_models(pid, component, query, limit)`，并在 `tina_native_edit_circuit` 中接入两种记录：

```json
{"op":"set_device_model","component":"D1","model":"1N4007"}
{"op":"set_device_instance","component":"D1","field":"temperature_delta_C","value":"15"}
```

字段限定如下。索引来自本机实际属性窗口和原生 XML 的核对，客户端使用字段名即可。

| 字段 | 适用器件 | 原生参数索引 | 含义 |
|---|---|---:|---|
| `temperature_delta_C` | D / Schottky | 2 | 相对于分析温度的摄氏温度偏移 |
| `temperature_delta_C` | NPN / PNP / NMOS / PMOS | 3 | 同上 |
| `area_factor` | D / Schottky | 3 | 公开实例“区域因数” |
| `area_factor` | NPN / PNP | 4 | 公开实例“区域因数” |
| `multiplicity` | NMOS / PMOS | 14 | 公开实例“M 区域乘法器” |

温度字段仅在原生模式为“相对”时返回。`15` 是增加 15 °C；它不是把器件绝对温度设为 15 °C。面积因子和 MOS 乘法器必须为正数。`IS`、`VTO`、`KP`、`BF` 等模型常数不属于这个接口。

`select_model` 返回 `model/library/family/previous_model`，`set_instance` 返回实际字段、原生索引及前后值。保存前应核对目标参数与回执一致、该器件其他参数未改、其他器件/接线/宏未改。离散器件型号参数 0 应走目录选择接口，避免把它当作普通自由文本参数写入。

## 已实测的原生行为

- 六种器件打开属性窗口后，初始行都是参数 0 的型号。向上一次是“(参数)”，向上两次是位号；已有 `native_topology.rename` 在六类器件上均完成改名和恢复。
- `LB_SETCURSEL` 单独改变列表高亮，不足以提交 TINA 内部选型。接口使用列表自身的 Home/Down 消息，并留出已实测需要的 0.5 秒原生记录加载时间；随后核对返回属性行的型号，再确认对话框。
- MOS 属性表的键盘导航不会自动把下方字段滚到可视区。索引 14 使用该网格自身的 `WM_VSCROLL / SB_BOTTOM` 显示后再核对旧值。无需全局鼠标、剪贴板或截图识读。
- 调查时的少量原生窗口截图仅用于确认非窗口化字段标签；正常接口不依赖截图。界面控件和消息都限定在调用方给定的 PID。
