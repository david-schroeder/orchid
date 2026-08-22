# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: David Schröder 2026

import subprocess
import shlex

def convert_sv2v(cwd, design_srcs, output, defines={}, cmdargs=[]):
    cmdline = [
        "sv2v",
        *design_srcs,
        "-w", output
    ]
    for k, v in defines.items():
        cmdline.append(f"--define={k}={v}")

    cmdline += cmdargs

    print("Compiling design:\n\t", shlex.join(cmdline))
    subprocess.check_call(cmdline, cwd=cwd)
