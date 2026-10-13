# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2024 RVLab Contributors

from pydesignflow import Flow

from .fpga_top import FpgaTop
from .asic_top import AsicTop
from .asic_macros import AsicMacros
from .digital_macro import DigitalMacro
from .analog_macro import AnalogMacro
from .simlibs_questa import SimlibsQuesta
from .testbench import Testbench
from .sources import Sources
from .config import Floorplan, Clock, Padring, MacroPlacement, Orientation
from .pdk.ihp_sg13g2 import IhpSg13g2

flow = Flow()

pdk = IhpSg13g2()

# Hardware
# --------

# Common
flow['srcs'] = Sources()
flow['simlibs_questa'] = SimlibsQuesta()

# ASIC (paths relative to src/)
flow['asic_macros'] = AsicMacros(pdk, [
    MacroPlacement('RM_IHPSG13_1P_1024x32_c2_bm_bist', 'core_i.sram0_i', 390, 390),
    MacroPlacement('RM_IHPSG13_1P_64x64_c2_bm_bist', 'core_i.sram1_i', 860, 390, Orientation.EAST),
])
flow['asic_top'] = AsicTop(pdk,
    top='asic_top',
    floorplan=Floorplan(die_width=1600, die_height=1600, core_margin=365),
    clock=Clock(port='clk_PAD', net='clk_pad/p2c', period_ns=10), # 100 MHz
    padring=Padring(
        north=['clk_pad', 'rst_n_pad'],
        south=['iovdd_pad', 'iovss_pad', 'vdd_pad', 'vss_pad'],
        west=[f'gen_in_pads[{i}].in_pad' for i in range(8)],
        east=[f'gen_out_pads[{i}].out_pad' for i in range(8)],
    ),
    io_pin_order='asic/io/iopins.cfg',
    pdn_script='asic/scripts/pdn_cfg_base.tcl',
    dependency_map={
        'srcs':'srcs',
        'macro_block':'asic_macros'
    })

# Digital macros (paths relative to src/; srcs are globs)
flow['macro_counter'] = DigitalMacro(pdk,
    top='counter',
    srcs=['rtl/counter/*.sv'],
    floorplan=Floorplan(die_width=100, die_height=100, core_margin=10),
    clock=Clock(port='clk_i', period_ns=10), # 100 MHz
    io_pin_order='asic/macros/counter/iopins.cfg',
)

# Analog macros (ORDeC cells; module ams.<name>.<name> in src/ams/<name>/)
flow['macro_dac'] = AnalogMacro(pdk, cell='Dac')

# FPGA
flow['fpga_top'] = FpgaTop(dependency_map={'srcs':'srcs'})

# Testbenches
# -----------
# Testbench(srcs=['<name>.sv'], ...): srcs are globs in src/tb/; dut is any block with view_* tasks

flow['counter_tb'] = Testbench(dependency_map={
    'dut': 'macro_counter',
    'simlibs_questa': 'simlibs_questa'
})
flow['system_tb'] = Testbench(['system_tb.sv', 'nexys_video_board.sv'], sdf_scope='board_i/DUT',
    dependency_map={
        'dut': 'fpga_top',
        'simlibs_questa': 'simlibs_questa'
    })
