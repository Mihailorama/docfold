"""One-click MCP registration — ``docfold install <client>``.

Registers the ``docfold-mcp`` stdio server into an AI coding client.
Clients with their own registration CLI (Claude Code, Codex, VS Code) get
that CLI invoked when it is on PATH; Cursor gets ``~/.cursor/mcp.json``
merged in place; ``generic`` prints the standard ``mcpServers`` JSON for
any other client.

Pure planning/merging logic lives here so it is unit-testable; the argparse
wiring lives in :mod:`docfold.cli`.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

SERVER_NAME = "docfold"
SERVER_COMMAND = "docfold-mcp"

CLIENTS = ("claude", "codex", "cursor", "vscode", "generic")


def server_entry() -> dict[str, object]:
    """The standard stdio server entry for ``mcpServers``-style configs."""
    return {"command": SERVER_COMMAND, "args": []}


def mcp_config() -> dict[str, object]:
    """Full generic config snippet: ``{"mcpServers": {"docfold": ...}}``."""
    return {"mcpServers": {SERVER_NAME: server_entry()}}


@dataclass(frozen=True)
class InstallPlan:
    """What ``docfold install <client>`` will do."""

    client: str
    kind: Literal["run", "merge-json", "print"]
    argv: tuple[str, ...] = ()
    """Command to execute (``kind="run"``) or to show the user."""
    path: Path | None = None
    """Config file to merge (``kind="merge-json"``)."""


def plan_install(client: str, home: Path | None = None) -> InstallPlan:
    """Build the install plan for ``client``. Raises ValueError if unknown."""
    home = home or Path.home()
    argv: tuple[str, ...]

    if client == "claude":
        argv = ("claude", "mcp", "add", SERVER_NAME, "--", SERVER_COMMAND)
        kind: Literal["run", "print"] = "run" if shutil.which("claude") else "print"
        return InstallPlan(client=client, kind=kind, argv=argv)

    if client == "codex":
        argv = ("codex", "mcp", "add", SERVER_NAME, "--", SERVER_COMMAND)
        kind = "run" if shutil.which("codex") else "print"
        return InstallPlan(client=client, kind=kind, argv=argv)

    if client == "vscode":
        payload = json.dumps({"name": SERVER_NAME, "command": SERVER_COMMAND, "args": []})
        argv = ("code", "--add-mcp", payload)
        kind = "run" if shutil.which("code") else "print"
        return InstallPlan(client=client, kind=kind, argv=argv)

    if client == "cursor":
        return InstallPlan(client=client, kind="merge-json", path=home / ".cursor" / "mcp.json")

    if client == "generic":
        return InstallPlan(client=client, kind="print")

    raise ValueError(f"unknown client {client!r}; expected one of: {', '.join(CLIENTS)}")


def merge_mcp_json(path: Path) -> bool:
    """Merge the docfold server into an ``mcpServers`` JSON file.

    Creates the file (and parents) if missing. Returns True if the file
    changed, False if docfold was already registered identically.
    """
    config: dict[str, object] = {}
    if path.exists():
        text = path.read_text().strip()
        if text:
            config = json.loads(text)

    servers = config.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        raise ValueError(f"{path}: 'mcpServers' is not an object")

    if servers.get(SERVER_NAME) == server_entry():
        return False

    servers[SERVER_NAME] = server_entry()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2) + "\n")
    return True


def apply_plan(plan: InstallPlan, *, print_only: bool = False) -> str:
    """Execute (or describe) an install plan. Returns a human-readable message."""
    config_json = json.dumps(mcp_config(), indent=2)

    if plan.kind == "print" and plan.argv:
        return (
            f"{plan.client}: CLI not found on PATH. Run this once it is installed:\n\n"
            f"    {' '.join(plan.argv)}\n"
        )

    if plan.kind == "print":
        return (
            "Add this to your client's MCP settings "
            f"(requires: pip install 'docfold[mcp]'):\n\n{config_json}\n"
        )

    if plan.kind == "run":
        if print_only:
            return f"Would run:\n\n    {' '.join(plan.argv)}\n"
        subprocess.run(plan.argv, check=True)
        return f"Registered '{SERVER_NAME}' MCP server via: {' '.join(plan.argv)}"

    # merge-json (cursor)
    assert plan.path is not None
    if print_only:
        return f"Would merge into {plan.path}:\n\n{config_json}\n"
    changed = merge_mcp_json(plan.path)
    if changed:
        return f"Registered '{SERVER_NAME}' MCP server in {plan.path}"
    return f"'{SERVER_NAME}' MCP server already registered in {plan.path}"
