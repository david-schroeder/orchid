# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: David Schröder 2026

"""Schema for design configuration files under ``src/``.

Design config files are Python modules defining a ``config`` object built from the
dataclasses below. The flow loads them in a task and passes them on as plain JSON data
(``to_data``/``from_data``), so results stay JSON-serializable.
"""

import dataclasses
import importlib.util
import types
import typing
from dataclasses import dataclass, field
from enum import Enum, StrEnum
from pathlib import Path


class Orientation(StrEnum):
    """Placement orientation (LEF/DEF naming)."""
    NORTH = "N"
    SOUTH = "S"
    EAST = "E"
    WEST = "W"
    FLIPPED_NORTH = "FN"
    FLIPPED_SOUTH = "FS"
    FLIPPED_EAST = "FE"
    FLIPPED_WEST = "FW"


@dataclass
class Floorplan:
    """Die and core area in µm."""
    die_width: float
    die_height: float
    core_margin: float


@dataclass
class Clock:
    """Primary clock."""
    port: str
    """Top-level clock port."""
    period_ns: float
    net: str | None = None
    """Clock net to constrain, if different from the port (e.g. behind a pad cell)."""


@dataclass
class PowerNets:
    """Core supply nets of the design."""
    vdd: list[str] = field(default_factory=lambda: ["VDD"])
    gnd: list[str] = field(default_factory=lambda: ["VSS"])


@dataclass
class Padring:
    """Pad cell instance names per die side, in placement order."""
    north: list[str] = field(default_factory=list)
    east: list[str] = field(default_factory=list)
    south: list[str] = field(default_factory=list)
    west: list[str] = field(default_factory=list)


@dataclass
class MacroPlacement:
    """Placement of one hard macro instance."""
    cell: str
    """Macro cell name, as provided by the PDK plugin (e.g. a PDK SRAM)."""
    inst: str
    """Hierarchical instance name in the synthesized netlist (e.g. ``core_i.sram0_i``)."""
    x: float
    y: float
    orientation: Orientation = Orientation.NORTH


@dataclass
class AsicConfig:
    """Configuration of an ASIC (chip) implementation."""
    top: str
    """Top-level module name."""
    floorplan: Floorplan
    clock: Clock
    power: PowerNets = field(default_factory=PowerNets)
    padring: Padring = field(default_factory=Padring)
    io_pin_order: Path | None = None
    """Pin order file for the I/O placer."""
    pdn_script: Path | None = None
    """PDN script; macro-specific PDN commands are appended by the flow."""
    macros: list[MacroPlacement] = field(default_factory=list)
    librelane: dict = field(default_factory=dict)
    """Raw LibreLane config overrides, applied last. Backend-specific escape hatch."""


@dataclass
class Testbench:
    """Self-checking testbench: passes by finishing, fails via ``$fatal``/``$error``."""
    top: str
    """Testbench top module."""
    srcs: list[Path]
    """Testbench sources (the design under test is added by the flow)."""


@dataclass
class DigitalMacroConfig:
    """Configuration of a digital macro, hardened by a DigitalMacro block."""
    top: str
    """Top module name; also the name of the hardened macro cell."""
    srcs: list[Path]
    """RTL sources in compilation order (packages first)."""
    floorplan: Floorplan
    clock: Clock
    power: PowerNets = field(default_factory=PowerNets)
    defines: dict = field(default_factory=dict)
    """Verilog defines (name -> value)."""
    include_dirs: list[Path] = field(default_factory=list)
    io_pin_order: Path | None = None
    """Pin order file for the I/O placer."""
    pdn_script: Path | None = None
    """PDN script; required if sub-macros need PDN commands (appended by the flow)."""
    macros: list[MacroPlacement] = field(default_factory=list)
    """Hard macros placed inside this macro (e.g. PDK SRAMs)."""
    testbench: Testbench | None = None
    """Testbench for RTL and gate-level simulation of this macro."""
    librelane: dict = field(default_factory=dict)
    """Raw LibreLane config overrides, applied last. Backend-specific escape hatch."""


def to_data(obj, keep_paths: bool = False):
    """Convert a config dataclass into JSON-compatible data (for task Results).

    Fields set to None are omitted (Results cannot hold None; from_data restores the default).
    With keep_paths, Path objects are kept (Result stores them relative to the build dir).
    """
    if dataclasses.is_dataclass(obj):
        return {
            f.name: to_data(getattr(obj, f.name), keep_paths)
            for f in dataclasses.fields(obj) if getattr(obj, f.name) is not None
        }
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, Path):
        return obj if keep_paths else str(obj)
    if isinstance(obj, (list, tuple)):
        return [to_data(x, keep_paths) for x in obj]
    if isinstance(obj, dict):
        return {k: to_data(v, keep_paths) for k, v in obj.items()}
    return obj


def from_data(cls, data):
    """Reconstruct a config dataclass of type cls from to_data() output."""
    if data is None:
        return None
    origin = typing.get_origin(cls)
    if origin in (typing.Union, types.UnionType):
        (cls,) = [a for a in typing.get_args(cls) if a is not type(None)]
        return from_data(cls, data)
    if origin is list:
        (arg,) = typing.get_args(cls)
        return [from_data(arg, x) for x in data]
    if origin is dict:
        (_, arg) = typing.get_args(cls)
        return {k: from_data(arg, v) for k, v in data.items()}
    if dataclasses.is_dataclass(cls):
        hints = typing.get_type_hints(cls)
        return cls(**{
            f.name: from_data(hints[f.name], data[f.name])
            for f in dataclasses.fields(cls) if f.name in data
        })
    if cls in (Path,) or (isinstance(cls, type) and issubclass(cls, Enum)):
        return cls(data)
    return data


def load(path: Path, cls: type, name: str = "config"):
    """Load design config object `name` of type cls from Python file `path`."""
    spec = importlib.util.spec_from_file_location(f"design_config_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    obj = getattr(module, name, None)
    if not isinstance(obj, cls):
        raise TypeError(f"{path}: expected '{name}' of type {cls.__name__}, got {type(obj).__name__}")
    return obj
