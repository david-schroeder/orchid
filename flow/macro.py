# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: David Schröder 2026

"""Macro interfaces: hard macros placeable in an implementation, and the macro product."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from .config import MacroPlacement


class HardMacro(ABC):
    """A hard macro cell: provides its views and power-grid integration."""

    name: str

    @abstractmethod
    def views(self) -> dict:
        """Return macro views: gds, lef, vh (lists of paths), lib (corner glob -> paths), spice, sdf."""

    @abstractmethod
    def pdn_connections(self, placement: MacroPlacement) -> list[str]:
        """Return PDN connections `<inst_rx> <vdd_net> <gnd_net> <vdd_pin> <gnd_pin>`."""

    @abstractmethod
    def pdn_script(self, placement: MacroPlacement, grid_name: str) -> str:
        """Return PDN (OpenROAD pdngen) commands defining this instance's macro grid."""

    def librelane_config(self) -> dict:
        """Return LibreLane config options required by this macro type (list values are merged)."""
        return {}

    def sim_models(self) -> list[Path]:
        """Return Verilog simulation models of this macro."""
        return []


@dataclass
class Pin:
    """Macro pin, as found in the macro's LEF."""
    name: str
    direction: str
    """LEF direction: INPUT, OUTPUT or INOUT."""
    use: str
    """LEF use: SIGNAL, CLOCK, POWER, GROUND, ..."""
    layers: list[str] = field(default_factory=list)
    """Layers the pin has shapes on."""


@dataclass
class MacroProduct:
    """A hardened macro: the interface between macro blocks and the toplevel.

    Produced by the ``export`` task of every macro block (digital, analog, external),
    so the toplevel can integrate all macros uniformly. View fields mirror LibreLane's
    design formats; per-corner views map a corner name (or wildcard) to files.
    """
    name: str
    """Macro cell name."""
    kind: str
    """Producer: ``digital``, ``analog`` or ``external``."""
    pdk: str
    width: float
    """Macro width in µm."""
    height: float
    """Macro height in µm."""
    pins: list[Pin]
    gds: list[Path]
    lef: list[Path]
    vh: list[Path] = field(default_factory=list)
    """Verilog blackbox header."""
    nl: list[Path] = field(default_factory=list)
    """Gate-level Verilog netlist."""
    pnl: list[Path] = field(default_factory=list)
    """Gate-level Verilog netlist with power pins."""
    model: list[Path] = field(default_factory=list)
    """Behavioral Verilog model for system simulation (RTL for digital macros)."""
    lib: dict[str, list[Path]] = field(default_factory=dict)
    sdf: dict[str, list[Path]] = field(default_factory=dict)
    spef: dict[str, list[Path]] = field(default_factory=dict)
    spice: list[Path] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    """Free-form information (backend, top module, metrics, ...)."""

    def power_pins(self) -> list[Pin]:
        """Supply pins (LEF use POWER or GROUND)."""
        return [p for p in self.pins if p.use in ("POWER", "GROUND")]
