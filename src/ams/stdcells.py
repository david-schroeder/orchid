# SPDX-License-Identifier: SHL-2.1
# SPDX-FileCopyrightText: David Schröder 2026

"""SG13G2 standard cells for ORDeC designs, shared by all modules of a process.

Import from here instead of building an own ExtLibrary: separate libraries would put
distinct, suffixed copies of the same cells into netlists and GDS.
"""

import functools

from ordec.core.schema.layout import LayoutInstanceSubcursor, LayoutPin
from ordec.extlibrary import ExtLibrary
from ordec.layout.pnr import lef_pin_rects, place_and_route
from ordec.lib import ihp130

# Read LEF first: its symbols (with pin directions) win over the ones derived from SPICE.
lib = ExtLibrary()
lib.read_lef(ihp130.pdk().stdcell_lef)
lib.read_gds(ihp130.pdk().stdcell_gds, ihp130.SG13G2().layers)
lib.read_spice(ihp130.pdk().stdcell_spice, device_map=ihp130.device_map)


def cell(name: str):
    """Standard cell by name without library prefix, e.g. cell("buf_1")."""
    return lib[f"sg13g2_{name}"]


@functools.cache
def pin_rects() -> dict:
    """Metal1 pin rectangles of all cells (for place_and_route)."""
    return lef_pin_rects(ihp130.pdk().stdcell_lef, "Metal1")


def pnr(schematic, layout, **kwargs):
    """Place and route a stdcell schematic into layout (supplies vdd/vss).

    Signal ports end on Metal4 pads at the top/bottom edge (choose with
    port_edges={'net': 'top'|'bottom'}), supplies on the Metal1 rails or side straps.
    """
    return place_and_route(schematic, layout, grid=ihp130.grid,
        routing_spec=ihp130.SG13G2().default_routing_spec, pin_rects=pin_rects(), **kwargs)


def port(inst, *path):
    """Pin shape of a sub-cell port in the parent's coordinates, e.g. port(drv, 'q', 0).

    For pins without a named shape, such as the port pads of a pnr block.
    """
    sub = inst.subcursor()
    for lp in sub.node().all(LayoutPin):
        if tuple(lp.pin.full_path_list()) == path:
            return LayoutInstanceSubcursor(sub.hierarchy() + (lp.ref,))
    raise KeyError(f"{inst.full_path_str()}: no layout pin {path}")
