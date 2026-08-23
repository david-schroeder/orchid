# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2024 RVLab Contributors

from pydesignflow import Flow

from .fpga_top import FpgaTop
from .asic_top import AsicTop
from .asic_macros import AsicMacros
from .system_tb import SystemTb
from .simlibs_questa import SimlibsQuesta
from .module_tb import ModuleTb
from .sources import Sources

flow = Flow()

# Hardware
# --------

# Common
flow['srcs'] = Sources()
flow['simlibs_questa'] = SimlibsQuesta()

# ASIC
flow['asic_macros'] = AsicMacros()
flow['asic_top'] = AsicTop(dependency_map={
    'srcs':'srcs',
    'macro_block':'asic_macros'
})

# FPGA
flow['fpga_top'] = FpgaTop(dependency_map={'srcs':'srcs'})

# Testbenches
# -----------

module_tbs = [
]

for name in module_tbs:
    flow[name] = ModuleTb(name, dependency_map={
        'srcs':'srcs',
        'simlibs_questa':'simlibs_questa',
    })

flow[f'system_tb'] = SystemTb(dependency_map={
    'srcs':'srcs',
    'simlibs_questa':'simlibs_questa',
    'fpga_top':'fpga_top',
})
