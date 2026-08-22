# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: David Schröder 2026

from pydesignflow import Block, task, Result

from .tools import sv2v, gen_librelane_macros

import os
import json
from pathlib import Path

from librelane.config import Config
from librelane.flows import Flow


class AsicTop(Block):
    """
    Top-level ASIC design
    """

    name = "asic_top"

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

    @task(hidden=True)
    def gen_macros(self, cwd):
        """Generate LibreLane macro configuration from PDK"""
        r = Result()

        # Generate SRAM macros
        available = gen_librelane_macros.discover_macros(self.pdk_dir)
        if not available:
            raise FileNotFoundError("Could not find PDK SRAM macros!")

        r.macros = available
        return r

    @task(requires={
        'design': '.gen_verilog',
        'macros': '.gen_macros'
    }, hidden=True)
    def gen_librelane_config(self, cwd, design, macros):
        """Generate LibreLane config for ASIC synthesis"""
        r = Result()

        cfg = {}
        cfg["DESIGN_NAME"] = self.name
        cfg["CLOCK_PORT"] = "clk_i"
        cfg["CLOCK_PERIOD"] = 10 # 100MHz
        cfg["VDD_NETS"] = ["VDD"]
        cfg["GND_NETS"] = ["VSS"]
        cfg["VERILOG_FILES"] = list(map(str, [self.src_dir / "asic/rtl/asic_top.sv", design.design]))
        cfg["VERILOG_DEFINES"] = ["FUNCTIONAL"]
        cfg["VERILOG_POWER_DEFINE"] = "USE_POWER_PINS"
        cfg["FP_CORE_UTIL"] = 10
        cfg["MACROS"] = macros.macros

        config_file: Path = cwd / "librelane_config.json"
        config_file.write_text(json.dumps(cfg, indent=4))

        r.config = config_file
        return r

    @task(requires={'config': '.gen_librelane_config'})
    def librelane_classic(self, cwd, config):
        """Run ASIC synthesis using LibreLane's Classic flow"""
        r = Result()
        r.design_dir = cwd

        Classic = Flow.factory.get("Classic")

        config_path: Path = config.config
        flow = Classic(
            json.loads(config_path.read_text()),
            design_dir=str(r.design_dir),
            pdk_root=str(self.pdk_dir.parent),
            pdk="ihp-sg13g2"
        )
        flow.start()

        return r

    @task(requires={
        'config': '.gen_librelane_config',
        'classic': '.librelane_classic'
    })
    def librelane_klayout(self, cwd, config, classic):
        """View `librelane_classic` results in KLayout"""
        OpenInKLayout = Flow.factory.get("OpenInKLayout")

        config_path: Path = config.config
        flow = OpenInKLayout(
            json.loads(config_path.read_text()),
            design_dir=str(classic.design_dir),
            pdk_root=str(self.pdk_dir.parent),
            pdk="ihp-sg13g2"
        )

        flow.start(last_run=True)
