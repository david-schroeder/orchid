# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: David Schröder 2026

"""Thin wrapper around Icarus Verilog (iverilog + vvp) for batch simulation."""

import shlex
import shutil
import subprocess
from pathlib import Path


def simulate(srcs: list, top: str, cwd: Path, defines: dict = {}, include_dirs: list = []):
    """Compile srcs and run top in cwd; raise CalledProcessError if the simulation fails."""
    for tool in ("iverilog", "vvp"):
        if shutil.which(tool) is None:
            raise RuntimeError(f"{tool} not found on PATH (Icarus Verilog required).")

    cmd = ["iverilog", "-g2012", "-o", "sim.vvp", "-s", top]
    cmd += [f"-D{k}={v}" for k, v in defines.items()]
    cmd += [f"-I{d}" for d in include_dirs]
    cmd += [str(x) for x in srcs]
    print("Compiling:\n\t", shlex.join(cmd))
    subprocess.check_call(cmd, cwd=cwd)

    # -n: $stop ends the simulation instead of entering interactive mode
    subprocess.check_call(["vvp", "-n", "sim.vvp"], cwd=cwd)
