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
- Exported pin names are the ORDeC `Directory` names (`d[0]` → `d_0`), identical in GDS
  labels, SPICE subckt ports and LEF pins (and thus in `MacroProduct.pins`).

### D6 — Physical rules for analog macros

- Layers above the PDK's macro limit stay free for the toplevel (same limit as
  `librelane_macro_config`, e.g. up to Metal5 on SG13G2); checked in `drc`.
- Pins on routing metals with LVS-readable labels (ORDeC's `run_lvs` requires this anyway).
- Parent layouts land on a pnr block's Metal4 port pads (unnamed shapes) via
  `stdcells.port(inst, *pin_path)`, which resolves a sub-cell's `LayoutPin` in parent
  coordinates; supplies are on the block's Metal1 rails (one row) or side-strap pads. Routes
  enter these pads on Metal4 itself: a via stack on a pad collides with the pnr's own vias
  below it (V3.b/M3.b).
- An `Ntap`'s NWell gets ≥ 1 µm margin around the tap: the `Ntap` draws nBuLay, and DRC
  generates nBuLay 1 µm inside wide NWells; without the margin the two form narrow slivers
  (NBL.a).
- Resistor substrate (SG13G2 LVS merges it into one substrate net): every resistor's `sub`
  goes to the substrate-tap net (`vss`), the cell owning resistors places a `Ptap` on it,
  and a cell whose substrate net is not a port needs a `sub` port (see ORDeC docs,
  `ihp130_substrate_lvs`).
- A macro layout has its lower left corner (bounding box over all layers) at the origin;
  `abstract` checks this, and the LEF uses `ORIGIN 0 0`. Top-level pins are
  `LayoutRect`/`LayoutPoly` shapes of the macro's top cell (e.g. a copy of a sub-cell's pad,
  `! .rect == port(drv, 'd', 0).rect`).
- LEF abstract: pins (direction from the symbol, supplies `POWER`/`GROUND`), obstructions as
  the bounding box of each used metal up to the macro limit (conservative: pins lie inside).
- Product files: GDS without paths (converted to polygons, since ORDeC's GDS reader drops
  path widths, see Open items); SPICE with `.subckt` definitions only (no title, `.lib` or
  `.option` cards), self-contained including library cells, so it imports into an
  `ExtLibrary` and can be included in a simulator deck.
- Signoff runs on the same generator output that is exported (deterministic regeneration).
  `export` additionally imports the product (LEF/GDS/SPICE) as `ExtLibrary` cell and runs
  LVS on exactly the exported files; DRC on the exported GDS is still open (see Open items).
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
| `export` | `MacroProduct(kind="analog")`: gds, lef, spice, model, pins, size; LVS of the imported product |
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
  `layout`, `drc`, `lvs`, `abstract` (LEF data as JSON), `lvs_product` (round trip of an
  exported product), `reports`. Actions working on the request's cell import it lazily.
- `flow/tools/lef.py`: `write_macro(lef, abstract)` next to `read_macro`;
  `flow/tools/klayout.py`: `view(layouts, lyp)`.
- `Pdk` hooks: `ordec_env()`, `ordec_module` (`ordec.lib.ihp130`), names in that module:
  `ordec_tech` (technology cell `SG13G2`: layers, and the metal stack order of its
  `default_routing_spec` for the layer limit and LEF obstructions), `ordec_drc`/`ordec_lvs`
  (entry points), `ordec_device_map` (SPICE import); `macro_max_layer` (also LibreLane's
  `RT_MAX_LAYER`); `klayout_lyp()` (layer properties for `view`). IHP specifics in
  `flow/pdk/ihp_sg13g2/`.

## Demo design

Supply 1.2 V (SG13G2 LV core devices). All macros unclocked.

**`Adc` (`macro_adc`)** — 2-bit continuous-time flash ADC.
Ports: `vin`, `vrefp`, `vrefn`, `d[1:0]`, `vdd`, `vss`.
- Reference range: `vrefn`/`vrefp` within 0.3…0.9 V (the comparators' input common-mode
  range at 1.2 V); the testbenches use exactly these values.
- `Ladder`: 4 equal Rhigh units (0.5 × 4 µm, ~12 kΩ) between `vrefn` and `vrefp`, taps at
  1/4, 1/2, 3/4.
- `Comparator` ×3 (`comparator.ord`): 5-transistor OTA (NMOS input pair, PMOS mirror load,
  NMOS tail) plus output inverter, `out = inp > inn`; `inp` = `vin`, `inn` = tap. Offset
  ≤ 10 mV over the reference range (`comparator_tb`).
- `Bias`: ~100 kΩ Rhigh meander into a diode-connected NMOS of the tail's size (~7.5 µA),
  gate `vbn` shared by the comparator tails (no bias pin).
- `ThermEnc`: thermometer `t[2:0]` → binary: `d1 = t1`, `d0 = t0 ^ t1 ^ t2` (two `xor2` + a
  buffer), stdcell schematic laid out by `ordec.layout.pnr` as a single row.
