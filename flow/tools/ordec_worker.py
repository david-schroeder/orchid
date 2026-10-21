# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: David Schröder 2026

"""ORDeC worker: performs one action on one ORDeC cell, in its own process.

Usage (cwd = task directory): python -P ordec_worker.py <request.json> <reply.json>

Stand-alone: does not import the flow package (see flow/tools/ordec.py for the caller).

Request: ``action``, ``module`` (import name, e.g. ams.dac.dac), ``cell`` (class name in
module), ``params`` (cell parameters), ``path`` (import roots prepended to sys.path),
``pdk`` (``module``: ORDeC PDK module; ``tech``, ``drc``, ``lvs``, ``device_map``: names
in it; ``max_layer``) and ``options`` (action specific).

Reply: ``status`` "ok" plus the action's results (file paths relative to cwd), or
``status`` "error" with ``error`` and ``traceback``.
"""

import functools
import importlib
import json
import sys
import traceback
from pathlib import Path

ACTIONS = {}


def action(func):
    """Register func(request) -> dict as worker action."""
    ACTIONS[func.__name__] = func
    return func


@functools.cache
def _cell(module: str, cell: str, params: str):
    return getattr(importlib.import_module(module), cell)(**json.loads(params))


def cell_of(request: dict):
    """The request's cell (imported and instantiated once per process)."""
    return _cell(request["module"], request["cell"], json.dumps(request.get("params", {})))


def options(request: dict) -> dict:
    return request.get("options", {})


def pdk_module(request: dict):
    return importlib.import_module(request["pdk"]["module"])


def pdk_attr(request: dict, key: str):
    """Object named request["pdk"][key] in the ORDeC PDK module."""
    return getattr(pdk_module(request), request["pdk"][key])


def tech(request: dict):
    """The PDK's technology cell (layers, routing spec)."""
    return pdk_attr(request, "tech")()


def pin_name(pin) -> str:
    """Name of a symbol pin as written in ORD, e.g. d[0]."""
    first, *rest = pin.full_path_list()
    return str(first) + "".join(f"[{p}]" if isinstance(p, int) else f".{p}" for p in rest)


def macro_directory(top, name: str):
    """Directory naming the cells of a macro product (and their GDS/SPICE names).

    top is named name; cells authored for the macro get the prefix name__, so that
    products of different macros never collide; library cells (ExtLibrary cells such
    as stdcells, PDK primitives from ordec.*) keep their names. LvsDirectory, so that
    LVS can run with the same names.
    """
    from ordec.extlibrary import ExtLibraryCell
    from ordec.layout import klayout

    class MacroDirectory(klayout.LvsDirectory):
        def name_cell(self, cell):
            if cell == top:
                basename = name
            elif isinstance(cell, ExtLibraryCell) or type(cell).__module__.startswith("ordec."):
                return super().name_cell(cell)
            else:
                basename = f"{name}__{cell.escaped_name().lower()}"
            return self.unique_name(basename, cell, None)

    return MacroDirectory()


def routing_layers(request: dict) -> list:
    """RoutingSpecLayers of the PDK routing stack (metals and vias), bottom up."""
    from ordec.core import RoutingSpecLayer
    rs = tech(request).default_routing_spec
    return sorted(rs.all(RoutingSpecLayer), key=lambda l: l.route_id)


def layers_up_to(request: dict, max_layer: str) -> tuple[list, list]:
    """Routing layers (Layer nodes) up to and including max_layer, and those above."""
    layers = [l.layer for l in routing_layers(request)]
    names = [l.full_path_str() for l in layers]
    if max_layer not in names:
        raise ValueError(f"max_layer {max_layer} is not a routing layer ({', '.join(names)}).")
    i = names.index(max_layer) + 1
    return layers[:i], layers[i:]


def gds_layer_boxes(gds: Path) -> dict[int, list[float]]:
    """Bounding box [lx, ly, ux, uy] (µm) of the top cell's shapes per GDS layer number."""
    import klayout.db as kdb
    ly = kdb.Layout()
    ly.read(str(gds))
    top = ly.top_cell()
    boxes = {}
    for li in ly.layer_indexes():
        box = top.dbbox(li)
        if box.empty():
            continue
        n = ly.get_info(li).layer
        old = boxes.get(n)
        boxes[n] = [box.left, box.bottom, box.right, box.top] if old is None else [
            min(old[0], box.left), min(old[1], box.bottom), max(old[2], box.right), max(old[3], box.top)]
    return boxes


