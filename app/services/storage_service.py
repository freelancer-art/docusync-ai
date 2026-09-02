import io
import logging
import os
from app.config import settings

logger = logging.getLogger("docusync.storage")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "docusync-uploads")

LOCAL_UPLOAD_DIR = "storage/uploads"
os.makedirs(LOCAL_UPLOAD_DIR, exist_ok=True)


class StorageService:
    def __init__(self):
        self.use_supabase = bool(SUPABASE_URL and SUPABASE_KEY)
        self.client = None

        if self.use_supabase:
            try:
                from supabase import create_client
                self.client = create_client(SUPABASE_URL, SUPABASE_KEY)
                logger.info("StorageService configured using Supabase Cloud Storage.")
            except ImportError:
                logger.warning(
                    "supabase package not installed. Defaulting to local file storage."
                )
                self.use_supabase = False
            except Exception as e:
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
                res = self.client.storage.from_(SUPABASE_BUCKET).upload(
                    path=filename,
                    file=content,
                    file_options={"upsert": "true"}
                )
                return filename
            except Exception as e:
                logger.error(f"Supabase upload failed for {filename}: {e}. Falling back to local storage.")

        # Local disk handling
        local_path = os.path.join(LOCAL_UPLOAD_DIR, filename)
        with open(local_path, "wb") as f:
            f.write(content)
        return filename

    def get_file_bytes(self, filename: str) -> bytes:
        """
        Retrieves file bytes from Supabase Storage or local disk.
        """
        if self.use_supabase and self.client:
            try:
                data = self.client.storage.from_(SUPABASE_BUCKET).download(filename)
                return data
            except Exception as e:
                logger.error(f"Supabase download failed for {filename}: {e}. Trying local disk.")

        # Local disk fallback
        local_path = os.path.join(LOCAL_UPLOAD_DIR, filename)
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
                res = self.client.storage.from_(SUPABASE_BUCKET).get_public_url(filename)
                return res
            except Exception as e:
                logger.error(f"Failed to get Supabase public URL for {filename}: {e}")
        
        return f"/storage/uploads/{filename}"


storage_service = StorageService()