# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: David Schröder 2026

from pydesignflow import Block, task, Result

from .pdk import Pdk
from .tools import ordec


class AnalogTestbench(Block):
    """
    Analog testbench: an ORDeC testbench cell whose report* views check the design.

    The DUT is bound by the testbench's own import, not by the flow.
    """

    def __init__(self, pdk: Pdk, *, cell: str = None, module: str = None, dependency_map={}):
        """
        Args:
            cell: Testbench cell class name (default: block id in CamelCase, e.g. DacTb).
            module: Python/ORD module defining cell, relative to src/ (default: tb.<block id>).
        """
        super().__init__(dependency_map)
        self.pdk = pdk
        self.cell = cell
        self.module = module

    def setup(self):
        self.src_dir = self.flow.base_dir / "src"
        self.cell = self.cell or "".join(p.capitalize() for p in self.id.split("_"))
        self.module = self.module or f"tb.{self.id}"

    @task()
    def sim(self, cwd):
        """Simulate the testbench and check its reports (PassFail elements)"""
        r = Result()
        reply = ordec.run(self.pdk, {
            "action": "reports",
            "module": self.module,
            "cell": self.cell,
            "path": [self.src_dir],
        }, cwd)
        if not reply["reports"]:
            raise RuntimeError(f"{self.id}: {self.cell} has no report* views.")
        failures = []
        for report in reply["reports"]:
            if not report["checks"]:
                failures.append(f"{report['name']}: no PassFail check")
            failures += [f"{report['name']}: {c['label']}: {c.get('instructions', 'failed')}"
                         for c in report["checks"] if not c["passed"]]
        if failures:
            raise RuntimeError(f"{self.id}: {len(failures)} check(s) failed (reports in {cwd}):\n  "
                               + "\n  ".join(failures))
        r.reports = {report["name"]: cwd / report["md"] for report in reply["reports"]}
        return r

    @task()
    def ui(self, cwd):
        """Open the testbench in the ORDeC web UI"""
        ordec.ui(self.pdk, self.module, cwd, path=[self.src_dir], views=[f"{self.cell}().schematic"])
