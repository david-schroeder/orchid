# 03 — Roadmap

Ordered plan toward the target in `01`/`02`. **Review the actual repository state before
starting any item**: some items may already be (partly) done. Remove completed items from
this file instead of marking them. Items marked ❓ need a user decision (see
`04_conventions_and_notes.md`, Open questions).

Principle: the example design in `src/` keeps building end-to-end between steps; no
big-bang rewrite.

## Phase 2 — `DigitalMacro` block

- Extract the generic digital hardening path (preprocess -> LibreLane config -> run ->
  collect outputs) into a parametrized `DigitalMacro` block.
- Define and document the **macro product** schema (LEF, GDS, netlist, LIB, SDF/SPEF, SPICE,
  pins, metadata). This is the central interface for all later phases.
- Isolate LibreLane in a backend adapter; use macro-mode settings (no padring, pin
  placement, macro outputs).
- Re-express the example: project core as a `DigitalMacro`, SRAMs as external macros (inside
  the macro).
- Per-macro tasks: `lint`, `sim_rtl`, gate-level sim.
- Multiple instances driven by a list/config.

## Phase 3 — ORDeC integration and `AnalogMacro` block

- Add a tiny real analog example macro in ORD/Python under `src/analog/`.
- Tool wrappers/blocks for ORDeC views: netlist export, NGSpice sims, layout generation,
  GDS export, KLayout DRC and LVS (requires `ORDEC_PDK_IHP_SG13G2`).
- `AnalogMacro` tasks per `02`; reuse the macro product schema.
- Define how analog macros expose a digital-visible model (Verilog / real-number model,
  liberty abstract).
- Multiple instantiation via config.

## Phase 4 — `ChipTop` (ORDeC analog toplevel)

- Toplevel ORDeC cell instantiating digital/analog macros; schematic-driven connectivity.
- Explicit `padring` task (initially still driving LibreLane's chip flow for the
  digital-only case, then ChipTop-owned steps).
- Global PDN, GDS merge, fill, full-chip DRC and LVS, signoff report.
- Chip-level simulations: RTL with behavioral macro models; gate-level; SPICE/mixed on
  selected paths (❓ mixed-signal simulator).
- `tapeout_package`.

## Phase 5 — Replace LibreLane with an in-house PyDesignFlow digital flow

- Reimplement the LibreLane Chip flow steps as PyDesignFlow blocks/tasks (Yosys, OpenROAD
  floorplan/place/CTS/route, fill, KLayout/Magic signoff, Netgen LVS, STA), using the
  underlying tools directly.
- Keep the `DigitalMacro` interface unchanged; LibreLane backend stays selectable for
  regression comparison until parity (area/timing/DRC/LVS) is shown.
- Hardcoded example values and suppressed signoff checks inherited from the LibreLane-based
  setup are resolved here; clean signoff becomes the baseline.
- Fine-grained caching, partial reruns, parallel macro builds.

## Phase 6 — Template polish

- Second PDK (e.g. sky130 via ORDeC) to validate the PDK-agnostic structure.
- CI running lightweight flow tasks (import, lint, open-tool sims, small hardening run).
- Sphinx documentation, "start your own project from this template" guide, example gallery
  (digital-only, analog-only, mixed).
- Optional: ORDeC web UI integration; HTML reports.

## Ordering notes

- The macro-product schema (phase 2) gates phases 3–4.
- Phase 5 is independent of phases 3–4 after phase 2 and may run in parallel.
