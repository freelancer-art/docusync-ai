"""Credential-free connector doubles for deterministic local testing."""

from collections.abc import Iterable

from app.connectors.base import ConnectorFile


class MockConnector:
    """Deterministic connector for local development and ingestion tests."""

    provider = "mock"

    def __init__(
        self,
        files: Iterable[tuple[ConnectorFile, bytes]],
        account_id: str = "mock-account",
    ):
        self.account_id = account_id
        self._files = {
            metadata.source_file_id: (metadata, content) for metadata, content in files
        }

    def list_files(
        self, *, folder_id: str | None = None, limit: int = 100
    ) -> list[ConnectorFile]:
        files = [
            metadata
            for metadata, _ in self._files.values()
            if folder_id is None or getattr(metadata, "container_id", None) == folder_id
        ]
        return files[: max(1, min(limit, 1000))]

    def download_file(self, source_file_id: str) -> bytes:
        try:
            return self._files[source_file_id][1]
        except KeyError as exc:
            raise FileNotFoundError(
                f"Mock connector file {source_file_id} was not found."
            ) from exc


class MockDropboxConnector(MockConnector):
    provider = "dropbox"


class MockGmailConnector(MockConnector):
    provider = "gmail"
