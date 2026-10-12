// SPDX-License-Identifier: SHL-2.1
// SPDX-FileCopyrightText: David Schröder 2026

// Self-checking testbench of the counter macro (RTL and gate-level).

module counter_tb;

    localparam int unsigned Width = 8;

    logic             clk = 1'b0;
    logic             rst_n = 1'b0;
    logic [Width-1:0] count;
    logic [Width-1:0] expected = '0;

    counter dut (
        .clk_i  (clk),
        .rst_ni (rst_n),
        .count_o(count)
    );

    always #5 clk = ~clk;

    initial begin
        $dumpfile("counter_tb.vcd");
        $dumpvars(0, counter_tb);

        repeat (2) @(negedge clk);
        if (count !== expected) $fatal(1, "count = %0d after reset, expected 0", count);

        // Count through one full wrap-around
        rst_n = 1'b1;
        repeat (2 ** Width + 4) begin
            @(negedge clk);
            expected++;
            if (count !== expected) $fatal(1, "count = %0d, expected %0d", count, expected);
        end

        $display("PASS");
        $finish;
    end

endmodule
