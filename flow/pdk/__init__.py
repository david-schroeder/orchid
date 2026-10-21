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
    macro_max_layer: str | None = None
    """Topmost routing layer inside macros; layers above stay free for the toplevel."""
    ordec_module: str | None = None
    """ORDeC PDK module (e.g. ordec.lib.ihp130); None if ORDeC does not support the PDK."""
    ordec_tech: str | None = None
    """Technology cell in ordec_module (layers, default_routing_spec)."""
    ordec_drc: str | None = None
    """DRC entry point in ordec_module: f(layout, use_tempdir=False, **options) -> DrcReport."""
    ordec_lvs: str | None = None
    """LVS entry point in ordec_module: f(layout, symbol, use_tempdir=False) -> LvsReport."""
    ordec_device_map: str | None = None
    """SPICE model -> ORDeC device mapping in ordec_module (for importing SPICE netlists)."""

    def root(self) -> Path:
        """PDK directory."""
        value = os.environ.get(self.root_env)
        if not value:
            raise RuntimeError(f"${self.root_env} must point to the {self.name} PDK directory.")
        return Path(value).resolve()

    def ordec_env(self) -> dict[str, str]:
        """Environment variables ORDeC needs for this PDK (derived from root())."""
        return {}

    def klayout_lyp(self) -> Path | None:
        """KLayout layer properties file for viewing layouts."""
        return None

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
