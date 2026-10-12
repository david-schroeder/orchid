# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2024 RVLab Contributors
# Modified by David Schröder 2026

"""Thin wrapper around verible-verilog-lint (optional style lint)."""

import shutil
import subprocess
from pathlib import Path

RULES = [
    'always-comb',
    'always-comb-blocking',
    'always-ff-non-blocking',
    'case-missing-default',
    'explicit-function-lifetime',
    'explicit-function-task-parameter-type',
    'explicit-parameter-storage-type',
    'explicit-task-lifetime',
    'forbid-consecutive-null-statements',
    'forbid-defparam',
    'forbid-line-continuations',
    'generate-label',
    'module-begin-block',
    'module-filename',
    'module-parameter',
    'module-port',
    'one-module-per-file',
    'package-filename',
    'packed-dimensions-range-ordering',
    #'port-name-suffix',
    'undersized-binary-literal',
    'v2001-generate-begin',
    'void-cast',
]


def lint(srcs: list, cwd: Path):
    """Style-lint SystemVerilog sources (.v files are skipped); warn on findings, skip if not installed."""
    if shutil.which('verible-verilog-lint') is None:
        print("verible-verilog-lint not found; skipping Verible style lint.")
        return

    lint_srcs = [str(fn) for fn in srcs if Path(fn).suffix != '.v']
    try:
        subprocess.check_call(['verible-verilog-lint', '--ruleset', 'none', '--rules', ",".join(RULES)]+lint_srcs, cwd=cwd)
    except subprocess.CalledProcessError as e:
        print(f"WARNING: verible-verilog-lint returned {e.returncode} errors.")
    else:
        print("Lint returned no errors.")
