# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: David Schröder 2026

"""KLayout (GUI) wrapper."""

import subprocess
from pathlib import Path


def view(layouts: list[Path], lyp: Path | None = None):
    """Open layouts in the KLayout viewer (with layer properties lyp); blocks until closed."""
    cmd = ["klayout"]
    if lyp is not None:
        cmd += ["-l", str(lyp)]
    subprocess.run(cmd + [str(l) for l in layouts], check=True)
