"""Shared verification support: real subprocess and fixture helpers.

No planks: verification support carries none, per the Planking agreement.
"""

from __future__ import annotations

import re
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RIGGING_PATH = REPO_ROOT / "RIGGING.md"


def new_tmp_dir(context, prefix):
    """Create a namespaced temp dir and register its teardown on the context."""
    path = Path(tempfile.mkdtemp(prefix=prefix))
    context.add_cleanup(shutil.rmtree, path, ignore_errors=True)
    return path


def run(cmd, cwd=None, env=None, timeout=None):
    """Run a real subprocess and capture its result."""
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env, timeout=timeout)


def read_rigging_command(key):
    """Read the single-line backtick command value for `key` under RIGGING.md's
    ## Commands heading, per the Rigging read contract."""
    text = RIGGING_PATH.read_text(encoding="utf-8")
    match = re.search(rf"^- {re.escape(key)}: `(.+)`$", text, re.MULTILINE)
    if not match:
        raise ValueError(f"no {key!r} command found in RIGGING.md")
    return match.group(1)


def run_rigging_command(key, scenario_args=None, cwd=None, timeout=None):
    """Run a RIGGING.md command for real, substituting the {scenario}
    placeholder token with scenario_args (a list of scenario references)
    when the command carries one.

    Runs through a real shell rather than shlex-splitting: the command
    string embeds a shell-double-quoted Python literal (`'\\$'`), and only
    a real shell's double-quote backslash rule reduces it to the intended
    regex end-anchor. shlex.split does not replicate that rule and yields
    a mismatched anchor, a QM-side harness defect rather than a product one.
    """
    template = read_rigging_command(key)
    if scenario_args is not None:
        quoted = " ".join(shlex.quote(a) for a in scenario_args)
        template = template.replace("{scenario}", quoted)
    return subprocess.run(
        template, shell=True, cwd=cwd or REPO_ROOT,
        capture_output=True, text=True, timeout=timeout,
    )
