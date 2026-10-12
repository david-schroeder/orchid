# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: David Schröder 2026

from pydesignflow import Block, task, Result

from . import config
from .pdk import Pdk
from .tools import librelane

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
        hm = librelane.hard_macro_config(self.pdk, placements)

        pdn_script_ext: Path = cwd / "pdn_macros.tcl"
        pdn_script_ext.write_text(hm["pdn_script"])

        r.macros = hm["macros"]
        r.pdn_connections = hm["pdn_connections"]
        r.pdn_script_ext = pdn_script_ext
        r.librelane_config = hm["config"]
        return r
