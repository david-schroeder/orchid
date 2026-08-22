// SPDX-License-Identifier: SHL-2.1
// SPDX-FileCopyrightText: 2024 RVLab Contributors

module iocell_opendrain (
  inout  wire  pad,
  input  logic oe,
  output logic in
);
  IOBUF #(
    .DRIVE       (4),
    .IBUF_LOW_PWR("TRUE"),
    .IOSTANDARD  ("DEFAULT"),
    .SLEW        ("SLOW")
  ) iocell (
    .O (in),  // Buffer output
    .IO(pad),  // Buffer inout port (connect directly to top-level port)
    .I ('0),   // Buffer input
    .T (~oe)   // 3-state enable input, high=input, low=output
  );
endmodule
