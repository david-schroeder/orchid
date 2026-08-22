// SPDX-License-Identifier: SHL-2.1
// SPDX-FileCopyrightText: David Schröder 2026

module fpga_io_wrapper
    import top_pkg::*;
(
    input  fpga2board_t io_i,
    output board2fpga_t io_o,

    input  logic jtag_tck_i,
    input  logic jtag_tdi_i,
    output logic jtag_tdo_o,
    input  logic jtag_tms_i,
    input  logic jtag_trst_ni,
    input  logic jtag_srst_ni,

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

    // JTAG
    assign io_o.jtag_tck    = jtag_tck_i;
    assign io_o.jtag_tdi    = jtag_tdi_i;
    assign io_o.jtag_tms    = jtag_tms_i;
    assign io_o.jtag_trst_n = jtag_trst_ni;
    assign io_o.jtag_srst_n = jtag_srst_ni;

    (* IOB = "TRUE" *)
    FDRE #(
        .INIT('0)
    ) tdo_flop_i (
        .Q (jtag_tdo_o),
        .C (~jtag_tck_i),
        .CE('1),
        .R ('0),
        .D (io_i.jtag_tdo)
    );

    // LED / Switch / Buttons
    assign led_o       = io_i.led;
    assign io_o.switch = switch_i;
    assign io_o.button = button_i;

    // UART
    assign io_o.uart_tx_in = uart_tx_in;
    assign uart_rx_out     = io_i.uart_rx_out;

    // PS/2 keyboard / mouse:
    iocell_opendrain io_ps2_clk (
        .pad(ps2_clk),
        .oe (io_i.ps2_clk_oe),
        .in (io_o.ps2_clk)
    );

    iocell_opendrain io_ps2_data (
        .pad(ps2_data),
        .oe (io_i.ps2_data_oe),
        .in (io_o.ps2_data)
    );

    // I2C for Audio codec and Ethernet-associated EEPROM:
    iocell_opendrain io_scl (
        .pad(scl),
        .oe (io_i.scl_oe),
        .in (io_o.scl)
    );

    iocell_opendrain io_sda (
        .pad(sda),
        .oe (io_i.sda_oe),
        .in (io_o.sda)
    );

    // Mini OLED display

    assign oled_sdin = io_i.oled_sdin;
    assign oled_sclk = io_i.oled_sclk;
    assign oled_dc   = io_i.oled_dc;
    assign oled_res  = io_i.oled_res;
    assign oled_vbat = io_i.oled_vbat;
    assign oled_vdd  = io_i.oled_vdd;

    // Audio codec

    assign ac_dac_sdata      = io_i.ac_dac_sdata;
    assign ac_bclk           = io_i.ac_bclk;
    assign ac_lrclk          = io_i.ac_lrclk;
    assign ac_mclk           = io_i.ac_mclk;
    assign io_o.ac_adc_sdata = ac_adc_sdata;

    // SD card

    assign sd_sck       = io_i.sd_sck;
    assign sd_mosi      = io_i.sd_mosi;
    assign sd_cs        = io_i.sd_cs;
    assign sd_reset     = io_i.sd_reset;
    assign io_o.sd_cd   = sd_cd;
    assign io_o.sd_miso = sd_miso;

    // hdmi_rx: HDMI sink / input

    assign hdmi_rx_hpa  = io_i.hdmi_rx_hpa;
    assign hdmi_rx_txen = io_i.hdmi_rx_txen;

    IBUFDS #(
        .IOSTANDARD("TMDS_33")
    ) io_hdmi_rx_clk (
        .O (io_o.hdmi_rx_clk),
        .I (hdmi_rx_clk_p),
        .IB(hdmi_rx_clk_n)
    );

    IBUFDS #(
        .IOSTANDARD("TMDS_33")
    ) io_hdmi_rx0 (
        .O (io_o.hdmi_rx[0]),
        .I (hdmi_rx_p[0]),
        .IB(hdmi_rx_n[0])
    );

    IBUFDS #(
        .IOSTANDARD("TMDS_33")
    ) io_hdmi_rx1 (
        .O (io_o.hdmi_rx[1]),
        .I (hdmi_rx_p[1]),
        .IB(hdmi_rx_n[1])
    );

    IBUFDS #(
        .IOSTANDARD("TMDS_33")
    ) io_hdmi_rx2 (
        .O (io_o.hdmi_rx[2]),
        .I (hdmi_rx_p[2]),
        .IB(hdmi_rx_n[2])
    );

    iocell_opendrain io_hdmi_rx_cec (
        .pad(hdmi_rx_cec),
        .oe (io_i.hdmi_rx_cec_oe),
        .in (io_o.hdmi_rx_cec)
    );

    iocell_opendrain io_hdmi_rx_scl (
        .pad(hdmi_rx_scl),
        .oe (io_i.hdmi_rx_scl_oe),
        .in (io_o.hdmi_rx_scl)
    );

    iocell_opendrain io_hdmi_rx_sda (
        .pad(hdmi_rx_sda),
        .oe (io_i.hdmi_rx_sda_oe),
        .in (io_o.hdmi_rx_sda)
    );

    // hdmi_tx: HDMI source / output

    assign io_o.hdmi_tx_hpd = hdmi_tx_hpd;

    OBUFDS #(
        .IOSTANDARD("TMDS_33")
    ) io_hdmi_tx_clk (
        .I (io_i.hdmi_tx_clk),
        .O (hdmi_tx_clk_p),
        .OB(hdmi_tx_clk_n)
    );

    OBUFDS #(
        .IOSTANDARD("TMDS_33")
    ) io_hdmi_tx0 (
        .I (io_i.hdmi_tx[0]),
        .O (hdmi_tx_p[0]),
        .OB(hdmi_tx_n[0])
    );

    OBUFDS #(
        .IOSTANDARD("TMDS_33")
    ) io_hdmi_tx1 (
        .I (io_i.hdmi_tx[1]),
        .O (hdmi_tx_p[1]),
        .OB(hdmi_tx_n[1])
    );

    OBUFDS #(
        .IOSTANDARD("TMDS_33")
    ) io_hdmi_tx2 (
        .I (io_i.hdmi_tx[2]),
        .O (hdmi_tx_p[2]),
        .OB(hdmi_tx_n[2])
    );

    iocell_opendrain io_hdmi_tx_cec (
        .pad(hdmi_tx_cec),
        .oe (io_i.hdmi_tx_cec_oe),
        .in (io_o.hdmi_tx_cec)
    );

    iocell_opendrain io_hdmi_tx_rscl (
        .pad(hdmi_tx_rscl),
        .oe (io_i.hdmi_tx_rscl_oe),
        .in (io_o.hdmi_tx_rscl)
    );

    iocell_opendrain io_hdmi_tx_rsda (
        .pad(hdmi_tx_rsda),
        .oe (io_i.hdmi_tx_rsda_oe),
        .in (io_o.hdmi_tx_rsda)
    );

    // Ethernet (RGMII)
    // ----------------

    iocell_bidir io_eth_mdio (
        .pad(eth_mdio),
        .oe (io_i.eth_mdio_oe),
        .out(io_i.eth_mdio_out),
        .in (io_o.eth_mdio)
    );

    assign io_o.eth_rxd   = eth_rxd;
    assign io_o.eth_rxctl = eth_rxctl;
    assign io_o.eth_rxck  = eth_rxck;
    assign io_o.eth_int_b = eth_int_b;
    assign io_o.eth_pme_b = eth_pme_b;
    assign eth_txd        = io_i.eth_txd;
    assign eth_txctl      = io_i.eth_txctl;
    assign eth_txck       = io_i.eth_txck;
    assign eth_mdc        = io_i.eth_mdc;
    assign eth_rst_b      = io_i.eth_rst_b;

    // Pmod ports A, B, C

    iocell_bidir #(
        .Width(8)
    ) io_pmod_a (
        .pad(pmod_a),
        .oe (io_i.pmod_a_oe),
        .out(io_i.pmod_a_out),
        .in (io_o.pmod_a)
    );

    iocell_bidir #(
        .Width(8)
    ) io_pmod_b (
        .pad(pmod_b),
        .oe (io_i.pmod_b_oe),
        .out(io_i.pmod_b_out),
        .in (io_o.pmod_b)
    );

    iocell_bidir #(
        .Width(8)
    ) io_pmod_c (
        .pad(pmod_c),
        .oe (io_i.pmod_c_oe),
        .out(io_i.pmod_c_out),
        .in (io_o.pmod_c)
    );

    // DDR3 -- PHY goes here
    assign ddr3_addr    = '0;
    assign ddr3_ba      = '0;
    assign ddr3_ras_n   = '1;
    assign ddr3_cas_n   = '1;
    assign ddr3_we_n    = '1;
    assign ddr3_reset_n = '0;
    assign ddr3_cke     = '0;
    assign ddr3_dm      = '0;
    assign ddr3_odt     = '0;

    // Differential clock buffer for clock output
    OBUFDS #(
        .IOSTANDARD("SSTL15")
    ) io_ddr3_ck (
        .I ('1),
        .O (ddr3_ck_p[0]),
        .OB(ddr3_ck_n[0])
    );

endmodule
