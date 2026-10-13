# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: David Schröder 2026

from pydesignflow import Block, task, Result

from .config import Floorplan, Clock, PowerNets, Padring
from .pdk import Pdk
from .tools import slang, librelane

import re
from pathlib import Path


class AsicTop(Block):
    """
    Top-level ASIC design
    """

    def __init__(self, pdk: Pdk, *, top: str, floorplan: Floorplan, clock: Clock,
                 power: PowerNets = None, padring: Padring = None,
                 io_pin_order: str = None, pdn_script: str = None, librelane: dict = {},
                 dependency_map={}):
        """
        Args:
            top: Top-level module name.
            floorplan: Die size and core margin.
            clock: Primary clock.
            power: Core supply nets (default: VDD/VSS).
            padring: Pad cell instances per die side (default: no padring).
            io_pin_order: Pin order file for the I/O placer, relative to src/.
            pdn_script: PDN script relative to src/; macro-specific PDN commands are appended
                by the flow.
            librelane: Raw LibreLane config overrides, applied last (backend escape hatch).
        """
        super().__init__(dependency_map)
        self.pdk = pdk
        self.top = top
        self.floorplan = floorplan
        self.clock = clock
        self.power = power or PowerNets()
        self.padring = padring or Padring()
        self.io_pin_order = io_pin_order
        self.pdn_script = pdn_script
        self.librelane = librelane

    def setup(self):
        src_dir = self.flow.base_dir / "src"
        if self.io_pin_order is not None:
            self.io_pin_order = src_dir / self.io_pin_order
        if self.pdn_script is not None:
            self.pdn_script = src_dir / self.pdn_script

    @task(requires={'srcs': 'srcs.srcs_asic'}, hidden=True)
    def elaborate(self, cwd, srcs):
        """Check design sources with slang (with and without power pins)"""
        r = Result()

        r.design_srcs = list(map(str, srcs.design_srcs))
        r.defines = dict(srcs.defines)
        r.include_dirs = list(map(str, srcs.include_dirs))

        # Hard macros / pad cells are blackboxes resolved later by Yosys
        cmdargs = ["--ignore-unknown-modules"]
        for defines in (r.defines, r.defines | {librelane.POWER_DEFINE: 1}):
            slang.elaborate(r.design_srcs, self.top, defines, r.include_dirs, cmdargs)

        return r

    @task(requires={
        'design': '.elaborate',
        'macros': 'macro_block.gen_macro_cfg'
    }, hidden=True)
    def gen_librelane_config(self, cwd, design, macros):
        """Generate LibreLane config for ASIC synthesis"""
        r = Result()

        ll = librelane.design_config(
            self.pdk, self.top, self.clock, self.power,
            design.design_srcs, design.defines, design.include_dirs, self.floorplan
        )
        ll["FP_CORE_UTIL"] = 10 # unused for sizing, but sets the default placement density

        # Macros + PDN: design script + per-macro grids
        ll = librelane.add_hard_macros(
            ll, macros.macros, macros.pdn_connections, Path(macros.pdn_script_ext).read_text(),
            macros.librelane_config, self.pdn_script, cwd
        )

        # I/O
        sides = {"PAD_NORTH": self.padring.north, "PAD_EAST": self.padring.east,
                 "PAD_SOUTH": self.padring.south, "PAD_WEST": self.padring.west}
        if any(sides.values()):
            # Instance names pass through Tcl list parsing; escape brackets
            for key, insts in sides.items():
                ll[key] = [re.sub(r"([\[\]])", r"\\\1", x) for x in insts]
            ll |= self.pdk.librelane_padring_config()
            ll["PDN_CORE_RING"] = True
            ll["PDN_CORE_RING_VWIDTH"] = 15
            ll["PDN_CORE_RING_HWIDTH"] = 15
            ll["PDN_CORE_RING_VSPACING"] = 5
            ll["PDN_CORE_RING_HSPACING"] = 5
            ll["PDN_CORE_RING_CONNECT_TO_PADS"] = True
            ll["PDN_ENABLE_PINS"] = False
        if self.io_pin_order is not None:
            ll["IO_PIN_ORDER_CFG"] = str(self.io_pin_order)

        # Workarounds
        ll["MAGIC_EXT_UNIQUE"] = "notopports"
        ll["ERROR_ON_MAGIC_DRC"] = False # still spurious errors; prevent flow from crashing

        # Design-specific raw overrides
        ll |= self.librelane

        r.config = librelane.write_config(ll, cwd)
        return r

    @task(requires={'config': '.gen_librelane_config'})
    def librelane(self, cwd, config):
        """Run ASIC synthesis using LibreLane's Chip flow"""
        r = Result()
        r.design_dir = cwd
        librelane.run(self.pdk, config.config, cwd, flow="Chip", substitutions={
            "Checker.IllegalOverlap": None
        })
        return r

    @task(requires={
        'config': '.gen_librelane_config',
        #'impl': '.librelane'
    })
    def librelane_klayout(self, cwd, config):
        """View `librelane` results in KLayout"""
        librelane.view(self.pdk, config.config, cwd.parent / "librelane")
