# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: David Schröder 2026

"""Backend adapter for LibreLane (digital synthesis, PnR and signoff).

LibreLane specifics (config variables, flow classes, run directory layout) are kept
here, so blocks keep a stable interface when the backend is replaced.
"""

import json
from pathlib import Path

from ..config import Clock, Floorplan, PowerNets
from ..pdk import Pdk

POWER_DEFINE = "USE_POWER_PINS"
"""Define enabling power pins in Verilog sources and netlists."""


def merge_config(dst: dict, src: dict) -> dict:
    """Return dst updated with src; list values are merged without duplicates."""
    out = dict(dst)
    for k, v in src.items():
        if isinstance(v, list):
            old = out.get(k, [])
            out[k] = old + [x for x in v if x not in old]
        else:
            out[k] = v
    return out


def design_config(pdk: Pdk, top: str, clock: Clock, power: PowerNets, design_srcs: list,
                  defines: dict, include_dirs: list, floorplan: Floorplan) -> dict:
    """Common config of a LibreLane design: sources, clock, supplies, absolute floorplan."""
    ll = {}

    # General
    ll["DESIGN_NAME"] = top
    ll["CLOCK_PORT"] = clock.port
    if clock.net is not None:
        ll["CLOCK_NET"] = clock.net
    ll["CLOCK_PERIOD"] = clock.period_ns
    ll["VDD_NETS"] = list(power.vdd)
    ll["GND_NETS"] = list(power.gnd)

    # Sources
    ll["VERILOG_FILES"] = [str(x) for x in design_srcs]
    ll["VERILOG_DEFINES"] = list(pdk.verilog_defines) + [f"{k}={v}" for k, v in defines.items()]
    ll["VERILOG_INCLUDE_DIRS"] = [str(x) for x in include_dirs]
    ll["VERILOG_POWER_DEFINE"] = POWER_DEFINE
    ll["USE_SLANG"] = True

    # Floorplan
    fp = floorplan
    ll["FP_SIZING"] = "absolute"
    ll["DIE_AREA"] = [0, 0, fp.die_width, fp.die_height]
    ll["CORE_AREA"] = [
        fp.core_margin,
        fp.core_margin,
        fp.die_width - fp.core_margin,
        fp.die_height - fp.core_margin
    ]

    # Workarounds
    ll["RUN_LINTER"] = False # we can lint elsewhere; prevent spurious file missing etc. errors

    return ll


def macro_mode_config(pdk: Pdk) -> dict:
    """Config for hardening a macro: no padring/global grid, power grid pins on the lower layer."""
    return {
        "PDN_MULTILAYER": False,
        "PDN_ENABLE_PINS": True,
    } | pdk.librelane_macro_config()


def hard_macro_config(pdk: Pdk, placements: list) -> dict:
    """Collect views and PDN configuration for hard macros placed in a design.

    Returns a dict with ``macros`` (LibreLane MACROS), ``pdn_connections``,
    ``pdn_script`` (pdngen commands for the macro grids) and ``config`` (extra options).
    """
    macros = {}
    pdn_connections = []
    pdn_scripts = []
    config = {}
    for i, p in enumerate(placements):
        macro = pdk.macro(p.cell)
        if p.cell not in macros:
            macros[p.cell] = macro.views() | {"instances": {}}
            config = merge_config(config, macro.librelane_config())
        macros[p.cell]["instances"][p.inst] = {
            "location": [p.x, p.y],
            "orientation": str(p.orientation),
        }
        pdn_connections += macro.pdn_connections(p)
        pdn_scripts.append(macro.pdn_script(p, f"grid{i}_{p.inst.split('.')[-1]}"))
    return {
        "macros": macros,
        "pdn_connections": pdn_connections,
        "pdn_script": "\n\n".join(pdn_scripts),
        "config": config,
    }


def add_hard_macros(ll: dict, macros: dict, pdn_connections: list, pdn_script_ext: str,
                    librelane_config: dict, pdn_script: Path | None, cwd: Path) -> dict:
    """Return ll with hard macros (see hard_macro_config) and the design's PDN script added.

    Macro grid commands are appended to pdn_script; the result is written into cwd.
    """
    ll = dict(ll)
    if macros:
        ll["MACROS"] = macros
        ll["PDN_MACRO_CONNECTIONS"] = list(pdn_connections)
    ll |= librelane_config

    if pdn_script is not None:
        pdn_cfg: Path = (cwd / "pdn_cfg.tcl").resolve()
        pdn_cfg.write_text(pdn_script.read_text() + "\n" + pdn_script_ext)
        ll["PDN_CFG"] = str(pdn_cfg)
    elif pdn_script_ext:
        raise ValueError("Macros require PDN commands, but the design config sets no pdn_script.")
    return ll


def write_config(ll: dict, cwd: Path) -> Path:
    """Write a LibreLane config into cwd; return its path."""
    config_file: Path = cwd / "librelane_config.json"
    config_file.write_text(json.dumps(ll, indent=4))
    return config_file


def _flow(pdk: Pdk, name: str, config_file: Path, design_dir: Path, substitutions: dict | None = None):
    from librelane.flows import Flow

    cls = Flow.factory.get(name)
    if substitutions:
        cls = cls.Substitute(substitutions)
    return cls(
        json.loads(config_file.read_text()),
        design_dir=str(design_dir),
        **pdk.librelane_flow_args()
    )


def _plain(value):
    """Convert LibreLane state values (paths, nested dicts/lists) into plain Paths."""
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items() if v is not None}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return Path(str(value))


def run(pdk: Pdk, config_file: Path, design_dir: Path, flow: str = "Classic",
        substitutions: dict | None = None) -> tuple[dict, Path]:
    """Run a LibreLane flow in design_dir.

    Returns the final views ({design format id: path or {corner: path}}) and the run directory.
    """
    f = _flow(pdk, flow, config_file, design_dir, substitutions)
    state = f.start()
    views = {k: _plain(v) for k, v in state.items() if v is not None}
    return views, Path(f.run_dir)


def view(pdk: Pdk, config_file: Path, design_dir: Path):
    """Open the last run in design_dir in KLayout."""
    _flow(pdk, "OpenInKLayout", config_file, design_dir).start(last_run=True)