- Layout: comparators in a row between shared Metal1 `vss`/`vdd` rails (Ptap/Ntap per
  comparator), `Bias` left of them, `ThermEnc` right of them, `Ladder` (serpentine row of
  upright and flipped resistors) below. Comparator signal pins are Metal2 pads; `vin`,
  `vbn` and the thermometer lines run on Metal4, ladder taps on Metal2/Metal3. Macro pins:
  `vin` (Metal4, left edge), `vrefn`/`vrefp` (ladder terminals, bottom), `d[1:0]` (the
  encoder's Metal4 pads, reached from below), `vdd`/`vss` (rails).

**`Dac` (`macro_dac`)** — 3-bit R-2R DAC with unbuffered output.
Ports: `d[2:0]`, `vout`, `vdd`, `vss`.
- `DacDrivers`: 3 stdcell buffers (pnr block) driving the ladder rail to rail.
- `R2r`: unit R and 2R (= two series units, for matching); R large against the driver output
  resistance: `buf_1` drivers and a ~12 kΩ unit (Rhigh 0.5 × 4 µm) keep the settled output
  within ~0.11 LSB (2.6 %, worst at the MSB), inside the `dac_tb` tolerance of ¼ LSB.
  `vout = vdd · code / 8`.
- Layout: `R2r` as resistor columns (termination, one 2R stack per bit) with the series
  resistors in a row above, wired on Metal1, `Ptap` beside the termination; `DacDrivers`
  pnr block below; driver outputs fan out Metal4 → Metal3 → Metal2 to the ladder inputs.

**`MixSum` (`macro_mixsum`)** — parent.
Ports: `va`, `vb`, `vout`, `vrefp`, `vrefn`, `vdd`, `vss`.
- Two `Adc` instances, `Adder` (2b+2b→3b: half adder + full adder from `xor2`/`and2`/`or2`,
  pnr block, sub-cell in `src/ams/mixsum/`), one `Dac`.
- Output: `vout = vdd · (qa + qb) / 8`, `qa`/`qb` the ADC codes.
- Layout: `adc_a` mirrored (`FlippedSouth`) below `adc_b`, so that their ladders face each
  other across a gap where `vrefn`/`vrefp` are bridged (Metal1) and led to the left edge
  (Metal2). Right of the ADCs: Metal2 supply straps (the macro's `vdd`/`vss` pins) tying all
  children's rails, a routing channel, the adder and the DAC above it. Signals between the
  children run horizontally on Metal3 and vertically on Metal4, into the Metal4 pads of the
  ADC outputs, the adder and the DAC drivers.

**Testbenches** (`src/tb/`, all self-checking with `PassFail`):
- `adc_tb`: slow ramp on `vin` across the reference range; check the decoded code against the
  ideal thresholds (with a margin around transitions); report code vs. `vin`.
- `comparator_tb`: DC sweep of `inp` around `inn` at the ends and the middle of the
  reference range (with the ADC's `Bias`); check offset and output swing.
- `dac_tb`: step through all 8 codes with `Vpulse` sources (as in ORDeC's `adder_pnr.ord`
  testbench); check settled `vout` against `vdd · code / 8` within ¼ LSB (100 fF load).
- `mixsum_tb` (cell `MixsumTb`): two sines of different frequencies on `va`, `vb`; Python
  reference model `ideal(qa) + ideal(qb)` → expected `vout`; check at settled points away
  from code transitions; every sum 0…6 must be covered; plot inputs, output and reference.

## Implementation phases

Each sub-phase ends with the example flow importing and the new tasks running end to end.

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

- **Signoff on exported files**: LVS runs on the exported files through the `export` round
  trip. For DRC (and for `lvs` with export names), preferred is a small upstream ORDeC
  change letting `run_drc`/`run_lvs` take a `Directory` and run directory (or file-based
  entry points); until then, rely on deterministic regeneration. (Substituting the export
  `Directory` for `klayout.LvsDirectory` inside `run_lvs` gives a clean LVS, so a
  `directory` parameter is all `run_lvs` needs.)
- **ORDeC GDS reader drops path widths** (`layout/gds_in.py` ignores the PATH `WIDTH`
  record, so imported wires vanish): fix upstream; the flow writes product GDS without
  paths meanwhile. Check LibreLane products for paths before importing them in phase 4.
- **Shared stdcell library upstream**: a cached `ihp130` stdcell `ExtLibrary` in ORDeC would
  replace `src/ams/stdcells.py`.
- **Multi-row pnr blocks**: a two-row `ThermEnc` produced an NW.d violation (NWell to
  N+ Activ near the shared rail); the demo's blocks stay single-row via
  `stdcells.pnr(aspect=...)`. Investigate and fix upstream in `ordec.layout.pnr`.
- **Simulation runtime**: transistor-level stdcells in ngspice; keep testbench durations
  short, few corners by default.
- **ORDeC version**: `requirements.txt` lists `ordec` unpinned while development uses the
  sibling clone; pin a known-good version or commit once phase 3 stabilizes.
- Liberty abstract for analog macros (pin capacitances, no arcs) is deferred to phase 4, when
  chip-level STA needs it.

## Handoff to phase 4

- `ChipTop` is an ORDeC cell; LibreLane `DigitalMacro` products enter it via `ExtLibrary`
  (LEF/GDS + powered Verilog netlist or SPICE, power-pin mapping to be verified), analog
  macros either by source import (D1) or as products (the `export` round trip, D6).
- Collecting multiple macro products into `ChipTop` uses a project-specific
  `dependency_map` in `flow/__init__.py`.
- Export naming (D5) guarantees collision-free GDS merging.
