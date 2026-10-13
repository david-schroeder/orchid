# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: David Schröder 2026

"""Thin wrapper around Icarus Verilog (iverilog + vvp) for batch simulation."""

import shlex
import shutil
import subprocess
from pathlib import Path

SDF_MODULE = "sdf_annotate"
"""Generated extra top module applying the SDF annotations."""


def write_sdf_module(sdf: dict, cwd: Path) -> Path:
    """Write a module calling $sdf_annotate per {'tb_top/inst/path': sdf_file} into cwd."""
    lines = [f"module {SDF_MODULE};", "    initial begin"]
    for scope, file in sdf.items():
        scope = scope.strip("/").replace("/", ".")
        lines.append(f'        $sdf_annotate("{Path(file).resolve()}", {scope});')
    lines += ["    end", "endmodule", ""]
    module = cwd / f"{SDF_MODULE}.v"
    module.write_text("\n".join(lines))
    return module


def simulate(srcs: list, tops: list[str], cwd: Path, defines: dict = {}, include_dirs: list = [],
             sdf: dict = {}):
    """Compile srcs and run the top modules in cwd; raise CalledProcessError if the simulation fails.

    sdf: Delay annotation, e.g. {'tb_top/dut': '/path/to/file.sdf'}.
    """
    for tool in ("iverilog", "vvp"):
        if shutil.which(tool) is None:
            raise RuntimeError(f"{tool} not found on PATH (Icarus Verilog required).")

    srcs = list(srcs)
    tops = list(tops)
    cmd = ["iverilog", "-g2012", "-o", "sim.vvp"]
    if sdf:
        # Specify blocks are ignored without -gspecify, leaving nothing to annotate
        cmd.append("-gspecify")
        srcs.append(write_sdf_module(sdf, cwd))
        tops.append(SDF_MODULE)
    for t in tops:
        cmd += ["-s", t]
    cmd += [f"-D{k}={v}" for k, v in defines.items()]
    cmd += [f"-I{d}" for d in include_dirs]
    cmd += [str(x) for x in srcs]
    print("Compiling:\n\t", shlex.join(cmd))
    subprocess.check_call(cmd, cwd=cwd)

    # -n: $stop ends the simulation instead of entering interactive mode
    subprocess.check_call(["vvp", "-n", "sim.vvp"], cwd=cwd)
