# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: David Schröder 2026

"""Minimal LEF reader: macro size and pins."""

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