def gds_bbox(gds: Path) -> list[float]:
    """Bounding box [lx, ly, ux, uy] of the top cell in µm."""
    import klayout.db as kdb
    ly = kdb.Layout()
    ly.read(str(gds))
    b = ly.top_cell().dbbox()
    return [b.left, b.bottom, b.right, b.top]


def gds_paths_to_polygons(gds: Path):
    """Replace all paths in gds by equivalent polygons (in place).

    ORDeC's GDS reader drops path widths, so products must not contain paths to be
    importable as ExtLibrary cells.
    """
    import klayout.db as kdb
    ly = kdb.Layout()
    ly.read(str(gds))
    for cell in ly.each_cell():
        for li in ly.layer_indexes():
            shapes = cell.shapes(li)
            paths = [s for s in shapes.each() if s.is_path()]
            for s in paths:
                shapes.insert(s.polygon)
                shapes.erase(s)
    ly.write(str(gds))


def subckts_only(netlist: str) -> str:
    """The .subckt definitions of a netlist, without title, model and option cards."""
    out, inside = [], False
    for line in netlist.splitlines():
        card = line.strip().lower()
        if card.startswith(".subckt"):
            inside = True
        if inside:
            out.append(line)
        if card.startswith(".ends"):
            inside = False
    return "\n".join(out) + "\n"


# Actions
# -------

@action
def elaborate(request: dict) -> dict:
    """Build symbol and schematic, render both as SVG, check schematic and supply pins.

    options: ``supplies`` (pin names that must exist as inout pins).
    """
    from ordec.core import Pin, PinType, SchemErrorMarker

    cell = cell_of(request)
    symbol = cell.symbol
    schematic = cell.schematic
    Path("symbol.svg").write_bytes(symbol.render().svg())
    Path("schematic.svg").write_bytes(schematic.render().svg())

    errors = [f"{m.error_type.name} at {m.pos}" for m in schematic.all(SchemErrorMarker)]
    if errors:
        raise ValueError("Schematic check failed (see schematic.svg): " + "; ".join(errors))

    pins = {pin_name(p): p.pintype for p in symbol.all(Pin)}
    for supply in options(request).get("supplies", []):
        if pins.get(supply) != PinType.Inout:
            raise ValueError(f"Supply {supply} is not an inout pin of the symbol "
                             f"(pins: {', '.join(pins)}).")

    return {
        "files": {"symbol_svg": "symbol.svg", "schematic_svg": "schematic.svg"},
        "pins": [{"name": n, "direction": t.value} for n, t in pins.items()],
    }


@action
def netlist(request: dict) -> dict:
    """Write the hierarchical SPICE subckt netlist <name>.spice (macro naming).

    options: ``name`` (macro name).
    """
    from ordec.schematic import Netlister

    cell = cell_of(request)
    name = options(request)["name"]
    nl = Netlister(macro_directory(cell, name), lvs=False)
    nl.netlist_hier_symbol(cell.symbol)
    spice = Path(f"{name}.spice")
    spice.write_text(subckts_only(nl.out()))
    return {"files": {"spice": str(spice)}}


@action
def layout(request: dict) -> dict:
    """Write the layout as <name>.gds (macro naming, paths as polygons); return its
    cells and bounding box.

    options: ``name`` (macro name).
    """
    from ordec.layout import write_gds

    cell = cell_of(request)
    name = options(request)["name"]
    directory = macro_directory(cell, name)
    gds = Path(f"{name}.gds")
    with open(gds, "wb") as f:
        write_gds(cell.layout, f, directory)
    gds_paths_to_polygons(gds)
    cells = sorted(n for (domain, n) in directory.obj_of_name if domain is None)
    return {"files": {"gds": str(gds)}, "cells": cells, "bbox": gds_bbox(gds)}


@action
def drc(request: dict) -> dict:
    """Run the PDK DRC (into drc/) and check that no layer above the macro limit is used.

    options: ``drc`` (keyword arguments of the PDK DRC entry point).
    Returns ``violations`` ({category: count}) and ``reserved_layers`` (used layers
    above ``max_layer``).
    """
    cell = cell_of(request)
    report = pdk_attr(request, "drc")(cell.layout, use_tempdir=False, **options(request).get("drc", {}))
    violations = report.summary()

    reserved = []
    max_layer = request["pdk"].get("max_layer")
    if max_layer is not None:
        _, above = layers_up_to(request, max_layer)
        used = gds_layer_boxes(Path("drc/layout.gds"))
        reserved = [l.full_path_str() for l in above if l.gdslayer_shapes.layer in used]

    result = {"violations": violations, "reserved_layers": reserved}
    Path("drc.json").write_text(json.dumps(result, indent=4))
    return result | {"files": {"report": "drc.json", "dir": "drc"}}


