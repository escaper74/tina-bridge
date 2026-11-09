# Minimal MCP examples

Call tools through the client using the JSON argument objects below. The command-line client `server/mcp_call.py` also accepts `--request request.json` containing `{"tool":"tool_name","arguments":{...}}` and uses the same stdio server.

All paths and PIDs below are placeholders. Read the current schema and `tina_catalog`; get component names, parameter indices, terminal names and coordinates from a fresh circuit snapshot. Use an independent session for experiments.

## Read and edit a copy

1. Call `tina_sessions` with `{}`, then `tina_create_session` with `{}`.
2. Open your saved schematic with `tina_project`:

```json
{"pid":12345,"action":"open","path":"<absolute source.TSC path>"}
```

3. Read it using `tina_read_circuit({"pid":12345})`. Query the returned snapshot with `tina_query_circuit`:

```json
{"snapshot":"<returned snapshot.json path>","component":"R1","depth":1}
```

4. If the snapshot confirms that R1 parameter 0 is the resistance, edit into a new file using `tina_native_edit_circuit`:

```json
{
  "pid":12345,
  "source_tsc":"<absolute source.TSC path>",
  "save_path":"<new absolute edited.TSC path>",
  "operations":[{"op":"set_parameter","component":"R1","index":0,"value":"2k"}],
  "include_connectivity":true
}
```

5. Read/compare the before and after snapshots. Reopen the saved file to verify persistence. Native editing preserves opaque factory macros; never send encrypted circuits through the XML-edit route.

The example value is illustrative, not a design recommendation.

## Run and collect a transient

After opening the intended file, use `tina_analysis_parameters` to inspect/set solver parameters. For this adapter, index 25 is transient relative tolerance and index 30 is maximum time step. Choose settings for the actual experiment.

`tina_run_analysis`:

```json
{"pid":12345,"kind":"transient","start":"0","end":"20m","initial":"zero"}
```

Poll `tina_job_status` using the returned `job_file` and `collect:true`. Wait for the completed result before starting another job. Read the collected numerical text with `tina_read_result`; use a signal name from that response.

`tina_measure_result`:

```json
{"path":"<collected result.txt path>","signal":"VOUT","options":{"start":0.01,"end":0.02}}
```

This computes statistics on an interval within the actual record, using its sampling grid. It does not invent a signal named VOUT if the circuit exports a different name.

## Two parameter cases

Prepare topology and source/model types first, save the baseline, then call `tina_batch_prepare`:

```json
{
  "source_tsc":"<absolute saved baseline.TSC path>",
  "directory":"<new absolute batch directory>",
  "cases":[
    {"id":"r-1k","operations":[{"op":"set_parameter","component":"R1","index":0,"value":"1k"}]},
    {"id":"r-2k","operations":[{"op":"set_parameter","component":"R1","index":0,"value":"2k"}]}
  ],
  "analysis":{"kind":"transient","settings":{"start":"0","end":"20m","initial":"zero"}},
  "measurements":[{"signal":"VOUT","start":0.01,"end":0.02}],
  "close_completed":true
}
```

Call `tina_batch_advance({"manifest":"<returned manifest path>","pid":12345})` repeatedly; it advances one phase at a time. `tina_batch_status` reads progress. Resume the same manifest after a client reconnect; do not duplicate completed cases. Case operations support external `set_parameter` and existing `set_pwl` only.

See [full dictionary examples](usage.md) for the seven analysis settings, grid/tolerance/sensitivity/boundary specifications and measurement options. Fourier returns a native plot only, so use an empty measurement list for that analysis.
