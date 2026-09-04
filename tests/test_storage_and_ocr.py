import pytest

from app.core.ocr_engine import ocr_engine
from app.services.storage_service import StorageService, storage_service


def test_storage_service_local_flow(tmp_path):
    filename = "test_document.txt"
    content = b"Sample document payload for testing storage service."

    # Save
    saved_name = storage_service.save_file(filename, content)
    assert saved_name == filename

    # Retrieve
    retrieved = storage_service.get_file_bytes(filename)
    assert retrieved == content

    # URL
    url = storage_service.get_file_url(filename)
    assert "/storage/uploads/test_document.txt" in url


def test_storage_service_file_not_found():
    with pytest.raises(FileNotFoundError):
        storage_service.get_file_bytes("non_existent_file_12345.bin")


def test_ocr_engine_invalid_input():
    result = ocr_engine.extract_text(b"not a valid pdf content")
    assert result == ""


def test_storage_service_supabase_success(monkeypatch):
    class FakeBucket:
        def upload(self, path, file, file_options):
            return {"path": path, "size": len(file), "file_options": file_options}

        def download(self, filename):
            return f"cloud:{filename}".encode()

        def get_public_url(self, filename):
            return f"https://storage.example/{filename}"

    class FakeStorage:
        def from_(self, bucket):
            assert bucket == "configured-bucket"
            return FakeBucket()

    class FakeClient:
        storage = FakeStorage()

    monkeypatch.setattr("app.services.storage_service.settings.SUPABASE_URL", "https://supabase.example")
    monkeypatch.setattr("app.services.storage_service.settings.SUPABASE_KEY", "service-key")
    monkeypatch.setattr("app.services.storage_service.settings.SUPABASE_SERVICE_ROLE_KEY", None)
    monkeypatch.setattr("app.services.storage_service.settings.SUPABASE_STORAGE_BUCKET", "configured-bucket")
    monkeypatch.setattr("app.services.storage_service.create_supabase_client", lambda url, key: FakeClient())

    service = StorageService()

    assert service.save_file("invoice.pdf", b"pdf") == "invoice.pdf"
    assert service.get_file_bytes("invoice.pdf") == b"cloud:invoice.pdf"
    assert service.get_file_url("invoice.pdf") == "https://storage.example/invoice.pdf"


def test_storage_service_supabase_download_falls_back_to_local(tmp_path, monkeypatch):
    class BrokenBucket:
        def download(self, filename):
            raise RuntimeError("cloud unavailable")

    class FakeStorage:
        def from_(self, bucket):
            return BrokenBucket()

    class FakeClient:
        storage = FakeStorage()

    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    (upload_dir / "invoice.pdf").write_bytes(b"local copy")

    monkeypatch.setattr("app.services.storage_service.settings.SUPABASE_URL", "https://supabase.example")
    monkeypatch.setattr("app.services.storage_service.settings.SUPABASE_KEY", "service-key")
    monkeypatch.setattr("app.services.storage_service.settings.SUPABASE_SERVICE_ROLE_KEY", None)
    monkeypatch.setattr("app.services.storage_service.settings.SUPABASE_STORAGE_BUCKET", "configured-bucket")
    monkeypatch.setattr("app.services.storage_service.settings.UPLOAD_DIR", str(upload_dir))
    monkeypatch.setattr("app.services.storage_service.create_supabase_client", lambda url, key: FakeClient())

    service = StorageService()

    assert service.get_file_bytes("invoice.pdf") == b"local copy"
