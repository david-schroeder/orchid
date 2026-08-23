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
    logic [31:0] rdata1, rdata1_q;
    logic [63:0] rdata2, rdata2_q;

    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (~rst_ni) begin
            switch_q <= '0;
            rdata1_q <= '0;
            rdata2_q <= '0;
        end else begin
            switch_q <= switch_i;
            rdata1_q <= rdata1;
            rdata2_q <= rdata2;
        end
    end

    (* keep *) RM_IHPSG13_1P_1024x32_c2_bm_bist sram0_i (
        .A_CLK (clk_i),
        .A_MEN ('1),
        .A_WEN ('0),
        .A_REN ('1),
        .A_ADDR('0),
        .A_DIN ('0),
        .A_DLY ('1),
        .A_DOUT(rdata1),
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

    (* keep *) RM_IHPSG13_1P_64x64_c2_bm_bist sram1_i (
        .A_CLK (clk_i),
        .A_MEN ('1),
        .A_WEN ('0),
        .A_REN ('1),
        .A_ADDR('0),
        .A_DIN ('0),
        .A_DLY ('1),
        .A_DOUT(rdata2),
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

    assign led_o = switch_q ^ rdata1_q[7:0] ^ rdata2_q[7:0];

endmodule
