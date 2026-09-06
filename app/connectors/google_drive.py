"""Read-only Google Drive connector with injectable authenticated API service."""

import io
from datetime import datetime
from typing import Any

from app.connectors.base import ConnectorFile

GOOGLE_DRIVE_READONLY_SCOPE = "https://www.googleapis.com/auth/drive.readonly"


class GoogleDriveConnector:
    provider = "google_drive"

    def __init__(self, service: Any, account_id: str):
        self.service = service
        self.account_id = account_id

    @classmethod
    def from_credentials(cls, credentials: Any, account_id: str):
        try:
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise RuntimeError(
                "Google Drive support requires google-api-python-client."
            ) from exc
        return cls(build("drive", "v3", credentials=credentials), account_id)

    @classmethod
    def from_service_account_info(cls, info: dict[str, Any], account_id: str):
        try:
            from google.oauth2 import service_account
        except ImportError as exc:
            raise RuntimeError("Google Drive support requires google-auth.") from exc
        credentials = service_account.Credentials.from_service_account_info(
            info, scopes=[GOOGLE_DRIVE_READONLY_SCOPE]
        )
        return cls.from_credentials(credentials, account_id)

    @classmethod
    def from_access_token(cls, access_token: str, account_id: str):
        if not access_token.strip():
            raise ValueError("A Google Drive access token is required.")
        try:
            from google.oauth2.credentials import Credentials
        except ImportError as exc:
            raise RuntimeError("Google Drive support requires google-auth.") from exc
        credentials = Credentials(
            token=access_token,
            scopes=[GOOGLE_DRIVE_READONLY_SCOPE],
        )
        return cls.from_credentials(credentials, account_id)

    def list_files(
        self, *, folder_id: str | None = None, limit: int = 100
    ) -> list[ConnectorFile]:
        bounded_limit = max(1, min(limit, 1000))
        query = "trashed = false"
        if folder_id:
            query += f" and '{folder_id}' in parents"

        response = (
            self.service.files()
            .list(
                q=query,
                pageSize=bounded_limit,
                fields="files(id,name,mimeType,size,modifiedTime,parents),nextPageToken",
            )
            .execute()
        )
        files = []
        for item in response.get("files", []):
            modified_at = item.get("modifiedTime")
            files.append(
                ConnectorFile(
                    source_file_id=item["id"],
                    name=item.get("name") or item["id"],
                    mime_type=item.get("mimeType"),
                    size=int(item["size"]) if item.get("size") else None,
                    modified_at=(
                        datetime.fromisoformat(modified_at.replace("Z", "+00:00"))
                        if modified_at
                        else None
                    ),
                    container_id=(item.get("parents") or [None])[0],
                )
            )
        return files

    def download_file(self, source_file_id: str) -> bytes:
        try:
            from googleapiclient.http import MediaIoBaseDownload
        except ImportError as exc:
            raise RuntimeError(
                "Google Drive support requires google-api-python-client."
            ) from exc

        request = self.service.files().get_media(fileId=source_file_id)
        output = io.BytesIO()
        downloader = MediaIoBaseDownload(output, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return output.getvalue()
