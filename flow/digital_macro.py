# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: David Schröder 2026

from pydesignflow import Block, task, Result

from . import config
from .config import Floorplan, Clock, PowerNets, MacroPlacement
from .macro import MacroProduct
from .testbench import SimView
from .pdk import Pdk
from .tools import slang, verible, librelane, lef

import re
import shutil
from pathlib import Path


class DigitalMacro(Block):
    """
    Digital macro: RTL hardened into a macro product (LEF/GDS/netlists/LIB/SDF/SPEF).

    One instance per macro.
    """

    def __init__(self, pdk: Pdk, *, top: str, srcs: list[str], floorplan: Floorplan, clock: Clock,
                 power: PowerNets = None, defines: dict = {}, include_dirs: list[str] = [],
                 io_pin_order: str = None, pdn_script: str = None,
                 macros: list[MacroPlacement] = [], librelane: dict = {}, dependency_map={}):
        """
        Args:
            top: Top module name; also the name of the hardened macro cell.
            srcs: RTL source glob patterns relative to src/, in compilation order (packages first).
            floorplan: Die size and core margin.
            clock: Primary clock.
            power: Core supply nets (default: VDD/VSS).
            defines: Verilog defines (name -> value).
            include_dirs: Include directories relative to src/.
            io_pin_order: Pin order file for the I/O placer, relative to src/.
            pdn_script: PDN script relative to src/; required if sub-macros need PDN commands
                (appended by the flow).
            macros: Hard macros placed inside this macro (e.g. PDK SRAMs).
            librelane: Raw LibreLane config overrides, applied last (backend escape hatch).
        """
        super().__init__(dependency_map)
        self.pdk = pdk
        self.top = top
        self.srcs = srcs
        self.floorplan = floorplan
        self.clock = clock
        self.power = power or PowerNets()
        self.defines = defines
        self.include_dirs = include_dirs
        self.io_pin_order = io_pin_order
        self.pdn_script = pdn_script
        self.macros = macros
        self.librelane = librelane

    def setup(self):
        self.src_dir = self.flow.base_dir / "src"
        self.include_dirs = [self.src_dir / d for d in self.include_dirs]
        if self.io_pin_order is not None:
            self.io_pin_order = self.src_dir / self.io_pin_order
        if self.pdn_script is not None:
            self.pdn_script = self.src_dir / self.pdn_script

    def rtl_srcs(self) -> list[Path]:
        """Expand the source patterns in order (sorted per pattern, no duplicates)."""
        return config.expand(self.srcs, self.src_dir)

    def pdk_defines(self) -> dict:
        """PDK defines (for cell models) as dict."""
        defines = {}
        for d in self.pdk.verilog_defines:
            k, _, v = d.partition("=")
            defines[k] = v or 1
        return defines

    def sim_view(self, srcs: list, sdf: dict = {}) -> Result:
        """Result holding a SimView of srcs plus the models of the hard macros inside."""
        models = []
        for cell in dict.fromkeys(p.cell for p in self.macros):
            models += self.pdk.macro(cell).sim_models()
        r = Result()
        r.view = config.to_data(SimView(
            srcs=[*models, *srcs],
            defines=self.pdk_defines() | self.defines,
            include_dirs=self.include_dirs,
            sdf=sdf,
        ), keep_paths=True)
        return r

    @task(hidden=True)
    def elaborate(self, cwd):
        """Check macro sources with slang (with and without power pins)"""
        r = Result()
        srcs = self.rtl_srcs()

        # Hard macros are blackboxes resolved later by Yosys
        cmdargs = ["--ignore-unknown-modules"] if self.macros else []
        for defines in (self.defines, self.defines | {librelane.POWER_DEFINE: 1}):
            slang.elaborate(srcs, self.top, defines, self.include_dirs, cmdargs)
        return r

    @task()
    def lint(self, cwd):
        """Run static code quality assessment"""
        srcs = self.rtl_srcs()
        cmdargs = ["--ignore-unknown-modules"] if self.macros else []
        slang.lint(srcs, self.defines, self.include_dirs, cmdargs)
        verible.lint(srcs, cwd)

    @task(hidden=True)
    def gen_macro_cfg(self, cwd):
        """Collect views and PDN configuration of hard macros inside this macro"""
        r = Result()
        hm = librelane.hard_macro_config(self.pdk, self.macros)

        pdn_script_ext: Path = cwd / "pdn_macros.tcl"
        pdn_script_ext.write_text(hm["pdn_script"])

        r.macros = hm["macros"]
        r.pdn_connections = hm["pdn_connections"]
        r.pdn_script_ext = pdn_script_ext
        r.librelane_config = hm["config"]
        return r

    @task(always_rebuild=True, hidden=True)
    def view_rtl(self, cwd):
        """Simulation view: macro RTL"""
        return self.sim_view(self.rtl_srcs())

    @task(requires={'elaborate': '.elaborate', 'macros': '.gen_macro_cfg'}, hidden=True)
    def gen_librelane_config(self, cwd, elaborate, macros):
        """Generate LibreLane config for hardening the macro"""
        r = Result()

        ll = librelane.design_config(
            self.pdk, self.top, self.clock, self.power,
            self.rtl_srcs(), self.defines, self.include_dirs, self.floorplan
        )
        ll |= librelane.macro_mode_config(self.pdk)
        ll = librelane.add_hard_macros(
            ll, macros.macros, macros.pdn_connections, Path(macros.pdn_script_ext).read_text(),
            macros.librelane_config, self.pdn_script, cwd
        )
        if self.io_pin_order is not None:
            ll["IO_PIN_ORDER_CFG"] = str(self.io_pin_order)
            ll["ERRORS_ON_UNMATCHED_IO"] = "both" # every macro pin placed deliberately, no stale entries

        # Design-specific raw overrides
        ll |= self.librelane

        r.config = librelane.write_config(ll, cwd)
        return r

    @task(requires={'config': '.gen_librelane_config'})
    def harden(self, cwd, config):
        """Harden the macro (LibreLane Classic flow)"""
        r = Result()
        views, run_dir = librelane.run(self.pdk, config.config, cwd)
        r.views = views
        r.run_dir = run_dir
        return r

    @task(requires={'harden': '.harden'})
    def export(self, cwd, harden):
        """Assemble the macro product (views + pin/size info) for toplevel integration"""
        r = Result()

        # Copy views out of the backend's run directory: <view>[/<corner>]/<file>
        def copy(path, subdir: Path) -> Path:
            dst = cwd / subdir / Path(path).name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, dst)
            return dst

        def single(fmt) -> list[Path]:
            return [copy(harden.views[fmt], Path(fmt))] if fmt in harden.views else []

        def corners(fmt) -> dict[str, list[Path]]:
            # Corner keys may be wildcards; keep directory names shell-safe
            return {
                k: [copy(v, Path(fmt) / re.sub(r"[^\w.-]", "_", k))]
                for k, v in harden.views.get(fmt, {}).items()
            }

        product = MacroProduct(
            name=self.top,
            kind="digital",
            pdk=self.pdk.name,
            width=0, height=0, pins=[],
            gds=single("gds"),
            lef=single("lef"),
            vh=single("vh"),
            nl=single("nl"),
            pnl=single("pnl"),
            model=self.rtl_srcs(),
            lib=corners("lib"),
            sdf=corners("sdf"),
            spef=corners("spef"),
            spice=single("spice"),
            metadata={"backend": "librelane", "block": self.id},
        )
        if not (product.gds and product.lef):
            raise RuntimeError(f"{self.id}: hardening produced no GDS/LEF.")
        product.width, product.height, product.pins = lef.read_macro(product.lef[0], self.top)

        r.product = config.to_data(product, keep_paths=True)
        return r

    @task(requires={'export': '.export'}, always_rebuild=True, hidden=True)
    def view_gl(self, cwd, export):
        """Simulation view: hardened netlist with standard cell models"""
        product = config.from_data(MacroProduct, export.product)
        return self.sim_view([*self.pdk.sim_models(cwd), *product.nl])

    @task(requires={'export': '.export'}, always_rebuild=True, hidden=True)
    def view_sdf(self, cwd, export):
        """Simulation view: hardened netlist with standard cell models and SDF per corner"""
        product = config.from_data(MacroProduct, export.product)
        sdf = {corner: files[0] for corner, files in product.sdf.items()}
        return self.sim_view([*self.pdk.sim_models(cwd), *product.nl], sdf)

    @task(requires={'config': '.gen_librelane_config', 'harden': '.harden'})
    def view(self, cwd, config, harden):
        """View the hardened macro in KLayout"""
        librelane.view(self.pdk, config.config, harden.run_dir.parent.parent)
