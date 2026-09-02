import pytest
from app.services.storage_service import storage_service
from app.core.ocr_engine import ocr_engine


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