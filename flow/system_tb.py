# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2024 RVLab Contributors
# Modified by David Schröder 2026

from pydesignflow import Block, task
from .tools import questasim, xsim
import shutil

class SystemTb(Block):
    """System testbench"""
    name = "system_tb"

    def setup(self):
        self.src_dir = self.flow.base_dir / "src"
        self.wave_dir = self.src_dir / "common/wave"
        self.design_dir = self.src_dir / "fpga"

    def simulate(self, simulator, cwd, srcs, libs=[], netlist=None, sdf={}, batch=False):
        """Generic function that is called by all sim_... tasks."""

        plusargs = {}
        top_modules = [self.name, 'glbl']

        verilog_srcs = srcs.design_srcs + srcs.tb_srcs
        if netlist:
            verilog_srcs.append(netlist)

        kwargs = {}

        if simulator == 'questasim':
            sim = questasim.simulate
            wave_do = [
                self.wave_dir / f"{self.name}.do",
            ]
        elif simulator == 'xsim':
            sim = xsim.simulate
            wave_do = self.wave_dir / f"{self.name}.xsim.wcfg"
        else:
            raise ValueError(f"Unknown simulator '{simulator}'")
        
        # Copy XADC temperature input file
        shutil.copyfile(
            self.design_dir / "ip/design.txt",
            cwd / 'design.txt'
        )

        sim(
            verilog_srcs,
            top_modules,
            cwd=cwd,
            include_dirs=srcs.include_dirs,
            defines=srcs.defines,
            plusargs=plusargs,
            libs=libs,
            batch_mode=batch,
            sdf=sdf,
            wave_do=wave_do,
            **kwargs
            )

    # QuestaSim tasks
    # ---------------

    @task(requires={
        'srcs':'srcs.srcs_fpga',
        'unisims':'simlibs_questa.unisims',
        })
    def sim_rtl_questa(self, cwd, srcs, unisims):
        """RTL simulation with QuestaSim"""
        self.simulate('questasim', cwd, srcs, libs=[unisims.lib])

    @task(requires={
        'srcs':'srcs.srcs_fpga',
        'unisims':'simlibs_questa.unisims',
        }, hidden=True)
    def sim_rtl_questa_batch(self, cwd, srcs, unisims):
        """RTL simulation with QuestaSim (batch mode)"""
        self.simulate('questasim', cwd, srcs, libs=[unisims.lib], batch=True)

    @task(requires={
        'srcs':'srcs.srcs_fpga',
        'unisims':'simlibs_questa.unisims',
        'secureip':'simlibs_questa.secureip',
        'syn':'fpga_top.syn',
        })
    def sim_synfunc_questa(self, cwd, srcs, unisims, secureip, syn):
        """Post-synthesis functional simulation with QuestaSim"""
        self.simulate(
            'questasim', cwd, srcs,
            libs=[unisims.lib, secureip.lib],
            netlist=syn.verilog_funcsim)

    @task(requires={
        'srcs':'srcs.srcs_fpga',
        'simprims':'simlibs_questa.simprims',
        'secureip':'simlibs_questa.secureip',
        'pnr':'fpga_top.pnr',
        })
    def sim_pnrtime_questa(self, cwd, srcs, simprims, secureip, pnr):
        """Post-PNR timing simulation with QuestaSim"""
        self.simulate('questasim', cwd, srcs,
            libs=[simprims.lib, secureip.lib],
            netlist=pnr.verilog_timesim,
            sdf={'system_tb/board_i/DUT':pnr.sdf})

    # Vivado XSim tasks
    # -----------------

    @task(requires={
        'srcs':'srcs.srcs_fpga',
        })
    def sim_rtl_xsim(self, cwd, srcs):
        """RTL simulation with XSim"""
        self.simulate('xsim', cwd, srcs, libs=['unisims_ver', 'secureip']) # Xilinx XSim has this as builtin library. 

    @task(requires={
        'srcs':'srcs.srcs_fpga',
        'syn':'fpga_top.syn',
        })
    def sim_synfunc_xsim(self, cwd, srcs, syn):
        """Post-synthesis functional simulation with XSim"""
        self.simulate('xsim', cwd, srcs,
            libs=['unisims_ver', 'secureip'], # Xilinx XSim has this as builtin library.
            netlist=syn.verilog_funcsim)

    @task(requires={
        'srcs':'srcs.srcs_fpga',
        'pnr':'fpga_top.pnr',
        })
    def sim_pnrtime_xsim(self, cwd, srcs, pnr):
        """Post-PNR timing simulation with XSim"""
        # WARNING: This simulation currently fails!! Compare with sim_pnrtime_questa
        self.simulate('xsim', cwd, srcs,
            libs=['simprims_ver', 'secureip'], # Xilinx XSim has this as builtin library.
            netlist=pnr.verilog_timesim,
            sdf={'system_tb/board_i/DUT':pnr.sdf})
