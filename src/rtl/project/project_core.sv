// SPDX-License-Identifier: SHL-2.1
// SPDX-FileCopyrightText: David Schröder 2026

// This is your project toplevel.

module project_core (
    input  logic clk_i,
    input  logic rst_ni,
    input  logic [7:0] switch_i,
    output logic [7:0] led_o
);

    logic [7:0] switch_q;

    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (~rst_ni) begin
            switch_q <= '0;
        end else begin
            switch_q <= switch_i;
        end
    end

    always_comb begin
        led_o = switch_q;
    end

endmodule
