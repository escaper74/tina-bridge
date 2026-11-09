# TINA Bridge 0.2.2

Use Codex to read a TINA circuit, edit components and connections, run simulations, and analyze the results.

## What you can do

- Open a `.TSC` file and ask about its components, pins and connections.
- Change values, add components and wires, and save the edited circuit.
- Run transient, AC, DC, operating-point and temperature analyses; view output-noise spectra and Fourier plots.
- Read waveform samples and measurements, or compare several parameter choices in a batch.

The plugin was developed with the Simplified Chinese edition of TINA-TI 9.3 on Windows. It includes 32 MCP tools and 15 native component templates.

## Get started

Download `tina-bridge-0.2.2.zip`, extract it, and follow the [installation guide](https://github.com/escaper74/tina-bridge/blob/main/plugins/tina-bridge/README.md). You'll need TINA-TI and Python 3.11 or newer.

Once connected, try:

> Open this circuit, change R1 to 2 kΩ, save a copy, and run a 20 ms transient simulation.

[中文说明](https://github.com/escaper74/tina-bridge/blob/main/README.zh-CN.md) · [Tool reference](https://github.com/escaper74/tina-bridge/blob/main/docs/tools.md) · [Tests and TINA examples](https://github.com/escaper74/tina-bridge/blob/main/docs/validation.md)

The release includes the source ZIP, its SHA-256 checksum and a file manifest. The 68 offline tests and release build pass on GitHub's Windows runner. Source code is available under the MIT license.
