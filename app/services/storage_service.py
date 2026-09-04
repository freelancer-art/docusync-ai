import logging
import os

from app.config import settings

logger = logging.getLogger("docusync.storage")

LOCAL_UPLOAD_DIR = settings.UPLOAD_DIR
os.makedirs(LOCAL_UPLOAD_DIR, exist_ok=True)


def create_supabase_client(url: str, key: str):
    from supabase import create_client

    return create_client(url, key)


class StorageService:
    def __init__(self):
        self.supabase_url = settings.SUPABASE_URL
        self.supabase_key = settings.SUPABASE_KEY or settings.SUPABASE_SERVICE_ROLE_KEY
        self.supabase_bucket = settings.SUPABASE_STORAGE_BUCKET
        self.local_upload_dir = settings.UPLOAD_DIR
        self.public_prefix = settings.STORAGE_PUBLIC_PREFIX.rstrip("/")
        self.use_supabase = bool(self.supabase_url and self.supabase_key)
        self.client = None

        if self.use_supabase:
            try:
                self.client = create_supabase_client(self.supabase_url, self.supabase_key)
                logger.info("StorageService configured using Supabase Cloud Storage.")
            except ImportError:
                logger.warning(
                    "supabase package not installed. Defaulting to local file storage."
                )
                self.use_supabase = False
            except Exception as e:  # noqa: BLE001
                logger.error(f"Failed to initialize Supabase client: {e}")
                self.use_supabase = False
        else:
            logger.info("StorageService configured using local disk persistence.")

    def save_file(self, filename: str, content: bytes) -> str:
        """
        Saves file to Supabase Storage or local disk.
        Returns the relative storage key/path.
        """
        if self.use_supabase and self.client:
            try:
                self.client.storage.from_(self.supabase_bucket).upload(
                    path=filename,
                    file=content,
                    file_options={"upsert": "true"}
                )
                return filename
            except Exception as e:  # noqa: BLE001
                logger.error(f"Supabase upload failed for {filename}: {e}. Falling back to local storage.")

        # Local disk handling
        local_path = os.path.join(self.local_upload_dir, filename)
        with open(local_path, "wb") as f:
            f.write(content)
        return filename

    def get_file_bytes(self, filename: str) -> bytes:
        """
        Retrieves file bytes from Supabase Storage or local disk.
        """
        if self.use_supabase and self.client:
            try:
                data = self.client.storage.from_(self.supabase_bucket).download(filename)
                return data
            except Exception as e:  # noqa: BLE001
                logger.error(f"Supabase download failed for {filename}: {e}. Trying local disk.")

        # Local disk fallback
        local_path = os.path.join(self.local_upload_dir, filename)
        if os.path.exists(local_path):
            with open(local_path, "rb") as f:
                return f.read()
        
        raise FileNotFoundError(f"File {filename} not found in cloud or local storage.")

    def get_file_url(self, filename: str) -> str:
        """
        Generates public URL if hosted on Supabase Storage or local path fallback.
        """
        if self.use_supabase and self.client:
            try:
                res = self.client.storage.from_(self.supabase_bucket).get_public_url(filename)
                return res
            except Exception as e:  # noqa: BLE001
                logger.error(f"Failed to get Supabase public URL for {filename}: {e}")
        
        return f"{self.public_prefix}/{filename}"


storage_service = StorageService()
