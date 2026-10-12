# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: David Schröder 2026

"""IHP SG13G2 SRAM macros (libs.ref/sg13g2_sram)."""

from pathlib import Path

from ...config import MacroPlacement, Orientation
from ...macro import HardMacro

SRAM_CELLS = [
    "RM_IHPSG13_1P_64x64_c2_bm_bist",
    "RM_IHPSG13_1P_256x8_c3_bm_bist",
    "RM_IHPSG13_1P_256x16_c2_bm_bist",
    "RM_IHPSG13_1P_256x32_c2_bm_bist",
    "RM_IHPSG13_1P_256x48_c2_bm_bist",
    "RM_IHPSG13_1P_256x64_c2_bm_bist",
    "RM_IHPSG13_1P_512x8_c3_bm_bist",
    "RM_IHPSG13_1P_512x16_c2_bm_bist",
    "RM_IHPSG13_1P_512x32_c2_bm_bist",
    "RM_IHPSG13_1P_512x64_c2_bm_bist",
    "RM_IHPSG13_1P_1024x8_c2_bm_bist",
    "RM_IHPSG13_1P_1024x16_c2_bm_bist",
    "RM_IHPSG13_1P_1024x32_c2_bm_bist",
    "RM_IHPSG13_1P_1024x64_c2_bm_bist",
    "RM_IHPSG13_1P_2048x64_c2_bm_bist",
    "RM_IHPSG13_1P_4096x8_c3_bm_bist",
    "RM_IHPSG13_1P_4096x16_c3_bm_bist",
    "RM_IHPSG13_1P_8192x32_c4",
]

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

_VERTICAL = (Orientation.NORTH, Orientation.SOUTH, Orientation.FLIPPED_NORTH, Orientation.FLIPPED_SOUTH)


class Sg13g2Sram(HardMacro):
    """One IHP SG13G2 SRAM macro cell."""

    def __init__(self, name: str, lib_dir: Path):
        self.name = name
        self.lib_dir = lib_dir

    def views(self) -> dict:
        lef = self.lib_dir / "lef" / f"{self.name}.lef"
        gds = self.lib_dir / "gds" / f"{self.name}.gds"
        missing = [str(p) for p in (lef, gds) if not p.is_file()]
        if missing:
            raise FileNotFoundError(f"{self.name}: missing view(s) {', '.join(missing)}")

        lib = {}
        for lf in sorted((self.lib_dir / "lib").glob(f"{self.name}*.lib")):
            corner = lf.stem[len(self.name):].strip("_")
            # SRAM libs are characterized at -55C, the stdcell corner is named -40C.
            # IHP maps them the same way, see
            # https://github.com/IHP-GmbH/ihp-sg13g2-librelane-template/blob/main/librelane/config.yaml#L176
            if corner == "fast_1p32V_m55C":
                corner = "fast_1p32V_m40C"
            lib.setdefault(f"*{corner}*" if corner else "*", []).append(str(lf))
        if not lib:
            print(f"NOTE: no .lib files found for {self.name}; STA will treat it as a black box.")

        return {
            "gds": [str(gds)],
            "lef": [str(lef)],
            "vh": [str(self.lib_dir / "verilog" / f"{self.name}.v")],
            "lib": lib,
            "spice": [],
            "sdf": {},
        }

    def pdn_connections(self, placement: MacroPlacement) -> list[str]:
        return [
            f"{placement.inst} VDD VSS VDDARRAY! VSS!",
            f"{placement.inst} VDD VSS VDD! VSS!",
        ]

    def pdn_script(self, placement: MacroPlacement, grid_name: str) -> str:
        parts = [
            _PDN_COMMENT_TEMPLATE % (self.name, placement.inst),
            _PDN_GRIDDEF_TEMPLATE % (placement.inst, grid_name),
        ]
        if placement.orientation in _VERTICAL:
            # Metal5 stripe + connections Metal4-Metal5 and Metal5-TopMetal1
            parts += [
                _PDN_MET5_STRIPE_TEMPLATE % grid_name,
                _PDN_CONNECT_TEMPLATE % (grid_name, "Metal4 Metal5"),
                _PDN_CONNECT_TEMPLATE % (grid_name, "Metal5 TopMetal1"),
            ]
        else:
            # Rotated: no Metal5 stripe, connect Metal4 directly to TopMetal1
            parts.append(_PDN_CONNECT_TEMPLATE % (grid_name, "Metal4 TopMetal1"))
        return "\n\n".join(parts)

    def sim_models(self) -> list[Path]:
        # Cell wrapper + behavioral cores (with and without BIST) it may instantiate
        v = self.lib_dir / "verilog"
        return [
            v / f"{self.name}.v",
            v / "RM_IHPSG13_1P_core_behavioral.v",
            v / "RM_IHPSG13_1P_core_behavioral_bm_bist.v",
        ]

    def librelane_config(self) -> dict:
        return {
            "MAGIC_GDS_FLATGLOB": [
                "lvsres_*",
                "VIA_M1_*",
                "VIA_M2_*",
                "*_CELL_CORNER",
                "RSC_*",
                "*_CELL_SUB",
            ]
        }
