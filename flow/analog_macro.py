# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: David Schröder 2026

from pydesignflow import Block, task, Result

from .config import PowerNets
from .pdk import Pdk
from .tools import ordec


class AnalogMacro(Block):
    """
    Analog macro: one ORDeC cell checked and exported as macro product.

    One instance per macro. Sub-cells are instantiated by the ORDeC sources themselves.
    """

    def __init__(self, pdk: Pdk, *, cell: str, module: str = None, params: dict = {},
                 power: PowerNets = None, dependency_map={}):
        """
        Args:
            cell: Class name of the macro's top cell.
            module: Python/ORD module defining cell, relative to src/ (default: ams.<name>.<name>,
                <name> being the block id without the macro_ prefix).
            params: Cell parameters.
            power: Supply nets (default: vdd/vss).
        """
        super().__init__(dependency_map)
        self.pdk = pdk
        self.cell = cell
        self.module = module
        self.params = params
        self.power = power or PowerNets(vdd=["vdd"], gnd=["vss"])

    def setup(self):
        self.src_dir = self.flow.base_dir / "src"
        self.name = self.id.removeprefix("macro_")
        if self.module is None:
            self.module = f"ams.{self.name}.{self.name}"

    def ordec(self, action: str, cwd, **options) -> dict:
        """Run an ORDeC worker action on the macro cell in cwd; return the reply."""
        return ordec.run(self.pdk, {
            "action": action,
            "module": self.module,
            "cell": self.cell,
            "params": self.params,
            "path": [self.src_dir],
            "options": options,
        }, cwd)

    @task(hidden=True)
    def elaborate(self, cwd):
        """Build symbol and schematic (SVGs), check schematic and supply pins"""
        r = Result()
        reply = self.ordec("elaborate", cwd, supplies=self.power.vdd + self.power.gnd)
        r.symbol_svg = cwd / reply["files"]["symbol_svg"]
        r.schematic_svg = cwd / reply["files"]["schematic_svg"]
        r.pins = reply["pins"]
        return r
