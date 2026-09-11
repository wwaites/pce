"""Shared verification support: real subprocess and fixture helpers.

No planks: verification support carries none, per the Planking agreement.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def new_tmp_dir(context, prefix):
    """Create a namespaced temp dir and register its teardown on the context."""
    path = Path(tempfile.mkdtemp(prefix=prefix))
    context.add_cleanup(shutil.rmtree, path, ignore_errors=True)
    return path


def run(cmd, cwd=None, env=None, timeout=None):
    """Run a real subprocess and capture its result."""
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env, timeout=timeout)
