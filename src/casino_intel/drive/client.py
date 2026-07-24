"""Drive API client: archive uploads, content hashing, folder-path management
(research.md decision, source doc §9.6).

Large raw content (documents, screenshots, extracted text/JSON) is always
archived here and referenced by path + hash from the fact sheets — never
stored inline in a Sheets cell (spec FR-012, source doc §17.2).
"""

from __future__ import annotations

import hashlib
import io
import os
from typing import Any

from googleapiclient.discovery import Resource, build
from googleapiclient.http import MediaIoBaseUpload

from casino_intel.sheets.client import build_credentials

ROOT_FOLDER_NAME = "Casino Competitive Intelligence"

#: Drive folder hierarchy per source doc §9.6.
ARCHIVE_SUBFOLDERS = [
    "sources/regulators",
    "sources/operators",
    "sources/brands",
    "sources/traffic",
    "sources/app-stores",
    "sources/reviews",
    "extracted/text",
    "extracted/tables",
    "extracted/json",
    "screenshots/brand",
    "exports",
    "logs",
]


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class DriveClient:
    """Wrapper over the Drive API v3 for archiving pipeline artifacts."""

    def __init__(self, service: Resource | None = None, root_folder_id: str | None = None) -> None:
        self._service = service or build("drive", "v3", credentials=build_credentials())
        self._root_folder_id = root_folder_id or os.environ.get("DRIVE_ROOT_FOLDER_ID")
        self._folder_cache: dict[str, str] = {}

    def ensure_root_folder(self) -> str:
        """Return the root archive folder's ID, creating it if necessary."""
        if self._root_folder_id:
            return self._root_folder_id
        self._root_folder_id = self._ensure_folder(ROOT_FOLDER_NAME, parent_id=None)
        return self._root_folder_id

    def _ensure_folder(self, name: str, parent_id: str | None) -> str:
        cache_key = f"{parent_id}/{name}"
        if cache_key in self._folder_cache:
            return self._folder_cache[cache_key]

        query = (
            f"name = '{name}' and "
            "mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        )
        if parent_id:
            query += f" and '{parent_id}' in parents"
        # supportsAllDrives/includeItemsFromAllDrives are required for the
        # archive to live on a Shared Drive — service accounts have no My Drive
        # storage quota, so a Shared Drive (or delegation) is the only place
        # they can create files (see drive/client.py module note / README).
        results = (
            self._service.files()
            .list(
                q=query,
                fields="files(id, name)",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
            .execute()
        )
        files = results.get("files", [])
        if files:
            folder_id = files[0]["id"]
        else:
            metadata: dict[str, Any] = {
                "name": name,
                "mimeType": "application/vnd.google-apps.folder",
            }
            if parent_id:
                metadata["parents"] = [parent_id]
            folder = (
                self._service.files()
                .create(body=metadata, fields="id", supportsAllDrives=True)
                .execute()
            )
            folder_id = folder["id"]

        self._folder_cache[cache_key] = folder_id
        return folder_id

    def ensure_archive_path(self, relative_path: str) -> str:
        """Ensure a nested folder path (e.g. 'sources/regulators') exists
        under the root archive folder, returning the leaf folder's ID."""
        parent_id = self.ensure_root_folder()
        for segment in relative_path.strip("/").split("/"):
            parent_id = self._ensure_folder(segment, parent_id)
        return parent_id

    def upload(
        self, relative_folder: str, filename: str, content: bytes, mime_type: str
    ) -> tuple[str, str, str]:
        """Upload `content` to `relative_folder/filename`, returning
        (file_id, archive_path, content_hash)."""
        folder_id = self.ensure_archive_path(relative_folder)
        content_hash = sha256_bytes(content)
        media = MediaIoBaseUpload(io.BytesIO(content), mimetype=mime_type, resumable=False)
        metadata = {"name": filename, "parents": [folder_id]}
        uploaded = (
            self._service.files()
            .create(body=metadata, media_body=media, fields="id", supportsAllDrives=True)
            .execute()
        )
        archive_path = f"{ROOT_FOLDER_NAME}/{relative_folder}/{filename}"
        return uploaded["id"], archive_path, content_hash
