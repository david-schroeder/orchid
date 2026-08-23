# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: David Schröder 2026

from pydesignflow import Block, task, Result

from .tools import gen_librelane_macros
from .tools.macro_utils import MacroInstance, Orientation
from .pdk.sg13g2_sram_macros import SRAM1_1K_32, SRAM1_64_64

import os
import pickle
from pathlib import Path


class AsicMacros(Block):
    """
    Tasks for ASIC macro instances.
    """

    # Design-specific static methods (ideally this would be a design file
    # but having full python capabilities is nice)

    @task(hidden=True)
    def get_design_macros(self, cwd):
        """Generate information about macros used in the design"""
        r = Result()

        insts = [
            SRAM1_1K_32.Instance("core_i.sram0_i", 390, 390),
            SRAM1_64_64.Instance("core_i.sram1_i", 860, 390, Orientation.EAST)
        ]

        inst_file: Path = cwd / "insts.bin"
        inst_file.write_bytes(pickle.dumps(insts))

        r.inst_file = inst_file
        return r

    @staticmethod
    def _get_pdn_conns(macro_list) -> list[str]:
        return sum(map(MacroInstance.get_pdn_connections, macro_list), [])

    @staticmethod
    def _get_pdn_cfg_script_ext(macro_list) -> list[str]:
        return "\n\n".join(map(MacroInstance.get_pdn_cfg_script_ext, macro_list))

    def setup(self):
        self.src_dir: Path = self.flow.base_dir / "src"
        # TODO: consider passing this as a parameter?
        self.pdk_dir = Path(os.environ["PDK_ROOT"]).resolve()

    @task(requires={
        'design_macros': '.get_design_macros'
    }, hidden=True)
    def gen_pdn_cfg(self, cwd, design_macros):
        """Generate PDN config script"""
        r = Result()

        macro_insts = pickle.loads(design_macros.inst_file.read_bytes())

        base_script_path = self.src_dir / "asic/scripts/pdn_cfg_base.tcl"
        script = base_script_path.read_text() + "\n"

        script += self._get_pdn_cfg_script_ext(macro_insts)

        design_script_file: Path = cwd / "pdn_cfg.tcl"
        design_script_file.write_text(script)

        r.script = design_script_file
        return r

    @task(requires={
        'design_macros': '.get_design_macros',
        'pdn_cfg': '.gen_pdn_cfg'
    })
    def gen_macro_cfg(self, cwd, design_macros, pdn_cfg):
        """Generate LibreLane macro configuration from PDK"""
        r = Result()

        # Generate SRAM macros
        available = gen_librelane_macros.discover_macros(self.pdk_dir)
        if not available:
            raise FileNotFoundError("Could not find PDK SRAM macros!")

        macro_insts = pickle.loads(design_macros.inst_file.read_bytes())

        for inst in macro_insts:
            available[inst.macro.name].setdefault("instances", {})
            available[inst.macro.name]["instances"][inst.inst_name] = {
                "location": [inst.x, inst.y],
                "orientation": str(inst.orientation)
            }

        # Generate configuration options for macros
        macro_config_opts = {}
        macro_config_opts["MAGIC_GDS_FLATGLOB"] = [
            "lvsres_*",
            "VIA_M1_*",
            "VIA_M2_*",
            "*_CELL_CORNER",
            "RSC_*",
            "*_CELL_SUB"
        ]
        macro_config_opts["PDN_MACRO_CONNECTIONS"] = self._get_pdn_conns(
            macro_insts
        )

        r.macro_config = macro_config_opts
        r.pdn_cfg_script = pdn_cfg.script
        r.macros = available
        return r
