# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: David Schröder 2026

from pydesignflow import Block, task, Result

from . import config
from .pdk import Pdk
from .tools import slang, librelane

import re
from pathlib import Path


class AsicTop(Block):
    """
    Top-level ASIC design
    """

    def __init__(self, pdk: Pdk, dependency_map={}):
        super().__init__(dependency_map)
        self.pdk = pdk

    @task(requires={
        'srcs': 'srcs.srcs_asic',
        'cfg': 'srcs.cfg_asic',
    }, hidden=True)
    def elaborate(self, cwd, srcs, cfg):
        """Check design sources with slang (with and without power pins)"""
        r = Result()
        top = config.from_data(config.AsicConfig, cfg.config).top

        r.design_srcs = list(map(str, srcs.design_srcs))
        r.defines = dict(srcs.defines)
        r.include_dirs = list(map(str, srcs.include_dirs))

        # Hard macros / pad cells are blackboxes resolved later by Yosys
        cmdargs = ["--ignore-unknown-modules"]
        for defines in (r.defines, r.defines | {librelane.POWER_DEFINE: 1}):
            slang.elaborate(r.design_srcs, top, defines, r.include_dirs, cmdargs)

        return r

    @task(requires={
        'design': '.elaborate',
        'cfg': 'srcs.cfg_asic',
        'macros': 'macro_block.gen_macro_cfg'
    }, hidden=True)
    def gen_librelane_config(self, cwd, design, cfg, macros):
        """Generate LibreLane config for ASIC synthesis"""
        r = Result()
        c = config.from_data(config.AsicConfig, cfg.config)

        ll = librelane.design_config(
            self.pdk, c.top, c.clock, c.power,
            design.design_srcs, design.defines, design.include_dirs, c.floorplan
        )
        ll["FP_CORE_UTIL"] = 10 # unused for sizing, but sets the default placement density

        # Macros + PDN: design script + per-macro grids
        ll = librelane.add_hard_macros(
            ll, macros.macros, macros.pdn_connections, Path(macros.pdn_script_ext).read_text(),
            macros.librelane_config, c.pdn_script, cwd
        )

        # I/O
        sides = {"PAD_NORTH": c.padring.north, "PAD_EAST": c.padring.east,
                 "PAD_SOUTH": c.padring.south, "PAD_WEST": c.padring.west}
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
        if c.io_pin_order is not None:
            ll["IO_PIN_ORDER_CFG"] = str(c.io_pin_order)

        # Workarounds
        ll["MAGIC_EXT_UNIQUE"] = "notopports"
        ll["ERROR_ON_MAGIC_DRC"] = False # still spurious errors; prevent flow from crashing

        # Design-specific raw overrides
        ll |= c.librelane

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
