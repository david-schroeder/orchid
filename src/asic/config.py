# SPDX-License-Identifier: SHL-2.1
# SPDX-FileCopyrightText: David Schröder 2026

# ASIC implementation of the example design.

from pathlib import Path

from flow.config import (
    AsicConfig, Floorplan, Clock, PowerNets, Padring, MacroPlacement, Orientation
)

here = Path(__file__).parent

config = AsicConfig(
    top="asic_top",
    floorplan=Floorplan(die_width=1600, die_height=1600, core_margin=365),
    clock=Clock(port="clk_PAD", net="clk_pad/p2c", period_ns=10), # 100 MHz
    power=PowerNets(vdd=["VDD"], gnd=["VSS"]),
    padring=Padring(
        north=["clk_pad", "rst_n_pad"],
        south=["iovdd_pad", "iovss_pad", "vdd_pad", "vss_pad"],
        west=[f"gen_in_pads[{i}].in_pad" for i in range(8)],
        east=[f"gen_out_pads[{i}].out_pad" for i in range(8)],
    ),
    io_pin_order=here / "io/iopins.cfg",
    pdn_script=here / "scripts/pdn_cfg_base.tcl",
    macros=[
        MacroPlacement("RM_IHPSG13_1P_1024x32_c2_bm_bist", "core_i.sram0_i", 390, 390),
        MacroPlacement("RM_IHPSG13_1P_64x64_c2_bm_bist", "core_i.sram1_i", 860, 390, Orientation.EAST),
    ],
)
