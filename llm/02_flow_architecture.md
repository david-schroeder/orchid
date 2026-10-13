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

One block instance `macro_<name>` per macro, declared explicitly by name in
`flow/__init__.py` (like all blocks); its config is read from `src/asic/macros/<name>/config.py`.
The config (`DigitalMacroConfig`) holds: top module (= macro cell name), RTL sources,
defines/include dirs, clock, floorplan (absolute die size + core margin), power nets, optional
pin order and PDN script, sub-macros (e.g. PDK SRAMs, as `MacroPlacement`s resolved by the PDK
plugin), and a raw backend override dict. Macro RTL lives in `src/rtl/<name>/` (shared with the
FPGA path); macro config in `src/asic/macros/<name>/`.

Macro-mode hardening: no padring, no core ring, power grid on the lower PDN layer only with
its stripes promoted to pins; PDK-specific layer limits (keeping upper layers free for the
toplevel grid) come from `Pdk.librelane_macro_config()`.

| Task | Description |
|------|-------------|
| `srcs` / `elaborate` | Select sources, elaboration check (pyslang) |
| `lint` | Static checks |
| `synth` | Logic synthesis (Yosys) |
| `harden` | PnR to macro (LibreLane Chip flow first, in-house flow later) |
| `drc`, `lvs` | Signoff checks (KLayout/Magic, Netgen) |
| `sta` | Multi-corner STA, SDF/SPEF |
| `view` | KLayout/OpenROAD GUI |
| `export` | Assemble the *macro product* consumed by `ChipTop` |
| `view_rtl` / `view_gl` / `view_sdf` | Simulation views (RTL; netlist + PDK cell and sub-macro models; + SDF per corner) |

The macro block provides simulation views but knows nothing about testbenches; see
*Simulation*.

**Macro product** — `flow.macro.MacroProduct`, returned as `product` by every macro block's
`export` task (`config.to_data(..., keep_paths=True)`; read back with
`config.from_data(MacroProduct, ...)`). It is the central interface between macro blocks
and the toplevel; analog and external macros produce the same schema.

| Field | Content |
|-------|---------|
| `name`, `kind`, `pdk` | Cell name; `digital` / `analog` / `external`; PDK name |
| `width`, `height` | Macro size in µm (from LEF) |
| `pins` | `Pin(name, direction, use, layers)` per LEF pin; supply pins have use `POWER`/`GROUND` and carry the PDN connection layer |
| `gds`, `lef` | Physical views (lists of files) |
| `vh`, `nl`, `pnl` | Verilog blackbox header, gate netlist, powered gate netlist |
| `model` | Behavioral Verilog for system simulation (RTL for digital macros) |
| `lib`, `sdf`, `spef` | Per-corner views: corner name/wildcard -> files |
| `spice` | SPICE netlist(s) |
| `metadata` | Free-form (backend, producing block, ...) |

View field names mirror LibreLane design formats / `Macro` fields, so a product maps
directly onto the backend's macro inputs. Export copies all views out of the backend run
directory into `<view>[/<corner>]/<file>` under the export task directory.

**Backend swap:** LibreLane-specific code (config variables, flow classes, run layout,
hard-macro/PDN config) is isolated in the adapter `flow/tools/librelane.py`, shared by
`DigitalMacro` and the ASIC toplevel, so the block interface (config in, macro product
out) stays stable when the in-house PyDesignFlow replacement lands. That replacement is
built from fine-grained blocks (synth, floorplan, place, cts, route, fill, signoff).

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
A simulation is *testbench* × *design view* × *simulator*; the three are independent.

- **Views** (`flow.testbench.SimView`): every design block (sources, macros, FPGA top, ASIC
  top/`ChipTop`) offers hidden `always_rebuild` tasks `view_rtl`, `view_gl` and `view_sdf`
  returning a `SimView` as `view`: design sources or netlist plus simulation models (PDK
  cells, sub-macros, vendor primitives), extra top modules, defines, include dirs,
  precompiled vendor libraries, SDF per corner and support files. A block offers only the
  steps it has. Chip-level views compose macro products (`model` for behavioral, `nl` for
  gate-level), allowing mixed RTL/gate-level simulation.
  PDK cell models are the same for gate-level and SDF views and work in every simulator;
  simulator-specific workarounds (e.g. driving timing-check delayed nets for Icarus) are
  guarded by the simulator's predefined macro, never applied unconditionally.
- **Testbenches**: all testbench sources live in `src/tb/`. A `Testbench` block binds one
  testbench to one design block, wired as `dut` in its `dependency_map`
  (`Testbench(srcs, top, sdf_scope, dependency_map)`, declared in `flow/__init__.py`;
  sources are glob patterns). The binding is many-to-many by declaring further blocks; neither testbenches nor design blocks reference each other,
  and nothing is discovered automatically.
- **Simulators**: tasks `sim_<step>_<simulator>`, using the wrappers in `flow/tools/`
  (Icarus as the open default for the ASIC path; QuestaSim and XSim optional). SDF views
  are simulated once per corner. Further open simulators (Verilator, CocoTB) plug in the
  same way.
- **Testbench contract** for running unchanged on every view: instantiate the design by
  its top module name, no parameter overrides differing from the implementation, no
  hierarchical references into the design (or guarded by a define the view sets), inputs
  driven away from active clock edges; self-checking (pass by `$finish`, fail via `$fatal`).

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
