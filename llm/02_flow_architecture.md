# 02 — Flow architecture: blocks, tasks, relations

> Describes the **target** flow. Names of blocks/tasks are proposals. Review the actual code
> in `flow/` before acting; some of what is described here may exist, partly or not at all.

PyDesignFlow vocabulary: a *Block* is a class with *tasks* (`@task` methods). Tasks declare
inputs via `requires={'arg': 'block.task'}`; blocks are registered in the global `Flow`
(`flow/__init__.py`) and wired via `dependency_map`. A block can be instantiated multiple
times with different constructor parameters — the mechanism used for macros.

```
  PDK plugin (flow/pdk)  ─────────────────────────────────────────────┐ (layers, corners,
                                                                       │  stdcell/IO libs,
  srcs ──> DigitalMacro[<m1..mN>] ──┐                                  │  DRC/LVS decks,
  ORDeC ─> AnalogMacro[<a1..aM>]  ──┼──> ChipTop ──> signoff artefacts │  fill rules)
  srcs ──> (FPGA path, optional)  ──┘        │
                                             └─> chip-level simulations (digital, SPICE, mixed)
```

## Sources

Collects source file lists (RTL, packages, defines, include dirs, testbenches) per target
(common / FPGA / ASIC) and provides `lint` (Verible and/or slang). The ASIC path has no
SystemVerilog-to-Verilog conversion step: synthesis reads the sources directly through the
**yosys-slang** frontend, and conditionals such as `USE_POWER_PINS` are resolved by the
synthesis/netlisting tools per step. A flow task elaborates the same sources with
**pyslang** (all relevant define variants) to fail early.

## DigitalMacro — generic, multiply instantiable

Parameters (conceptual): macro name, RTL source selection, top module, clock/constraint spec,
floorplan hints (size/utilization/pin order), power nets, sub-macros (e.g. SRAMs), backend
(`librelane` first, in-house later).

| Task | Description |
|------|-------------|
| `srcs` / `elaborate` | Select sources, elaboration check (pyslang) |
| `lint` | Static checks |
| `sim_rtl` | RTL simulation (open simulator preferred; Questa optional) |
| `synth` | Logic synthesis (Yosys) |
| `harden` | PnR to macro (LibreLane Chip flow first, in-house flow later) |
| `drc`, `lvs` | Signoff checks (KLayout/Magic, Netgen) |
| `sta` | Multi-corner STA, SDF/SPEF |
| `sim_gl` / `sim_sdf` | Gate-level / SDF-annotated simulation |
| `view` | KLayout/OpenROAD GUI |
| `export` | Assemble the *macro product* consumed by `ChipTop` |

**Macro product** (`Result`): `lef`, `gds`, `verilog` (netlist + behavioral/blackbox),
`lib` per corner, `sdf`/`spef`, `spice`, pin list, PDN connection info, size/obstructions,
metadata (name, version, PDK).

**Backend swap:** LibreLane-specific code is isolated in a backend adapter so the block
interface (parameters in, macro product out) stays stable when the in-house PyDesignFlow
replacement lands. That replacement is built from fine-grained blocks (synth, floorplan,
place, cts, route, fill, signoff).

## AnalogMacro — generic, multiply instantiable, ORDeC-based

An ORDeC `Cell` (ORD or Python) with `@viewgen` views: `symbol`, `schematic`, `layout`,
plus testbench cells.

| Task | Description | Tooling |
|------|-------------|---------|
| `elaborate` | Build views, schematic checks | ORDeC |
| `sim_<tb>` | SPICE sims: DC/AC/tran/noise, corners, MC where supported | ORDeC netlister + NGSpice |
| `netlist` | Hierarchical SPICE netlist export | ORDeC netlister |
| `layout` | Layout generation/assembly (PCells, SRouter, constraints, `ordec.layout.pnr`) | ORDeC |
| `gds_export` | GDS (and LEF abstract) export | ORDeC |
| `drc` | DRC | KLayout (ORDeC integration) |
| `lvs` | Layout-vs-schematic | KLayout LVS (ORDeC) / Netgen |
| `pex` | Parasitic extraction (optional) | KLayout/Magic |
| `sim_post_layout` | SPICE with parasitics | NGSpice |
| `abstract` | LEF + liberty/behavioral model for chip-level integration | ORDeC + scripts |
| `export` | Macro product (same schema as digital) | |

