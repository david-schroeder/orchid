# 04 — Conventions, environment, open questions

> Target-oriented. Review the actual state (`flow/`, `requirements.txt`, environment)
> before acting.

## Toolchain (intended)

| Tool | Used for |
|------|----------|
| PyDesignFlow | Flow orchestration, CLI |
| LibreLane | Digital synth/PnR/signoff until replaced by the in-house flow |
| ORDeC (`ordec`; sibling clone `../ordec`) | Analog/AMS design data, sims, layout, DRC/LVS |
| slang | SystemVerilog frontend: yosys-slang plugin in synthesis (LibreLane `USE_SLANG`), pyslang for elaboration checks and lint |
| Yosys, OpenROAD, Magic, Netgen, KLayout | Underlying digital synthesis/PnR/signoff tools |
| NGSpice | Analog simulation (via ORDeC) |
| Verible | Lint |
| Icarus Verilog (further open simulators ❓) | ASIC RTL/netlist simulation (`Testbench` blocks, gate-level with PDK cell models) |
| Vivado, QuestaSim | Optional: FPGA prototyping and simulation |
| IHP-Open-PDK `ihp-sg13g2` | PDK |

Environment: `source .venv/bin/activate`; `PDK_ROOT` and `ORDEC_PDK_IHP_SG13G2` point to the
`ihp-sg13g2` directory of the PDK checkout. Yosys must be able to load the yosys-slang
frontend (`yosys -m slang`; built in from Yosys 0.67), since LibreLane runs with `USE_SLANG`.
`setup_flow` is a user-local, gitignored script that sets PATH/licences and defines the alias `flow="python shortcut.py"`.

## Conventions

- **Licensing/REUSE**: SPDX header in every file; unheaderable files via `REUSE.toml`. Flow
  code is Apache-2.0; example RTL SHL-2.1; code inherited from RVLab keeps its
  `2024 RVLab Contributors` header with a "Modified by" line.
- **Flow code**:
  - One block per file in `flow/`, class name `CamelCase`, registered in `flow/__init__.py`.
  - `setup(self)` resolves paths from `self.flow.base_dir`.
  - Intermediate, non-user-facing tasks are `hidden=True`.
  - Tasks return a `Result()` holding paths/data; artefacts are written into `cwd`.
  - External tools are wrapped in `flow/tools/`; no raw `subprocess` boilerplate in blocks.
  - PDK-specific logic only in `flow/pdk/`.
  - Tool/env lookups inside tasks, not at import time, so the flow imports (and the ASIC
    path runs) without proprietary tools.
  - Lists/dicts received from other tasks' `Result`s are copied before mutation.
- **`src/`**: example/template content only; minimal and generic.
- **Design config**: no config files under `src/` and no per-block config classes. Each
  block takes its config as keyword arguments in `flow/__init__.py`, with defaults wherever
  sensible; structured values (floorplan, clock, padring, macro placements) use the
  dataclasses in `flow/config.py`. Paths are relative to `src/` and resolved in `setup()`;
  source lists are glob patterns expanded inside tasks. Data passed between tasks goes
  through `config.to_data`/`from_data` (`None` fields are omitted since `Result`s cannot
  hold `None`). Tool-specific settings get an explicit escape hatch (e.g. a raw `librelane`
  override dict), not first-class fields.
- **Testbenches**: sources in `src/tb/`; declared as `Testbench` blocks in
  `flow/__init__.py` with minimal arguments (no config file). Keep configuration data
  minimal and avoid boilerplate.
- **PDK**: one `flow.pdk.Pdk` descriptor instance, created in `flow/__init__.py` and passed
  to block constructors. Hard macros (PDK SRAMs, later digital/analog macros) implement
  `flow.macro.HardMacro`. Ownership of tool settings: PDK-inherent ones live in the PDK
  plugin or macro provider, tool workarounds in the block, design choices in the config.
- **Naming**: block names lowercase snake_case; macro blocks are `macro_<name>`, `<name>`
  being the macro's directory `src/asic/macros/<name>/`; the hardened cell is named after the
  macro's top module.
- **Docs**: describe target and intent only — never current state. Remove roadmap items
  when done.
- **Git**: see `CLAUDE.md`.

## Open questions (need a user decision before the corresponding phase)

1. **Where SRAMs live**: external macros of the digital macro using them, or at chip
   toplevel only?
2. **Open simulators**: beyond Icarus for the ASIC path (Verilator, CocoTB?), and for
   mixed-signal (NGSpice + behavioral digital models, XSPICE, co-sim in ORDeC?).
3. **Digital top-level routing in `ChipTop`**: OpenROAD via LibreLane steps vs. wait for the
   in-house flow.
4. **LVS/DRC engine** of record: KLayout (ORDeC) vs. Magic/Netgen (LibreLane).
5. **Second PDK** (sky130) as a template goal, or IHP SG13G2 only?
6. Should the **FPGA flow** remain in the template long-term or become an optional module?

## Pointers

- PyDesignFlow: https://pydesignflow.readthedocs.io (source in
  `.venv/lib/python*/site-packages/pydesignflow/`)
- ORDeC: https://ordec.readthedocs.io; `../ordec/AGENTS.md`, `docs/ref/`,
  `src/ordec/layout/` (GDS, KLayout, pnr), `src/ordec/sim/` (NGSpice),
  `src/ordec/lib/ihp130.py` (PDK integration)
- LibreLane: https://librelane.readthedocs.io
- slang: https://sv-lang.com
- IHP SG13G2 PDK: https://github.com/IHP-GmbH/IHP-Open-PDK
