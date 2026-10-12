// SPDX-License-Identifier: SHL-2.1
// SPDX-FileCopyrightText: David Schröder 2026

// Example digital macro: free-running binary counter.

module counter #(
    parameter int unsigned Width = 8
) (
    input  logic             clk_i,
    input  logic             rst_ni,
    output logic [Width-1:0] count_o
);

    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            count_o <= '0;
        end else begin
            count_o <= count_o + 1'b1;
        end
    end

endmodule
