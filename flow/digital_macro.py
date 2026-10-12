# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: David Schröder 2026

from pydesignflow import Block, task, Result

from . import config
from .macro import MacroProduct
from .pdk import Pdk
from .tools import slang, verible, icarus, librelane, lef

import re
import shutil
from pathlib import Path


class DigitalMacro(Block):
    """
    Digital macro: RTL hardened into a macro product (LEF/GDS/netlists/LIB/SDF/SPEF).

    One instance per macro; configured by src/macros/<name>/config.py.
    """

    def __init__(self, name: str, pdk: Pdk, dependency_map={}):
        super().__init__(dependency_map)
        self.name = name
        self.pdk = pdk

    def setup(self):
        self.config_file = self.flow.base_dir / "src/macros" / self.name / "config.py"

    def pdk_defines(self) -> dict:
        """PDK defines (for cell models) as dict."""
        defines = {}
        for d in self.pdk.verilog_defines:
            k, _, v = d.partition("=")
            defines[k] = v or 1
        return defines

    @task(always_rebuild=True, hidden=True)
    def cfg(self, cwd):
        """Macro config (src/macros/<name>/config.py)"""
        r = Result()
        r.config = config.to_data(config.load(self.config_file, config.DigitalMacroConfig))
        return r

    @task(requires={'cfg': '.cfg'}, hidden=True)
    def elaborate(self, cwd, cfg):
        """Check macro sources with slang (with and without power pins)"""
        r = Result()
        c = config.from_data(config.DigitalMacroConfig, cfg.config)

        # Hard macros are blackboxes resolved later by Yosys
        cmdargs = ["--ignore-unknown-modules"] if c.macros else []
        for defines in (c.defines, c.defines | {librelane.POWER_DEFINE: 1}):
            slang.elaborate(c.srcs, c.top, defines, c.include_dirs, cmdargs)
        return r

    @task(requires={'cfg': '.cfg'})
    def lint(self, cwd, cfg):
        """Run static code quality assessment"""
        c = config.from_data(config.DigitalMacroConfig, cfg.config)
        cmdargs = ["--ignore-unknown-modules"] if c.macros else []
        slang.lint(c.srcs, c.defines, c.include_dirs, cmdargs)
        verible.lint(c.srcs, cwd)

    @task(requires={'cfg': '.cfg'}, hidden=True)
    def gen_macro_cfg(self, cwd, cfg):
        """Collect views, PDN configuration and models of hard macros inside this macro"""
        r = Result()
        placements = config.from_data(config.DigitalMacroConfig, cfg.config).macros
        hm = librelane.hard_macro_config(self.pdk, placements)

        pdn_script_ext: Path = cwd / "pdn_macros.tcl"
        pdn_script_ext.write_text(hm["pdn_script"])

        r.macros = hm["macros"]
        r.pdn_connections = hm["pdn_connections"]
        r.pdn_script_ext = pdn_script_ext
        r.librelane_config = hm["config"]
        r.sim_models = []
        for cell in dict.fromkeys(p.cell for p in placements):
            r.sim_models += self.pdk.macro(cell).sim_models()
        return r

    def simulate(self, cwd, c: config.DigitalMacroConfig, design_srcs: list, sim_models: list):
        """Run the configured testbench against design_srcs."""
        if c.testbench is None:
            raise ValueError(f"{self.config_file}: no testbench configured.")
        icarus.simulate(
            [*sim_models, *design_srcs, *c.testbench.srcs],
            c.testbench.top, cwd,
            defines=self.pdk_defines() | c.defines,
            include_dirs=c.include_dirs,
        )

    @task(requires={'cfg': '.cfg', 'macros': '.gen_macro_cfg'})
    def sim_rtl(self, cwd, cfg, macros):
        """RTL simulation of the macro testbench (Icarus Verilog)"""
        c = config.from_data(config.DigitalMacroConfig, cfg.config)
        self.simulate(cwd, c, c.srcs, macros.sim_models)

    @task(requires={'cfg': '.cfg', 'elaborate': '.elaborate', 'macros': '.gen_macro_cfg'}, hidden=True)
    def gen_librelane_config(self, cwd, cfg, elaborate, macros):
        """Generate LibreLane config for hardening the macro"""
        r = Result()
        c = config.from_data(config.DigitalMacroConfig, cfg.config)

        ll = librelane.design_config(
            self.pdk, c.top, c.clock, c.power,
            c.srcs, c.defines, c.include_dirs, c.floorplan
        )
        ll |= librelane.macro_mode_config(self.pdk)
        ll = librelane.add_hard_macros(
            ll, macros.macros, macros.pdn_connections, Path(macros.pdn_script_ext).read_text(),
            macros.librelane_config, c.pdn_script, cwd
        )
        if c.io_pin_order is not None:
            ll["IO_PIN_ORDER_CFG"] = str(c.io_pin_order)
            ll["ERRORS_ON_UNMATCHED_IO"] = "both" # every macro pin placed deliberately, no stale entries

        # Design-specific raw overrides
        ll |= c.librelane

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

    @task(requires={'cfg': '.cfg', 'harden': '.harden'})
    def export(self, cwd, cfg, harden):
        """Assemble the macro product (views + pin/size info) for toplevel integration"""
        r = Result()
        c = config.from_data(config.DigitalMacroConfig, cfg.config)

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
            name=c.top,
            kind="digital",
            pdk=self.pdk.name,
            width=0, height=0, pins=[],
            gds=single("gds"),
            lef=single("lef"),
            vh=single("vh"),
            nl=single("nl"),
            pnl=single("pnl"),
            model=list(c.srcs),
            lib=corners("lib"),
            sdf=corners("sdf"),
            spef=corners("spef"),
            spice=single("spice"),
            metadata={"backend": "librelane", "block": self.id},
        )
        if not (product.gds and product.lef):
            raise RuntimeError(f"{self.id}: hardening produced no GDS/LEF.")
        product.width, product.height, product.pins = lef.read_macro(product.lef[0], c.top)

        r.product = config.to_data(product, keep_paths=True)
        return r

    @task(requires={'cfg': '.cfg', 'macros': '.gen_macro_cfg', 'export': '.export'})
    def sim_gl(self, cwd, cfg, macros, export):
        """Gate-level simulation of the macro testbench against the hardened netlist (Icarus Verilog)"""
        c = config.from_data(config.DigitalMacroConfig, cfg.config)
        product = config.from_data(MacroProduct, export.product)
        self.simulate(cwd, c, product.nl, [*self.pdk.sim_models(cwd), *macros.sim_models])

    @task(requires={'config': '.gen_librelane_config', 'harden': '.harden'})
    def view(self, cwd, config, harden):
        """View the hardened macro in KLayout"""
        librelane.view(self.pdk, config.config, harden.run_dir.parent.parent)
