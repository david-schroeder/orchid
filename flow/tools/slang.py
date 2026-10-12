# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: David Schröder 2026

"""Thin wrapper around slang (via pyslang) for SystemVerilog elaboration checks.

Synthesis reads the sources directly through the yosys-slang frontend (LibreLane
``USE_SLANG``); this wrapper runs the same parse/elaboration standalone, so errors
surface early and without Yosys.
"""

import shlex
from pathlib import Path


def slang_args(design_srcs, top=None, defines={}, include_dirs=[], cmdargs=[]) -> list[str]:
    """Build a slang command line (without program name)."""
    args = []
    if top is not None:
        args += ["--top", top]
    for k, v in defines.items():
        args.append(f"-D{k}={v}")
    for d in include_dirs:
        args.append(f"-I{d}")
    args += cmdargs
    args += map(str, design_srcs)
    return args


def elaborate(design_srcs, top=None, defines={}, include_dirs=[], cmdargs=[]):
    """Parse and elaborate the design with slang; raise on errors."""
    from pyslang import driver

    args = slang_args(design_srcs, top, defines, include_dirs, cmdargs)
    print("Elaborating design:\n\t", shlex.join(["slang", *args]))

    d = driver.Driver()
    d.addStandardArgs()
    if not d.parseCommandLine(shlex.join(["slang", *args]), driver.CommandLineOptions()):
        raise RuntimeError("slang: invalid command line")
    if not (d.processOptions() and d.parseAllSources()):
        raise RuntimeError("slang: failed to load sources")
    if not d.runFullCompilation(quiet=False):
        raise RuntimeError("slang: elaboration failed")


def lint(design_srcs, defines={}, include_dirs=[], cmdargs=[]):
    """Lint sources with slang without elaborating a full hierarchy; raise on errors."""
    elaborate(design_srcs, None, defines, include_dirs, ["--lint-only", "-Wextra", *cmdargs])
