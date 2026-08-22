// SPDX-License-Identifier: SHL-2.1
// SPDX-FileCopyrightText: David Schröder 2026

module asic_top (
    `ifdef USE_POWER_PINS
    inout wire VDD,
    inout wire VSS,
    `endif

    input  logic clk_i,
    input  logic rst_ni,
    input  logic [7:0] switch_i,
    output logic [7:0] led_o
);

    (* keep *) project_core core_i (
        .clk_i,
        .rst_ni,
        .switch_i,
        .led_o
    );

endmodule
