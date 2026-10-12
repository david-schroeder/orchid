# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: David Schröder 2026

"""IHP SG13G2 PDK plugin."""

from pathlib import Path

from .. import Pdk
from ...macro import HardMacro
from .sram import SRAM_CELLS, Sg13g2Sram

_DATA_DIR = Path(__file__).parent


class IhpSg13g2(Pdk):
    """IHP SG13G2 (IHP-Open-PDK)."""

    name = "ihp-sg13g2"
    verilog_defines = ["FUNCTIONAL"]

    # Not shipped with the PDK; bundled here.
    BONDPAD = "bondpad_70x70_novias"

    def macro(self, cell: str) -> HardMacro:
        if cell in SRAM_CELLS:
            return Sg13g2Sram(cell, self.root() / "libs.ref/sg13g2_sram")
        raise KeyError(f"{self.name}: unknown macro cell '{cell}'")

    def librelane_padring_config(self) -> dict:
        return {
            "PAD_BONDPAD_NAME": self.BONDPAD,
            "EXTRA_GDS": [str(_DATA_DIR / f"{self.BONDPAD}.gds")],
            "EXTRA_LEFS": [str(_DATA_DIR / f"{self.BONDPAD}.lef")],
            "IGNORE_DISCONNECTED_MODULES": [self.BONDPAD],
        }
