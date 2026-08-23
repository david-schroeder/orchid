# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: David Schröder 2026

from pydesignflow import Block, task, Result

from .tools import gen_librelane_macros
from .tools.macro_utils import Orientation, DesignMacro, MacroInstance

import os
import pickle
from pathlib import Path


PDN_SRAM_GRID_ID = 0
PDN_SRAM_COMMENT_TEMPLATE = """
#####
#
# %s instance %s
#
#####
"""
PDN_SRAM_GRIDDEF_TEMPLATE = """define_pdn_grid \\
    -macro \\
    -instances "%s" \\
    -name %s \\
    -starts_with POWER
"""
PDN_SRAM_MET5_STRIPE_TEMPLATE = """add_pdn_stripe \\
    -grid %s \\
    -layer Metal5 \\
    -width 2.81 \\
    -pitch 11.24 \\
    -offset 2.81 \\
    -spacing 2.81 \\
    -nets "VSS VDD" \\
    -starts_with POWER
"""
PDN_SRAM_CONNECT_TEMPLATE = """add_pdn_connect \\
    -grid %s \\
    -layers "%s" \\
"""


class SG13G2SRAM(DesignMacro):
    # name should be overridden by subclasses
    # consider moving to file in `tools` dir

    @staticmethod
    def get_pdn_connections(inst: MacroInstance) -> list[str]:
        return [
            f"{inst.inst_name} VDD VSS VDDARRAY! VSS!",
            f"{inst.inst_name} VDD VSS VDD! VSS!"
        ]

    @staticmethod
    def get_pdn_cfg_script_ext(inst):
        global PDN_SRAM_GRID_ID

        inst_suffix = inst.inst_name.split(".")[-1]

        pdn_grid_name = f"grid{PDN_SRAM_GRID_ID}_{inst_suffix}"
        PDN_SRAM_GRID_ID += 1

        comment_block = PDN_SRAM_COMMENT_TEMPLATE % (
            inst.macro.name, inst.inst_name
        )

        grid_def = PDN_SRAM_GRIDDEF_TEMPLATE % (
            inst.inst_name,
            pdn_grid_name
        )

        if inst.orientation in (Orientation.NORTH, Orientation.SOUTH):
            # Create Metal5 stripe + connections to Met4 + TopMet1

            met5_stripe = PDN_SRAM_MET5_STRIPE_TEMPLATE % (
                pdn_grid_name
            )

            met4_conn = PDN_SRAM_CONNECT_TEMPLATE % (
                pdn_grid_name,
                "Metal4 Metal5"
            )

            topmet1_conn = PDN_SRAM_CONNECT_TEMPLATE % (
                pdn_grid_name,
                "Metal5 TopMetal1"
            )

            return "\n\n".join([
                comment_block, grid_def, met5_stripe, met4_conn, topmet1_conn
            ])

        else:
            # East-west: no Metal5 stripe, connect met4 directly to topmet1

            met4_topmet1_conn = PDN_SRAM_CONNECT_TEMPLATE % (
                pdn_grid_name,
                "Metal4 TopMetal1"
            )

            return "\n\n".join([
                comment_block, grid_def, met4_topmet1_conn
            ])


class SRAM1_64_64(SG13G2SRAM): name = "RM_IHPSG13_1P_64x64_c2_bm_bist"
class SRAM1_256_8(SG13G2SRAM): name = "RM_IHPSG13_1P_256x8_c3_bm_bist"
class SRAM1_256_16(SG13G2SRAM): name = "RM_IHPSG13_1P_256x16_c2_bm_bist"
class SRAM1_256_32(SG13G2SRAM): name = "RM_IHPSG13_1P_256x32_c2_bm_bist"
class SRAM1_256_48(SG13G2SRAM): name = "RM_IHPSG13_1P_256x48_c2_bm_bist"
class SRAM1_256_64(SG13G2SRAM): name = "RM_IHPSG13_1P_256x64_c2_bm_bist"
class SRAM1_512_8(SG13G2SRAM): name = "RM_IHPSG13_1P_512x8_c3_bm_bist"
class SRAM1_512_16(SG13G2SRAM): name = "RM_IHPSG13_1P_512x16_c2_bm_bist"
class SRAM1_512_32(SG13G2SRAM): name = "RM_IHPSG13_1P_512x32_c2_bm_bist"
class SRAM1_512_64(SG13G2SRAM): name = "RM_IHPSG13_1P_512x64_c2_bm_bist"
class SRAM1_1K_8(SG13G2SRAM): name = "RM_IHPSG13_1P_1024x8_c2_bm_bist"
class SRAM1_1K_16(SG13G2SRAM): name = "RM_IHPSG13_1P_1024x16_c2_bm_bist"
class SRAM1_1K_32(SG13G2SRAM): name = "RM_IHPSG13_1P_1024x32_c2_bm_bist"
class SRAM1_1K_64(SG13G2SRAM): name = "RM_IHPSG13_1P_1024x64_c2_bm_bist"
class SRAM1_2K_64(SG13G2SRAM): name = "RM_IHPSG13_1P_2048x64_c2_bm_bist"
class SRAM1_4K_8(SG13G2SRAM): name = "RM_IHPSG13_1P_4096x8_c3_bm_bist"
class SRAM1_4K_16(SG13G2SRAM): name = "RM_IHPSG13_1P_4096x16_c3_bm_bist"
class SRAM1_8K_32(SG13G2SRAM): name = "RM_IHPSG13_1P_8192x32_c4"


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
            SRAM1_1K_32.Instance("core_i.sram_i", 450, 450)
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
