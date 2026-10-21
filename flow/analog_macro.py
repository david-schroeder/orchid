# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: David Schröder 2026

import shutil
from pathlib import Path

from pydesignflow import Block, task, Result

from . import config
from .config import PowerNets
from .macro import MacroProduct
from .pdk import Pdk
from .tools import klayout, lef, ordec


class AnalogMacro(Block):
    """
    Analog macro: one ORDeC cell checked and exported as macro product.

    One instance per macro. Sub-cells are instantiated by the ORDeC sources themselves.
    """

    def __init__(self, pdk: Pdk, *, cell: str, module: str = None, params: dict = {},
                 power: PowerNets = None, model: list[str] = None, drc: dict = {},
                 dependency_map={}):
        """
        Args:
            cell: Class name of the macro's top cell.
            module: Python/ORD module defining cell, relative to src/ (default: ams.<name>.<name>,
                <name> being the block id without the macro_ prefix).
            params: Cell parameters.
            power: Supply nets (default: vdd/vss).
            model: Behavioral model glob patterns relative to src/ (default: ams/<name>/*.sv,
                if any).
            drc: Raw options for the PDK's ORDeC DRC call (escape hatch).
        """
        super().__init__(dependency_map)
        self.pdk = pdk
        self.cell = cell
        self.module = module
        self.params = params
        self.power = power or PowerNets(vdd=["vdd"], gnd=["vss"])
        self.model = model
        self.drc_options = drc

    def setup(self):
        self.src_dir = self.flow.base_dir / "src"
        self.name = self.id.removeprefix("macro_")
        if self.module is None:
            self.module = f"ams.{self.name}.{self.name}"

    def ordec(self, action: str, cwd, **options) -> dict:
        """Run an ORDeC worker action on the macro cell in cwd; return the reply."""
        return ordec.run(self.pdk, {
            "action": action,
            "module": self.module,
            "cell": self.cell,
            "params": self.params,
            "path": [self.src_dir],
            "options": options,
        }, cwd)

    def model_srcs(self) -> list[Path]:
        """Behavioral model sources."""
        if self.model is None:
            return sorted(self.src_dir.glob(f"ams/{self.name}/*.sv"))
        return config.expand(self.model, self.src_dir)

    @task(hidden=True)
    def elaborate(self, cwd):
        """Build symbol and schematic (SVGs), check schematic and supply pins"""
        r = Result()
        reply = self.ordec("elaborate", cwd, supplies=self.power.vdd + self.power.gnd)
        r.symbol_svg = cwd / reply["files"]["symbol_svg"]
        r.schematic_svg = cwd / reply["files"]["schematic_svg"]
        r.pins = reply["pins"]
        return r

    @task(requires={'elaborate': '.elaborate'})
    def netlist(self, cwd, elaborate):
        """Write the hierarchical SPICE netlist of the macro"""
        r = Result()
        reply = self.ordec("netlist", cwd, name=self.name)
        r.spice = cwd / reply["files"]["spice"]
        return r

    @task(requires={'elaborate': '.elaborate'})
    def layout(self, cwd, elaborate):
        """Generate the macro layout (GDS)"""
        r = Result()
        reply = self.ordec("layout", cwd, name=self.name)
        r.gds = cwd / reply["files"]["gds"]
        r.cells = reply["cells"]
        r.bbox = reply["bbox"]
        return r

    @task(requires={'layout': '.layout'})
    def drc(self, cwd, layout):
        """Run DRC (PDK decks, plus layers reserved for the toplevel)"""
        r = Result()
        reply = self.ordec("drc", cwd, drc=self.drc_options)
        errors = [f"{n}x {cat}" for cat, n in reply["violations"].items()]
        if reply["reserved_layers"]:
            errors.append(f"layers above {self.pdk.macro_max_layer} used: "
                          f"{', '.join(reply['reserved_layers'])}")
        if errors:
            raise RuntimeError(f"{self.id}: DRC failed ({'; '.join(errors)}); "
                               f"reports in {cwd / reply['files']['dir']}")
        r.report = cwd / reply["files"]["report"]
        return r

    @task(requires={'layout': '.layout'})
    def lvs(self, cwd, layout):
        """Run LVS (layout vs. schematic)"""
        r = Result()
        reply = self.ordec("lvs", cwd)
        if not reply["clean"]:
            failed = [f"{c['layout']}/{c['schematic']}: {c['status']}"
                      for c in reply["circuits"] if c["status"] not in ("match", "warning")]
            raise RuntimeError(f"{self.id}: LVS {reply['outcome']} ({'; '.join(failed)}); "
                               f"report in {cwd / reply['files']['dir']}")
        r.report = cwd / reply["files"]["report"]
        return r

    @task(requires={'layout': '.layout'}, hidden=True)
    def abstract(self, cwd, layout):
        """Write the LEF abstract of the macro"""
        r = Result()
        reply = self.ordec("abstract", cwd, name=self.name, gds=str(layout.gds),
                           power=self.power.vdd, ground=self.power.gnd)
        r.lef = cwd / f"{self.name}.lef"
        lef.write_macro(r.lef, reply)
        return r

    @task(requires={'netlist': '.netlist', 'layout': '.layout', 'abstract': '.abstract',
                    'drc': '.drc', 'lvs': '.lvs'})
    def export(self, cwd, netlist, layout, abstract, drc, lvs):
        """Assemble the signed-off macro product (GDS/LEF/SPICE/model) and check it by LVS"""
        r = Result()

        def copy(path, subdir: str) -> list[Path]:
            dst = cwd / subdir / Path(path).name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, dst)
            return [dst]

        product = MacroProduct(
            name=self.name,
            kind="analog",
            pdk=self.pdk.name,
            width=0, height=0, pins=[],
            gds=copy(layout.gds, "gds"),
            lef=copy(abstract.lef, "lef"),
            spice=copy(netlist.spice, "spice"),
            model=self.model_srcs(),
            metadata={"backend": "ordec", "block": self.id, "module": self.module,
                      "cell": self.cell},
        )
        product.width, product.height, product.pins = lef.read_macro(product.lef[0], self.name)

        # Round trip: the product, imported as ExtLibrary cell, passes LVS on its own files.
        reply = ordec.run(self.pdk, {
            "action": "lvs_product",
            "options": {"name": self.name, "gds": str(product.gds[0]),
                        "lef": str(product.lef[0]), "spice": str(product.spice[0])},
        }, cwd)
        if not reply["clean"]:
            raise RuntimeError(f"{self.id}: LVS of the exported product {reply['outcome']}; "
                               f"report in {cwd / reply['files']['dir']}")

        r.product = config.to_data(product, keep_paths=True)
        return r

    @task(requires={'layout': '.layout'})
    def view(self, cwd, layout):
        """View the macro layout in KLayout"""
        klayout.view([layout.gds], self.pdk.klayout_lyp())

    @task()
    def ui(self, cwd):
        """Open the macro cell in the ORDeC web UI"""
        args = ", ".join(f"{k}={v!r}" for k, v in self.params.items())
        views = [f"{self.cell}({args}).{v}" for v in ("schematic", "layout")]
        ordec.ui(self.pdk, self.module, cwd, path=[self.src_dir], views=views)
