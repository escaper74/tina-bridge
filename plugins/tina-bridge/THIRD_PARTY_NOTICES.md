# Third-party notices and asset provenance

The MIT license applies to project-authored adapter code and documentation. It does not relicense TINA, TINA-TI, vendor chip models, manuals, installed libraries, or Python dependencies.

## Runtime dependencies

Dependencies are installed separately; their source code, wheels and binaries are not vendored in the release ZIP. The exact dependency closure is in `server/requirements-lock.txt`. License information below was checked against the installed distributions' metadata for this release.

| Dependency | Version | License metadata | Upstream |
| --- | --- | --- | --- |
| MCP Python SDK | 1.30.0 | MIT | [modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk) |
| comtypes | 1.4.17 | MIT | [enthought/comtypes](https://github.com/enthought/comtypes) |
| pywin32 (dependency closure) | 312 | PSF | [mhammond/pywin32](https://github.com/mhammond/pywin32) |

The dependency packages retain their own copyright and license files in the Python environment. Python itself is separately distributed by the Python Software Foundation. If you redistribute an offline wheelhouse or an environment, preserve each dependency's notices and applicable license terms.

## TINA interoperability assets

`server/assets/empty.xml` contains empty-schematic analysis settings. `server/assets/primitives.xml` and `catalog.json` contain serialized primitive instances and parameter/geometry metadata, originally observed through a native TINA-TI export and reduced to basic components. The catalog records that provenance. They contain no connected vendor example, device-model equations, macro subcircuit, encrypted model payload, executable, manual or symbol artwork. Numeric type identifiers and native field names are used to interoperate with the user's installed program.

Native palette insertion uses the symbols and models in the user's own TINA installation. `add_macro` and library-model selection use local assets at runtime; they do not grant redistribution rights or publish those files. TINA and TINA-TI remain subject to their owners' terms. Download them from the [official TINA-TI page](https://www.ti.com/tool/TINA-TI).

## Related projects

Projects in [related-work.md](https://github.com/escaper74/tina-bridge/blob/main/docs/related-work.md) were researched for comparison; their implementations have not been copied into this release. In particular, no GPL-licensed SPICE MCP implementation is bundled with or relicensed as this MIT adapter.
