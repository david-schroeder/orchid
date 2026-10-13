# 01 — Project goal and directory layout

> These docs describe the **target**. Review the actual repository state before acting
> (see `CLAUDE.md`).

## Goal

ORChiD (*Open Rapid Chip Designer*) is a **template repository** for generic mixed-signal
(AMS) ASIC projects. A user clones it, drops in their design sources and configuration, and
drives the entire chip design — RTL to GDS, including simulation, DRC and LVS — from **one
global flow entrypoint** (`python shortcut.py <block>.<task>`).

The value of the repository is the *glue*: a coherent, reproducible flow integrating many
open-source tools around an open PDK (initially IHP SG13G2), not design content.

### Design principles

1. **Template, not a design.** `src/` holds only minimal example content. Real designs are
   placed there by users; the framework (`flow/`) stays design-agnostic.
2. **Modular, reusable flow blocks.** A hardened macro (digital or analog) is produced by a
   generic flow block instantiable once per macro. A toplevel block integrates the products.
3. **ORDeC as design backbone for analog/AMS.** Analog macros and the chip toplevel are
   described in ORDeC (ORD / Python): one data model (schematic, symbol, layout, simulation
   hierarchy) across stages.
4. **PyDesignFlow as orchestration.** All steps are PyDesignFlow tasks with explicit
   dependencies and cached results in `build/`. External tools are wrapped in `flow/tools/`
   so they can be swapped (e.g. LibreLane -> in-house PyDesignFlow digital flow).
5. **Open-source first.** Proprietary tools (Vivado, QuestaSim) are optional conveniences
   (FPGA prototyping, simulation) and must not be required for the ASIC path.
6. **PDK-agnostic structure, PDK-specific plugins.** PDK knowledge (macro lists, PDN recipes,
   layer names, corners) lives in `flow/pdk/`, not in generic blocks.
7. **Design data is separate from flow logic.** Instances, floorplan numbers, clocks etc. are
   configuration under `src/`, not constants in block classes.

### Target architecture

```
                  +-----------------------------+
 RTL (src/)  ---> | DigitalMacro  (N instances) | --> LEF/GDS/netlist/LIB/SDF/SPEF
                  +-----------------------------+                 |
 ORDeC cells ---> | AnalogMacro   (M instances) | --> LEF/GDS/netlist/LIB(abstract)
                  +-----------------------------+                 |
                                                                  v
                  +-----------------------------------------------------------+
                  | ChipTop (ORDeC analog toplevel)                           |
                  |  integrate macros, global PDN, padring, fill, DRC, LVS,   |
                  |  netlist sims, final GDS / sign-off artefacts             |
                  +-----------------------------------------------------------+
```

Details: `02_flow_architecture.md`. Plan: `03_roadmap.md`.

## Intended directory layout

Verify against the real tree; this is the convention new work should follow.

### Repository root

| Path | Purpose |
|------|---------|
| `flow/` | The flow: PyDesignFlow blocks, tool wrappers, PDK plugins (framework code) |
| `src/` | Example design sources and config (template placeholder content only) |
| `docs/` | Sphinx / ReadTheDocs documentation |
| `llm/` | LLM-oriented documentation (this directory) |
| `img/` | README images |
| `LICENSES/`, `REUSE.toml` | REUSE-compliant licensing |
| `shortcut.py` | CLI entrypoint importing `flow/` and calling `flow.cli_main` |
| `setup_flow` | User-local environment script (gitignored) |
| `requirements.txt` | Python dependencies |
| `build/` | Flow output, one subdirectory per block (gitignored) |

### `src/`

```
src/
├── rtl/<macro_or_block>/     # Shared (FPGA + ASIC) RTL, one directory per module/macro
├── asic/                     # ASIC-implementation-only sources, IO pin order and PDN scripts
│   └── macros/<macro>/       # Per-macro pin order and PDN scripts for the macro blocks
├── fpga/                     # FPGA-implementation-only sources/config (rtl, xdc, pincheck, ip)
├── ams/<macro>/              # ORDeC sources (.ord / .py) per analog macro incl. testbenches
├── chip/                     # AMS toplevel (ORDeC), floorplan, padring, constraints
├── tb/                       # System / module (incl. macro) / mixed-signal testbenches
└── common/                   # Shared helpers (waveform setups, ...)
```

The exact detail is decided during roadmap phases 3–4.

### `flow/`

```
flow/
├── __init__.py       # Builds the global Flow(); registers blocks with their design config
│                     #   and wires dependencies
├── <block>.py        # One module per flow block (sources, digital macro, analog macro,
│                     #   chip top, FPGA top, testbenches, ...)
├── config.py         # Design config data types (dataclasses) + glob expansion / JSON conversion
├── macro.py          # Macro-provider interface (HardMacro)
├── pdk/              # Pdk descriptor base; one plugin package per PDK (macro definitions,
│                     #   PDN recipes, corners, decks, bundled PDK supplements)
└── tools/            # Thin wrappers for external tools (LibreLane/Yosys/OpenROAD, slang,
                      #   KLayout, NGSpice, Magic/Netgen, simulators, Vivado, ...)
```
