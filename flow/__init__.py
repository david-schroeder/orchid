# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2024 RVLab Contributors

from pydesignflow import Flow

from .fpga_top import FpgaTop
from .asic_top import AsicTop
from .system_tb import SystemTb
from .simlibs_questa import SimlibsQuesta
from .module_tb import ModuleTb
from .sources import Sources

flow = Flow()

# Hardware
# --------

flow['srcs'] = Sources()

flow['fpga_top'] = FpgaTop(dependency_map={'srcs':'srcs'})
flow['asic_top'] = AsicTop(dependency_map={'srcs':'srcs'})

flow['simlibs_questa'] = SimlibsQuesta()

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
