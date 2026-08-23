# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: David Schröder 2026

from pydesignflow import Block, task, Result

from .tools import sv2v

import os
import json
from pathlib import Path

from librelane.flows import Flow


class AsicTop(Block):
    """
    Top-level ASIC design
    """

    name = "asic_top"
    DIE_WIDTH = 1300
    DIE_HEIGHT = 1600
    CORE_MARGIN = 365

    def setup(self):
        self.src_dir = self.flow.base_dir / "src"
        # TODO: consider passing this as a parameter?
        self.pdk_dir = Path(os.environ["PDK_ROOT"]).resolve()

    @task(requires={'srcs':'srcs.srcs_asic'}, hidden=True)
    def gen_verilog(self, cwd, srcs):
        """Convert design sources to single verilog file"""
        r = Result()

        sv2v.convert_sv2v(
            cwd,
            list(map(str, srcs.design_srcs)),
            str(cwd / "design.v"),
            srcs.defines
        )

        r.design = cwd / "design.v"
        return r

    @task(requires={
        'design': '.gen_verilog',
        'macros': 'macro_block.gen_macro_cfg'
    }, hidden=True)
    def gen_librelane_config(self, cwd, design, macros):
        """Generate LibreLane config for ASIC synthesis"""
        r = Result()

        # Build configuration
        cfg = {}

        # General
        cfg["DESIGN_NAME"] = self.name
        cfg["CLOCK_PORT"] = "clk_PAD"
        cfg["CLOCK_NET"] = "clk_pad/p2c"
        cfg["CLOCK_PERIOD"] = 10 # 100MHz
        cfg["VDD_NETS"] = ["VDD"]
        cfg["GND_NETS"] = ["VSS"]

        # Sources
        cfg["VERILOG_FILES"] = list(map(str, [self.src_dir / "asic/rtl/asic_top.sv", design.design]))
        cfg["VERILOG_DEFINES"] = ["FUNCTIONAL"]
        cfg["VERILOG_POWER_DEFINE"] = "USE_POWER_PINS"

        # Macros
        cfg["MACROS"] = macros.macros
        cfg["PDN_CFG"] = str(macros.pdn_cfg_script)
        cfg |= macros.macro_config

        # Floorplanning
        cfg["FP_SIZING"] = "absolute"
        cfg["FP_CORE_UTIL"] = 10
        cfg["DIE_AREA"] = [
            0,
            0,
            self.DIE_WIDTH,
            self.DIE_HEIGHT
        ]
        cfg["CORE_AREA"] = [
            self.CORE_MARGIN,
            self.CORE_MARGIN,
            self.DIE_WIDTH - self.CORE_MARGIN,
            self.DIE_HEIGHT - self.CORE_MARGIN
        ]

        # I/O
        pad_config_file: Path = self.src_dir / "asic/io/pads.json"
        pad_config = json.loads(pad_config_file.read_text())
        cfg |= pad_config
        cfg["IO_PIN_ORDER_CFG"] = str(self.src_dir / "asic/io/iopins.cfg")
        cfg["PDN_CORE_RING"] = True
        cfg["PDN_CORE_RING_VWIDTH"] = 15
        cfg["PDN_CORE_RING_HWIDTH"] = 15
        cfg["PDN_CORE_RING_VSPACING"] = 5
        cfg["PDN_CORE_RING_HSPACING"] = 5
        cfg["PDN_CORE_RING_CONNECT_TO_PADS"] = True
        cfg["PDN_ENABLE_PINS"] = False

        # Bondpads; not included in IHP130-SG13G2 PDK for whatever reason
        cfg["PAD_BONDPAD_NAME"] = "bondpad_70x70_novias"
        cfg["EXTRA_GDS"] = [str(self.src_dir / "asic/io/bondpad_70x70_novias.gds")]
        cfg["EXTRA_LEFS"] = [str(self.src_dir / "asic/io/bondpad_70x70_novias.lef")]
        cfg["IGNORE_DISCONNECTED_MODULES"] = ["bondpad_70x70_novias"]

        # Other
        cfg["MAGIC_EXT_UNIQUE"] = "notopports"
        cfg["RUN_LINTER"] = False # we can lint elsewhere; prevent spurious file missing etc. errors

        # Return
        config_file: Path = cwd / "librelane_config.json"
        config_file.write_text(json.dumps(cfg, indent=4))

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
            pdk_root=str(self.pdk_dir.parent),
            pdk="ihp-sg13g2"
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
            pdk_root=str(self.pdk_dir.parent),
            pdk="ihp-sg13g2"
        )

        flow.start(last_run=True)
