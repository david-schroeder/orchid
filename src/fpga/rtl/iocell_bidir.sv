// SPDX-License-Identifier: SHL-2.1
// SPDX-FileCopyrightText: 2024 RVLab Contributors

module iocell_bidir #(
    parameter int Width = 1
) (
  inout  wire  [Width-1:0] pad,
  input  logic [Width-1:0] oe,
  input  logic [Width-1:0] out,
  output logic [Width-1:0] in
);
  generate
    genvar i;
    for (i = 0; i < Width; i++) begin : cellarray
      IOBUF #(
        .DRIVE       (4),
        .IBUF_LOW_PWR("TRUE"),
        .IOSTANDARD  ("DEFAULT"),
        .SLEW        ("SLOW")
      ) iocell (
        .O (in[i]),   // Buffer output
        .IO(pad[i]),  // Buffer inout port (connect directly to top-level port)
        .I (out[i]),  // Buffer input
        .T (~oe[i])   // 3-state enable input, high=input, low=output
      );
    end
  endgenerate
endmodule
