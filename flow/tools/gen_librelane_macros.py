# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: David Schröder 2026

import sys
from pathlib import Path

# Relative to $PDK_ROOT
# TODO: make this more general / also work with other macros
SRAM_LIB_SUBPATH = Path("libs.ref/sg13g2_sram")


def build_macro_entry(macro_name: str, pdk_root: Path) -> dict:
    base = pdk_root / SRAM_LIB_SUBPATH

    lef_file = base / "lef" / f"{macro_name}.lef"
    gds_file = base / "gds" / f"{macro_name}.gds"
    vh_top = base / "verilog" / f"{macro_name}.v"
    vh_behav = []#list((base / "verilog").glob("*behavioral*.v"))

    missing = [str(p) for p in (lef_file, gds_file) if not p.is_file()]
    if missing:
        print(
            f"WARNING: {macro_name} is instantiated but missing required "
            f"view(s): {', '.join(missing)} -- skipping this macro.",
            file=sys.stderr,
        )
        return None

    entry = {
        "instances": {},
        "gds": [str(gds_file)],
        "lef": [str(lef_file)],
        "vh": list(map(str, [vh_top, *vh_behav]))
    }

    lib_dir = base / "lib"
    lib_matches = sorted(lib_dir.glob(f"{macro_name}*.lib")) if lib_dir.is_dir() else []
    if lib_matches:
        lib_dict = {}
        for lf in lib_matches:
            corner_tag = lf.stem[len(macro_name):].strip("_")

            # This looks weird, but is required for SG13G2 SRAM macro corner definitions
            # IHP does it this way too
            # See https://github.com/IHP-GmbH/ihp-sg13g2-librelane-template/blob/main/librelane/config.yaml#L176
            if corner_tag == "fast_1p32V_m55C":
                corner_tag = "fast_1p32V_m40C"

            key = f"*{corner_tag}*" if corner_tag else "*"
            lib_dict.setdefault(key, []).append(str(lf))
        entry["lib"] = lib_dict
    else:
        print(
            f"NOTE: no .lib files found for {macro_name} in {lib_dir} -- "
            f"STA for this macro will need a fallback (nl.v/spef or black-boxed).",
            file=sys.stderr,
        )
        entry["lib"] = {}

    entry["spice"] = []
    entry["sdf"] = {}

    return entry


def discover_macros(pdk_root: Path) -> dict:
    """Map macro name -> entry, derived from the PDK's sram LEF dir
    (every physically real macro has a LEF; behavioral-only helper
    models like RM_IHPSG13_1P_core_behavioral_bm_bist do not)."""
    macros = {}
    lef_dir = pdk_root / SRAM_LIB_SUBPATH / "lef"
    if not lef_dir.is_dir():
        print(f"WARNING: {lef_dir} does not exist; check $PDK_ROOT", file=sys.stderr)
        return macros
    for lef_file in lef_dir.glob("*.lef"):
        entry = build_macro_entry(lef_file.stem, pdk_root)
        if entry:
            macros[lef_file.stem] = entry
    return macros
