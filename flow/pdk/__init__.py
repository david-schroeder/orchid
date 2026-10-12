# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: David Schröder 2026

"""PDK plugins: one descriptor per PDK, selected once in flow/__init__.py."""

import os
from abc import ABC, abstractmethod
from pathlib import Path

from ..macro import HardMacro


class Pdk(ABC):
    """PDK descriptor passed to blocks. Environment lookups happen on use, not at import."""

    name: str
    """PDK name (as used by LibreLane)."""
    root_env: str = "PDK_ROOT"
    """Environment variable pointing to this PDK's directory (e.g. .../ihp-sg13g2)."""
    verilog_defines: list[str] = []
    """Defines required by the PDK's Verilog cell models."""

    def root(self) -> Path:
        """PDK directory."""
        value = os.environ.get(self.root_env)
        if not value:
            raise RuntimeError(f"${self.root_env} must point to the {self.name} PDK directory.")
        return Path(value).resolve()

    def librelane_flow_args(self) -> dict:
        """Keyword arguments for constructing a LibreLane flow."""
        return {"pdk_root": str(self.root().parent), "pdk": self.name}

    def librelane_padring_config(self) -> dict:
        """LibreLane config options for designs with a padring."""
        return {}

    def librelane_macro_config(self) -> dict:
        """LibreLane config options for hardening a macro (e.g. layers reserved for the toplevel)."""
        return {}

    @abstractmethod
    def macro(self, cell: str) -> HardMacro:
        """Return the hard macro provider for a cell name; raise KeyError if unknown."""

    @abstractmethod
    def sim_models(self, cwd: Path) -> list[Path]:
        """Return Verilog simulation models of the standard cells (for gate-level simulation).

        Simulator-ready copies of the models may be written into cwd.
        """
