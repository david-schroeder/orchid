# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: David Schröder 2026

from pydesignflow import Block, task, Result

from . import config
from .pdk import Pdk
from .tools import slang

import json
import re
from pathlib import Path

from librelane.flows import Flow


class AsicTop(Block):
    """
    Top-level ASIC design
    """

    POWER_DEFINE = "USE_POWER_PINS"

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
        for defines in (r.defines, r.defines | {self.POWER_DEFINE: 1}):
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

        # Build configuration
        ll = {}

        # General
        ll["DESIGN_NAME"] = c.top
        ll["CLOCK_PORT"] = c.clock.port
        if c.clock.net is not None:
            ll["CLOCK_NET"] = c.clock.net
        ll["CLOCK_PERIOD"] = c.clock.period_ns
        ll["VDD_NETS"] = list(c.power.vdd)
        ll["GND_NETS"] = list(c.power.gnd)

        # Sources
        ll["VERILOG_FILES"] = list(design.design_srcs)
        ll["VERILOG_DEFINES"] = list(self.pdk.verilog_defines) + [f"{k}={v}" for k, v in design.defines.items()]
        ll["VERILOG_INCLUDE_DIRS"] = list(design.include_dirs)
        ll["VERILOG_POWER_DEFINE"] = self.POWER_DEFINE
        ll["USE_SLANG"] = True

        # Macros
        ll["MACROS"] = macros.macros
        ll["PDN_MACRO_CONNECTIONS"] = list(macros.pdn_connections)
        ll |= macros.librelane_config

        # PDN: design script + per-macro grids
        pdn_ext = Path(macros.pdn_script_ext).read_text()
        if c.pdn_script is not None:
            pdn_script: Path = (cwd / "pdn_cfg.tcl").resolve()
            pdn_script.write_text(c.pdn_script.read_text() + "\n" + pdn_ext)
            ll["PDN_CFG"] = str(pdn_script)
        elif pdn_ext:
            raise ValueError("Macros require PDN commands, but the design config sets no pdn_script.")

        # Floorplanning
        fp = c.floorplan
        ll["FP_SIZING"] = "absolute"
        ll["FP_CORE_UTIL"] = 10 # unused for sizing, but sets the default placement density
        ll["DIE_AREA"] = [0, 0, fp.die_width, fp.die_height]
        ll["CORE_AREA"] = [
            fp.core_margin,
            fp.core_margin,
            fp.die_width - fp.core_margin,
            fp.die_height - fp.core_margin
        ]

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
        ll["RUN_LINTER"] = False # we can lint elsewhere; prevent spurious file missing etc. errors

        # Design-specific raw overrides
        ll |= c.librelane

        # Return
        config_file: Path = cwd / "librelane_config.json"
        config_file.write_text(json.dumps(ll, indent=4))

        r.config = config_file
        return r

    @task(requires={'config': '.gen_librelane_config'})
    def librelane(self, cwd, config):
        """Run ASIC synthesis using LibreLane's Classic flow"""
        r = Result()
        r.design_dir = cwd

        Chip = Flow.factory.get("Chip")

        ChipNoOverlap = Chip.Substitute({
            "Checker.IllegalOverlap": None
        })

        config_path: Path = config.config
        flow = ChipNoOverlap(
            json.loads(config_path.read_text()),
            design_dir=str(r.design_dir),
            **self.pdk.librelane_flow_args()
        )
        flow.start()

        return r

    @task(requires={
        'config': '.gen_librelane_config',
        #'impl': '.librelane'
    })
    def librelane_klayout(self, cwd, config):
        """View `librelane` results in KLayout"""
        OpenInKLayout = Flow.factory.get("OpenInKLayout")

        config_path: Path = config.config
        flow = OpenInKLayout(
            json.loads(config_path.read_text()),
            design_dir=str(cwd.parent / "librelane"),
            **self.pdk.librelane_flow_args()
        )

        flow.start(last_run=True)
