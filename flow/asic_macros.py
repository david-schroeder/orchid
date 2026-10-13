# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: David Schröder 2026

from pydesignflow import Block, task, Result

from .config import MacroPlacement
from .pdk import Pdk
from .tools import librelane

from pathlib import Path


class AsicMacros(Block):
    """
    Hard macro instances of an ASIC implementation.
    """

    def __init__(self, pdk: Pdk, placements: list[MacroPlacement], dependency_map={}):
        super().__init__(dependency_map)
        self.pdk = pdk
        self.placements = placements

    @task()
    def gen_macro_cfg(self, cwd):
        """Collect macro views and PDN configuration for placed macros"""
        r = Result()
        hm = librelane.hard_macro_config(self.pdk, self.placements)

        pdn_script_ext: Path = cwd / "pdn_macros.tcl"
        pdn_script_ext.write_text(hm["pdn_script"])

        r.macros = hm["macros"]
        r.pdn_connections = hm["pdn_connections"]
        r.pdn_script_ext = pdn_script_ext
        r.librelane_config = hm["config"]
        return r
