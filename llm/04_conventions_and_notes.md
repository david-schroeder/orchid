# 04 — Conventions, environment, open questions

> Target-oriented. Review the actual state (`flow/`, `requirements.txt`, environment)
> before acting.

## Toolchain (intended)

| Tool | Used for |
|------|----------|
| PyDesignFlow | Flow orchestration, CLI |
| LibreLane | Digital synth/PnR/signoff until replaced by the in-house flow |
| ORDeC (`ordec`; sibling clone `../ordec`) | Analog/AMS design data, sims, layout, DRC/LVS |
| slang | SystemVerilog preprocessing/elaboration/conversion (replaces sv2v), lint |
| Yosys, OpenROAD, Magic, Netgen, KLayout | Underlying digital synthesis/PnR/signoff tools |
| NGSpice | Analog simulation (via ORDeC) |
| Verible | Lint |
| Open simulator (Verilator/Icarus/CocoTB ❓) | ASIC RTL/netlist simulation |
| Vivado, QuestaSim | Optional: FPGA prototyping and simulation |
| IHP-Open-PDK `ihp-sg13g2` | PDK |

Environment: `source .venv/bin/activate`; `PDK_ROOT` and `ORDEC_PDK_IHP_SG13G2` point to the
`ihp-sg13g2` directory of the PDK checkout. `setup_flow` is a user-local, gitignored script
that sets PATH/licences and defines the alias `flow="python shortcut.py"`.

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
- **Naming**: block names lowercase snake_case; macro instances named by macro (exact scheme
  decided in phase 2).
- **Docs**: describe target and intent only — never current state. Remove roadmap items
  when done.
- **Git**: see `CLAUDE.md`.

## Open questions (need a user decision before the corresponding phase)

1. **Directory layout for multiple macros** under `src/`: one dir per macro with a config
   file, or one central config enumerating macros and instances?
2. **Config format** for design/macro declarations: Python modules, JSON/TOML, or ORDeC?
3. **Where SRAMs live**: external macros of the digital macro using them, or at chip
   toplevel only?
4. **Open simulators** for the ASIC path (Verilator, Icarus, CocoTB?) and for mixed-signal
   (NGSpice + behavioral digital models, XSPICE, co-sim in ORDeC?).
5. **Digital top-level routing in `ChipTop`**: OpenROAD via LibreLane steps vs. wait for the
   in-house flow.
6. **LVS/DRC engine** of record: KLayout (ORDeC) vs. Magic/Netgen (LibreLane).
7. **slang integration**: CLI/pyslang conversion output vs. Yosys-slang plugin.
8. **Second PDK** (sky130) as a template goal, or IHP SG13G2 only?
9. Should the **FPGA flow** remain in the template long-term or become an optional module?
10. Final naming of `DigitalMacro` / `AnalogMacro` / `ChipTop` (proposals).

## Pointers

- PyDesignFlow: https://pydesignflow.readthedocs.io (source in
  `.venv/lib/python*/site-packages/pydesignflow/`)
- ORDeC: https://ordec.readthedocs.io; `../ordec/AGENTS.md`, `docs/ref/`,
  `src/ordec/layout/` (GDS, KLayout, pnr), `src/ordec/sim/` (NGSpice),
  `src/ordec/lib/ihp130.py` (PDK integration)
- LibreLane: https://librelane.readthedocs.io
- slang: https://sv-lang.com
- IHP SG13G2 PDK: https://github.com/IHP-GmbH/IHP-Open-PDK
