---
name: tina-bridge
description: Read, edit, build and simulate native TINA-TI circuits through the local TINA Bridge MCP. Use for TINA projects, circuit connectivity, device parameters, native analyses, waveform data and experiment batches; not for MATLAB/Simulink or Cadence.
---

Use the installed `tina_*` tools. Read their schemas for the supported operations; the bridge's runtime is the authority for currently available features. Installation and the small protocol check are described in [the plugin README](../../README.md).

For the dictionaries in batch, experiment-design and measurement tools, consult [the shipped usage examples](../../references/usage.md). They include explicit field names, supported case operations and analysis settings. Read discrete-device choices with `tina_device_models` before selecting a catalog model or editing one of its public instance fields.

Discover sessions before using a saved PID. Use the user's selected session for their requested work, and create an independent session for development or experiments that should not change their active work. Keep track of which chat owns each process. Never borrow another chat's session.

Read the actual circuit through native XML and netlist exports. Query a snapshot's components, pins and nets to understand topology; preserve unknown statements and opaque model internals. A circuit image helps identify intended layout, but does not establish electrical connectivity. For an unfinished circuit, `tina_read_circuit(include_connectivity=False)` avoids trying to export a solver netlist.

Edit into a new file. Ordinary unencrypted circuits can use XML edits. TINA-TI 9.3 silently loses encrypted macros during XML import; use the supported native editing tools for those projects. Do not change factory chip internals or substitute another chip. Verify the saved result's component values, connections and model preservation, and reopen when a persistent change needs confirmation. Use the source snapshot's actual parameter indices and terminal names.

Use `tina_catalog` for supported primitive templates and `native_waveforms`. Build with the native circuit transaction's component, wire and pin-connection operations. Configure a voltage generator with `set_waveform`; keep its power circuit and wiring visible. The native `pulse` is a single pulse, not periodic PWM. A square wave is bipolar around `dc_level`, and its `rise_fall` field is TINA's tau (a complete edge spans twice tau). The bridge restores the sine-phase side effect of this TINA version's XML export automatically; do not add another phase correction yourself.

Open the project before setting native solver parameters. Pass the intended run settings explicitly: the active dialog values and the old values saved in XML/TSC may differ. Run one analysis per process at a time, poll its durable job file, and collect results before another run. Report native errors; do not silently retry with looser tolerances or different initial conditions.

Prefer numerical result exports to screenshots. Preserve each signal's native sampling grid, units and sign convention. Time-weighted statistics require the time axis; an arithmetic mean or an FFT on nonuniform samples is not interchangeable. State the interval and calculation used. Completed tool calls do not by themselves prove the circuit meets its design requirements.

For repeated experiments, prepare an explicit batch manifest and advance that manifest one phase at a time. Resume recorded jobs and results instead of recreating or rerunning completed cases. Use measurement and experiment-design tools for the supported grid, tolerance, sensitivity and boundary-search tasks; inspect their returned interval, interpolation method and validity limits.

Keep the workspace readable. Close this chat's obsolete test tabs after their useful artifacts are saved. TINA can mark an initially empty page modified when analysis settings change; save that owned page before exiting too. Preserve user work and other chats' windows. The adapter uses a logged-in Windows desktop and native process-bound controls; it is not a headless solver.
