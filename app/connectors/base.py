"""Provider-neutral metadata and protocol used by external document connectors."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

SUPPORTED_CONNECTOR_PROVIDERS = frozenset({"google_drive", "dropbox", "gmail"})


@dataclass(frozen=True)
class ConnectorFile:
    source_file_id: str
    name: str
    mime_type: str | None = None
    size: int | None = None
    modified_at: datetime | None = None
    container_id: str | None = None


class DocumentConnector(Protocol):
    provider: str
    account_id: str

    def list_files(
        self, *, folder_id: str | None = None, limit: int = 100
    ) -> list[ConnectorFile]:
        """List files visible to the configured external account."""

    def download_file(self, source_file_id: str) -> bytes:
        """Download one file from the configured external account."""
