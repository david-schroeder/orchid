# 03 — Roadmap

Ordered plan toward the target in `01`/`02`. **Review the actual repository state before
starting any item**: some items may already be (partly) done. Remove completed items from
this file instead of marking them. Items marked ❓ need a user decision (see
`04_conventions_and_notes.md`, Open questions).

Principle: the example design in `src/` keeps building end-to-end between steps; no
big-bang rewrite.

## Phase 3 — ORDeC integration and `AnalogMacro` block

Detailed plan with decisions and sub-phases: `05_phase3_ordec_plan.md`.

- ORDeC as an external tool (subprocess worker) with PDK hooks; ORD sources under `src/ams/`,
  ORD testbenches under `src/tb/`.
- `AnalogMacro` (check and export one ORDeC cell) and `AnalogTestbench` blocks; analog
  hierarchy expressed in ORDeC only.
- LEF abstract and `MacroProduct` export for analog macros; digital-visible behavioral models.
- Demo: 2-bit flash ADCs + stdcell adder + 3-bit R-2R DAC composed by an ORDeC parent macro.

## Phase 4 — `ChipTop` (ORDeC analog toplevel)

- Toplevel ORDeC cell instantiating digital/analog macros; schematic-driven connectivity.
- Explicit `padring` task (initially still driving LibreLane's chip flow for the
  digital-only case, then ChipTop-owned steps).
- Global PDN, GDS merge, fill, full-chip DRC and LVS, signoff report.
- Chip-level simulations through `view_*` tasks of the toplevel: RTL with behavioral macro
  models; gate-level; SPICE/mixed on selected paths (❓ mixed-signal simulator).
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

- Phase 5 is independent of phases 3–4 and may run in parallel.
