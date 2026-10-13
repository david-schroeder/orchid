# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: David Schröder 2026

"""Wrapper around ORDeC: runs ordec_worker.py in a subprocess per call.

ORDeC keeps process-wide state (ORDB, imported design modules, run directories relative
to the process cwd), so every call gets a fresh interpreter with cwd = the task directory.
Request and reply are JSON files in cwd (protocol: see ordec_worker.py).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

from ..pdk import Pdk

WORKER = Path(__file__).with_name("ordec_worker.py")


class OrdecError(RuntimeError):
    """An ORDeC action failed."""


def env(pdk: Pdk, path: list = []) -> dict[str, str]:
    """Process environment for ORDeC: PDK variables, path prepended to PYTHONPATH."""
    if pdk.ordec_module is None:
        raise RuntimeError(f"ORDeC does not support the {pdk.name} PDK.")
    e = os.environ | pdk.ordec_env()
    pythonpath = [str(p) for p in path] + [p for p in e.get("PYTHONPATH", "").split(os.pathsep) if p]
    if pythonpath:
        e["PYTHONPATH"] = os.pathsep.join(pythonpath)
    return e


def run(pdk: Pdk, request: dict, cwd: Path) -> dict:
    """Run one worker action in cwd and return its reply.

    request: action, module, cell, params, path (import roots) and action options;
    PDK entries are added here. Raises OrdecError if the action fails.
    """
    request = {"pdk": {
        "module": pdk.ordec_module,
        "drc": pdk.ordec_drc,
        "lvs": pdk.ordec_lvs,
        "max_layer": pdk.macro_max_layer,
    }} | request
    request["path"] = [str(p) for p in request.get("path", [])]
    request_file = cwd / "ordec_request.json"
    reply_file = cwd / "ordec_reply.json"
    request_file.write_text(json.dumps(request, indent=4))
    reply_file.unlink(missing_ok=True)

    # -P: the worker's directory (flow/tools, with this ordec.py) must not shadow the
    # ordec package. Output goes to the task log.
    cmd = [sys.executable, "-P", str(WORKER), str(request_file), str(reply_file)]
    proc = subprocess.run(cmd, cwd=cwd, env=env(pdk))
    if not reply_file.is_file():
        raise OrdecError(f"ORDeC worker exited with code {proc.returncode} without a reply "
                         f"(action {request.get('action')}).")
    reply = json.loads(reply_file.read_text())
    if reply["status"] != "ok":
        # The worker printed the traceback (task log); it is also in the reply file.
        raise OrdecError(f"ORDeC {request.get('action')} of {request.get('module')}:"
                         f"{request.get('cell')} failed: {reply['error']}")
    return reply


def ui(pdk: Pdk, module: str, cwd: Path, path: list = [], views: list[str] = []):
    """Open module in the ORDeC web UI (local mode); blocks until the server is stopped."""
    cmd = [sys.executable, "-m", "ordec", "-m", module]
    for v in views:
        cmd += ["-e", v]
    subprocess.run(cmd, cwd=cwd, env=env(pdk, path))
