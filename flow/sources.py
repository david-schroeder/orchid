# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2024 RVLab Contributors
# Modified by David Schröder 2026

from pydesignflow import Block, task, Result
from .tools import vivado, slang, verible
from . import config

class Sources(Block):
    """Hardware sources"""

    def setup(self):
        self.src_dir = self.flow.base_dir / "src"
        self.fpga_dir = self.src_dir / "fpga"
        self.asic_dir = self.src_dir / "asic"

    @task(always_rebuild=True, hidden=True)
    def srcs_rtl(self, cwd):
        """Common RTL sources for all design runs"""
        r = Result()

        design_srcs_pkg = []
        for d in []:
            design_srcs_pkg += [x for x in self.src_dir.glob(f"rtl/{d}/pkg/*.sv")]
        design_srcs = []
        design_srcs += [x for x in self.src_dir.glob("rtl/*/*.sv")]
        design_srcs += [x for x in self.src_dir.glob("rtl/*/*.v")]

        r.design_srcs_pkg = design_srcs_pkg
        r.design_srcs = design_srcs
        r.defines = {}
        r.include_dirs = []

        return r

    @task(requires={
        'srcs_rtl': '.srcs_rtl'
    }, always_rebuild=True, hidden=True)
    def srcs_fpga(self, cwd, srcs_rtl):
        """RTL + verification sources for FPGA synthesis"""
        r = Result()

        design_srcs_pkg = list(srcs_rtl.design_srcs_pkg)
        design_srcs_pkg += [x for x in self.fpga_dir.glob("rtl/pkg/*.sv")]

        design_srcs = list(srcs_rtl.design_srcs)
        design_srcs += [x for x in self.fpga_dir.glob("rtl/*.sv")]
        design_srcs += [x for x in self.fpga_dir.glob("rtl/*.v")]

        r.design_srcs = design_srcs_pkg + design_srcs

        r.defines = srcs_rtl.defines | {"FPGA": 1}
        r.include_dirs = list(srcs_rtl.include_dirs)
        r.tb_srcs = [x for x in self.src_dir.glob("tb/*.sv")]
        r.tb_srcs += [vivado.vivado_dir() / "data/verilog/src/glbl.v"]
        r.xcis = []

        return r

    @task(requires={
            'srcs_rtl': '.srcs_rtl'
        }, always_rebuild=True, hidden=True)
    def srcs_asic(self, cwd, srcs_rtl):
        """RTL + verification sources for ASIC synthesis"""
        r = Result()

        design_srcs_pkg = list(srcs_rtl.design_srcs_pkg)
        design_srcs_pkg += [x for x in self.asic_dir.glob("rtl/pkg/*.sv")]

        design_srcs = list(srcs_rtl.design_srcs)
        design_srcs += [x for x in self.asic_dir.glob("rtl/*.sv")]
        design_srcs += [x for x in self.asic_dir.glob("rtl/*.v")]

        r.design_srcs = design_srcs_pkg + design_srcs
        r.defines = srcs_rtl.defines
        r.include_dirs = list(srcs_rtl.include_dirs)
        return r

    @task(always_rebuild=True, hidden=True)
    def cfg_asic(self, cwd):
        """ASIC implementation config (src/asic/config.py)"""
        r = Result()
        cfg = config.load(self.asic_dir / "config.py", config.AsicConfig)
        r.config = config.to_data(cfg)
        return r

    @task(requires={"srcs":".srcs_asic"})
    def lint(self, cwd, srcs):
        """Run static code quality assessment"""
        slang.lint(srcs.design_srcs, srcs.defines, srcs.include_dirs, ["--ignore-unknown-modules"])

        verible.lint(srcs.design_srcs, cwd)
