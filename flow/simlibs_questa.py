# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2024 RVLab Contributors

from pydesignflow import Block, task, Result
from .tools import questasim, vivado
from pathlib import Path
import os

class SimlibsQuesta(Block):
    """Xilinx simulation cell libraries for QuestaSim"""

    def unisims_srcs(self):
        # unisims and simprims share the same Verilog sources.
        # They differ only in XIL_TIMING being set or not set.
        unisims_dir = vivado.vivado_dir() / "data/verilog/src/unisims"
        return [str(fn) for fn in unisims_dir.glob("*.v")]

    @task(hidden=True)
    def unisims(self, cwd):
        """Library for functional simulation"""
        srcs = self.unisims_srcs()
        r = Result()
        r.lib = questasim.compile(srcs, cwd, 'unisims')
        return r

    @task(hidden=True)
    def simprims(self, cwd):
        """Library for timing-annotated netlist simulation"""
        srcs = self.unisims_srcs()
        r = Result()
        r.lib = questasim.compile(srcs, cwd, 'simprims', defines={'XIL_TIMING':1})
        return r

    @task(hidden=True)
    def secureip(self, cwd):
        """Encrypted simulation model library"""
        secureip_dir = vivado.vivado_dir() / "data/secureip"
        srcs = [str(fn) for fn in secureip_dir.glob("**/*.vp")]
        print(srcs)
        r = Result()
        r.lib = questasim.compile(srcs, cwd, 'secureip', defines={'XIL_TIMING':1})
        return r
