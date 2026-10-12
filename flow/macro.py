# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: David Schröder 2026

"""Macro-provider interface: hard macros placeable in an ASIC implementation."""

from abc import ABC, abstractmethod

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
