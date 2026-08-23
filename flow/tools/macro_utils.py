from typing import TypeAlias
from enum import StrEnum
from dataclasses import dataclass
from abc import ABC, abstractmethod


Microns: TypeAlias = int


class Orientation(StrEnum):
    NORTH = "N"
    SOUTH = "S"
    EAST = "E"
    WEST = "W"


@dataclass
class MacroInstance:
    macro: type["DesignMacro"]
    inst_name: str
    x: Microns
    y: Microns
    orientation: Orientation = Orientation.NORTH

    def get_pdn_connections(self) -> list[str]:
        return self.macro.get_pdn_connections(self)

    def get_pdn_cfg_script_ext(self) -> str:
        return self.macro.get_pdn_cfg_script_ext(self)


class DesignMacro(ABC):
    name: str

    @classmethod
    def Instance(cls, name: str,
        x: Microns, y: Microns,
        dir: Orientation = Orientation.NORTH
    ):
        return MacroInstance(cls, name, x, y, dir)

    @staticmethod
    @abstractmethod
    def get_pdn_connections(inst: "MacroInstance") -> list[str]:
        """Return list of PDN connections for
        LibreLane PDN_MACRO_CONNECTIONS option"""

    @staticmethod
    @abstractmethod
    def get_pdn_cfg_script_ext(inst: "MacroInstance") -> str:
        """Return TCL script as string which is
        appended to the PDN config script"""