def lvs_result(report) -> dict:
    from ordec.core import LvsCircuitPair
    return {
        "outcome": report.status.value,
        "clean": report.clean(),
        "circuits": [{
            "layout": p.layout_cell, "schematic": p.schem_cell,
            "status": p.status.value, "message": p.message,
        } for p in report.all(LvsCircuitPair)],
    }


@action
def lvs(request: dict) -> dict:
    """Run LVS of layout against schematic (into lvs/)."""
    cell = cell_of(request)
    result = lvs_result(pdk_attr(request, "lvs")(cell.layout, cell.symbol, use_tempdir=False))
    Path("lvs.json").write_text(json.dumps(result, indent=4))
    return result | {"files": {"report": "lvs.json", "dir": "lvs"}}


@action
def abstract(request: dict) -> dict:
    """Abstract (LEF data) of the macro layout written by the layout action.

    options: ``name``, ``gds`` (the macro GDS), ``power``/``ground`` (supply pin names).
    Returns ``size`` (µm), ``pins`` (name as in GDS/SPICE, LEF direction and use,
    rect/polygon shapes per layer) and ``obstructions`` (bounding box of each used
    routing metal up to max_layer). The layout's lower left corner must be at the
    origin; pins must be shapes in the top cell.
    """
    from ordec.core import LayoutPin, LayoutPoly, LayoutRect, PinType, Directory

    opts = options(request)
    cell = cell_of(request)
    gds = Path(opts["gds"])
    lx, ly, ux, uy = gds_bbox(gds)
    if abs(lx) > 1e-6 or abs(ly) > 1e-6:
        raise ValueError(f"The macro layout's lower left corner is at ({lx:g}, {ly:g}) µm; "
                         f"move its content by ({-lx:g}, {-ly:g}) µm to the origin.")
    unit = float(cell.layout.ref_layers.unit) * 1e6  # µm per database unit
    directions = {PinType.In: "INPUT", PinType.Out: "OUTPUT", PinType.Inout: "INOUT"}

    directory = Directory()
    pins = {}
    for lp in cell.layout.all(LayoutPin):
        shape = lp.ref
        if isinstance(shape, LayoutRect):
            r = shape.rect
            geometry = {"rect": [r.lx * unit, r.ly * unit, r.ux * unit, r.uy * unit]}
        elif isinstance(shape, LayoutPoly):
            geometry = {"polygon": [[v.x * unit, v.y * unit] for v in shape.vertices()]}
        else:
            raise ValueError(f"Pin {pin_name(lp.pin)}: unsupported shape {type(shape).__name__} "
                             "(use a LayoutRect or LayoutPoly in the macro's top cell).")
        name = directory.name_node(lp.pin)
        use = ("POWER" if name in opts.get("power", []) else
               "GROUND" if name in opts.get("ground", []) else "SIGNAL")
        pin = pins.setdefault(name, {"name": name, "direction": directions[lp.pin.pintype],
                                     "use": use, "shapes": []})
        pin["shapes"].append({"layer": shape.layer.full_path_str()} | geometry)

    # Metals are the routing layers with wires (the others are cuts).
    max_layer = request["pdk"].get("max_layer")
    rsls = routing_layers(request)
    if max_layer is not None:
        below, _ = layers_up_to(request, max_layer)
        rsls = [l for l in rsls if l.layer in below]
    used = gds_layer_boxes(gds)
    obstructions = [
        {"layer": l.layer.full_path_str(), "rect": used[l.layer.gdslayer_shapes.layer]}
        for l in rsls
        if l.route_wire_width is not None and l.layer.gdslayer_shapes.layer in used
    ]

    return {
        "name": opts["name"],
        "size": [ux, uy],
        "pins": list(pins.values()),
        "obstructions": obstructions,
    }


@action
def lvs_product(request: dict) -> dict:
    """LVS of a macro product imported as ExtLibrary cell (round trip of the export).

    options: ``name``, ``gds``, ``lef``, ``spice`` (product files). Runs in lvs/.
    """
    from ordec.extlibrary import ExtLibrary

    opts = options(request)
    lib = ExtLibrary()
    lib.read_lef(opts["lef"])
    lib.read_gds(opts["gds"], tech(request).layers)
    lib.read_spice(opts["spice"], device_map=pdk_attr(request, "device_map"))
    cell = lib[opts["name"]]
    result = lvs_result(pdk_attr(request, "lvs")(cell.layout, cell.symbol, use_tempdir=False))
    Path("lvs_product.json").write_text(json.dumps(result, indent=4))
    return result | {"files": {"report": "lvs_product.json", "dir": "lvs"}}


