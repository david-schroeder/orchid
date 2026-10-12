# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: David Schröder 2026

from pydesignflow import Block, task, Result

from . import config
from .pdk import Pdk

from pathlib import Path


class AsicMacros(Block):
    """
    Hard macro instances of an ASIC implementation.
    """

    def __init__(self, pdk: Pdk, dependency_map={}):
        super().__init__(dependency_map)
        self.pdk = pdk

    @task(requires={'cfg': 'srcs.cfg_asic'})
    def gen_macro_cfg(self, cwd, cfg):
        """Collect macro views and PDN configuration for placed macros"""
        r = Result()
        placements = config.from_data(config.AsicConfig, cfg.config).macros

        macros = {}
        pdn_connections = []
        pdn_scripts = []
        librelane_config = {}
        for i, p in enumerate(placements):
            macro = self.pdk.macro(p.cell)
            if p.cell not in macros:
                macros[p.cell] = macro.views() | {"instances": {}}
                for k, v in macro.librelane_config().items():
                    if isinstance(v, list):
                        old = librelane_config.get(k, [])
                        librelane_config[k] = old + [x for x in v if x not in old]
                    else:
                        librelane_config[k] = v
            macros[p.cell]["instances"][p.inst] = {
                "location": [p.x, p.y],
                "orientation": str(p.orientation),
            }
            pdn_connections += macro.pdn_connections(p)
            pdn_scripts.append(macro.pdn_script(p, f"grid{i}_{p.inst.split('.')[-1]}"))

        pdn_script_ext: Path = cwd / "pdn_macros.tcl"
        pdn_script_ext.write_text("\n\n".join(pdn_scripts))

        r.macros = macros
        r.pdn_connections = pdn_connections
        r.pdn_script_ext = pdn_script_ext
        r.librelane_config = librelane_config
        return r
