import hashlib
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import aiofiles
from fastapi import UploadFile

from casemesh.core.exceptions import DocumentTooLargeError


@dataclass(frozen=True)
class StoredDocument:
    uri: str
    sha256: str
    size_bytes: int


class LocalDocumentStorage:
    def __init__(self, root: Path, max_upload_bytes: int) -> None:
        self._root = root.resolve()
        self._max_upload_bytes = max_upload_bytes

    async def save_upload(
        self,
        *,
        case_id: UUID,
        document_id: UUID,
        filename: str,
        upload: UploadFile,
    ) -> StoredDocument:
        target_dir = self._root / "cases" / str(case_id) / "documents" / str(document_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / filename
        temp_path = target_dir / f".{filename}.part"

        digest = hashlib.sha256()
        total_bytes = 0

        try:
            async with aiofiles.open(temp_path, "wb") as handle:
                while True:
                    chunk = await upload.read(1024 * 1024)
                    if not chunk:
                        break

                    total_bytes += len(chunk)
                    if total_bytes > self._max_upload_bytes:
                        raise DocumentTooLargeError(
                            f"Document exceeds {self._max_upload_bytes} bytes."
                        )

                    digest.update(chunk)
                    await handle.write(chunk)

            temp_path.replace(target_path)
        except Exception:
            temp_path.unlink(missing_ok=True)
            target_path.unlink(missing_ok=True)
            raise
        finally:
            await upload.close()

        return StoredDocument(
            uri=target_path.relative_to(Path.cwd()).as_posix(),
            sha256=digest.hexdigest(),
            size_bytes=total_bytes,
        )

    def resolve_uri(self, uri: str) -> Path:
        path = (Path.cwd() / uri).resolve()
        if self._root not in path.parents and path != self._root:
            raise ValueError("Document URI escapes the configured storage root.")
        return path

    def delete_uri(self, uri: str) -> None:
        path = self.resolve_uri(uri)
        path.unlink(missing_ok=True)

        parent = path.parent
        while parent != self._root and parent.exists():
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent
