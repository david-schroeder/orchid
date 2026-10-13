# 05 — Phase 3 plan: ORDeC integration, `AnalogMacro`, mixed-signal demo

> Implementation plan for roadmap phase 3 (`03_roadmap.md`). Like the roadmap, **remove
> sub-phases from this file when they are done**, and delete the file when phase 3 is
> complete (after moving lasting conventions into `01`/`02`/`04`). Review the actual
> repository and ORDeC state before starting a sub-phase (see `CLAUDE.md`).

## Goal

1. ORDeC design sources live in the source tree and are driven by the flow: batch
   elaboration, netlisting, layout/GDS, DRC, LVS, SPICE testbenches, export.
2. A generic, multiply instantiable `AnalogMacro` block turns one ORDeC cell into a
   `MacroProduct` (same schema as `DigitalMacro`), ready for `ChipTop` in phase 4.
3. Hierarchies of arbitrary depth (analog cells containing analog cells and standard-cell
   logic) work without flow-side hierarchy machinery.
4. A mixed-signal demo: two 2-bit flash ADCs, a 2b+2b→3b adder in SG13G2 standard cells, and
   a 3-bit R-2R DAC, composed by an ORDeC parent macro (`MixSum`), DRC/LVS clean and verified
   by SPICE testbenches. Not a chip toplevel (no padring, no seal ring): that is phase 4.

## Decisions

### D1 — Hierarchy lives in ORDeC, not in the flow

ORDeC already covers hierarchical composition end to end: a parent cell imports and
instantiates sub-cells (plain Python/ORD imports); netlisting and SimHierarchy are
hierarchical; `run_lvs` compares hierarchically (KLayout `align` flattens differing cuts);
DRC decks run on hierarchical GDS; `ordec.layout.pnr` blocks are composable (ports on Metal4
pads outside the block interior, supplies on side straps); `ExtLibrary` imports foreign
LEF/GDS/SPICE/Verilog as ordinary cells. A single ORDeC `Directory` keeps netlist and GDS
names consistent, which hierarchical LVS depends on.

Therefore:

- **Analog-in-analog hierarchy is expressed only by imports in the ORD sources.** The flow has
  no `macros=[...]` edges between `AnalogMacro` blocks and needs no variadic dependencies.
- **An `AnalogMacro` block = "check and export one ORDeC cell".** Declaring a sub-cell (e.g.
  the ADC) as its own block is optional and only adds unit-level signoff and an exported
  product; such blocks are independent leaves.
- **The flow owns what ORDeC does not:** persistent on-disk artefacts (GDS, LEF abstract,
  SPICE, behavioral model, `MacroProduct`), caching across runs, batch/CI execution with
  pass/fail, and handing non-ORDeC artefacts (LibreLane macros, external IP) into ORDeC.
- Foreign macros enter an ORDeC hierarchy through `ExtLibrary` built from a `MacroProduct`
  (LEF → symbol, GDS → layout, SPICE or powered Verilog netlist → schematic). This is the
  only cross-tool edge and is needed first by `ChipTop` (phase 4).

### D2 — Digital logic inside analog macros is ORDeC-native

Small logic inside analog macros (thermometer encoder, adder, DAC drivers) is an ORD
schematic of SG13G2 standard cells (`ExtLibrary` of the PDK stdcell LEF/GDS/SPICE), laid out
by `ordec.layout.pnr.place_and_route` as a sub-block. LibreLane-hardened `DigitalMacro`s are
integrated into ORDeC hierarchies in phase 4.

### D3 — ORDeC runs as an external tool, one subprocess per task

PyDesignFlow runs independent targets in threads (`-j`); ORDeC's DRC/LVS helpers use
process-relative run directories, ORDB is process state, and design sources should be
re-imported fresh on every run. Each ORDeC-facing task therefore runs a worker script in a
subprocess (wrapper in `flow/tools/`), with:

- `cwd` = the task directory,
- `src/` prepended to `sys.path` (import root, see D5),
- PDK environment derived from the `Pdk` descriptor (e.g. `ORDEC_PDK_IHP_SG13G2` set from
  `Pdk.root()`, so users need only one PDK variable),
- a small JSON request (module, cell expression, action, options) and JSON reply (written
  files, check status), which the task turns into its `Result`.

Views are regenerated per task; this is cheap for macro-sized cells and deterministic.

Worker conventions (verified):

- Run as `python -P ordec_worker.py <request> <reply>`: `-P` keeps the worker's directory
  (`flow/tools/`, holding the wrapper `ordec.py`) off `sys.path`, where it would shadow the
  `ordec` package. The worker imports `ordec.importer` before any design module.
- Request/reply files stay in the task directory, so a failing action can be rerun by hand
  there. Worker output goes to the task log (PyDesignFlow routes subprocess output per
  thread); the traceback is in the log and the reply, the raised `OrdecError` is one line.
- ORD bytecode caches stay in `src/**/__pycache__` (gitignored, shared with the UI, written
  atomically per process). `PYTHONPYCACHEPREFIX` is not used: it redirects all bytecode,
  including the standard library.
- `run_drc`/`run_lvs` with `use_tempdir=False` write to `<cwd>/drc/` (`layout.gds`,
  `main`/`maximal`/`antenna.lyrdb` + logs) and `<cwd>/lvs/` (`layout.gds`, `schematic.cir`,
  `extracted.cir`, `out.lvsdb`). On a ~10-cell pnr block, DRC (maximal + antenna) takes
  ~7 s and LVS ~2 s.
- The UI runs `ordec -m <module>` with `src/` on `PYTHONPATH`; it needs an ORDeC install
  with frontend (`webdist.tar`, or a `web/dist` build for editable installs).
- A `.py` file shadows an `.ord` file of the same name in the same directory.

### D4 — Testbenches are ORDeC cells; `AnalogTestbench` runs them

Analog testbenches are ORD testbench cells (schematic with sources and loads, `sim_*`
viewgens, `report*` viewgens). Reports contain `PassFail` elements as self-checks (ORDeC's
`Report` schema). An `AnalogTestbench` block evaluates every `report*` viewgen, writes the
results to disk, and fails if any check fails or a report has no check. As with the Verilog
`Testbench`, testbenches and design blocks do not reference each other in the flow; the DUT
is bound by the testbench's ORD import. Corners/sweeps are written in the testbench (ORDeC
`simulate(corner=...)`).

### D5 — Source layout and naming

```
src/ams/
├── stdcells.py            # Shared SG13G2 stdcell ExtLibrary + pnr helpers (one instance per process)
├── adc/                   # One directory per analog macro; module ams.adc.adc
│   ├── adc.ord            #   Top cell Adc (+ small sub-cells, or further modules)
│   ├── comparator.ord
│   └── adc.sv             #   Behavioral model (digital-visible, see 3.7)
├── dac/  ...
└── mixsum/ ...            # Parent: imports ams.adc.adc, ams.dac.dac; adder sub-cell
src/tb/
├── adc_tb.ord             # ORDeC testbenches (next to the Verilog testbenches)
├── dac_tb.ord
└── mixsum_tb.ord
```

- Import root is `src/`; modules are addressed as `ams.<name>.<file>` and `tb.<name>`
  (namespace packages, no `__init__` files).
- **One shared stdcell `ExtLibrary`** (`src/ams/stdcells.py`): separate `ExtLibrary`
  instances would create distinct, suffixed copies of the same stdcells in netlists/GDS.
- Block naming follows `DigitalMacro`: `macro_<name>`, sources in `src/ams/<name>/`, default
  module `ams.<name>.<name>`; testbench block `<name>_tb` → module `tb.<name>_tb`, cell
  `CamelCase(<name>_tb)`.
- Supply nets/pins `vdd`/`vss` (ORDeC/`ihp130.grid` convention); signal ports lowercase.
- `.ord` and `.py` design files carry SPDX headers (`#` comments; example design content:
  SHL-2.1).
- Exported names: the macro's top cell is named `<name>`; ORDeC-authored sub-cells are
  prefixed `<name>__` so that products of different macros never collide when merged
  (phase 4); library cells (stdcells, PDK primitives) keep their names. Implemented with one
  export `Directory` (subclass) used for both GDS and SPICE, so names stay LVS-consistent:
  a `klayout.LvsDirectory` subclass overriding `name_cell` (top cell → `<name>`;
  `ExtLibraryCell`s and cells from `ordec.*` modules → default name; others →
  `<name>__<default name>`). LVS with this naming is clean. `run_lvs` creates its own
  directory, so using it there requires the upstream change in Open items. PDK PCell
  structures keep their parameter-derived names (e.g. `rppd_l_2u_w_500n_b_0_ps_180n_m_1`),
  identical across macros built with the same ORDeC version.

### D6 — Physical rules for analog macros

- Layers above the PDK's macro limit stay free for the toplevel (same limit as
  `librelane_macro_config`, e.g. up to Metal5 on SG13G2); checked in `drc`.
- Pins on routing metals with LVS-readable labels (ORDeC's `run_lvs` requires this anyway).
- Parent layouts land on a pnr block's Metal4 port pads (unnamed shapes) via
  `stdcells.port(inst, *pin_path)`, which resolves a sub-cell's `LayoutPin` in parent
  coordinates; supplies are on the block's Metal1 rails (one row) or side-strap pads.
- Resistor substrate (SG13G2 LVS merges it into one substrate net): every resistor's `sub`
  goes to the substrate-tap net (`vss`), the cell owning resistors places a `Ptap` on it,
  and a cell whose substrate net is not a port needs a `sub` port (see ORDeC docs,
  `ihp130_substrate_lvs`).
- Signoff runs on the same generator output that is exported (deterministic regeneration);
  the preferred end state is DRC/LVS on exactly the exported files (see Open items).
- Post-layout extraction/simulation is out of scope (ORDeC has no PEX); a `pex` task is added
  later via KLayout/Magic.

## Interfaces (target)

### `AnalogMacro` (`flow/analog_macro.py`)

```python
flow['macro_adc'] = AnalogMacro(pdk, cell='Adc')
flow['macro_dac'] = AnalogMacro(pdk, cell='Dac')
flow['macro_mixsum'] = AnalogMacro(pdk, cell='MixSum')
```

Constructor (keyword-only, defaults wherever sensible): `cell` (class name), `module`
(default `ams.<name>.<name>`), `params` (cell parameters, default none), `power`
(`PowerNets`, default `vdd`/`vss`), `model` (behavioral model globs relative to `src/`,
default `ams/<name>/*.sv` if present), `drc` (raw options for the PDK DRC call, escape
hatch).

| Task | Description |
|------|-------------|
| `elaborate` (hidden) | Import module, build symbol + schematic, render SVGs, basic checks |
| `netlist` | Hierarchical SPICE subckt netlist of the macro |
| `layout` | Generate layout, write GDS |
| `drc` | PDK DRC via ORDeC/KLayout, plus macro layer limit; report on disk |
| `lvs` | LVS via ORDeC/KLayout; report on disk |
| `abstract` (hidden) | LEF abstract: size, pins (direction from symbol, supplies as POWER/GROUND), obstructions |
| `export` | `MacroProduct(kind="analog")`: gds, lef, spice, model, pins, size |
| `view_rtl` (hidden) | `SimView` with the behavioral model (for Verilog `Testbench`s) |
| `view` | Open the GDS in KLayout |
| `ui` | Open the cell in the ORDeC web UI (local mode) |

`export` requires `drc` and `lvs` to pass (an analog product is only exported signed off).

### `AnalogTestbench` (`flow/analog_testbench.py`)

```python
flow['adc_tb'] = AnalogTestbench(pdk)
```

Arguments: `cell` (default `CamelCase(block id)`), `module` (default `tb.<block id>`).
Tasks: `sim` (evaluate all `report*` viewgens; write `<report>.md` with markdown and check
results, `<report>.json` with the report data, plot series as CSV; fail on failing/missing
`PassFail`), `ui` (ORDeC web UI on the testbench).

### Tool wrapper and PDK hooks

- `flow/tools/ordec.py`: `run(pdk, request, cwd) -> reply` (subprocess, env, `sys.path`,
  JSON protocol, error propagation with ORDeC tracebacks), `ui(pdk, module, cwd, path, views)`.
- Worker script `flow/tools/ordec_worker.py` (stand-alone, does not import the `flow`
  package): one function per action, registered with `@action`: `elaborate`, `netlist`,
  `layout`, `drc`, `lvs`, `abstract`, `reports`.
- `flow/tools/lef.py`: add `write_macro(...)` (LEF abstract writer) next to `read_macro`.
- `Pdk` hooks: `ordec_env()`, `ordec_module` (`ordec.lib.ihp130`), `ordec_drc`/`ordec_lvs`
  (entry point names in that module), `macro_max_layer` (also used for LibreLane's
  `RT_MAX_LAYER`). IHP specifics in `flow/pdk/ihp_sg13g2/`.

## Demo design

Supply 1.2 V (SG13G2 LV core devices). All macros unclocked.

**`Adc` (`macro_adc`)** — 2-bit continuous-time flash ADC.
Ports: `vin`, `vrefp`, `vrefn`, `d[1:0]`, `vdd`, `vss`.
- `Ladder`: 4 equal unit resistors (Rppd or Rhigh) between `vrefp` and `vrefn`, taps at
  1/4, 1/2, 3/4.
- `Comparator` ×3: 5-transistor OTA plus output inverter; input-pair type (NMOS/PMOS) chosen
  so that all ladder taps lie in its input common-mode range at 1.2 V (decide by DC sim; the
  testbench reference range follows, e.g. `vrefn`/`vrefp` inside the rails).
- `Bias`: resistor into a diode-connected transistor, mirrored into the comparator tails (no
  bias pin).
- `ThermEnc`: thermometer `t[2:0]` → binary: `d1 = t1`, `d0 = t0 ^ t1 ^ t2` (two `xor2` + a
  buffer), stdcell schematic laid out by `ordec.layout.pnr`.
- Layout: analog sub-cells with PDK PCells, placed by hand/constraints; `ThermEnc` as pnr
  block; top-level wiring with `SRouter`.

**`Dac` (`macro_dac`)** — 3-bit R-2R DAC with unbuffered output.
Ports: `d[2:0]`, `vout`, `vdd`, `vss`.
- `DacDrivers`: 3 stdcell buffers (pnr block) driving the ladder rail to rail.
- `R2r`: unit R and 2R (= two series units, for matching); R large against the driver output
  resistance (e.g. ≥10 kΩ unit with Rhigh). `vout = vdd · code / 8`. With `buf_1` drivers
  and a 12 kΩ unit (Rhigh 0.5 × 4 µm), the operating point is up to ~2.7 % low (MSB); pick
  driver strength/unit length so the `dac_tb` tolerance holds.

**`MixSum` (`macro_mixsum`)** — parent.
Ports: `va`, `vb`, `vout`, `vrefp`, `vrefn`, `vdd`, `vss`.
- Two `Adc` instances, `Adder` (2b+2b→3b: half adder + full adder from `xor2`/`and2`/`or2`,
  pnr block, sub-cell in `src/ams/mixsum/`), one `Dac`.
- Output: `vout = vdd · (qa + qb) / 8`, `qa`/`qb` the ADC codes.
- Layout: macro instances placed side by side, wiring with `SRouter` to the pnr blocks' Metal4
  port pads, supply straps tying `vdd`/`vss` of all children.

**Testbenches** (`src/tb/`, all self-checking with `PassFail`):
- `adc_tb`: slow ramp on `vin` across the reference range; check the decoded code against the
  ideal thresholds (with a margin around transitions); report code vs. `vin`.
- `dac_tb`: step through all 8 codes with `Vpulse` sources (as in ORDeC's `adder_pnr.ord`
  testbench); check settled `vout` against `vdd · code / 8` within a tolerance (output
  load specified in the testbench).
- `mixsum_tb`: two ramps/sines of different frequencies on `va`, `vb`; Python reference model
  `ideal(qa) + ideal(qb)` → expected `vout`; check at settled points away from code
  transitions; plot inputs, codes, output.

## Implementation phases

Each sub-phase ends with the example flow importing and the new tasks running end to end.

### 3.2 — `AnalogMacro` core tasks with the DAC

- `AnalogMacro` tasks `netlist`, `layout`, `drc`, `lvs`, `view`, `ui` next to `elaborate`,
  each backed by a worker action.
- `Dac` layout (`DacDrivers` via `stdcells.pnr`, `R2r` with PCells, `Ptap` and `SRouter`),
  the first real macro.

Acceptance: `macro_dac.drc` and `macro_dac.lvs` pass; `macro_dac.view` shows the GDS.

### 3.3 — `AnalogTestbench` with `dac_tb`

- `flow/analog_testbench.py` (`sim`, `ui`), report files on disk, pass/fail gating.
- `src/tb/dac_tb.ord`.

Acceptance: `dac_tb.sim` passes; a deliberately wrong tolerance makes it fail.

### 3.4 — Abstract and export

- LEF writer (`flow/tools/lef.py`), `abstract` task; layer-limit check in `drc`.
- Export `Directory` naming (D5); `export` task producing `MacroProduct(kind="analog")`
  (`gds`, `lef`, `spice`, `model`, pins/size via `lef.read_macro`), gated on `drc`/`lvs`.
- Round-trip check: the exported product reads back into an ORDeC `ExtLibrary` (LEF/GDS/SPICE)
  and passes LVS as an imported cell (proves the phase-4 import path for analog products).

Acceptance: `macro_dac.export` writes a complete product; the round-trip check passes.

### 3.5 — ADC

- `src/ams/adc/`: `Ladder`, `Comparator`, `Bias`, `ThermEnc`, `Adc` (schematics first,
  then layouts).
- `src/tb/adc_tb.ord`; optionally a comparator unit testbench (DC transfer, offset).

Acceptance: `adc_tb.sim`, `macro_adc.drc`, `macro_adc.lvs`, `macro_adc.export` pass.

### 3.6 — `MixSum` parent

- `src/ams/mixsum/`: `Adder` (pnr block), `MixSum` (schematic importing `Adc`/`Dac`, layout
  assembly).
- `src/tb/mixsum_tb.ord` with Python reference model.

Acceptance: `mixsum_tb.sim`, `macro_mixsum.drc`, `macro_mixsum.lvs` (hierarchical, children
compared pairwise), `macro_mixsum.export` pass.

### 3.7 — Digital-visible models

- Hand-written SystemVerilog behavioral models with `real` analog ports (`adc.sv`, `dac.sv`,
  `mixsum.sv` instantiating the other two); exported as `model`, offered as `view_rtl`.
- A small Verilog `Testbench` (`mixsum_model_tb`) against `macro_mixsum` with Icarus, checking
  the same reference as `mixsum_tb`. Icarus (12) supports `real` ports and parameters through
  the hierarchy; use `always @*` rather than `always_comb` for `real`-valued locals (Icarus
  warns about the latter).

Acceptance: `mixsum_model_tb.sim_rtl_icarus` passes.

### 3.8 — Documentation and cleanup

- Move lasting conventions (ORDeC source layout, testbench conventions, export naming, PDK
  hooks) into `01`/`02`/`04`; remove phase 3 from `03_roadmap.md`; delete this file.
- Sphinx docs page for analog macros; README feature list.

## Open items (decide/verify during implementation)

- **Signoff on exported files**: preferred is a small upstream ORDeC change letting
  `run_drc`/`run_lvs` take a `Directory` and run directory (or file-based entry points), so
  checks run on exactly the exported names/files; until then, rely on deterministic
  regeneration. (Substituting the export `Directory` for `klayout.LvsDirectory` inside
  `run_lvs` gives a clean LVS, so a `directory` parameter is all `run_lvs` needs.)
- **Shared stdcell library upstream**: a cached `ihp130` stdcell `ExtLibrary` in ORDeC would
  replace `src/ams/stdcells.py`.
- **Comparator input range** at 1.2 V decides the reference range of the demo; acceptable to
  constrain `vrefp`/`vrefn` inside the rails.
- **Simulation runtime**: transistor-level stdcells in ngspice; keep testbench durations
  short, few corners by default.
- **ORDeC version**: `requirements.txt` lists `ordec` unpinned while development uses the
  sibling clone; pin a known-good version or commit once phase 3 stabilizes.
- Liberty abstract for analog macros (pin capacitances, no arcs) is deferred to phase 4, when
  chip-level STA needs it.

## Handoff to phase 4

- `ChipTop` is an ORDeC cell; LibreLane `DigitalMacro` products enter it via `ExtLibrary`
  (LEF/GDS + powered Verilog netlist or SPICE, power-pin mapping to be verified), analog
  macros either by source import (D1) or as products (round trip from 3.4).
- Collecting multiple macro products into `ChipTop` uses a project-specific
  `dependency_map` in `flow/__init__.py`.
- Export naming (D5) guarantees collision-free GDS merging.
