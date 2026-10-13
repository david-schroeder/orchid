# SPDX-License-Identifier: SHL-2.1
# SPDX-FileCopyrightText: David Schröder 2026

# Example digital macro: 8-bit binary counter.

from pathlib import Path

from flow.config import DigitalMacroConfig, Floorplan, Clock, PowerNets

here = Path(__file__).parent
rtl = here.parents[2] / "rtl/counter"

config = DigitalMacroConfig(
    top="counter",
    srcs=[rtl / "counter.sv"],
    floorplan=Floorplan(die_width=100, die_height=100, core_margin=10),
    clock=Clock(port="clk_i", period_ns=10), # 100 MHz
    power=PowerNets(vdd=["VDD"], gnd=["VSS"]),
    io_pin_order=here / "iopins.cfg",
)
