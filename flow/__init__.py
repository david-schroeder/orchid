# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2024 RVLab Contributors

from pydesignflow import Flow

from .fpga_top import FpgaTop
from .asic_top import AsicTop
from .asic_macros import AsicMacros
from .digital_macro import DigitalMacro
from .simlibs_questa import SimlibsQuesta
from .testbench import Testbench
from .sources import Sources
from .pdk.ihp_sg13g2 import IhpSg13g2

flow = Flow()

pdk = IhpSg13g2()

# Hardware
# --------

# Common
flow['srcs'] = Sources()
flow['simlibs_questa'] = SimlibsQuesta()

# ASIC
flow['asic_macros'] = AsicMacros(pdk, dependency_map={'srcs':'srcs'})
flow['asic_top'] = AsicTop(pdk, dependency_map={
    'srcs':'srcs',
    'macro_block':'asic_macros'
})

# Digital macros (config: src/asic/macros/<name>/config.py)
digital_macros = [
    'counter',
]

for name in digital_macros:
    flow[f'macro_{name}'] = DigitalMacro(name, pdk)

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
