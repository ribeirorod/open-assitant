"""Docker Compose helpers — detects plugin vs standalone, finds project dir."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import typer


def compose_cmd() -> list[str]:
    """Return ['docker', 'compose'] or ['docker-compose'] depending on what's installed."""
    try:
        subprocess.run(
            ["docker", "compose", "version"],
            capture_output=True,
            check=True,
        )
        return ["docker", "compose"]
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    try:
        subprocess.run(
            ["docker-compose", "version"],
            capture_output=True,
            check=True,
        )
        return ["docker-compose"]
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    typer.echo(
        "Docker Compose not found. "
        "Install Docker Desktop or the compose plugin: https://docs.docker.com/compose/install/",
        err=True,
    )
    raise typer.Exit(1)


def find_project_dir(project_dir: Path | None) -> Path:
    """
    Resolve the directory that contains docker-compose.yaml.

    Checks (in order):
      1. --project-dir flag if given
      2. Current working directory
      3. Package-bundled data directory (for pip-installed users who haven't initialised yet)

    Exits with a helpful message if none are found.
    """
    candidates: list[Path] = []

    if project_dir:
        candidates.append(project_dir)
    else:
        candidates.append(Path.cwd())

    for d in candidates:
        if (d / "docker-compose.yaml").exists():
            return d

    # No compose file found — guide the user
    typer.echo(
        "\n  docker-compose.yaml not found.\n\n"
        "  If you installed open-assistant via pip, initialise a project directory first:\n\n"
        "    open-assistant init          # creates docker-compose.yaml + .env.example here\n"
        "    open-assistant setup         # interactive setup wizard\n\n"
        "  Or clone the repository and run from inside it:\n\n"
        "    git clone -b public https://github.com/ribeirorod/open-assitant.git\n"
        "    cd open-assitant\n"
        "    open-assistant setup\n",
        err=True,
    )
    raise typer.Exit(1)


def run_compose(args: list[str], project_dir: Path) -> int:
    """Run a docker compose command in the given project directory. Returns exit code."""
    cmd = compose_cmd() + args
    result = subprocess.run(cmd, cwd=project_dir)
    return result.returncode
