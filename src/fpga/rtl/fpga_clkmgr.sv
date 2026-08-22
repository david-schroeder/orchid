// SPDX-License-Identifier: SHL-2.1
// SPDX-FileCopyrightText: David Schröder 2026

module fpga_clkmgr (
  input  logic clk_100mhz_i,
  
  output logic clk_o,
  output logic locked_o
);

  logic clk_fb;
  logic clkout0;

  MMCME2_BASE #(
    .BANDWIDTH         ("OPTIMIZED"),
    .CLKFBOUT_MULT_F   (10.0), // fVCO = 1GHz 
    .CLKFBOUT_PHASE    (0.0),
    .CLKIN1_PERIOD     (10.0), // Input clock period in ns
    .CLKOUT0_DIVIDE_F  (10.0), // clkout0 = fVCO / 10 = 100 MHz
    .CLKOUT1_DIVIDE    (20), 
    .CLKOUT2_DIVIDE    (20),
    .CLKOUT3_DIVIDE    (20),
    .CLKOUT4_DIVIDE    (20),
    .CLKOUT5_DIVIDE    (20),
    .CLKOUT6_DIVIDE    (20),
    // CLKOUT0_DUTY_CYCLE - CLKOUT6_DUTY_CYCLE: Duty cycle for each CLKOUT (0.01-0.99).
    .CLKOUT0_DUTY_CYCLE(0.5),
    .CLKOUT1_DUTY_CYCLE(0.5),
    .CLKOUT2_DUTY_CYCLE(0.5),
    .CLKOUT3_DUTY_CYCLE(0.5),
    .CLKOUT4_DUTY_CYCLE(0.5),
    .CLKOUT5_DUTY_CYCLE(0.5),
    .CLKOUT6_DUTY_CYCLE(0.5),
    // CLKOUT0_PHASE - CLKOUT6_PHASE: Phase offset for each CLKOUT (-360.000-360.000).
    .CLKOUT0_PHASE     (0.0),
    .CLKOUT1_PHASE     (0.0),
    .CLKOUT2_PHASE     (0.0),
    .CLKOUT3_PHASE     (0.0),
    .CLKOUT4_PHASE     (0.0),
    .CLKOUT5_PHASE     (0.0),
    .CLKOUT6_PHASE     (0.0),
    .CLKOUT4_CASCADE   ("FALSE"),      // Cascade CLKOUT4 counter with CLKOUT6 (FALSE, TRUE)
    .DIVCLK_DIVIDE     (1),            // Master division value (1-106)
    .REF_JITTER1       (0.0),          // Reference input jitter in UI (0.000-0.999).
    .STARTUP_WAIT      ("FALSE")       // Delays DONE until MMCM is locked (FALSE, TRUE)
  ) mmcm_i (
    // Input clock
    .CLKIN1   (clk_100mhz_i),
    // Output clocks
    .CLKOUT0  (clkout0),
    .CLKOUT0B (),
    .CLKOUT1  (),
    .CLKOUT1B (),
    .CLKOUT2  (),
    .CLKOUT2B (),
    .CLKOUT3  (),
    .CLKOUT3B (),
    .CLKOUT4  (),
    .CLKOUT5  (),
    .CLKOUT6  (),
    // Feedback Clocks
    .CLKFBIN  (clk_fb),
    .CLKFBOUT (clk_fb),
    .CLKFBOUTB(),
    // Control + Status ports
    .LOCKED   (locked_o),
    .PWRDWN   ('0),
    .RST      ('0)
  );

  prim_clock_gating sys_clk_gating_i (
    .clk_i    (clkout0),
    .en_i     (locked_o),
    .test_en_i('0),
    .clk_o    (clk_o)
  );

endmodule
