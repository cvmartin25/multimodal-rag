from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import Settings


def pdf_page_derivative_key(content_key: str, page_number: int, extension: str) -> str:
    """Key layout aligned with `RagService._default_storage_refs` (PDF branch)."""
    base = content_key.rstrip("/")
    return f"{base}/pages/{page_number}.{extension}"


def _key_is_safe(key: str) -> bool:
    if ".." in key or key.startswith("/") or "\\" in key:
        return False
    return True


class WorkerObjectStorage:
    """
    S3-compatible worker access (Hetzner Object Storage, AWS S3, MinIO, ...).

    Configure via environment variables (placeholders in deployment):
    - RAG_S3_ENDPOINT_URL
    - RAG_S3_ACCESS_KEY_ID
    - RAG_S3_SECRET_ACCESS_KEY
    - RAG_S3_REGION (optional, default us-east-1)
    - RAG_S3_ADDRESSING_STYLE: path | virtual (default path, typical for S3-compatible providers)
    - RAG_S3_ALLOWED_BUCKETS: comma-separated allowlist; empty = any bucket
    - RAG_S3_KEY_PREFIX_ALLOWLIST: comma-separated; empty = no extra prefix check
    """

    def __init__(self, settings: "Settings") -> None:
        self._endpoint = (settings.s3_endpoint_url or "").strip()
        self._access_key = (settings.s3_access_key_id or "").strip()
        self._secret_key = (settings.s3_secret_access_key or "").strip()
        self._region = (settings.s3_region or "us-east-1").strip()
        self._addressing = (settings.s3_addressing_style or "path").strip().lower()
        buckets_raw = (settings.s3_allowed_buckets or "").strip()
        self._allowed_buckets = frozenset(b.strip() for b in buckets_raw.split(",") if b.strip())
        prefixes_raw = (settings.s3_key_prefix_allowlist or "").strip()
        self._allowed_prefixes = tuple(p.strip() for p in prefixes_raw.split(",") if p.strip())
        self._client = None

    def is_enabled(self) -> bool:
        return bool(self._endpoint and self._access_key and self._secret_key)

    def _require_enabled(self) -> None:
        if not self.is_enabled():
            raise RuntimeError(
                "Object Storage Worker nicht konfiguriert. Setze RAG_S3_ENDPOINT_URL, "
                "RAG_S3_ACCESS_KEY_ID, RAG_S3_SECRET_ACCESS_KEY."
            )

    def _get_client(self):
        self._require_enabled()
        if self._client is None:
            import boto3
            from botocore.config import Config

            addressing = "path" if self._addressing != "virtual" else "virtual"
            cfg = Config(
                signature_version="s3v4",
                s3={"addressing_style": addressing},
            )
            self._client = boto3.client(
                "s3",
                endpoint_url=self._endpoint,
                aws_access_key_id=self._access_key,
                aws_secret_access_key=self._secret_key,
                region_name=self._region,
                config=cfg,
            )
        return self._client

    def _bucket_allowed(self, bucket: str) -> bool:
        if not self._allowed_buckets:
            return True
        return bucket in self._allowed_buckets

    def _key_allowed(self, key: str) -> bool:
        if not _key_is_safe(key):
            return False
        if not self._allowed_prefixes:
            return True
        return any(key.startswith(prefix) for prefix in self._allowed_prefixes)

    def download_original(self, *, bucket: str, key: str, expected_bucket: str, expected_key: str) -> bytes:
        """GET object only if bucket/key exactly match the indexing job (no arbitrary reads)."""
        self._require_enabled()
        if bucket != expected_bucket or key != expected_key:
            raise PermissionError("Storage Pfad stimmt nicht mit Index-Job ueberein.")
        if not self._bucket_allowed(bucket):
            raise PermissionError(f"Bucket nicht erlaubt: {bucket}")
        if not self._key_allowed(key):
            raise PermissionError(f"Key nicht erlaubt (Prefix): {key}")
        client = self._get_client()
        response = client.get_object(Bucket=bucket, Key=key)
        body = response["Body"].read()
        if not isinstance(body, (bytes, bytearray)):
            raise RuntimeError("Unerwarteter S3 Body-Typ.")
        return bytes(body)

    def upload_pdf_page_image(
        self,
        *,
        bucket: str,
        original_key: str,
        page_number: int,
        extension: str,
        body: bytes,
        content_type: str,
        expected_bucket: str,
        coach_profile_id: str,
    ) -> str:
        """
        PUT unter `{originalKey}/pages/{page}.{ext}` — nur wenn Keys zum Job passen.
        """
        self._require_enabled()
        if bucket != expected_bucket:
            raise PermissionError("Bucket stimmt nicht mit Job ueberein.")
        if not self._bucket_allowed(bucket):
            raise PermissionError(f"Bucket nicht erlaubt: {bucket}")
        derivative_key = pdf_page_derivative_key(original_key, page_number, extension)
        if not original_key or original_key != original_key.strip():
            raise ValueError("original_key ungueltig.")
        # Optional: Coach-Pfad erzwingen (Prefix allowlist sollte coach/... enthalten)
        if coach_profile_id and coach_profile_id not in original_key:
            pass  # weicher Check — Prefix-Allowlist ist schaerfer
        if not self._key_allowed(derivative_key):
            raise PermissionError(f"Derivative-Key nicht erlaubt (Prefix): {derivative_key}")
        client = self._get_client()
        client.put_object(
            Bucket=bucket,
            Key=derivative_key,
            Body=body,
            ContentType=content_type,
        )
        return derivative_key


def build_worker_object_storage(settings: "Settings") -> WorkerObjectStorage | None:
    store = WorkerObjectStorage(settings)
    return store if store.is_enabled() else None