The shared `export` interface lets `ChipTop` treat digital and analog macros uniformly
(LEF/GDS/netlist/pins); analog macros additionally supply a SPICE netlist and behavioral
model, digital ones liberty/SDF.

Third-party hard macros (PDK SRAMs, bondpads) are the degenerate case — an `ExternalMacro`
that only *exports* existing views from the PDK.

## ChipTop — ORDeC analog toplevel

The toplevel is an ORDeC cell instantiating digital macros, analog macros, pad cells and
glue; its schematic is the single source for netlist and connectivity.

| Task | Description |
|------|-------------|
| `collect_macros` | Gather macro products from all macro blocks |
| `elaborate` | Build toplevel schematic, connectivity checks (macro pins vs. nets) |
| `floorplan` | Die/core area, macro placement, halos, keep-outs |
| `padring` | I/O ring (IO cells, power pads, bondpads, corners, filler) from a pad spec |
| `pdn` | Global power distribution (rings, stripes, macro connections, domain separation) |
| `route` | Top-level routing of glue signals (Top-level is analog, thus via ORDeC SRouter) |
| `fill` | Metal/active fill |
| `merge_gds` | Combine macro GDS + top layout (+ seal ring) |
| `drc` / `lvs` | Full-chip DRC (incl. density) and LVS vs. toplevel schematic |
| `antenna`, `erc` | As applicable |
| `sta` | Chip-level timing of digital portions with macro libs |
| `sim_rtl` | Mixed RTL simulation (digital behavioral + analog behavioral models) |
| `sim_netlist` | Gate-level; SPICE / mixed-signal for selected paths |
| `view` | KLayout view of final GDS |
| `signoff_report` | Aggregate DRC/LVS/STA/sim status |
| `tapeout_package` | Final GDS/OASIS, netlists, reports, config snapshot |

`ChipTop` owns everything global (padring, PDN, fill, seal ring, full-chip checks). Macros
must not assume their own padring/global PDN; their products expose pins and PDN connection
requirements only.

## Simulation (cross-cutting)

- FPGA-oriented sims (Vivado/XSim/Questa, incl. post-synth/post-PnR with SDF) are an
  optional prototyping path.
- ASIC-oriented sims reuse the same testbench sources against (a) RTL + behavioral macro
  models, (b) post-synth/post-PnR netlist + SDF, (c) mixed with analog macro models. The
  simulator abstraction in `flow/tools/` should include an open simulator backend
  (Verilator / Icarus / CocoTB) so the ASIC path needs no proprietary tool (Future).

## PDK plugin

A small PDK descriptor (name, root, stdcell lib, IO lib, corners, SRAM macro list, PDN
recipes, DRC/LVS deck paths, layer map, fill rules, matching ORDeC PDK module such as
`ordec.lib.ihp130`) selected once at flow level and passed to blocks. No bare PDK paths or
PDK names in generic blocks.

## Dependency summary

```
PDK ──> everything
DigitalMacro.export ──┐
AnalogMacro.export  ──┼──> ChipTop.collect_macros ─> floorplan ─> padring ─> pdn ─> route
ExternalMacro.export ─┘                                                          │
                                  fill <─────────────────────────────────────────┘
                                   │
                          merge_gds ─> drc ─> lvs ─> signoff_report ─> tapeout_package
ChipTop.elaborate ──> netlist ──> sim_netlist
Macro sim_* tasks are independent leaves (cheap, run per macro)
```
