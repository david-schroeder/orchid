// SPDX-License-Identifier: SHL-2.1
// SPDX-FileCopyrightText: David Schröder 2026

module fpga_top (
    input  logic clk_100mhz_i,
    input  logic button_rst_ni,

    input  logic jtag_tck_i,
    input  logic jtag_tdi_i,
    output logic jtag_tdo_o,
    input  logic jtag_tms_i,
    input  logic jtag_trst_ni,
    input  logic jtag_srst_ni,

    // DDR3 DQ signals are truly bidirectional.
    // They are thus not in the b2f / f2b structs
    // and should be passed to an IO-wrapper-level PHY
    inout  wire [15:0] ddr3_dq,
    inout  wire [ 1:0] ddr3_dqs_n,
    inout  wire [ 1:0] ddr3_dqs_p,
    output wire [14:0] ddr3_addr,
    output wire [ 2:0] ddr3_ba,
    output wire        ddr3_ras_n,
    output wire        ddr3_cas_n,
    output wire        ddr3_we_n,
    output wire        ddr3_reset_n,
    output wire [ 0:0] ddr3_ck_p,
    output wire [ 0:0] ddr3_ck_n,
    output wire [ 0:0] ddr3_cke,
    output wire [ 1:0] ddr3_dm,
    output wire [ 0:0] ddr3_odt,

    output wire [7:0] led_o,
    input  wire [7:0] switch_i,
    input  wire [4:0] button_i,
    output wire       uart_rx_out,
    input  wire       uart_tx_in,
    inout  wire       ps2_clk,
    inout  wire       ps2_data,
    inout  wire       scl,
    inout  wire       sda,

    output wire oled_sdin,
    output wire oled_sclk,
    output wire oled_dc,
    output wire oled_res,
    output wire oled_vbat,
    output wire oled_vdd,

    input  wire ac_adc_sdata,
    output wire ac_bclk,
    output wire ac_lrclk,
    output wire ac_mclk,
    output wire ac_dac_sdata,

    output wire sd_sck,
    output wire sd_mosi,
    output wire sd_cs,
    output wire sd_reset,
    input  wire sd_cd,
    input  wire sd_miso,

    input  wire       hdmi_rx_clk_n,
    input  wire       hdmi_rx_clk_p,
    input  wire [2:0] hdmi_rx_n,
    input  wire [2:0] hdmi_rx_p,
    inout  wire       hdmi_rx_cec,
    inout  wire       hdmi_rx_scl,
    inout  wire       hdmi_rx_sda,
    output wire       hdmi_rx_hpa,
    output wire       hdmi_rx_txen,
    output wire       hdmi_tx_clk_n,
    output wire       hdmi_tx_clk_p,
    output wire [2:0] hdmi_tx_n,
    output wire [2:0] hdmi_tx_p,
    inout  wire       hdmi_tx_cec,
    inout  wire       hdmi_tx_rscl,
    inout  wire       hdmi_tx_rsda,
    input  wire       hdmi_tx_hpd,

    input  wire [3:0] eth_rxd,
    input  wire       eth_rxctl,
    input  wire       eth_rxck,
    output wire [3:0] eth_txd,
    output wire       eth_txctl,
    output wire       eth_txck,
    inout  wire       eth_mdio,
    output wire       eth_mdc,
    input  wire       eth_int_b,
    input  wire       eth_pme_b,
    output wire       eth_rst_b,

    inout wire [7:0] pmod_a,
    inout wire [7:0] pmod_b,
    inout wire [7:0] pmod_c
);

    import top_pkg::*;

    // Clocking + Reset logic
    // ----------------------

    logic clk;
    logic locked;
    logic locked_q = '0;  // fpga bitstream init val = reset active
    logic sys_rst_n;

    fpga_clkmgr clkmgr_i (
        .clk_100mhz_i(clk_100mhz_i),
        .clk_o       (clk),
        .locked_o    (locked)
    );

    always_ff @(posedge clk) begin
        // JTAG reset signals are not included in the reset logic by default.
        locked_q  <= locked && button_rst_ni;
        sys_rst_n <= locked_q;
    end

    // Core
    // ----

    board2fpga_t boardio_b2f;
    fpga2board_t boardio_f2b;

    fpga_io_wrapper io_wrapper_i (
        .io_i(boardio_f2b),
        .io_o(boardio_b2f),

        .jtag_tck_i,
        .jtag_tdi_i,
        .jtag_tdo_o,
        .jtag_tms_i,
        .jtag_trst_ni,
        .jtag_srst_ni,

        .ddr3_dq,
        .ddr3_dqs_n,
        .ddr3_dqs_p,
        .ddr3_addr,
        .ddr3_ba,
        .ddr3_ras_n,
        .ddr3_cas_n,
        .ddr3_we_n,
        .ddr3_reset_n,
        .ddr3_ck_p,
        .ddr3_ck_n,
        .ddr3_cke,
        .ddr3_dm,
        .ddr3_odt,

        .led_o,
        .switch_i,
        .button_i,
        .uart_rx_out,
        .uart_tx_in,
        .ps2_clk,
        .ps2_data,
        .scl,
        .sda,

        .oled_sdin,
        .oled_sclk,
        .oled_dc,
        .oled_res,
        .oled_vbat,
        .oled_vdd,

        .ac_adc_sdata,
        .ac_bclk,
        .ac_lrclk,
        .ac_mclk,
        .ac_dac_sdata,

        .sd_sck,
        .sd_mosi,
        .sd_cs,
        .sd_reset,
        .sd_cd,
        .sd_miso,

        .hdmi_rx_clk_n,
        .hdmi_rx_clk_p,
        .hdmi_rx_n,
        .hdmi_rx_p,
        .hdmi_rx_cec,
        .hdmi_rx_scl,
        .hdmi_rx_sda,
        .hdmi_rx_hpa,
        .hdmi_rx_txen,
        .hdmi_tx_clk_n,
        .hdmi_tx_clk_p,
        .hdmi_tx_n,
        .hdmi_tx_p,
        .hdmi_tx_cec,
        .hdmi_tx_rscl,
        .hdmi_tx_rsda,
        .hdmi_tx_hpd,

        .eth_rxd,
        .eth_rxctl,
        .eth_rxck,
        .eth_txd,
        .eth_txctl,
        .eth_txck,
        .eth_mdio,
        .eth_mdc,
        .eth_int_b,
        .eth_pme_b,
        .eth_rst_b,

        .pmod_a,
        .pmod_b,
        .pmod_c
    );

    logic [7:0] led;
    assign boardio_f2b = '{default: '0, led: led};

    project_core core_i (
        .clk_i   (clk),
        .rst_ni  (sys_rst_n),
        .switch_i(boardio_b2f.switch),
        .led_o   (led)
    );

endmodule
