// SPDX-FileCopyrightText: David Schröder 2026
// SPDX-License-Identifier: SHL-2.1

module prim_clock_gating (
  input  logic clk_i,
  input  logic en_i,
  input  logic test_en_i,
  output logic clk_o
);
    
  BUFGCE #(
    .SIM_DEVICE("7SERIES")
  ) clkbuf_i (
    .O (clk_o),
    .CE(en_i | test_en_i),
    .I (clk_i)
  );

endmodule
