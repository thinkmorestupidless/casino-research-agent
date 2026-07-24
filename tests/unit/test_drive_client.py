"""DriveClient must pass the all-drives flags so the archive can live on a
Shared Drive — service accounts have no My Drive storage quota, so a Shared
Drive is the only place they can create files."""

from __future__ import annotations

from typing import Any

from casino_intel.drive.client import DriveClient


class _RecordingDriveService:
    def __init__(self) -> None:
        self._next_id = 1
        self.create_calls: list[dict[str, Any]] = []
        self.list_calls: list[dict[str, Any]] = []
        self._pending: tuple[str, dict[str, Any]] = ("", {})

    def files(self) -> _RecordingDriveService:
        return self

    def list(self, **kwargs: Any) -> _RecordingDriveService:
        self.list_calls.append(kwargs)
        self._pending = ("list", kwargs)
        return self

    def create(self, **kwargs: Any) -> _RecordingDriveService:
        self.create_calls.append(kwargs)
        self._pending = ("create", kwargs)
        return self

    def execute(self) -> dict[str, Any]:
        kind, _ = self._pending
        if kind == "list":
            return {"files": []}  # always "not found" -> forces a create
        file_id = f"file-{self._next_id}"
        self._next_id += 1
        return {"id": file_id}


def test_upload_passes_supports_all_drives_on_every_create_and_list():
    service = _RecordingDriveService()
    client = DriveClient(service=service, root_folder_id="shared-drive-folder")

    file_id, archive_path, content_hash = client.upload(
        "sources/regulators", "ukgc.html", b"<html/>", "text/html"
    )

    assert file_id.startswith("file-")
    assert archive_path.endswith("sources/regulators/ukgc.html")
    assert content_hash  # sha256 hex

    # Every folder-existence check must include items from all drives...
    assert service.list_calls, "expected at least one folder lookup"
    assert all(c.get("supportsAllDrives") for c in service.list_calls)
    assert all(c.get("includeItemsFromAllDrives") for c in service.list_calls)
    # ...and every create (folders + the file upload) must support all drives,
    # otherwise the Shared Drive parent is rejected.
    assert service.create_calls, "expected folder/file creates"
    assert all(c.get("supportsAllDrives") for c in service.create_calls)
