# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2024 RVLab Contributors

from notcl import TclTool
import os
from pathlib import Path

class Vivado(TclTool):
    called_object_pos = "last"
    
    def cmdline(self):
        return ["vivado",
            "-mode", "tcl",
            #"-nolog",
            "-nojournal",
            "-source", self.script_name()
        ]

def vivado_dir():
    return Path(os.environ["XILINX_VIVADO"])
