"""Bi-directional sync between local memory files and Google Drive.

On startup every agent instance pulls the latest memory from GDrive into the
local ``~/.open-assistant/memory/`` directory.  After any local write the
changed file is pushed back so that other agent instances (or a future
container) see the update immediately.

Conflict resolution: **last-write-wins** using GDrive ``modifiedTime``.
Each file is compared individually — only files that are newer on the remote
side overwrite local copies during pull, and vice-versa during push.

Requires the ``gws`` CLI (Google Workspace CLI) to be installed and
authenticated.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from src.config import settings

log = logging.getLogger(__name__)

MEMORY_DIR = Path.home() / ".open-assistant" / "memory"
SYNC_META = MEMORY_DIR / ".sync-meta.json"

# GDrive folder name at drive root
_GDRIVE_FOLDER = "open_assistant"
# Subfolder inside GDrive folder for active memory
_GDRIVE_MEMORY_SUBFOLDER = "memory"


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------


async def _run_gws(*args: str, timeout: float = 30, cwd: Path | None = None) -> tuple[int, str, str]:
    """Run a ``gws`` CLI command and return (returncode, stdout, stderr)."""
    cmd = [settings.gws_binary, *args]
    log.debug("gws command: %s", " ".join(cmd))
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(cwd) if cwd else None,
    )
    try:
        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return -1, "", "timeout"
    return proc.returncode, stdout_b.decode(), stderr_b.decode()


def _load_sync_meta() -> dict[str, str]:
    """Return ``{filename: iso_modified_time}`` from the local sync metadata."""
    if SYNC_META.exists():
        try:
            return json.loads(SYNC_META.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_sync_meta(meta: dict[str, str]) -> None:
    SYNC_META.parent.mkdir(parents=True, exist_ok=True)
    SYNC_META.write_text(json.dumps(meta, indent=2) + "\n")


# ---------------------------------------------------------------------------
# GDrive folder resolution
# ---------------------------------------------------------------------------


async def _find_folder_id(name: str, parent_id: str | None = None) -> str | None:
    """Return the GDrive file-id of a folder by *name*, optionally under *parent_id*."""
    q = f'name="{name}" and mimeType="application/vnd.google-apps.folder" and trashed=false'
    if parent_id:
        q += f' and "{parent_id}" in parents'
    rc, out, err = await _run_gws(
        "drive", "files", "list",
        "--params", json.dumps({"q": q, "pageSize": 1, "fields": "files(id,name)"}),
    )
    if rc != 0:
        log.warning("gws drive files list failed: %s", err)
        return None
    try:
        data = json.loads(out)
        files = data.get("files", [])
        return files[0]["id"] if files else None
    except (json.JSONDecodeError, KeyError, IndexError):
        return None


async def _ensure_folder(name: str, parent_id: str | None = None) -> str | None:
    """Return the id of folder *name*, creating it if necessary."""
    fid = await _find_folder_id(name, parent_id)
    if fid:
        return fid
    # Create the folder
    metadata: dict[str, object] = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    if parent_id:
        metadata["parents"] = [parent_id]
    rc, out, err = await _run_gws(
        "drive", "files", "create",
        "--params", json.dumps({"fields": "id"}),
        "--json", json.dumps(metadata),
    )
    if rc != 0:
        log.error("failed to create folder %s: %s", name, err)
        return None
    try:
        return json.loads(out).get("id")
    except (json.JSONDecodeError, KeyError):
        return None


async def _get_memory_folder_id() -> str | None:
    """Resolve (or create) ``open_assistant/memory/`` on GDrive and return its id."""
    root_id = await _ensure_folder(_GDRIVE_FOLDER)
    if not root_id:
        return None
    return await _ensure_folder(_GDRIVE_MEMORY_SUBFOLDER, parent_id=root_id)


# ---------------------------------------------------------------------------
# List remote memory files
# ---------------------------------------------------------------------------


async def _list_remote_files(folder_id: str) -> list[dict]:
    """Return list of ``{id, name, modifiedTime}`` for files in *folder_id*."""
    q = f'"{folder_id}" in parents and trashed=false'
    rc, out, err = await _run_gws(
        "drive", "files", "list",
        "--params", json.dumps({
            "q": q,
            "pageSize": 50,
            "fields": "files(id,name,modifiedTime)",
        }),
    )
    if rc != 0:
        log.warning("listing remote memory files failed: %s", err)
        return []
    try:
        return json.loads(out).get("files", [])
    except (json.JSONDecodeError, KeyError):
        return []


# ---------------------------------------------------------------------------
# Download / Upload
# ---------------------------------------------------------------------------


async def _download_file(file_id: str, dest: Path) -> bool:
    """Download a GDrive file by *file_id* to *dest*.

    gws requires --upload/-o paths to be relative within cwd, so we run
    from the destination directory and use just the filename.
    """
    cwd = dest.parent
    name = dest.name
    # Plain Drive files: use get with alt=media
    rc, out, err = await _run_gws(
        "drive", "files", "get",
        "--params", json.dumps({"fileId": file_id, "alt": "media"}),
        "-o", name,
        cwd=cwd,
    )
    if rc != 0:
        # Google Docs files: use export
        rc, out, err = await _run_gws(
            "drive", "files", "export",
            "--params", json.dumps({"fileId": file_id, "mimeType": "text/plain"}),
            "-o", name,
            cwd=cwd,
        )
    return rc == 0


async def _upload_file(local_path: Path, folder_id: str, existing_id: str | None = None) -> str | None:
    """Upload *local_path* to GDrive. Update in-place if *existing_id* given.

    Returns the file id on success, None on failure.
    """
    if existing_id:
        # Update existing file — fileId via --params, upload relative path
        rc, out, err = await _run_gws(
            "drive", "files", "update",
            "--params", json.dumps({"fileId": existing_id, "fields": "id"}),
            "--upload", local_path.name,
            cwd=local_path.parent,
        )
    else:
        # Create new file in the folder
        metadata = json.dumps({"name": local_path.name, "parents": [folder_id]})
        rc, out, err = await _run_gws(
            "drive", "files", "create",
            "--json", metadata,
            "--upload", local_path.name,
            "--params", json.dumps({"fields": "id"}),
            cwd=local_path.parent,
        )
    if rc != 0:
        log.error("upload failed for %s: %s", local_path.name, err)
        return None
    try:
        return json.loads(out).get("id", existing_id)
    except (json.JSONDecodeError, KeyError):
        return existing_id


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def pull(*, force: bool = False) -> dict[str, str]:
    """Pull memory files from GDrive → local.  Returns ``{filename: action}``."""
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    folder_id = await _get_memory_folder_id()
    if not folder_id:
        log.warning("GDrive memory folder not available — skipping pull")
        return {}

    remote_files = await _list_remote_files(folder_id)
    if not remote_files:
        log.info("no remote memory files found")
        return {}

    meta = _load_sync_meta()
    results: dict[str, str] = {}

    for rf in remote_files:
        name = rf["name"]
        remote_modified = rf.get("modifiedTime", "")
        local_path = MEMORY_DIR / name

        # Decide whether to download
        if not force and local_path.exists():
            last_synced = meta.get(name, "")
            if last_synced and remote_modified <= last_synced:
                results[name] = "up-to-date"
                continue

        ok = await _download_file(rf["id"], local_path)
        if ok:
            meta[name] = remote_modified
            results[name] = "pulled"
            log.info("pulled %s from GDrive", name)
        else:
            results[name] = "error"
            log.error("failed to pull %s", name)

    _save_sync_meta(meta)
    return results


async def push(files: list[str] | None = None) -> dict[str, str]:
    """Push local memory files → GDrive.  If *files* is None, push all ``.md`` files."""
    folder_id = await _get_memory_folder_id()
    if not folder_id:
        log.warning("GDrive memory folder not available — skipping push")
        return {}

    if files is None:
        files = [p.name for p in MEMORY_DIR.glob("*.md")]

    # Build lookup of existing remote files
    remote_files = await _list_remote_files(folder_id)
    remote_by_name: dict[str, dict] = {rf["name"]: rf for rf in remote_files}

    meta = _load_sync_meta()
    results: dict[str, str] = {}

    for name in files:
        local_path = MEMORY_DIR / name
        if not local_path.exists():
            results[name] = "missing"
            continue

        existing = remote_by_name.get(name)
        fid = await _upload_file(local_path, folder_id, existing_id=existing["id"] if existing else None)
        if fid:
            now_iso = datetime.now(timezone.utc).isoformat()
            meta[name] = now_iso
            results[name] = "pushed"
            log.info("pushed %s to GDrive", name)
        else:
            results[name] = "error"

    _save_sync_meta(meta)
    return results


async def sync() -> dict[str, str]:
    """Full bi-directional sync: pull then push.

    Pull brings remote-only or remote-newer files down.
    Push sends local-only or local-newer files up.
    """
    results: dict[str, str] = {}

    # 1. Pull remote → local (remote wins if newer)
    pull_results = await pull()
    for name, action in pull_results.items():
        results[name] = f"pull:{action}"

    # 2. Push local → remote (pushes files not yet on remote or modified locally)
    folder_id = await _get_memory_folder_id()
    if not folder_id:
        return results

    remote_files = await _list_remote_files(folder_id)
    remote_by_name = {rf["name"]: rf for rf in remote_files}
    meta = _load_sync_meta()

    local_files = list(MEMORY_DIR.glob("*.md"))
    to_push: list[str] = []
    for lf in local_files:
        name = lf.name
        if name not in remote_by_name:
            # Local-only file → push
            to_push.append(name)
        else:
            # Compare local mtime vs last sync time
            local_mtime = datetime.fromtimestamp(lf.stat().st_mtime, tz=timezone.utc).isoformat()
            last_synced = meta.get(name, "")
            if not last_synced or local_mtime > last_synced:
                to_push.append(name)

    if to_push:
        push_results = await push(to_push)
        for name, action in push_results.items():
            results[name] = f"push:{action}"

    return results


async def is_gdrive_available() -> bool:
    """Quick check whether GDrive is reachable and authenticated."""
    folder_id = await _find_folder_id(_GDRIVE_FOLDER)
    return folder_id is not None
