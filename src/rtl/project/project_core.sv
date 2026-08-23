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

    logic [31:0] rdata;

    (* keep *) RM_IHPSG13_1P_1024x32_c2_bm_bist sram_i (
        .A_CLK (clk_i),
        .A_MEN ('1),
        .A_WEN ('0),
        .A_REN ('1),
        .A_ADDR('0),
        .A_DIN ('0),
        .A_DLY ('1),
        .A_DOUT(rdata),
        .A_BM  ('0),

        .A_BIST_CLK ('0),
        .A_BIST_EN  ('0),
        .A_BIST_MEN ('0),
        .A_BIST_WEN ('0),
        .A_BIST_REN ('0),
        .A_BIST_ADDR('0),
        .A_BIST_DIN ('0),
        .A_BIST_BM  ('0)
    );

    assign led_o = switch_q ^ rdata[7:0];

endmodule
