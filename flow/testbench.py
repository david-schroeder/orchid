# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: David Schröder 2026

from pydesignflow import Block, task

from . import config
from .tools import icarus, questasim, xsim

import glob
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SimView:
    """Design under test after one implementation step, as seen by a simulator.

    Returned as ``view`` by the ``view_rtl`` / ``view_gl`` / ``view_sdf`` tasks of design
    blocks (``config.to_data(..., keep_paths=True)``).
    """
    srcs: list[Path]
    """Design sources (RTL or netlist) plus simulation models (cells, sub-macros, primitives)."""
    tops: list[str] = field(default_factory=list)
    """Additional top modules required by the view (e.g. Xilinx ``glbl``)."""
    defines: dict = field(default_factory=dict)
    include_dirs: list[Path] = field(default_factory=list)
    libs: list[str] = field(default_factory=list)
    """Precompiled vendor libraries: ``unisims``, ``simprims``, ``secureip``."""
    sdf: dict[str, Path] = field(default_factory=dict)
    """SDF of the design per corner."""
    files: list[Path] = field(default_factory=list)
    """Support files copied into the simulation directory."""


# Vendor libraries built into Vivado XSim
XSIM_LIBS = {'unisims': 'unisims_ver', 'simprims': 'simprims_ver', 'secureip': 'secureip'}


class Testbench(Block):
    """Testbench, simulated against the views of a design block"""

    def __init__(self, srcs: list[str] = None, top: str = None, sdf_scope: str = "dut",
                 dependency_map={}):
        """
        Args:
            srcs: Testbench source glob patterns relative to src/tb (default: <block name>.sv).
            top: Testbench top module (default: block name).
            sdf_scope: Instance path of the design below the testbench top (SDF annotation).
            dependency_map: 'dut' (design block providing view_rtl/view_gl/view_sdf) and
                'simlibs_questa' (Xilinx libraries for QuestaSim).
        """
        super().__init__(dependency_map)
        self.srcs = srcs
        self.top = top
        self.sdf_scope = sdf_scope

    def setup(self):
        self.tb_dir = self.flow.base_dir / "src/tb"
        self.wave_dir = self.flow.base_dir / "src/common/wave"
        self.top = self.top or self.id
        self.srcs = self.srcs or [f"{self.id}.sv"]

    def tb_srcs(self) -> list[Path]:
        """Expand the source patterns in order (sorted per pattern, no duplicates)."""
        srcs = {}
        for pattern in self.srcs:
            matches = sorted(glob.glob(pattern, root_dir=self.tb_dir, recursive=True))
            if not matches:
                raise FileNotFoundError(f"{self.id}: '{pattern}' matches no file in {self.tb_dir}.")
            srcs |= dict.fromkeys((self.tb_dir / m).resolve() for m in matches)
        return list(srcs)

    def simulate(self, simulator, cwd, view, libs={}, batch=False):
        """Simulate the testbench against view (once per SDF corner if the view has any)."""
        v = config.from_data(SimView, view.view)
        srcs = [*v.srcs, *self.tb_srcs()]
        tops = [self.top, *v.tops]

        for corner, sdf in (v.sdf or {None: None}).items():
            # Corner names may be wildcards; keep directory names shell-safe
            run_dir = cwd / re.sub(r"[^\w.-]", "_", corner) if corner else cwd
            run_dir.mkdir(exist_ok=True)
            for f in v.files:
                shutil.copyfile(f, run_dir / f.name)
            sdf = {f"{self.top}/{self.sdf_scope}": sdf} if sdf else {}

            if simulator == 'icarus':
                icarus.simulate(srcs, tops, run_dir, v.defines, v.include_dirs)
            elif simulator == 'questasim':
                questasim.simulate(srcs, tops, cwd=run_dir,
                    include_dirs=v.include_dirs, defines=v.defines, sdf=sdf,
                    libs=[libs[l] for l in v.libs], batch_mode=batch,
                    wave_do=self.wave_dir / f"{self.id}.do")
            elif simulator == 'xsim':
                xsim.simulate(srcs, tops, cwd=run_dir,
                    include_dirs=v.include_dirs, defines=v.defines, sdf=sdf,
                    libs=[XSIM_LIBS[l] for l in v.libs], batch_mode=batch,
                    wave_do=self.wave_dir / f"{self.id}.xsim.wcfg")
            else:
                raise ValueError(f"Unknown simulator '{simulator}'")

    # Icarus Verilog tasks
    # --------------------

    @task(requires={'view': 'dut.view_rtl'})
    def sim_rtl_icarus(self, cwd, view):
        """RTL simulation with Icarus Verilog"""
        self.simulate('icarus', cwd, view)

    @task(requires={'view': 'dut.view_gl'})
    def sim_gl_icarus(self, cwd, view):
        """Gate-level simulation with Icarus Verilog"""
        self.simulate('icarus', cwd, view)

    # QuestaSim tasks
    # ---------------

    @task(requires={'view': 'dut.view_rtl',
        'unisims': 'simlibs_questa.unisims', 'secureip': 'simlibs_questa.secureip'})
    def sim_rtl_questa(self, cwd, view, unisims, secureip):
        """RTL simulation with QuestaSim"""
        self.simulate('questasim', cwd, view, {'unisims': unisims.lib, 'secureip': secureip.lib})

    @task(requires={'view': 'dut.view_rtl',
        'unisims': 'simlibs_questa.unisims', 'secureip': 'simlibs_questa.secureip'}, hidden=True)
    def sim_rtl_questa_batch(self, cwd, view, unisims, secureip):
        """RTL simulation with QuestaSim (batch mode)"""
        self.simulate('questasim', cwd, view, {'unisims': unisims.lib, 'secureip': secureip.lib},
            batch=True)

    @task(requires={'view': 'dut.view_gl',
        'unisims': 'simlibs_questa.unisims', 'secureip': 'simlibs_questa.secureip'})
    def sim_gl_questa(self, cwd, view, unisims, secureip):
        """Gate-level simulation with QuestaSim"""
        self.simulate('questasim', cwd, view, {'unisims': unisims.lib, 'secureip': secureip.lib})

    @task(requires={'view': 'dut.view_sdf',
        'simprims': 'simlibs_questa.simprims', 'secureip': 'simlibs_questa.secureip'})
    def sim_sdf_questa(self, cwd, view, simprims, secureip):
        """SDF-annotated gate-level simulation with QuestaSim"""
        self.simulate('questasim', cwd, view, {'simprims': simprims.lib, 'secureip': secureip.lib})

    # Vivado XSim tasks
    # -----------------

    @task(requires={'view': 'dut.view_rtl'})
    def sim_rtl_xsim(self, cwd, view):
        """RTL simulation with XSim"""
        self.simulate('xsim', cwd, view)

    @task(requires={'view': 'dut.view_gl'})
    def sim_gl_xsim(self, cwd, view):
        """Gate-level simulation with XSim"""
        self.simulate('xsim', cwd, view)

    @task(requires={'view': 'dut.view_sdf'})
    def sim_sdf_xsim(self, cwd, view):
        """SDF-annotated gate-level simulation with XSim"""
        # WARNING: fails for fpga_top, compare with sim_sdf_questa
        self.simulate('xsim', cwd, view)
