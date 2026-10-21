# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: David Schröder 2026

"""Minimal LEF reader (macro size and pins) and macro abstract writer."""

from pathlib import Path

from ..macro import Pin


def read_macro(lef: Path, name: str) -> tuple[float, float, list[Pin]]:
    """Return (width, height, pins) of MACRO name in lef."""
    width = height = None
    pins = []
    pin = None
    in_macro = False
    for line in Path(lef).read_text().splitlines():
        tok = line.replace(";", " ").split()
        if not tok:
            continue
        if not in_macro:
            in_macro = tok[:2] == ["MACRO", name]
        elif pin is not None:
            if tok == ["END", pin.name]:
                pins.append(pin)
                pin = None
            elif tok[0] == "DIRECTION":
                pin.direction = tok[1]
            elif tok[0] == "USE":
                pin.use = tok[1]
            elif tok[0] == "LAYER" and tok[1] not in pin.layers:
                pin.layers.append(tok[1])
        elif tok[0] == "SIZE":
            width, height = float(tok[1]), float(tok[3])
        elif tok[0] == "PIN":
            pin = Pin(tok[1], direction="INOUT", use="SIGNAL")
        elif tok == ["END", name]:
            break
    if width is None:
        raise ValueError(f"{lef}: no MACRO {name} with SIZE found")
    return width, height, pins


def _geometry(shape: dict) -> str:
    if "rect" in shape:
        return "RECT " + " ".join(f"{v:.3f}" for v in shape["rect"]) + " ;"
    return "POLYGON " + " ".join(f"{x:.3f} {y:.3f}" for x, y in shape["polygon"]) + " ;"


def write_macro(lef: Path, abstract: dict):
    """Write a macro abstract as LEF file.

    abstract: ``name``, ``size`` ([width, height] in µm, lower left corner at the
    origin), ``pins`` (``name``, ``direction``, ``use``, ``shapes``) and
    ``obstructions``; shapes are ``layer`` plus ``rect`` [lx, ly, ux, uy] or
    ``polygon`` [[x, y], ...].
    """
    name = abstract["name"]
    out = [
        "VERSION 5.8 ;",
        'BUSBITCHARS "[]" ;',
        'DIVIDERCHAR "/" ;',
        "",
        f"MACRO {name}",
        "  CLASS BLOCK ;",
        "  ORIGIN 0 0 ;",
        f"  FOREIGN {name} 0 0 ;",
        "  SIZE {:.3f} BY {:.3f} ;".format(*abstract["size"]),
        "  SYMMETRY X Y ;",
    ]
    for pin in abstract["pins"]:
        out += [
            f"  PIN {pin['name']}",
            f"    DIRECTION {pin['direction']} ;",
            f"    USE {pin['use']} ;",
            "    PORT",
        ]
        for shape in pin["shapes"]:
            out += [f"      LAYER {shape['layer']} ;", f"        {_geometry(shape)}"]
        out += ["    END", f"  END {pin['name']}"]
    if abstract["obstructions"]:
        out.append("  OBS")
        for shape in abstract["obstructions"]:
            out += [f"    LAYER {shape['layer']} ;", f"      {_geometry(shape)}"]
        out.append("  END")
    out += [f"END {name}", "", "END LIBRARY", ""]
    Path(lef).write_text("\n".join(out))
