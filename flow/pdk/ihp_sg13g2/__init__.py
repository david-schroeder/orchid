# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: David Schröder 2026

"""IHP SG13G2 PDK plugin."""

import re
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

    def sim_models(self, cwd: Path) -> list[Path]:
        v = self.root() / "libs.ref/sg13g2_stdcell/verilog"
        # Sequential cells read their inputs through the delayed nets of $setuphold/$recrem.
        # Icarus leaves them undriven, so drive them from the undelayed inputs there; other
        # simulators drive them from the timing checks (a second driver would cause X).
        stdcell = cwd / "sg13g2_stdcell_sim.v"
        stdcell.write_text(re.sub(
            r"^(\s*)wire\s+(delayed_\w+(?:\s*,\s*delayed_\w+)*)\s*;",
            lambda m: m[0] + "\n`ifdef __ICARUS__\n" + m[1] + "assign " + ", ".join(
                f"{n} = {n.removeprefix('delayed_')}" for n in re.split(r"\s*,\s*", m[2])
            ) + ";\n`endif",
            (v / "sg13g2_stdcell.v").read_text(),
            flags=re.MULTILINE,
        ))
        return [v / "sg13g2_udp.v", stdcell]

    def librelane_macro_config(self) -> dict:
        return {
            # Macro power grid: TopMetal1 stripes only (become the macro's power pins);
            # signals up to Metal5. TopMetal2 stays free for the toplevel power grid.
            "RT_MAX_LAYER": "Metal5",
        }

    def librelane_padring_config(self) -> dict:
        return {
            "PAD_BONDPAD_NAME": self.BONDPAD,
            "EXTRA_GDS": [str(_DATA_DIR / f"{self.BONDPAD}.gds")],
            "EXTRA_LEFS": [str(_DATA_DIR / f"{self.BONDPAD}.lef")],
            "IGNORE_DISCONNECTED_MODULES": [self.BONDPAD],
        }
