// SPDX-License-Identifier: SHL-2.1
// SPDX-FileCopyrightText: David Schröder 2026

module asic_top (
    `ifdef USE_POWER_PINS
    inout wire IOVDD,
    inout wire IOVSS,
    inout wire VDD,
    inout wire VSS,
    `endif

    inout wire clk_PAD,
    inout wire rst_n_PAD,
    inout wire [7:0] switch_PAD,
    inout wire [7:0] led_PAD
);

    wire clk_core;
    wire rst_n_core;

    wire [7:0] switch_core;
    wire [7:0] led_core;

    (* keep *) sg13g2_IOPadIOVdd iovdd_pad (
        `ifdef USE_POWER_PINS
        .iovdd(IOVDD),
        .iovss(IOVSS),
        .vdd  (VDD),
        .vss  (VSS)
        `endif
    );
    (* keep *) sg13g2_IOPadIOVss iovss_pad (
        `ifdef USE_POWER_PINS
        .iovdd(IOVDD),
        .iovss(IOVSS),
        .vdd  (VDD),
        .vss  (VSS)
        `endif
    );
    (* keep *) sg13g2_IOPadVdd vdd_pad (
        `ifdef USE_POWER_PINS
        .iovdd(IOVDD),
        .iovss(IOVSS),
        .vdd  (VDD),
        .vss  (VSS)
        `endif
    );
    (* keep *) sg13g2_IOPadVss vss_pad (
        `ifdef USE_POWER_PINS
        .iovdd(IOVDD),
        .iovss(IOVSS),
        .vdd  (VDD),
        .vss  (VSS)
        `endif
    );

    sg13g2_IOPadIn clk_pad (
        `ifdef USE_POWER_PINS
        .iovdd(IOVDD),
        .iovss(IOVSS),
        .vdd  (VDD),
        .vss  (VSS),
        `endif
        .p2c  (clk_core),
        .pad  (clk_PAD)
    );
    sg13g2_IOPadIn rst_n_pad (
        `ifdef USE_POWER_PINS
        .iovdd(IOVDD),
        .iovss(IOVSS),
        .vdd  (VDD),
        .vss  (VSS),
        `endif
        .p2c  (rst_n_core),
        .pad  (rst_n_PAD)
    );

    generate
        for (genvar i = 0; i < 8; i++) begin : gen_in_pads
            sg13g2_IOPadIn in_pad (
                `ifdef USE_POWER_PINS
                .iovdd(IOVDD),
                .iovss(IOVSS),
                .vdd  (VDD),
                .vss  (VSS),
                `endif
                .p2c  (switch_core[i]),
                .pad  (switch_PAD[i])
            );
        end : gen_in_pads

        for (genvar i = 0; i < 8; i++) begin : gen_out_pads
            sg13g2_IOPadOut30mA out_pad (
                `ifdef USE_POWER_PINS
                .iovdd(IOVDD),
                .iovss(IOVSS),
                .vdd  (VDD),
                .vss  (VSS),
                `endif
                .c2p  (led_core[i]),
                .pad  (led_PAD[i])
            );
        end : gen_out_pads
    endgenerate

    (* keep *) project_core core_i (
        .clk_i   (clk_core),
        .rst_ni  (rst_n_core),
        .switch_i(switch_core),
        .led_o   (led_core)
    );

endmodule
