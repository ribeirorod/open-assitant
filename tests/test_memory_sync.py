"""Tests for src.memory.sync — GDrive ↔ local memory synchronisation."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.memory.sync import (
    MEMORY_DIR,
    SYNC_META,
    _load_sync_meta,
    _save_sync_meta,
    is_gdrive_available,
    pull,
    push,
    sync,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FAKE_FOLDER_ID = "folder_abc123"
FAKE_MEMORY_FOLDER_ID = "folder_mem456"


def _mock_gws_folder_lookup(name: str, parent_id: str | None = None):
    """Return a mock gws response for folder lookups."""
    if name == "open_assistant" and parent_id is None:
        return (0, json.dumps({"files": [{"id": FAKE_FOLDER_ID, "name": "open_assistant"}]}), "")
    if name == "memory" and parent_id == FAKE_FOLDER_ID:
        return (0, json.dumps({"files": [{"id": FAKE_MEMORY_FOLDER_ID, "name": "memory"}]}), "")
    return (0, json.dumps({"files": []}), "")


# ---------------------------------------------------------------------------
# Sync metadata persistence
# ---------------------------------------------------------------------------


def test_sync_meta_roundtrip(tmp_path, monkeypatch):
    meta_file = tmp_path / ".sync-meta.json"
    monkeypatch.setattr("src.memory.sync.SYNC_META", meta_file)
    monkeypatch.setattr("src.memory.sync.MEMORY_DIR", tmp_path)

    data = {"index.md": "2026-01-01T00:00:00+00:00", "projects.md": "2026-01-02T00:00:00+00:00"}
    _save_sync_meta(data)
    assert meta_file.exists()
    loaded = _load_sync_meta()
    assert loaded == data


def test_load_sync_meta_missing(tmp_path, monkeypatch):
    monkeypatch.setattr("src.memory.sync.SYNC_META", tmp_path / "nope.json")
    assert _load_sync_meta() == {}


def test_load_sync_meta_corrupt(tmp_path, monkeypatch):
    meta_file = tmp_path / ".sync-meta.json"
    meta_file.write_text("not json!")
    monkeypatch.setattr("src.memory.sync.SYNC_META", meta_file)
    assert _load_sync_meta() == {}


# ---------------------------------------------------------------------------
# is_gdrive_available
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gdrive_available_true():
    async def fake_run(*args, **kw):
        return (0, json.dumps({"files": [{"id": "x", "name": "open_assistant"}]}), "")

    with patch("src.memory.sync._run_gws", side_effect=fake_run):
        assert await is_gdrive_available() is True


@pytest.mark.asyncio
async def test_gdrive_available_false():
    async def fake_run(*args, **kw):
        return (0, json.dumps({"files": []}), "")

    with patch("src.memory.sync._run_gws", side_effect=fake_run):
        assert await is_gdrive_available() is False


# ---------------------------------------------------------------------------
# pull
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pull_skips_when_no_gdrive(tmp_path, monkeypatch):
    monkeypatch.setattr("src.memory.sync.MEMORY_DIR", tmp_path)

    with patch("src.memory.sync._get_memory_folder_id", return_value=None):
        result = await pull()
    assert result == {}


@pytest.mark.asyncio
async def test_pull_downloads_new_file(tmp_path, monkeypatch):
    monkeypatch.setattr("src.memory.sync.MEMORY_DIR", tmp_path)
    monkeypatch.setattr("src.memory.sync.SYNC_META", tmp_path / ".sync-meta.json")

    remote_files = [{"id": "file1", "name": "index.md", "modifiedTime": "2026-03-01T00:00:00Z"}]

    async def fake_download(file_id, dest):
        dest.write_text("# Index\n")
        return True

    with (
        patch("src.memory.sync._get_memory_folder_id", return_value=FAKE_MEMORY_FOLDER_ID),
        patch("src.memory.sync._list_remote_files", return_value=remote_files),
        patch("src.memory.sync._download_file", side_effect=fake_download),
    ):
        result = await pull()

    assert result == {"index.md": "pulled"}
    assert (tmp_path / "index.md").read_text() == "# Index\n"


@pytest.mark.asyncio
async def test_pull_skips_up_to_date(tmp_path, monkeypatch):
    monkeypatch.setattr("src.memory.sync.MEMORY_DIR", tmp_path)
    monkeypatch.setattr("src.memory.sync.SYNC_META", tmp_path / ".sync-meta.json")

    # Local file exists and meta says it's already synced
    (tmp_path / "index.md").write_text("# Index\n")
    _save_sync_meta_at = tmp_path / ".sync-meta.json"
    _save_sync_meta_at.write_text(json.dumps({"index.md": "2026-03-01T00:00:00Z"}))

    remote_files = [{"id": "file1", "name": "index.md", "modifiedTime": "2026-03-01T00:00:00Z"}]

    with (
        patch("src.memory.sync._get_memory_folder_id", return_value=FAKE_MEMORY_FOLDER_ID),
        patch("src.memory.sync._list_remote_files", return_value=remote_files),
    ):
        result = await pull()

    assert result == {"index.md": "up-to-date"}


# ---------------------------------------------------------------------------
# push
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_push_uploads_file(tmp_path, monkeypatch):
    monkeypatch.setattr("src.memory.sync.MEMORY_DIR", tmp_path)
    monkeypatch.setattr("src.memory.sync.SYNC_META", tmp_path / ".sync-meta.json")

    (tmp_path / "index.md").write_text("# Index\n")

    async def fake_upload(local_path, folder_id, existing_id=None):
        return "new_file_id"

    with (
        patch("src.memory.sync._get_memory_folder_id", return_value=FAKE_MEMORY_FOLDER_ID),
        patch("src.memory.sync._list_remote_files", return_value=[]),
        patch("src.memory.sync._upload_file", side_effect=fake_upload),
    ):
        result = await push(["index.md"])

    assert result == {"index.md": "pushed"}


@pytest.mark.asyncio
async def test_push_skips_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr("src.memory.sync.MEMORY_DIR", tmp_path)
    monkeypatch.setattr("src.memory.sync.SYNC_META", tmp_path / ".sync-meta.json")

    with (
        patch("src.memory.sync._get_memory_folder_id", return_value=FAKE_MEMORY_FOLDER_ID),
        patch("src.memory.sync._list_remote_files", return_value=[]),
    ):
        result = await push(["nonexistent.md"])

    assert result == {"nonexistent.md": "missing"}


@pytest.mark.asyncio
async def test_push_skips_when_no_gdrive(tmp_path, monkeypatch):
    monkeypatch.setattr("src.memory.sync.MEMORY_DIR", tmp_path)

    with patch("src.memory.sync._get_memory_folder_id", return_value=None):
        result = await push(["index.md"])
    assert result == {}


# ---------------------------------------------------------------------------
# full sync
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_pulls_then_pushes(tmp_path, monkeypatch):
    monkeypatch.setattr("src.memory.sync.MEMORY_DIR", tmp_path)
    monkeypatch.setattr("src.memory.sync.SYNC_META", tmp_path / ".sync-meta.json")

    # Local file that's not on remote
    (tmp_path / "local-only.md").write_text("local\n")

    pull_mock = AsyncMock(return_value={"remote.md": "pulled"})
    push_mock = AsyncMock(return_value={"local-only.md": "pushed"})

    with (
        patch("src.memory.sync.pull", pull_mock),
        patch("src.memory.sync._get_memory_folder_id", return_value=FAKE_MEMORY_FOLDER_ID),
        patch("src.memory.sync._list_remote_files", return_value=[]),
        patch("src.memory.sync.push", push_mock),
    ):
        result = await sync()

    assert "remote.md" in result
    pull_mock.assert_awaited_once()
