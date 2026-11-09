# MCP tool reference

The 0.2.2 server exposes 32 tools. This inventory is extracted from its actual definitions.
Use the live MCP input schema for exact types, defaults and operation unions. The shipped skill and [examples](../plugins/tina-bridge/references/quickstart.md) describe sequencing.

| Tool | Description |
| --- | --- |
| `tina_sessions` | Discover TINA processes by executable identity; never assume a saved PID still exists. |
| `tina_create_session` | Start a separate TINA editor process, preserving existing sessions. Not headless. |
| `tina_exit_session` | Exit the explicitly selected TINA process normally. Save projects/results first. Unsaved-change prompts are not discarded; no process killing. |
| `tina_status` | Read process-bound editor/result/dialog state. Does not run an analysis. |
| `tina_place_windows` | Restore this TINA process and place its windows on the configured monitor (secondary by default), without requesting foreground activation. Does not move unrelated applications. |
| `tina_dismiss_errors` | Acknowledge native Error messages and close the ERC report after reading diagnostics. Does not dismiss unsaved-change/overwrite confirmations, change the circuit or restart analysis. |
| `tina_project` | Open/create/save/close a native document. Saves require a new .TSC path; unsaved prompts are not discarded. |
| `tina_documents` | List native schematic document tabs and current zero-based selection. Tab captions come from Windows accessibility, not images. |
| `tina_select_document` | Activate a listed native schematic tab in the explicitly selected process. |
| `tina_read_circuit` | Export/read actual circuit components, parameter indices, layout, wires, analysis settings, macro hashes and native netlist connectivity. Returns an immutable source XML path for edits. |
| `tina_catalog` | List tested primitive templates and blank native XML. Unknown pin geometry is not inferred. |
| `tina_find_library` | Find installed native examples, macro files and model libraries by path substring. Read-only discovery. |
| `tina_device_models` | Read installed model choices for an existing native diode/Schottky/NPN/PNP/NMOS/PMOS. Opens and cancels this component's native catalog; does not edit model constants or choose another library/family. Returns current model, filtered available names and supported public instance fields. Use native edit set_device_model/set_device_instance to change a private copy. |
| `tina_edit_circuit` | Apply sequential external circuit edits to an explicit XML snapshot, import as a new document, save a NEW .TSC and read back actual topology. Use catalog.empty_xml to create from scratch. Macro internals cannot be edited. Moving/deleting a component leaves wires unchanged: specify wire edits too. Wire indices refer to the current sequential list. Source document/file is preserved. |
| `tina_native_parameters` | Edit external values in a private native TSC copy, preserving encrypted macros. Verified scalar parameters for R/C/L/VG/battery in all orthogonal rotations and mirrors; set_pwl changes an existing PWL VG. Uses native controls without XML import. Verifies every component parameter, wire and model before saving a NEW TSC. May change this editor's zoom/scroll. |
| `tina_native_edit_circuit` | Edit native topology in a private TSC, retaining encrypted macros. Add catalog primitives or an existing .TSM macro; set waveforms, discrete catalog models/public instance fields; rename, rotate/mirror/move, remove components/wires, connect explicit symbol pins or coordinates and edit external values. Connect requires orthogonal via points. Reuses existing segments and starts new leads at the free endpoint. Checks each operation, models and actual connectivity; pure additive edits may not disconnect old nets. include_connectivity=False avoids ERC for unfinished circuits. Wire indices are sequential; use voltage_probe for labels. Saves a NEW TSC. Factory model internals are never edited. |
| `tina_analysis_parameters` | Read or set active native solver parameters. Keys are XML indices: 0 temperature, 1 DC absolute current, 3 DC absolute voltage, 4 DC relative error, 5 minimum conductance, 25 transient relative error, 27 truncation order, 30 max time step, 37 subdivision factor, 39 max saved points. Values use native units. Apply AFTER opening a project and BEFORE running; saved XML/TSC metadata can retain older values. Omit parameters to read. Never changes chip models. |
| `tina_run_analysis` | Start a native solve and return a durable job_file. transient:start/end/initial; ac:start/end/points/sweep; dc:start/end/points/source; operating_point:no overrides; temperature:start/end in degC/points; noise:start/end in Hz/points/signal_amplitude (output density only); fourier:signal/start/fundamental/samples/harmonics/initial (native TDR only, no numeric coefficients). Values accept TINA units. Set solver parameters after opening, pass run settings explicitly, poll/collect before another run. Settings are not guaranteed persistent in TSC. |
| `tina_job_status` | Poll the exact native job and collect actual results. Numeric analyses return text and structured data; Fourier returns native_only=true and a .tdr, with no text_path/data coefficients. Returns running/attention/succeeded/cancelled; never starts a replacement run. |
| `tina_cancel_job` | Request cancellation through this job's native progress dialog, including background/hidden progress. Does not kill TINA or discard circuit files. Poll until cancelled; partial results, if any, are not reported as a completed analysis. |
| `tina_result_pages` | Read diagram page count, active zero-based page index and document title. |
| `tina_select_result_page` | Select an existing native diagram page; changes native page selection only. |
| `tina_export_results` | Export the active diagram's exact numeric data and the native .tdr document. .tdr may contain multiple pages. Creates new files; no implicit overwrite. |
| `tina_open_results` | Open native .tdr results and select the first imported page. TINA appends pages rather than replacing the diagram. |
| `tina_read_result` | Read exported numeric data without TINA. Omit signal for stats, or name it for exact x/y points in the requested interval. Preserves each signal's grid; does not silently downsample. AC dB/degree units remain in native column names. |
| `tina_query_circuit` | Query a saved circuit snapshot/view without operating TINA. Find a component/net or one model pin; depth expands through adjacent components (0=incident network). Query a public subcircuit by its scope. Returns native source locations and explicit coverage. Model terminal indices are not package pad numbers; topology does not imply instantaneous current flow. |
| `tina_compare_circuits` | Compare saved circuit snapshots/views: component/parameter/layout changes and terminal connectivity. Numeric node renumbering alone is ignored; named-node changes are retained. Does not operate TINA. |
| `tina_batch_prepare` | Freeze a native baseline and explicit cases in a new directory; no TINA operation. Each case has id, operations, optional values/analysis/solver_parameters/measurements. Advance sequentially in one owned PID with explicit settings. By default, after results/metrics are saved, save and close only the uniquely matched still-active completed case tab; false keeps it open. Never closes unrelated pages. Returns a durable manifest. |
| `tina_batch_advance` | Advance one phase of one batch case: prepare a private TSC, start its native solve, or poll/collect its existing job. Completed cases are not repeated after client restart. Do not operate this PID concurrently; inspect attention states instead of blind retry. Records actual settings, native results and optional measurements. |
| `tina_batch_status` | Read durable experiment progress and results without operating TINA. |
| `tina_measure_result` | Measure actual native result data. Waveform options include start/end, target, relative_band/absolute_band, initial, block, crossing_level/crossing_axis. Integrates original nonuniform piecewise-linear samples for mean/RMS; reports peak-to-peak, overshoot and observed settling. Operating-point rows return SI values/units. No implicit resampling or FFT. |
| `tina_experiment_design` | Compose experiment cases or propose a boundary-search point without running TINA. grid: axes; tolerance: parameters/count/seed/distribution; sensitivity: parameters/relative_step; boundary: measured samples/target. Parameter specs use component,index,nominal and relative where needed. Returns explicit cases and distribution assumptions; physical validity remains an experiment-design decision. |

## Native templates

`resistor`, `capacitor`, `inductor`, `battery`, `voltage_generator`, `ground`, `voltage_probe`, `current_source`, `current_generator`, `diode`, `schottky_diode`, `npn`, `pnp`, `nmos`, `pmos`.

These 15 names select the native installed palette. The separate XML primitive catalog contains seven basic templates; the two counts refer to different paths.

## Analysis result types

| Kind | Result |
| --- | --- |
| `transient` | Native time samples and TDR |
| `ac` | Native frequency/dB/degree columns and TDR |
| `dc` | Native source sweep data and TDR |
| `operating_point` | DC table, SI values, units and available node ordering |
| `temperature` | DC temperature sweep data and TDR |
| `noise` | Output amplitude spectral density and TDR; unsupported transforms excluded |
| `fourier` | TDR only, `native_only=true`; no numerical harmonic coefficients |

A result-page document can contain older pages. Use the returned page index and job metadata. See [validation boundaries](validation.md).
