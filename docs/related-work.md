# Related work and search scope

Checked on **2026-11-09**. Repository status below is based on the upstream README, GitHub repository metadata and latest default-branch commit at the time of the check. Dates are UTC. A recent push is not proof of support quality; an old commit is not proof that software is unusable.

## Result

Within the sources and queries below, we did **not** find another public open-source MCP adapter providing native TINA/TINA-TI `.TSC` reading, editing and solver control. This is a bounded search result, not a claim to be first or unique worldwide. Search indexes can miss repositories, private work, differently named projects, or newly published code.

There is substantial adjacent work, including **official TINA scripting and AI functionality**. It would be incorrect to claim that nobody has automated TINA or connected AI to it.

## Relevant implementations

| Project / source | Observed status | Scope and difference from this bridge |
| --- | --- | --- |
| [DesignSoft TINA Python support](https://www.tina.com/python/) | Official commercial feature, documented from TINA v14 | Embedded Python shell and design procedures that calculate/set component values. This establishes real official scripting, but does not document an open-source stdio MCP adapter for TINA-TI 9.3. |
| [DesignSoft TINA AI / release history](https://www.tina.com/whats-new/) | Official page lists TINA v15 (2024-12-18) and v16 (2025-12-18) | Built-in AI assistant, circuit-design assistance, and later local LLM/Python-generation improvements. These belong to newer commercial TINA, not evidence that the free TINA-TI 9.3 build exposes the same integration. |
| [Cognitohazard/ltspice-mcp](https://github.com/Cognitohazard/ltspice-mcp) | Not archived; latest default-branch commit [2026-11-06](https://github.com/Cognitohazard/ltspice-mcp/commit/9455f3850948b6ff95653f7148eea91abea24b8c); repository pushed 2026-11-08 | Closest conceptual peer: MCP circuit editing, real simulation, measurements and experiments. Its README targets LTspice/ngspice (and secondary netlist engines), with `.asc` schematic editing; it does not claim native TINA `.TSC` support. |
| [clanker-lover/spicebridge](https://github.com/clanker-lover/spicebridge) | Not archived; latest default-branch commit [2026-04-06](https://github.com/clanker-lover/spicebridge/commit/fb1de30fda06f28e04def71594b44d4ef4e79b91) | MCP access to ngspice for circuit design, simulation and verification. It works with a different solver rather than preserving and operating native TINA project files and encrypted TINA macros. |
| [gtnoble/ngspice-mcp](https://github.com/gtnoble/ngspice-mcp) | Not archived; latest default-branch commit [2025-04-13](https://github.com/gtnoble/ngspice-mcp/commit/75e9f59863b8b1e04296113bcf236038547c8cd4) | Earlier MCP interface to ngspice. Relevant evidence that circuit-simulator MCPs already exist, but not a TINA desktop adapter. No later default-branch commit was observed. |
| [TI: importing a SPICE netlist into TINA-TI](https://www.ti.com/lit/an/slva424/slva424.pdf) | Official application note, April 2010 | Describes netlist compatibility and macro creation/import. A `.TSM` macro or SPICE model is circuit content; it is not itself an external automation or MCP protocol. |

The other MCP projects were inspected, not installed or independently benchmarked. Their feature descriptions are upstream claims. This release does not reuse their source code.

## Names that are not the circuit simulator

- [calumjs/TinaMCP](https://github.com/calumjs/TinaMCP): its README explicitly identifies a **TinaCMS** content-management MCP server. Latest default-branch commit observed: 2025-04-29. Not DesignSoft TINA.
- [kamisoel/tina_mcp_tools](https://github.com/kamisoel/tina_mcp_tools): coursework servers for a cafeteria menu and DICOM document retrieval. Latest default-branch commit observed: 2025-07-27. Not circuit simulation.
- Additional TinaCMS, personal-assistant and Playwright results were excluded based on their repository descriptions rather than treated as competing TINA adapters.
- TINA-TI schematic collections found by repository search contain circuits or coursework; their presence alone does not establish an automation adapter.

## Search scope and reproducible queries

The check covered GitHub repository search and upstream READMEs; DesignSoft and TI documentation; the connected OpenAI plugin directory; and web-indexed MCP directories including the official MCP registry, Smithery and mcp.so.

Representative GitHub searches:

```text
"tina" "mcp"
"TINA-TI" automation
tina simulator automation
tina circuit python
"tina-ti"
```

Representative web searches:

```text
"TINA-TI" "MCP"
"TINA" "Model Context Protocol" circuit -tinacms
"TINA-TI" automation github
"TINA" circuit simulator automation github python
"TINA" "mcp" "spice" github
"ngspice" "MCP" github
"LTspice" "MCP" github
"TINA-TI" scripting command line automation site:e2e.ti.com
"TINA" MCP site:registry.modelcontextprotocol.io
"TINA" circuit site:smithery.ai
"TINA" circuit site:mcp.so
```

The connected plugin search used `TINA circuit SPICE` and returned no matching plugin. The directory queries and web searches did not yield a confirmed direct TINA adapter. This does not establish that every directory entry or every source repository was exhaustively searched; GitHub search used repository name/description metadata rather than a complete global code audit.

## Contribution of this project

TINA Bridge exposes the installed **TINA-TI 9.3** application through structured tools while preserving native engineering files. Its useful distinction is native `.TSC` editing around opaque factory macros, actual TINA solver execution, numerical readback where reliable, and persistent experimental records. The claim is about this demonstrated scope, not universal novelty or broader capability than the adjacent tools.
