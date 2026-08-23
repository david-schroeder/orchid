# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: David Schröder 2026

from flow.tools.macro_utils import DesignMacro, Orientation, MacroInstance

_PDN_GRID_ID = 0
_PDN_COMMENT_TEMPLATE = """
#####
#
# %s instance %s
#
#####
"""
_PDN_GRIDDEF_TEMPLATE = """define_pdn_grid \\
    -macro \\
    -instances "%s" \\
    -name %s \\
    -starts_with POWER
"""
_PDN_MET5_STRIPE_TEMPLATE = """add_pdn_stripe \\
    -grid %s \\
    -layer Metal5 \\
    -width 2.81 \\
    -pitch 11.24 \\
    -offset 2.81 \\
    -spacing 2.81 \\
    -nets "VSS VDD" \\
    -starts_with POWER
"""
_PDN_CONNECT_TEMPLATE = """add_pdn_connect \\
    -grid %s \\
    -layers "%s" \\
"""

class _SG13G2SRAM(DesignMacro):
    # name should be overridden by subclasses

    @staticmethod
    def get_pdn_connections(inst: MacroInstance) -> list[str]:
        return [
            f"{inst.inst_name} VDD VSS VDDARRAY! VSS!",
            f"{inst.inst_name} VDD VSS VDD! VSS!"
        ]

    @staticmethod
    def get_pdn_cfg_script_ext(inst):
        global _PDN_GRID_ID

        inst_suffix = inst.inst_name.split(".")[-1]

        pdn_grid_name = f"grid{_PDN_GRID_ID}_{inst_suffix}"
        _PDN_GRID_ID += 1

        comment_block = _PDN_COMMENT_TEMPLATE % (
            inst.macro.name, inst.inst_name
        )

        grid_def = _PDN_GRIDDEF_TEMPLATE % (
            inst.inst_name,
            pdn_grid_name
        )

        if inst.orientation in (Orientation.NORTH, Orientation.SOUTH):
            # Create Metal5 stripe + connections to Met4 + TopMet1

            met5_stripe = _PDN_MET5_STRIPE_TEMPLATE % (
                pdn_grid_name
            )

            met4_conn = _PDN_CONNECT_TEMPLATE % (
                pdn_grid_name,
                "Metal4 Metal5"
            )

            topmet1_conn = _PDN_CONNECT_TEMPLATE % (
                pdn_grid_name,
                "Metal5 TopMetal1"
            )

            return "\n\n".join([
                comment_block, grid_def, met5_stripe, met4_conn, topmet1_conn
            ])

        else:
            # East-west: no Metal5 stripe, connect met4 directly to topmet1

            met4_topmet1_conn = _PDN_CONNECT_TEMPLATE % (
                pdn_grid_name,
                "Metal4 TopMetal1"
            )

            return "\n\n".join([
                comment_block, grid_def, met4_topmet1_conn
            ])


class SRAM1_64_64(_SG13G2SRAM): name = "RM_IHPSG13_1P_64x64_c2_bm_bist"
class SRAM1_256_8(_SG13G2SRAM): name = "RM_IHPSG13_1P_256x8_c3_bm_bist"
class SRAM1_256_16(_SG13G2SRAM): name = "RM_IHPSG13_1P_256x16_c2_bm_bist"
class SRAM1_256_32(_SG13G2SRAM): name = "RM_IHPSG13_1P_256x32_c2_bm_bist"
class SRAM1_256_48(_SG13G2SRAM): name = "RM_IHPSG13_1P_256x48_c2_bm_bist"
class SRAM1_256_64(_SG13G2SRAM): name = "RM_IHPSG13_1P_256x64_c2_bm_bist"
class SRAM1_512_8(_SG13G2SRAM): name = "RM_IHPSG13_1P_512x8_c3_bm_bist"
class SRAM1_512_16(_SG13G2SRAM): name = "RM_IHPSG13_1P_512x16_c2_bm_bist"
class SRAM1_512_32(_SG13G2SRAM): name = "RM_IHPSG13_1P_512x32_c2_bm_bist"
class SRAM1_512_64(_SG13G2SRAM): name = "RM_IHPSG13_1P_512x64_c2_bm_bist"
class SRAM1_1K_8(_SG13G2SRAM): name = "RM_IHPSG13_1P_1024x8_c2_bm_bist"
class SRAM1_1K_16(_SG13G2SRAM): name = "RM_IHPSG13_1P_1024x16_c2_bm_bist"
class SRAM1_1K_32(_SG13G2SRAM): name = "RM_IHPSG13_1P_1024x32_c2_bm_bist"
class SRAM1_1K_64(_SG13G2SRAM): name = "RM_IHPSG13_1P_1024x64_c2_bm_bist"
class SRAM1_2K_64(_SG13G2SRAM): name = "RM_IHPSG13_1P_2048x64_c2_bm_bist"
class SRAM1_4K_8(_SG13G2SRAM): name = "RM_IHPSG13_1P_4096x8_c3_bm_bist"
class SRAM1_4K_16(_SG13G2SRAM): name = "RM_IHPSG13_1P_4096x16_c3_bm_bist"
class SRAM1_8K_32(_SG13G2SRAM): name = "RM_IHPSG13_1P_8192x32_c4"