@action
def reports(request: dict) -> dict:
    """Evaluate all report* viewgens of a testbench cell and write them to disk.

    Per report: <report>.md (markdown, checks, plot references), <report>.json
    (elements, plot data in CSV files), <report>_plot<i>.csv. Returns the PassFail
    checks per report; deciding pass/fail is up to the caller.
    """
    from ordec.core.cell import ViewGenerator

    cell = cell_of(request)
    names = sorted(n for n in dir(type(cell))
                   if n.startswith("report") and isinstance(getattr(type(cell), n), ViewGenerator))
    results = []
    for name in names:
        results.append(write_report(name, getattr(cell, name)))
    return {"reports": results}


def write_report(name: str, report) -> dict:
    from ordec.core.schema.report import (Markdown, PreformattedText, Html, PassFail, Score,
                                          Svg, Plot2D)
    md, elements, checks = [], [], []
    plots = 0
    for e in report.elements():
        if isinstance(e, Markdown):
            md.append(e.markdown)
            elements.append({"type": "markdown", "markdown": e.markdown})
        elif isinstance(e, PreformattedText):
            md.append(f"```\n{e.text}\n```")
            elements.append({"type": "pre", "text": e.text})
        elif isinstance(e, Html):
            md.append(e.html)
            elements.append({"type": "html", "html": e.html})
        elif isinstance(e, PassFail):
            check = {"label": e.label, "passed": e.passed}
            if not e.passed:
                check["instructions"] = e.instructions
            checks.append(check)
            md.append(f"- **{'PASS' if e.passed else 'FAIL'}** {e.label}"
                      + ("" if e.passed or not e.instructions else f": {e.instructions}"))
            elements.append({"type": "passfail"} | check)
        elif isinstance(e, Score):
            md.append(f"- **{e.label}**: {e.value:g} {e.unit}".rstrip())
            elements.append({"type": "score", "label": e.label, "value": e.value,
                             "unit": e.unit, "eligible": e.eligible})
        elif isinstance(e, Svg):
            svg = f"{name}_svg{len(elements)}.svg"
            vb = " ".join(f"{v:g}" for v in (e.viewbox_min_x, e.viewbox_min_y,
                                             e.viewbox_width, e.viewbox_height))
            Path(svg).write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}">'
                                 f'{e.inner}</svg>\n')
            md.append(f"![]({svg})")
            elements.append({"type": "svg", "file": svg})
        elif isinstance(e, Plot2D):
            csv = f"{name}_plot{plots}.csv"
            plots += 1
            series = list(e.series())
            header = [e.xlabel or "x"] + [s.name for s in series]
            rows = zip(e.x, *(s.values for s in series))
            Path(csv).write_text(",".join(f'"{h}"' for h in header) + "\n"
                                 + "".join(",".join(f"{v:.9g}" for v in row) + "\n" for row in rows))
            md.append(f"Plot: [{csv}]({csv}) ({e.ylabel or 'y'} over {e.xlabel or 'x'}: "
                      f"{', '.join(s.name for s in series)})")
            elements.append({"type": "plot2d", "file": csv, "xlabel": e.xlabel,
                             "ylabel": e.ylabel, "series": [s.name for s in series]})
    # Consecutive list items (checks, scores) form one list.
    text, prev_item = "", False
    for block in md:
        item = block.startswith("- ")
        if text:
            text += "\n" if item and prev_item else "\n\n"
        text += block
        prev_item = item
    Path(f"{name}.md").write_text(text + "\n")
    Path(f"{name}.json").write_text(json.dumps({"name": name, "elements": elements}, indent=4))
    return {"name": name, "md": f"{name}.md", "json": f"{name}.json", "checks": checks}


def main(request_file: str, reply_file: str) -> int:
    request = json.loads(Path(request_file).read_text())
    try:
        if request["action"] not in ACTIONS:
            raise ValueError(f"Unknown action {request['action']!r} (known: {', '.join(ACTIONS)}).")
        sys.path[:0] = request.get("path", [])
        import ordec.importer  # makes .ord modules importable
        reply = {"status": "ok"} | ACTIONS[request["action"]](request)
    except Exception as e:
        traceback.print_exc()
        reply = {"status": "error", "error": f"{type(e).__name__}: {e}",
                 "traceback": traceback.format_exc()}
    Path(reply_file).write_text(json.dumps(reply, indent=4))
    return 0 if reply["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
