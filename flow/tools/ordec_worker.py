# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: David Schröder 2026

"""ORDeC worker: performs one action on one ORDeC cell, in its own process.

Usage (cwd = task directory): python -P ordec_worker.py <request.json> <reply.json>

Stand-alone: does not import the flow package (see flow/tools/ordec.py for the caller).

Request: ``action``, ``module`` (import name, e.g. ams.dac.dac), ``cell`` (class name in
module), ``params`` (cell parameters), ``path`` (import roots prepended to sys.path),
``pdk`` (``module``, ``drc``, ``lvs``: ORDeC PDK module and entry point names,
``max_layer``) and ``options`` (action specific).

Reply: ``status`` "ok" plus the action's results (file paths relative to cwd), or
``status`` "error" with ``error`` and ``traceback``.
"""

import importlib
import json
import sys
import traceback
from pathlib import Path

ACTIONS = {}


def action(func):
    """Register func(cell, request) -> dict as worker action."""
    ACTIONS[func.__name__] = func
    return func


def pin_name(pin) -> str:
    """Name of a symbol pin as written in ORD, e.g. d[0]."""
    first, *rest = pin.full_path_list()
    return str(first) + "".join(f"[{p}]" if isinstance(p, int) else f".{p}" for p in rest)


@action
def elaborate(cell, request: dict) -> dict:
    """Build symbol and schematic, render both as SVG, check schematic and supply pins.

    options: ``supplies`` (pin names that must exist as inout pins).
    """
    from ordec.core import Pin, PinType, SchemErrorMarker

    symbol = cell.symbol
    schematic = cell.schematic
    Path("symbol.svg").write_bytes(symbol.render().svg())
    Path("schematic.svg").write_bytes(schematic.render().svg())

    errors = [f"{m.error_type.name} at {m.pos}" for m in schematic.all(SchemErrorMarker)]
    if errors:
        raise ValueError("Schematic check failed (see schematic.svg): " + "; ".join(errors))

    pins = {pin_name(p): p.pintype for p in symbol.all(Pin)}
    for supply in request.get("options", {}).get("supplies", []):
        if pins.get(supply) != PinType.Inout:
            raise ValueError(f"Supply {supply} is not an inout pin of the symbol "
                             f"(pins: {', '.join(pins)}).")

    return {
        "files": {"symbol_svg": "symbol.svg", "schematic_svg": "schematic.svg"},
        "pins": [{"name": n, "direction": t.value} for n, t in pins.items()],
    }


def main(request_file: str, reply_file: str) -> int:
    request = json.loads(Path(request_file).read_text())
    try:
        if request["action"] not in ACTIONS:
            raise ValueError(f"Unknown action {request['action']!r} (known: {', '.join(ACTIONS)}).")
        sys.path[:0] = request.get("path", [])
        import ordec.importer  # makes .ord modules importable
        module = importlib.import_module(request["module"])
        cell = getattr(module, request["cell"])(**request.get("params", {}))
        reply = {"status": "ok"} | ACTIONS[request["action"]](cell, request)
    except Exception as e:
        traceback.print_exc()
        reply = {"status": "error", "error": f"{type(e).__name__}: {e}",
                 "traceback": traceback.format_exc()}
    Path(reply_file).write_text(json.dumps(reply, indent=4))
    return 0 if reply["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
