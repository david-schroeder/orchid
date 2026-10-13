# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: David Schröder 2026

"""Design configuration data types and helpers.

The dataclasses below are passed to block constructors in ``flow/__init__.py``.
``to_data``/``from_data`` convert dataclasses to and from plain JSON data, so task
results stay JSON-serializable.
"""

import dataclasses
import glob
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


def expand(patterns: list, root: Path) -> list[Path]:
    """Expand glob patterns relative to root in order (sorted per pattern, no duplicates)."""
    paths = {}
    for pattern in patterns:
        matches = sorted(glob.glob(str(pattern), root_dir=root, recursive=True))
        if not matches:
            raise FileNotFoundError(f"'{pattern}' matches no file in {root}.")
        paths |= dict.fromkeys((root / m).resolve() for m in matches)
    return list(paths)

